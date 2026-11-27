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
#include "dd_lootrng.h"
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
#include "playsim/dd_log.h" // [Doomerfall]
#include "filesystem.h"
#include "actorinlines.h"
#include "m_bbox.h"
#include "p_maputl.h"

bool DDTreadmill_PlayerSpace(double &x, double &y, double &z, double &yawDegrees, int &target);
void DD_SetupWait(const char *system);	// dd_setup.cpp: the arrival wait and autosave wait for the dungeon's spawn
void DD_SetupDone(const char *system);

// Monster squeeze width on Daggerfall maps (architecture.md, World Scale and Player Size). Doomguy is 10.5 wide there
// instead of 16. Monsters keep their stock radius against the player, other actors and open walls, and squeeze to the
// same proportion of it (AActor::SqueezeRadius) only to get through a gap in the level, or past a door leaf, that is
// narrower than they are (P_TryMove, DD_InGap). Their radius, and so every hit test, stays stock. This is the one test
// for "a Daggerfall map" that monster rules use: generated locations (DDTnnnnn, DDSnnnnn), the overworld (DDOVER*),
// and converted dungeons (MAP01 with DDDUNGN or DFPOINTS).
double DD_MonsterMoveScale = 1;
AActor *DD_SqueezeActor = nullptr;
static PClassActor *doorLeafClass;	// DFDoorBlocker, the links of a Daggerfall door (tools/dungeon_converter/door_objects.zs)

bool DD_IsDoorLeaf(const AActor *a)
{
	return doorLeafClass && a->IsKindOf(doorLeafClass);
}

// Would a body of radius r at pos touch level geometry or a door leaf? Other actors are ignored.
static bool GeometryBlocks(AActor *thing, const DVector2 &pos, double r)
{
	FBoundingBox box(pos.X, pos.Y, r);
	FBlockLinesIterator lines(thing->Level, box);
	while (line_t *ld = lines.Next())
	{
		if (!inRange(box, ld) || BoxOnLineSide(box, ld) != -1) continue;
		if (!ld->backsector || P_IsBlockedByLine(thing, ld)) return true;
		const DVector2 a = ld->v1->fPos(), delta = ld->Delta();
		const DVector2 c = a + delta * std::clamp(((pos - a) | delta) / delta.LengthSquared(), 0., 1.);
		FLineOpening open;
		P_LineOpening(open, thing, ld, c);
		if (open.range < thing->Height || open.bottom - thing->Z() > thing->MaxStepHeight || open.top < thing->Top()) return true;
	}
	FBlockThingsIterator things(thing->Level, box);
	while (AActor *t = things.Next())
	{
		if (!(t->flags & MF_SOLID) || !DD_IsDoorLeaf(t) || t->Z() >= thing->Top() || t->Top() <= thing->Z()) continue;
		if (fabs(t->X() - pos.X) < r + t->radius && fabs(t->Y() - pos.Y) < r + t->radius) return true;
	}
	return false;
}

// Is pos, where the monster's stock body is stuck on level geometry or a door leaf, a gap narrower than the monster?
// Not if its stock body would fit after a small step to the side (it is hugging a wall), and, when it is moving, not if
// its narrow body could not carry on forward (it is walking into a wall or a corner). So in an open room a monster
// keeps its stock distance from the walls, and only doorways and passages narrower than it make it squeeze. A monster
// already squeezed where it stands may carry on forward until it is clear, for example past an open door leaf.
bool DD_InGap(AActor *thing, const DVector2 &pos)
{
	const double r = thing->radius, narrow = thing->SqueezeRadius(), d = r - narrow;
	if (d <= 0) return false;
	DVector2 u = pos - thing->Pos().XY();
	const bool moving = u.LengthSquared() > 1e-6;
	if (moving)
	{
		u = u.Unit();
		if (GeometryBlocks(thing, pos + u * d, narrow)) return false;
		if (GeometryBlocks(thing, thing->Pos().XY(), r)) return true;
		const DVector2 v(-u.Y, u.X);
		for (double s : { d / 2, d, -d / 2, -d }) if (!GeometryBlocks(thing, pos + v * s, r)) return false;
		return true;
	}
	for (int i = 0; i < 8; i++)	// standing still (the encounter placer): the stock body fits nowhere close by
	{
		const DVector2 dir(cos(i * M_PI / 4), sin(i * M_PI / 4));
		if (!GeometryBlocks(thing, pos + dir * (d / 2), r) || !GeometryBlocks(thing, pos + dir * d, r)) return false;
	}
	return true;
}

