// [Doomerfall] Doom's side of monster identity and encounters. A converted dungeon marks each Daggerfall enemy
// placement with an invisible encounter marker (a MapSpot whose args carry the placement hash, record type and
// mobile id; see tools/dungeon_converter/EnemyRoster.cs). On a first visit, Daggerfall's area facts (bridge kinds 55
// and 56) and the markers become an encounter planner request, and each placement's leader (member 0) is spawned
// exactly on its marker. Until the placer (encounter card 5) lands, only leaders are spawned. A monster's id lives in
// AActor::ddRecordId, which already survives door trips and saves. Daggerfall decides what a death means. Without a
// bridge session, each marker gets one stock monster so a converted map stays playable.

#include <algorithm>
#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "vm.h"
#include "actor.h"
#include "c_cvars.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "m_argv.h"
#include "p_local.h"
#include "printf.h"

bool DDTreadmill_PlayerSpace(double &x, double &y, double &z, double &yawDegrees, int &target);

CVAR(Int, dd_mon_test_kill, 0, CVAR_NOSAVE | CVAR_MOD) // Test only, with -ddmontest: 1 kills a placed monster, 2 a quest foe.

namespace
{
constexpr int ClaimTics = 35;
constexpr double ClaimRange = 40;
constexpr int MarkerMagic = 7365;	// EnemyRoster.MarkerMagic in the converter
constexpr uint64_t PlacementMask = (uint64_t(1) << (DFB_MONSTER_TAG_SHIFT - DFB_MONSTER_MEMBER_BITS)) - 1;
constexpr uint64_t MemberMask = (uint64_t(1) << DFB_MONSTER_MEMBER_BITS) - 1;

struct Claim { uint64_t id; DVector3 pos; int deadline; };
struct Row { uint64_t id; uint32_t state; DVector3 pos; int32_t enemyType; };
struct Marker { uint64_t placement; int record, mobile; DVector3 pos; };
struct Facts
{
	bool have = false;
	dfb_encounter_area area{};
	FString location, region, type;
};
// One request placement: a map marker, or a living quest foe's encounter from Daggerfall's list.
struct Placement { uint64_t placement; DVector3 pos; int enemyType; bool quest; };

std::vector<Claim> claims;
std::vector<Row> incoming, accepted;
std::vector<Marker> markers;
std::unordered_set<uint64_t> reported;
Facts acceptedFacts, incomingFacts, facts;
uint32_t acceptedGeneration, currentContext;
int32_t currentTarget = -1;
bool spaceValid, wantList, incomingReady, leadersPending;
int dungeonMapId = -1;

bool IsMonsterId(uint64_t id) { return (id >> DFB_MONSTER_TAG_SHIFT) == DFB_MONSTER_TAG; }
uint64_t LeaderId(uint64_t placement) { return (uint64_t(DFB_MONSTER_TAG) << DFB_MONSTER_TAG_SHIFT) | ((placement & PlacementMask) << DFB_MONSTER_MEMBER_BITS); }
uint64_t PlacementOf(uint64_t id) { return (id >> DFB_MONSTER_MEMBER_BITS) & PlacementMask; }

void SendRequest(dfb_session *session)
{
	dfb_event e{};
	e.kind = DFB_KIND_MONSTERS_REQUEST;
	e.tic = gametic;
	const dfb_world_items body{ 0, currentContext, currentTarget, 0 };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

AActor *FindById(FLevelLocals *Level, uint64_t id)
{
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
		if (mo->ddRecordId == id) return mo;
	return nullptr;
}

// A replacement such as DRLA's can appear a few tics after the thing that named it, so claims wait.
void RunClaims(FLevelLocals *Level)
{
	if (claims.empty()) return;
	std::vector<AActor *> free;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
		if (!mo->player && !mo->ddRecordId && (mo->flags3 & MF3_ISMONSTER) && mo->health > 0) free.push_back(mo);
	for (size_t n = 0; n < claims.size();)
	{
		Claim &c = claims[n];
		AActor *best = nullptr;
		double range = ClaimRange * ClaimRange;
		for (AActor *mo : free)
		{
			if (mo->ddRecordId) continue;
			const double d = (mo->Pos() - c.pos).LengthSquared();
			if (d < range) { range = d; best = mo; }
		}
		if (best)
		{
			best->ddRecordId = c.id;
			Printf("DDMON claimed %016" PRIx64 " %s at %.1f,%.1f,%.1f\n", c.id, best->GetClass()->TypeName.GetChars(), best->X(), best->Y(), best->Z());
			claims.erase(claims.begin() + n);
		}
		else if (Level->maptime > c.deadline)
		{
			Printf("DDMON no monster for %016" PRIx64 "\n", c.id);
			claims.erase(claims.begin() + n);
		}
		else n++;
	}
}

// The stock fallback: Doom II's regular monsters, picked by the placement hash. Mods replace them through their own rules.
PClassActor *RosterClass(uint64_t placement)
{
	static const char *const roster[] = { "ZombieMan", "ShotgunGuy", "ChaingunGuy", "DoomImp", "Demon", "Spectre", "LostSoul", "Cacodemon",
		"HellKnight", "BaronOfHell", "Revenant", "Fatso", "Arachnotron", "PainElemental", "Archvile" };
	return PClass::FindActor(roster[placement % countof(roster)]);
}

// Spawns one leader on its exact point. A spawned monster takes its id at once; a spawner (such as DRLA's) is claimed.
bool SpawnLeader(FLevelLocals *Level, PClassActor *cls, uint64_t id, const DVector3 &at, bool replace, const char *why)
{
	if (!cls) return false;
	AActor *mo = Spawn(Level, cls, at, replace ? ALLOW_REPLACE : NO_REPLACE);
	if (!mo) return false;
	if ((mo->flags3 & MF3_ISMONSTER) && !mo->ddRecordId) mo->ddRecordId = id;
	else claims.push_back({ id, at, Level->maptime + ClaimTics });
	Printf("DDENC leader %016" PRIx64 " %s at %.1f,%.1f,%.1f (%s)\n", id, cls->TypeName.GetChars(), at.X, at.Y, at.Z, why);
	return true;
}

void CollectMarkers(FLevelLocals *Level)
{
	markers.clear();
	PClassActor *spot = PClass::FindActor("MapSpot");
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (!spot || mo->GetClass() != spot || mo->args[0] != MarkerMagic) continue;
		const uint64_t placement = ((uint64_t(uint32_t(mo->args[1])) << 32) | uint32_t(mo->args[2])) & PlacementMask;
		markers.push_back({ placement, mo->args[3], mo->args[4], mo->Pos() });
	}
	std::sort(markers.begin(), markers.end(), [](const Marker &a, const Marker &b) { return a.placement < b.placement; });
}

// Calls the ZScript planner (EncounterLeaders.zs) and returns, per placement, the leader's class (null when none).
bool PlanLeaders(const std::vector<Placement> &list, std::vector<PClassActor *> &leaders, std::vector<FString> &roles)
{
	leaders.assign(list.size(), nullptr);
	roles.assign(list.size(), "none");
	VMFunction *func = nullptr;
	PClass::FindFunction(&func, "DoomerfallEncounterLeaders", "PlanText");
	if (!func || !facts.have) return false;
	const dfb_encounter_area &a = facts.area;
	FString text;
	text.AppendFormat("area\t%d\t%d\t%d\t%.3f\t%.3f\t%s\t%d\t%d\n", a.dungeon_index, a.location_id, a.region_index, a.world_x, a.world_y,
		facts.type.GetChars(), a.area_level, a.seed_offset);
	text.AppendFormat("location\t%s\nregion\t%s\n", facts.location.GetChars(), facts.region.GetChars());
	for (const Placement &p : list)
		text.AppendFormat("p\t%d\t%d\t%.3f\t%.3f\t%.3f\t%d\t%d\n", int32_t(uint32_t(p.placement >> 32)), int32_t(uint32_t(p.placement)),
			p.pos.X, p.pos.Y, p.pos.Z, p.enemyType, p.quest ? 1 : 0);
	FString answer;
	VMValue params[] = { &text };
	VMReturn ret(&answer);
	VMCall(func, params, 1, &ret, 1);
	if (answer.IsEmpty()) return false;
	int mismatched = 0;
	for (auto &line : answer.Split("\n"))
	{
		if (line.IndexOf("plan ") == 0) { Printf("DDENC %s\n", line.GetChars()); continue; }
		int index, hi, lo, count;
		char cls[96], role[32];
		if (sscanf(line.GetChars(), "%d %95s %d %d %31s %d", &index, cls, &hi, &lo, role, &count) != 6 || index < 0 || index >= int(list.size())) continue;
		roles[index] = role;
		if (!strcmp(cls, "-")) continue;
		leaders[index] = PClass::FindActor(cls);
		const uint64_t id = (uint64_t(uint32_t(hi)) << 32) | uint32_t(lo);
		if (id != LeaderId(list[index].placement)) mismatched++;
	}
	if (mismatched) Printf("DDENC warning: %d leader ids from the plan differ from the placement ids\n", mismatched);
	return true;
}

// Builds the request from the markers and the quest foes, then spawns every leader that is missing and not dead.
// Map leaders are spawned once, on a first visit; quest foe leaders whenever Daggerfall lists them alive.
void SpawnEncounters(FLevelLocals *Level, bool mapLeaders)
{
	std::unordered_set<uint64_t> dead, present;
	std::vector<Placement> list;
	for (const Marker &m : markers) list.push_back({ m.placement, m.pos, m.record == 16 ? (m.mobile & 0xff) : -1, false });
	int quests = 0;
	for (const Row &r : incoming)
	{
		if (r.state == DFB_MONSTER_DEAD) dead.insert(r.id);
		else if (r.state == DFB_MONSTER_PLACE && (r.id & MemberMask) == 0) { list.push_back({ PlacementOf(r.id), r.pos, r.enemyType, true }); quests++; }
	}
	std::sort(list.begin() + markers.size(), list.end(), [](const Placement &a, const Placement &b) { return a.placement < b.placement; });
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next()) if (IsMonsterId(mo->ddRecordId)) present.insert(mo->ddRecordId);
		for (const Claim &c : claims) present.insert(c.id);
	}
	bool needed = false;
	for (size_t i = 0; i < list.size(); i++)
		needed |= (mapLeaders || list[i].quest) && !dead.count(LeaderId(list[i].placement)) && !present.count(LeaderId(list[i].placement));
	if (mapLeaders && facts.have)
	{
		const dfb_encounter_area &a = facts.area;
		Printf("DDENC facts map %d dungeonIndex %d locationId %d name '%s' region %d '%s' world %.1f,%.1f type %d (%s) areaLevel %d seedOffset %d markers %d quest %d dead %d\n",
			a.map_id, a.dungeon_index, a.location_id, facts.location.GetChars(), a.region_index, facts.region.GetChars(), a.world_x, a.world_y,
			a.dungeon_type, facts.type.GetChars(), a.area_level, a.seed_offset, int(markers.size()), quests, int(dead.size()));
	}
	if (!needed) return;
	std::vector<PClassActor *> leaders;
	std::vector<FString> roles;
	const bool planned = PlanLeaders(list, leaders, roles);
	if (!planned) Printf("DDENC no plan (planner or facts missing); using the stock roster\n");
	int spawned = 0, skippedDead = 0, skippedPresent = 0;
	for (size_t i = 0; i < list.size(); i++)
	{
		const Placement &p = list[i];
		if (!mapLeaders && !p.quest) continue;
		const uint64_t id = LeaderId(p.placement);
		if (dead.count(id)) { skippedDead++; continue; }
		if (present.count(id)) { skippedPresent++; continue; }
		// The exact point: the marker, or the spot Daggerfall chose for this quest foe member.
		const DVector3 at = p.pos;
		PClassActor *cls = planned ? leaders[i] : RosterClass(p.placement);
		if (planned && !cls) cls = RosterClass(p.placement);
		FString why = FString(p.quest ? "quest " : "") + (planned ? roles[i] : FString("roster"));
		if (SpawnLeader(Level, cls, id, at, !planned, why.GetChars())) spawned++;
	}
	Printf("DDENC spawned %d leaders of %d placements (%d dead, %d already present)%s\n", spawned, int(list.size()), skippedDead, skippedPresent, mapLeaders ? "" : ", quest foes only");
}

