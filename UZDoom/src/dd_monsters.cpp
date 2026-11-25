// [Doomerfall] Doom's side of monster identity and encounters. A converted dungeon marks each Daggerfall enemy
// placement with an invisible encounter marker (a MapSpot whose args carry the placement hash, record type and
// mobile id; see tools/dungeon_converter/EnemyRoster.cs). On a first visit, Daggerfall's area facts (bridge kinds 55
// and 56) and the markers become an encounter planner request, and the placer (dd_encounter_placer.cpp) spawns every
// mook: each placement's leader (member 0) exactly on its marker, the rest spread around it. A monster's id lives in
// AActor::ddRecordId, which already survives door trips and saves. Daggerfall decides what a death means. Without a
// bridge session, each marker gets one stock monster so a converted map stays playable.

#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "dd_encounter_placer.h"
#include "dd_locations.h"
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

struct Claim { uint64_t id; DVector3 pos; int deadline; int side = -1, stance = 0; };
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
// A dungeon's first encounter request. The world table stores only changed mooks (dd_treadmill.cpp Park), so every
// visit plans again and spawns the mooks that are neither dead nor present. The plan depends on the whole request, so
// a revisit reuses the first visit's quest placements, dead or alive, and gets the same mooks on the same spots.
struct DungeonPlan { std::vector<Placement> quests; int mooks = 0; };
std::unordered_map<int, DungeonPlan> plans;

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