bool DD_OnDaggerfallMap(FLevelLocals *Level)
{
	const char *map = Level->MapName.GetChars();
	if ((strnicmp(map, "DDT", 3) == 0 || strnicmp(map, "DDS", 3) == 0) && strlen(map) == 8) return true;
	if (strnicmp(map, "DDOVER", 6) == 0) return true;
	return stricmp(map, "MAP01") == 0 && (fileSystem.CheckNumForName("DDDUNGN") >= 0 || fileSystem.CheckNumForName("DFPOINTS") >= 0);
}

// Called as each map starts, before its things spawn (P_SetupLevel through DDTreadmill_BeginMap).
void DD_BodiesBeginMap(FLevelLocals *Level)
{
	if (!Level->isPrimaryLevel()) return;
	DD_MonsterMoveScale = DD_OnDaggerfallMap(Level) ? 10.5 / 16 : 1;
	doorLeafClass = PClass::FindActor("DFDoorBlocker");
	DD_SqueezeActor = nullptr;
}

CVAR(Int, dd_mon_test_kill, 0, CVAR_NOSAVE | CVAR_MOD) // Test only, with -ddmontest: 1 kills a placed monster, 2 a quest foe.

//--------------------------------------------------------------------
// [Doomerfall] DRLA's Monster-flagged spawner and other spawners. RLTheHungrySpawner (Armageddon skill's Lost Soul) is
// Monster-flagged itself, so a placed monster's id would go to the spawner and the monster it makes would have none
// (and, summoned, drop nothing). It spawns several RLTheHungrySingleSpawner helpers (not monsters), each of which spawns
// an RLArmageddonLostSoul. (DRLA's Adaptive spawners were the other case; the Doomerfall mod removes the Adaptive skill.)
// Identified by class only, never by behaviour, so a Pain Elemental or any real summoner is never one. SpawnMook gives
// such a spawner the id as ddHandoffId instead of ddRecordId, so it is never a mook; an overworld seed does the same for
// it and for a RandomSpawner (DDTreadmill). What it spawns while it acts (state actions, PostBeginPlay: DD_ActingActor)
// carries the handoff on if it is not a monster, and the first monster spawned along that line takes the id: one id,
// one drop set. Later monsters from the same spawner have no id: summoned. Without a bridge session or without DRLA
// nothing here does anything.
//--------------------------------------------------------------------

bool DD_BridgeHasSession();

bool DD_IsDrlaSpawner(AActor *mo)
{
	static const FName hungry("RLTheHungrySpawner");
	return mo && (mo->flags3 & MF3_ISMONSTER) && DD_BridgeHasSession() && mo->IsKindOf(hungry);
}

void DD_SpawnerHandoff(AActor *mo)
{
	AActor *from = DD_ActingActor;
	if (!from || !from->ddHandoffId || mo->player || (mo->flags & MF_MISSILE)) return;
	const uint64_t id = from->ddHandoffId;
	if (!(mo->flags3 & MF3_ISMONSTER)) { mo->ddHandoffId = id; return; }	// A helper (RLTheHungrySingleSpawner, a RandomSpawner): carries it on.
	// A monster. If an earlier one took the id (and so survived its spawn checks), every carrier lets go and this one is
	// summoned. A monster A_SpawnItemEx destroys at once because it was blocked does not count: the next one takes the id.
	auto it = mo->Level->GetThinkerIterator<AActor>();
	while (AActor *other = it.Next())
		if (other != mo && other->ddRecordId == id)
		{
			auto all = mo->Level->GetThinkerIterator<AActor>();
			while (AActor *carrier = all.Next()) if (carrier->ddHandoffId == id) carrier->ddHandoffId = 0;
			return;
		}
	if (DD_IsDrlaSpawner(mo)) mo->ddHandoffId = id;	// A spawner spawned by a spawner.
	else if (!mo->ddRecordId)
	{
		mo->ddRecordId = id;
		mo->SpawnPoint = mo->Pos();	// So the world table can tell it has not moved.
		DD_DebugPrintf("DDMON spawner %s gave %016" PRIx64 " to %s\n", from->GetClass()->TypeName.GetChars(), id, mo->GetClass()->TypeName.GetChars());
	}
}

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
// A dungeon's seeded army. Every visit plans again and spawns the mooks that are neither dead nor present. The army's
// request holds only the map's markers and its placer ignores who stands where, so every visit plans the same mooks on
// the same spots (PlanVersion names that rule). Quest foes are a second request, planned around the army's spots, so a
// quest never changes the army (gamedesign.md, encounters). `quests` is no longer filled; it stays for old records.
constexpr int PlanVersion = 1;
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
		if (!mo->player && !mo->ddRecordId && (mo->flags3 & MF3_ISMONSTER) && mo->health > 0 && !DD_IsDrlaSpawner(mo)) free.push_back(mo);
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
			DD_DebugPrintf("DDMON claimed %016" PRIx64 " %s at %.1f,%.1f,%.1f\n", c.id, best->GetClass()->TypeName.GetChars(), best->X(), best->Y(), best->Z());
			claims.erase(claims.begin() + n);
		}
		else if (Level->maptime > c.deadline)
		{
			DD_DebugPrintf("DDMON no monster for %016" PRIx64 "\n", c.id);
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
	uint64_t variant = DD_LootSeedOf(id, 0x7370776eull);	// A mod's spawner picks the same variant (and so the same drops) every game.
	AActor *mo;
	{
		DDLootScope scope(&variant);
		mo = Spawn(Level, cls, at, replace ? ALLOW_REPLACE : NO_REPLACE);
	}
	if (!mo) return nullptr;
	if (DD_IsDrlaSpawner(mo)) mo->ddHandoffId = id;	// Passed on to the monster it makes (DD_SpawnerHandoff).
	else if ((mo->flags3 & MF3_ISMONSTER) && !mo->ddRecordId) { mo->ddRecordId = id; mo->SpawnPoint = mo->Pos(); RigFaction(mo, side, stance); }
	else claims.push_back({ id, at, Level->maptime + ClaimTics, side, stance });
	return mo;
}