void ApplyRows(FLevelLocals *Level)
{
	if (!incomingReady) return;
	incomingReady = false;
	facts = incomingFacts;
	const bool mapLeaders = leadersPending && facts.have && facts.area.map_id == dungeonMapId;
	if (mapLeaders) leadersPending = false;
	SpawnEncounters(Level, mapLeaders);
	for (const Row &r : incoming)
	{
		if (r.state != DFB_MONSTER_DEAD || reported.count(r.id)) continue;
		// Daggerfall has it dead and this session did not kill it, so a mismatched state must not revive it.
		AActor *mo = FindById(Level, r.id);
		if (mo && mo->health > 0)
		{
			Printf("DDMON removed %016" PRIx64 ", which Daggerfall has as dead\n", r.id);
			mo->Destroy();
		}
		for (size_t n = 0; n < claims.size(); n++)
			if (claims[n].id == r.id) { claims.erase(claims.begin() + n); break; }
	}
	incoming.clear();
}

void RunTestKill(FLevelLocals *Level)
{
	const int want = dd_mon_test_kill;
	if (!want) return;
	dd_mon_test_kill = 0;
	bool enabled = false;
	for (int i = 1; i < Args->NumArgs(); i++) enabled |= !stricmp(Args->GetArg(i), "-ddmontest");
	if (!enabled) return;
	AActor *pick = nullptr;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (!IsMonsterId(mo->ddRecordId) || mo->health <= 0) continue;
		bool quest = false;
		for (const Row &r : accepted) quest |= r.id == mo->ddRecordId && r.state == DFB_MONSTER_PLACE;
		if (quest == (want == 2)) { pick = mo; break; }
	}
	if (!pick) { Printf("DDMON test kill found nothing\n"); return; }
	Printf("DDMON test kill %016" PRIx64 " %s at %.1f,%.1f,%.1f floor %.1f ceiling %.1f\n", pick->ddRecordId, pick->GetClass()->TypeName.GetChars(), pick->X(), pick->Y(), pick->Z(), pick->floorz, pick->ceilingz);
	P_DamageMobj(pick, Level->Players[consoleplayer]->mo, Level->Players[consoleplayer]->mo, pick->health + 1000, NAME_None, DMG_FORCED);
}