// Card 6: joins a Civil War army (CivilWar.zs). side < 0 is a united dungeon, which is left exactly as it was.
void RigFaction(AActor *mo, int side, int stance)
{
	if (side < 0 || !mo) return;
	VMFunction *func = nullptr;
	PClass::FindFunction(&func, "DoomerfallCivilWar", "Rig");
	if (!func) return;
	VMValue params[] = { mo, side, stance };
	VMCall(func, params, 3, nullptr, 0);
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
			best->SpawnPoint = best->Pos();	// So the world table can tell it has not moved.
			RigFaction(best, c.side, c.stance);
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

// Spawns one mook on its point. A spawned monster takes its id at once; a spawner (such as DRLA's) is claimed.
AActor *SpawnMook(FLevelLocals *Level, PClassActor *cls, uint64_t id, const DVector3 &at, bool replace, int side = -1, int stance = 0)
{
	if (!cls) return nullptr;
	AActor *mo = Spawn(Level, cls, at, replace ? ALLOW_REPLACE : NO_REPLACE);
	if (!mo) return nullptr;
	if ((mo->flags3 & MF3_ISMONSTER) && !mo->ddRecordId) { mo->ddRecordId = id; mo->SpawnPoint = mo->Pos(); RigFaction(mo, side, stance); }
	else claims.push_back({ id, at, Level->maptime + ClaimTics, side, stance });
	return mo;
}

bool SpawnLeader(FLevelLocals *Level, PClassActor *cls, uint64_t id, const DVector3 &at, bool replace, const char *why)
{
	if (!SpawnMook(Level, cls, id, at, replace)) return false;
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

// Plans and places every mook (dd_encounter_placer.cpp). False when the planner or the facts are missing.
bool PlaceMooks(FLevelLocals *Level, const std::vector<Placement> &list, std::vector<DDEncMookOut> &mooks)
{
	if (!facts.have) return false;
	const dfb_encounter_area &a = facts.area;
	FString header;
	header.AppendFormat("area\t%d\t%d\t%d\t%.3f\t%.3f\t%s\t%d\t%d\n", a.dungeon_index, a.location_id, a.region_index, a.world_x, a.world_y,
		facts.type.GetChars(), a.area_level, a.seed_offset);
	header.AppendFormat("location\t%s\nregion\t%s\n", facts.location.GetChars(), facts.region.GetChars());
	std::vector<DDEncPlacementIn> in;
	for (const Placement &p : list) in.push_back({ p.placement, p.pos, p.enemyType, p.quest });
	if (!DD_PlaceEncounters(Level, header, in, mooks)) return false;
	int mismatched = 0;
	for (const DDEncMookOut &m : mooks)
		mismatched += m.member == 0 && m.id != LeaderId(list[m.placement].placement);
	if (mismatched) Printf("DDENC warning: %d leader ids from the plan differ from the placement ids\n", mismatched);
	return true;
}

// Builds the request from the markers and the quest foes, plans and places every mook, then spawns the ones that are
// missing and not dead. Map encounters are spawned once, on a first visit; quest foe encounters whenever Daggerfall
// lists their leader alive and it is missing.
void SpawnPass(FLevelLocals *Level, const std::vector<Placement> &list, const std::unordered_set<uint64_t> &wanted, const std::unordered_set<uint64_t> &dead,
	const std::unordered_set<uint64_t> &present, bool mapLeaders, bool revisit, int *planned);

void SpawnEncounters(FLevelLocals *Level, bool mapLeaders)
{
	std::unordered_set<uint64_t> dead, present;
	std::vector<Placement> list, living;
	for (const Marker &m : markers) list.push_back({ m.placement, m.pos, m.record == 16 ? (m.mobile & 0xff) : -1, false });
	for (const Row &r : incoming)
	{
		if (r.state == DFB_MONSTER_DEAD) dead.insert(r.id);
		else if (r.state == DFB_MONSTER_PLACE && (r.id & MemberMask) == 0) living.push_back({ PlacementOf(r.id), r.pos, r.enemyType, true });
	}
	auto byPlacement = [](const Placement &a, const Placement &b) { return a.placement < b.placement; };
	std::sort(living.begin(), living.end(), byPlacement);
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next()) if (IsMonsterId(mo->ddRecordId)) present.insert(mo->ddRecordId);
		for (const Claim &c : claims) present.insert(c.id);
	}
	// Pass 1 is the first visit's request. Pass 2 holds quest foes that came after it, planned with everything, as before.
	auto known = plans.find(dungeonMapId);
	const bool revisit = known != plans.end();
	const std::vector<Placement> stored = revisit ? known->second.quests : living;
	std::unordered_set<uint64_t> inStored;
	for (const Placement &p : stored) inStored.insert(p.placement);
	std::vector<Placement> extra;
	for (const Placement &p : living) if (!inStored.count(p.placement)) extra.push_back(p);
	const int quests = int(stored.size() + extra.size());
	auto missing = [&](const Placement &p) { return !dead.count(LeaderId(p.placement)) && !present.count(LeaderId(p.placement)); };
	std::unordered_set<uint64_t> wantedFirst, wantedExtra;
	if (mapLeaders)
	{
		// Every placement of the first request. A cleared dungeon (all its mooks dead or present) is not planned again.
		std::unordered_set<uint64_t> placements;
		for (const Placement &p : list) placements.insert(p.placement);
		for (const Placement &p : stored) placements.insert(p.placement);
		int accounted = 0;
		for (const auto *set : { &dead, &present })
			for (uint64_t id : *set) accounted += placements.count(PlacementOf(id)) != 0 && !(set == &present && dead.count(id));
		if (!revisit || accounted < known->second.mooks) wantedFirst = placements;
		else Printf("DDENC all %d planned mooks are dead or present; not planning again\n", known->second.mooks);
	}
	else
		for (const Placement &p : stored) if (missing(p)) wantedFirst.insert(p.placement);
	for (const Placement &p : extra) if (mapLeaders || missing(p)) wantedExtra.insert(p.placement);
	std::vector<Placement> first = list;
	first.insert(first.end(), stored.begin(), stored.end());
	const bool needed = !wantedFirst.empty() || !wantedExtra.empty();
	if (mapLeaders && facts.have)
	{
		const dfb_encounter_area &a = facts.area;
		Printf("DDENC facts map %d dungeonIndex %d locationId %d name '%s' region %d '%s' world %.1f,%.1f type %d (%s) areaLevel %d seedOffset %d markers %d quest %d dead %d\n",
			a.map_id, a.dungeon_index, a.location_id, facts.location.GetChars(), a.region_index, facts.region.GetChars(), a.world_x, a.world_y,
			a.dungeon_type, facts.type.GetChars(), a.area_level, a.seed_offset, int(markers.size()), quests, int(dead.size()));
	}
	if (!needed) return;
	int planned = -1;
	if (!wantedFirst.empty()) SpawnPass(Level, first, wantedFirst, dead, present, mapLeaders, revisit && mapLeaders, &planned);
	if (mapLeaders && !revisit && planned >= 0) plans[dungeonMapId] = DungeonPlan{ stored, planned };
	if (!wantedExtra.empty())
	{
		std::vector<Placement> all = first;
		all.insert(all.end(), extra.begin(), extra.end());
		std::sort(all.begin() + markers.size(), all.end(), byPlacement);
		SpawnPass(Level, all, wantedExtra, dead, present, mapLeaders, false, nullptr);
	}
}