bool SpawnLeader(FLevelLocals *Level, PClassActor *cls, uint64_t id, const DVector3 &at, bool replace, const char *why)
{
	if (!SpawnMook(Level, cls, id, at, replace)) return false;
	DD_DebugPrintf("DDENC leader %016" PRIx64 " %s at %.1f,%.1f,%.1f (%s)\n", id, cls->TypeName.GetChars(), at.X, at.Y, at.Z, why);
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
bool PlaceMooks(FLevelLocals *Level, const std::vector<Placement> &list, std::vector<DDEncMookOut> &mooks, const std::vector<DDEncMookOut> *occupied)
{
	if (!facts.have) return false;
	const dfb_encounter_area &a = facts.area;
	FString header;
	header.AppendFormat("area\t%d\t%d\t%d\t%.3f\t%.3f\t%s\t%d\t%d\n", a.dungeon_index, a.location_id, a.region_index, a.world_x, a.world_y,
		facts.type.GetChars(), a.area_level, a.seed_offset);
	header.AppendFormat("location\t%s\nregion\t%s\n", facts.location.GetChars(), facts.region.GetChars());
	std::vector<DDEncPlacementIn> in;
	for (const Placement &p : list) in.push_back({ p.placement, p.pos, p.enemyType, p.quest });
	if (!DD_PlaceEncounters(Level, header, in, mooks, occupied)) return false;
	int mismatched = 0;
	for (const DDEncMookOut &m : mooks)
		mismatched += m.member == 0 && m.id != LeaderId(list[m.placement].placement);
	if (mismatched) DD_DebugPrintf("DDENC warning: %d leader ids from the plan differ from the placement ids\n", mismatched);
	return true;
}

// Plans one request and spawns the wanted placements' mooks that are neither dead nor present (spawn false: plan only).
// planOut receives the planned mooks; occupied are an earlier request's mooks to keep clear of.
void SpawnPass(FLevelLocals *Level, const std::vector<Placement> &list, const std::unordered_set<uint64_t> &wanted, const std::unordered_set<uint64_t> &dead,
	const std::unordered_set<uint64_t> &present, bool spawn, const char *what, std::vector<DDEncMookOut> *planOut, const std::vector<DDEncMookOut> *occupied);

// Two requests. The army: the map's markers alone, planned on every visit that still has mooks to spawn (a cleared
// dungeon is not planned again). The quest foes: Daggerfall's living quest leaders, planned around the army's spots
// whenever one is missing, so the army is the same whatever quests are active. A quest request needs the army's
// spots, so it plans the army (without spawning) when the army itself was not needed.
void SpawnEncounters(FLevelLocals *Level, bool mapLeaders)
{
	std::unordered_set<uint64_t> dead, present;
	std::vector<Placement> army, quests;
	for (const Marker &m : markers) army.push_back({ m.placement, m.pos, m.record == 16 ? (m.mobile & 0xff) : -1, false });
	for (const Row &r : incoming)
	{
		if (r.state == DFB_MONSTER_DEAD) dead.insert(r.id);
		else if (r.state == DFB_MONSTER_PLACE && (r.id & MemberMask) == 0) quests.push_back({ PlacementOf(r.id), r.pos, r.enemyType, true });
	}
	std::sort(quests.begin(), quests.end(), [](const Placement &a, const Placement &b) { return a.placement < b.placement; });
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (IsMonsterId(mo->ddRecordId)) present.insert(mo->ddRecordId);
			if (IsMonsterId(mo->ddHandoffId)) present.insert(mo->ddHandoffId);	// Still with a DRLA spawner.
		}
		for (const Claim &c : claims) present.insert(c.id);
	}
	auto known = plans.find(dungeonMapId);
	const bool revisit = known != plans.end();
	auto missing = [&](const Placement &p) { return !dead.count(LeaderId(p.placement)) && !present.count(LeaderId(p.placement)); };
	std::unordered_set<uint64_t> wantedArmy, wantedQuests;
	if (mapLeaders)
	{
		int accounted = 0;
		std::unordered_set<uint64_t> placements;
		for (const Placement &p : army) placements.insert(p.placement);
		for (const auto *set : { &dead, &present })
			for (uint64_t id : *set) accounted += placements.count(PlacementOf(id)) != 0 && !(set == &present && dead.count(id));
		if (!revisit || accounted < known->second.mooks) wantedArmy = placements;
		else Printf("DDENC all %d planned mooks are dead or present; not planning again\n", known->second.mooks);
	}
	for (const Placement &p : quests) if (mapLeaders || missing(p)) wantedQuests.insert(p.placement);
	if (mapLeaders && facts.have)
	{
		const dfb_encounter_area &a = facts.area;
		DD_DebugPrintf("DDENC facts map %d dungeonIndex %d locationId %d name '%s' region %d '%s' world %.1f,%.1f type %d (%s) areaLevel %d seedOffset %d markers %d quest %d dead %d plan version %d\n",
			a.map_id, a.dungeon_index, a.location_id, facts.location.GetChars(), a.region_index, facts.region.GetChars(), a.world_x, a.world_y,
			a.dungeon_type, facts.type.GetChars(), a.area_level, a.seed_offset, int(markers.size()), int(quests.size()), int(dead.size()), PlanVersion);
	}
	if (wantedArmy.empty() && wantedQuests.empty()) return;
	std::vector<DDEncMookOut> armyMooks;
	if (!army.empty())
	{
		SpawnPass(Level, army, wantedArmy, dead, present, !wantedArmy.empty(), wantedArmy.empty() ? "army spots for the quest foes" : revisit ? "army, revisit" : "army",
			&armyMooks, nullptr);
		if (mapLeaders && !revisit && !armyMooks.empty()) plans[dungeonMapId] = DungeonPlan{ {}, int(armyMooks.size()) };
	}
	if (!wantedQuests.empty()) SpawnPass(Level, quests, wantedQuests, dead, present, true, "quest foes", nullptr, &armyMooks);
}