FString PayloadText(const char *text, size_t size)
{
	size_t n = 0;
	while (n < size && text[n]) n++;
	return FString(text, n);
}
}

// Called when a dungeon starts. The map's markers are read on every visit, so the request stays the same; leaders
// are spawned only on a first visit, once Daggerfall's facts arrive.
void DD_MonstersEnterDungeon(FLevelLocals *Level, int mapId, bool firstVisit, bool bridged)
{
	claims.clear();
	dungeonMapId = mapId;
	CollectMarkers(Level);
	leadersPending = bridged && firstVisit;
	Printf("DDMON dungeon %d has %d encounter markers%s\n", mapId, int(markers.size()), firstVisit ? ", first visit" : "");
	if (bridged || !firstVisit) return;
	int spawned = 0;
	for (const Marker &m : markers)
		spawned += SpawnLeader(Level, RosterClass(m.placement), LeaderId(m.placement), m.pos, true, "no bridge, roster");
	Printf("DDENC spawned %d stock leaders without a bridge\n", spawned);
}

void DD_MonstersTick(FLevelLocals *Level)
{
	ApplyRows(Level);
	RunClaims(Level);
	RunTestKill(Level);
}

bool DD_MonstersEvent(const dfb_event &e)
{
	switch (e.kind)
	{
	case DFB_KIND_MONSTERS_BEGIN:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		acceptedGeneration = spaceValid && b.context == currentContext && b.target == currentTarget ? b.generation : 0;
		accepted.clear();
		acceptedFacts = Facts();
		return true;
	}
	case DFB_KIND_ENCOUNTER_AREA:
	{
		dfb_encounter_area a;
		memcpy(&a, e.payload, sizeof(a));
		if (acceptedGeneration && a.generation == acceptedGeneration) { acceptedFacts.area = a; acceptedFacts.have = true; }
		return true;
	}
	case DFB_KIND_ENCOUNTER_TEXT:
	{
		dfb_encounter_text t;
		memcpy(&t, e.payload, sizeof(t));
		if (!acceptedGeneration || t.generation != acceptedGeneration) return true;
		const FString text = PayloadText(t.text, sizeof(t.text));
		if (t.field == DFB_ENCOUNTER_LOCATION_NAME) acceptedFacts.location = text;
		else if (t.field == DFB_ENCOUNTER_REGION_NAME) acceptedFacts.region = text;
		else if (t.field == DFB_ENCOUNTER_DUNGEON_TYPE) acceptedFacts.type = text;
		return true;
	}
	case DFB_KIND_MONSTER:
	{
		dfb_monster m;
		memcpy(&m, e.payload, sizeof(m));
		if (acceptedGeneration && m.generation == acceptedGeneration)
			accepted.push_back({ m.id, m.state, DVector3(m.x, m.y, m.z), m.enemy_type });
		return true;
	}
	case DFB_KIND_MONSTERS_END:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		if (acceptedGeneration && b.generation == acceptedGeneration)
		{
			incoming = accepted;
			incomingFacts = acceptedFacts;
			incomingReady = true;
		}
		return true;
	}
	default:
		return false;
	}
}