// Plans one request and spawns the mooks of the wanted placements that are neither dead nor present. A quest foe that
// arrives during a visit comes back whole only when its leader is missing; its followers are skipped by id.
void SpawnPass(FLevelLocals *Level, const std::vector<Placement> &list, const std::unordered_set<uint64_t> &wanted, const std::unordered_set<uint64_t> &dead,
	const std::unordered_set<uint64_t> &present, bool mapLeaders, bool revisit, int *planned)
{
	std::vector<DDEncMookOut> mooks;
	const auto t0 = std::chrono::steady_clock::now();
	// A revisit plans with the monsters the table brought back out of the way, as they were on the first visit, so the
	// rebuilt mooks get the same spots.
	std::vector<AActor *> unsolid;
	if (revisit)
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (IsMonsterId(mo->ddRecordId) && (mo->flags & MF_SOLID)) { mo->flags &= ~MF_SOLID; unsolid.push_back(mo); }
	}
	const bool ok = PlaceMooks(Level, list, mooks);
	for (AActor *mo : unsolid) mo->flags |= MF_SOLID;
	if (!ok)
	{
		Printf("DDENC no plan (planner or facts missing); using the stock roster\n");
		int spawned = 0;
		for (const Placement &p : list)
		{
			const uint64_t id = LeaderId(p.placement);
			if (wanted.count(p.placement) && !dead.count(id) && !present.count(id))
				spawned += SpawnLeader(Level, RosterClass(p.placement), id, p.pos, true, p.quest ? "quest roster" : "roster");
		}
		Printf("DDENC spawned %d stock leaders of %d placements\n", spawned, int(list.size()));
		return;
	}
	if (planned) *planned = int(mooks.size());
	int spawned = 0, leaders = 0, skippedDead = 0, skippedPresent = 0, stuck = 0, stuckLeaders = 0, warSide[2] = { 0, 0 }, warStance[2] = { 0, 0 };
	for (const DDEncMookOut &m : mooks) if (m.side >= 0) warStance[m.side & 1] = m.stance;
	std::vector<std::pair<AActor *, bool>> fresh;
	for (const DDEncMookOut &m : mooks)
	{
		const Placement &p = list[m.placement];
		if (!wanted.count(p.placement)) continue;
		if (dead.count(m.id)) { skippedDead++; continue; }
		if (present.count(m.id)) { skippedPresent++; continue; }
		AActor *mo = SpawnMook(Level, m.cls, m.id, m.pos, false, m.side, m.stance);
		if (!mo) continue;
		spawned++;
		if (m.side >= 0) warSide[m.side & 1]++;
		leaders += m.member == 0;
		fresh.push_back({ mo, m.member == 0 });
		if (m.member == 0)
			Printf("DDENC leader %016" PRIx64 " %s at %.1f,%.1f,%.1f%s\n", m.id, m.cls->TypeName.GetChars(), mo->X(), mo->Y(), mo->Z(), p.quest ? " (quest)" : "");
	}
	// Stuck: a spawned monster that Doom's own check says does not fit where it stands.
	for (auto &f : fresh)
		if (!(f.first->ObjectFlags & OF_EuthanizeMe) && !P_TestMobjLocation(f.first)) { stuck++; stuckLeaders += f.second; }
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	Printf("DDENC spawned %d mooks (%d leaders) of %d planned for %d placements (%d dead, %d already present), stuck %d (%d leaders), %.1f ms with spawning%s\n",
		spawned, leaders, int(mooks.size()), int(list.size()), skippedDead, skippedPresent, stuck, stuckLeaders, ms, revisit ? ", revisit" : mapLeaders ? "" : ", quest foes only");
	if (warSide[0] + warSide[1])
		Printf("DDWAR civil war: army A %d mooks stance %d, army B %d mooks stance %d\n", warSide[0], warStance[0], warSide[1], warStance[1]);
}