// Plans one request and spawns the mooks of the wanted placements that are neither dead nor present. A quest foe that
// arrives during a visit comes back whole only when its leader is missing; its followers are skipped by id.
void SpawnPass(FLevelLocals *Level, const std::vector<Placement> &list, const std::unordered_set<uint64_t> &wanted, const std::unordered_set<uint64_t> &dead,
	const std::unordered_set<uint64_t> &present, bool spawn, const char *what, std::vector<DDEncMookOut> *planOut, const std::vector<DDEncMookOut> *occupied)
{
	std::vector<DDEncMookOut> mooks;
	const auto t0 = std::chrono::steady_clock::now();
	// The plan must not depend on who stands where: every player and monster (restored, spawned, or a mod's) is out of
	// the way while placing. Door and action objects stay solid; no state is applied to them before the plan, so they
	// are always at their start pose here.
	std::vector<AActor *> unsolid;
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if ((mo->player || (mo->flags3 & MF3_ISMONSTER)) && (mo->flags & MF_SOLID)) { mo->flags &= ~MF_SOLID; unsolid.push_back(mo); }
	}
	const bool ok = PlaceMooks(Level, list, mooks, occupied);
	for (AActor *mo : unsolid) mo->flags |= MF_SOLID;
	if (ok && planOut) *planOut = mooks;
	if (ok && !spawn)
	{
		DD_DebugPrintf("DDENC planned %d mooks for %d placements (%s), none spawned\n", int(mooks.size()), int(list.size()), what);
		return;
	}
	if (!ok)
	{
		DD_DebugPrintf("DDENC no plan (planner or facts missing); using the stock roster\n");
		int spawned = 0;
		for (const Placement &p : list)
		{
			const uint64_t id = LeaderId(p.placement);
			if (wanted.count(p.placement) && !dead.count(id) && !present.count(id))
				spawned += SpawnLeader(Level, RosterClass(p.placement), id, p.pos, true, p.quest ? "quest roster" : "roster");
		}
		DD_DebugPrintf("DDENC spawned %d stock leaders of %d placements\n", spawned, int(list.size()));
		return;
	}
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
			DD_DebugPrintf("DDENC leader %016" PRIx64 " %s at %.1f,%.1f,%.1f%s\n", m.id, m.cls->TypeName.GetChars(), mo->X(), mo->Y(), mo->Z(), p.quest ? " (quest)" : "");
	}
	// Stuck: a spawned monster that Doom's own check says does not fit where it stands.
	for (auto &f : fresh)
		if (!(f.first->ObjectFlags & OF_EuthanizeMe) && !P_TestMobjLocation(f.first)) { stuck++; stuckLeaders += f.second; }
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	DD_DebugPrintf("DDENC spawned %d mooks (%d leaders) of %d planned for %d placements (%d dead, %d already present), stuck %d (%d leaders), %.1f ms with spawning%s\n",
		spawned, leaders, int(mooks.size()), int(list.size()), skippedDead, skippedPresent, stuck, stuckLeaders, ms, FStringf(", %s", what).GetChars());
	if (warSide[0] + warSide[1])
		DD_DebugPrintf("DDWAR civil war: army A %d mooks stance %d, army B %d mooks stance %d\n", warSide[0], warStance[0], warSide[1], warStance[1]);
}