void DD_MonstersFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target)
{
	if (context != currentContext || inSpace != spaceValid || (inSpace && target != currentTarget))
	{
		currentContext = context;
		spaceValid = inSpace;
		currentTarget = inSpace ? target : -1;
		acceptedGeneration = 0;
		accepted.clear();
		incoming.clear();
		incomingReady = false;
		wantList = inSpace && context == DFB_WORLD_DUNGEON;
	}
	if (wantList && gamestate == GS_LEVEL)
	{
		wantList = false;
		SendRequest(session);
	}
}

// A load replaced every actor, so what this session reported no longer describes them. A restored level already
// has its leaders, and SpawnEncounters never doubles one that is present.
void DD_MonstersResync()
{
	reported.clear();
	claims.clear();
	incoming.clear();
	incomingReady = false;
	wantList = spaceValid && currentContext == DFB_WORLD_DUNGEON;
}

void DD_MonsterDied(dfb_session *session, AActor *mo)
{
	if (!IsMonsterId(mo->ddRecordId)) return;
	reported.insert(mo->ddRecordId);
	double x, y, z, yaw;
	int target = -1;
	const bool inSpace = DDTreadmill_PlayerSpace(x, y, z, yaw, target);
	const dfb_monster_death death{ mo->ddRecordId, inSpace ? uint32_t(DFB_WORLD_DUNGEON) : uint32_t(DFB_WORLD_NONE), target, float(mo->X()), float(mo->Y()), float(mo->floorz), 0 };
	dfb_event e{};
	e.kind = DFB_KIND_MONSTER_DEATH;
	e.tic = gametic;
	memcpy(e.payload, &death, sizeof(death));
	dfb_send(session, &e);
	Printf("DDMON died %016" PRIx64 " target %d\n", death.id, target);
}