void ApplyRows(FLevelLocals *Level)
{
	if (!incomingReady || DD_LocationsWaiting()) return;	// Daggerfall's record of the place comes first.
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

// Called when a dungeon starts, after the world table has brought back the changed monsters. The map's markers are read
// on every visit, so the request stays the same; once Daggerfall's facts arrive, every mook that is neither dead nor
// present is spawned again from the plan, because the table does not store unchanged ones.
void DD_MonstersEnterDungeon(FLevelLocals *Level, int mapId, bool firstVisit, bool bridged)
{
	claims.clear();
	dungeonMapId = mapId;
	CollectMarkers(Level);
	leadersPending = bridged;
	Printf("DDMON dungeon %d has %d encounter markers%s\n", mapId, int(markers.size()), firstVisit ? ", first visit" : "");
	if (bridged) return;
	int spawned = 0;
	for (const Marker &m : markers)
		if (!FindById(Level, LeaderId(m.placement)))
			spawned += SpawnLeader(Level, RosterClass(m.placement), LeaderId(m.placement), m.pos, true, "no bridge, roster");
	Printf("DDENC spawned %d stock leaders without a bridge\n", spawned);
}

// The plans travel in the save with the world table (dd_treadmill.cpp DDTreadmill_Serialize).
FString DD_MonstersSavePlans()
{
	FString out;
	for (auto &kv : plans)
	{
		out.AppendFormat("P %d %d %d\n", kv.first, kv.second.mooks, int(kv.second.quests.size()));
		for (const Placement &p : kv.second.quests)
			out.AppendFormat("Q %" PRIx64 " %.17g %.17g %.17g %d\n", p.placement, p.pos.X, p.pos.Y, p.pos.Z, p.enemyType);
	}
	return out;
}

void DD_MonstersLoadPlans(const FString &text)
{
	plans.clear();
	DungeonPlan *current = nullptr;
	for (auto &line : text.Split("\n"))
	{
		int map, mooks, count;
		uint64_t placement;
		double x, y, z;
		int type;
		if (sscanf(line.GetChars(), "P %d %d %d", &map, &mooks, &count) == 3) { current = &plans[map]; current->mooks = mooks; }
		else if (current && sscanf(line.GetChars(), "Q %" SCNx64 " %lf %lf %lf %d", &placement, &x, &y, &z, &type) == 5)
			current->quests.push_back({ placement, DVector3(x, y, z), type, true });
	}
}

// The location ledger (dd_locations.cpp) keeps each dungeon's plan in Daggerfall's record, so a rebuilt place plans
// exactly as its first visit did even when Doom's own copy is gone.
bool DD_MonstersPlanOf(int mapId, int &mooks, std::vector<DDPlanQuest> &quests)
{
	auto it = plans.find(mapId);
	if (it == plans.end()) return false;
	mooks = it->second.mooks;
	quests.clear();
	for (const Placement &p : it->second.quests) quests.push_back({ p.placement, p.pos.X, p.pos.Y, p.pos.Z, p.enemyType });
	return true;
}

void DD_MonstersSetPlan(int mapId, int mooks, const std::vector<DDPlanQuest> &quests)
{
	DungeonPlan &plan = plans[mapId];
	plan.mooks = mooks;
	plan.quests.clear();
	for (const DDPlanQuest &q : quests) plan.quests.push_back({ q.placement, DVector3(q.x, q.y, q.z), q.enemyType, true });
}

// Test only (dd_encounter_test.cpp, -ddenctest): plans and spawns this map's encounters from given facts.
void DD_MonstersTestEncounters(FLevelLocals *Level, const dfb_encounter_area &a, const char *location, const char *region, const char *type)
{
	facts = Facts{ true, a, location, region, type };
	claims.clear();	// the no-bridge roster's spawner claims, which only a bridge tick resolves
	CollectMarkers(Level);
	SpawnEncounters(Level, true);
}

void DD_MonstersTick(FLevelLocals *Level)
{
	DD_LocationsTick(Level);
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