void ApplyRows(FLevelLocals *Level)
{
	if (!incomingReady || DD_LocationsWaiting()) return;	// Daggerfall's record of the place comes first.
	incomingReady = false;
	facts = incomingFacts;
	const bool mapLeaders = leadersPending && facts.have && facts.area.map_id == dungeonMapId;
	if (mapLeaders) leadersPending = false;
	SpawnEncounters(Level, mapLeaders);
	if (mapLeaders) DD_SetupDone("monsters");
	for (const Row &r : incoming)
	{
		if (r.state != DFB_MONSTER_DEAD || reported.count(r.id)) continue;
		// Daggerfall has it dead and this session did not kill it, so a mismatched state must not revive it.
		AActor *mo = FindById(Level, r.id);
		if (mo && mo->health > 0)
		{
			DD_DebugPrintf("DDMON removed %016" PRIx64 ", which Daggerfall has as dead\n", r.id);
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
	if (!pick) { DD_DebugPrintf("DDMON test kill found nothing\n"); return; }
	DD_DebugPrintf("DDMON test kill %016" PRIx64 " %s at %.1f,%.1f,%.1f floor %.1f ceiling %.1f\n", pick->ddRecordId, pick->GetClass()->TypeName.GetChars(), pick->X(), pick->Y(), pick->Z(), pick->floorz, pick->ceilingz);
	P_DamageMobj(pick, Level->Players[consoleplayer]->mo, Level->Players[consoleplayer]->mo, pick->health + 1000, NAME_None, DMG_FORCED);
}

FString PayloadText(const char *text, size_t size)
{
	size_t n = 0;
	while (n < size && text[n]) n++;
	return FString(text, n);
}
}

void DD_MonstersRunClaimsForTest(FLevelLocals *Level) { RunClaims(Level); }	// -ddloottest only (dd_encounter_test.cpp).

// Called when a dungeon starts, after the world table has brought back the changed monsters. The map's markers are read
// on every visit, so the request stays the same; once Daggerfall's facts arrive, every mook that is neither dead nor
// present is spawned again from the plan, because the table does not store unchanged ones.
void DD_MonstersEnterDungeon(FLevelLocals *Level, int mapId, bool firstVisit, bool bridged)
{
	claims.clear();
	dungeonMapId = mapId;
	CollectMarkers(Level);
	leadersPending = bridged;
	DD_DebugPrintf("DDMON dungeon %d has %d encounter markers%s\n", mapId, int(markers.size()), firstVisit ? ", first visit" : "");
	if (bridged) DD_SetupWait("monsters");	// A no-op for a map restored from a save. Done in ApplyRows.
	if (bridged) return;
	int spawned = 0;
	for (const Marker &m : markers)
		if (!FindById(Level, LeaderId(m.placement)))
			spawned += SpawnLeader(Level, RosterClass(m.placement), LeaderId(m.placement), m.pos, true, "no bridge, roster");
	DD_DebugPrintf("DDENC spawned %d stock leaders without a bridge\n", spawned);
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
	DD_DebugPrintf("DDMON died %016" PRIx64 " target %d\n", death.id, target);
}
