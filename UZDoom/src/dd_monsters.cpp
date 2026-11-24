// [Doomerfall] Doom's side of monster identity. A generated dungeon's DDMONST lump names each placed
// monster. Its id lives in AActor::ddRecordId, which already survives door trips and saves. Daggerfall
// decides what a death means. Nothing here runs without a bridge session and a tagged monster.

#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <unordered_set>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "c_cvars.h"
#include "doomstat.h"
#include "filesystem.h"
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

struct Claim { uint64_t id; DVector3 pos; int deadline; };
struct Row { uint64_t id; uint32_t state; DVector3 pos; };

std::vector<Claim> claims;
std::vector<Row> incoming, accepted;
std::unordered_set<uint64_t> reported;
uint32_t acceptedGeneration, currentContext;
int32_t currentTarget = -1;
bool spaceValid, wantList;

bool IsMonsterId(uint64_t id) { return (id >> DFB_MONSTER_TAG_SHIFT) == DFB_MONSTER_TAG; }

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

void PlaceQuestFoe(FLevelLocals *Level, const Row &r)
{
	static const char *const roster[] = { "ZombieMan", "ShotgunGuy", "ChaingunGuy", "DoomImp", "Demon", "Spectre", "LostSoul", "Cacodemon",
		"HellKnight", "BaronOfHell", "Revenant", "Fatso", "Arachnotron", "PainElemental", "Archvile" };
	for (const Claim &c : claims) if (c.id == r.id) return;
	if (FindById(Level, r.id)) return;
	PClassActor *cls = PClass::FindActor(roster[(r.id >> DFB_MONSTER_MEMBER_BITS) % countof(roster)]);
	if (!cls) return;
	// Member offsets keep several foes on one marker from starting stuck inside each other.
	const int member = int(r.id & 0xff);
	const DVector3 at(r.pos.X + (member % 3) * 48.0, r.pos.Y + (member / 3) * 48.0, r.pos.Z + 4);
	if (!Spawn(Level, cls, at, ALLOW_REPLACE)) return;
	claims.push_back({ r.id, at, Level->maptime + ClaimTics });
	Printf("DDMON quest foe %016" PRIx64 " placed at %.1f,%.1f,%.1f\n", r.id, at.X, at.Y, at.Z);
}

void ApplyRows(FLevelLocals *Level)
{
	for (const Row &r : incoming)
	{
		if (r.state == DFB_MONSTER_PLACE) PlaceQuestFoe(Level, r);
		else if (!reported.count(r.id))
		{
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
}

// Called when a dungeon starts. On a first visit, every placed monster gets its id.
void DD_MonstersEnterDungeon(FLevelLocals *Level, int mapId, bool firstVisit, bool bridged)
{
	claims.clear();
	if (!bridged || !firstVisit) return;
	int last = 0, lump, rows = 0;
	while ((lump = fileSystem.FindLump("DDMONST", &last)) >= 0)
	{
		auto data = fileSystem.ReadFile(lump);
		FString text((const char *)data.data(), data.size());
		for (auto &line : text.Split("\n"))
		{
			int rowMap;
			uint64_t id;
			double x, y, z;
			if (sscanf(line.GetChars(), "%d %" SCNx64 " %lf %lf %lf", &rowMap, &id, &x, &y, &z) != 5 || rowMap != mapId) continue;
			claims.push_back({ id, DVector3(x, y, z), Level->maptime + ClaimTics });
			rows++;
		}
	}
	Printf("DDMON dungeon %d has %d placements\n", mapId, rows);
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
		return true;
	}
	case DFB_KIND_MONSTER:
	{
		dfb_monster m;
		memcpy(&m, e.payload, sizeof(m));
		if (acceptedGeneration && m.generation == acceptedGeneration)
			accepted.push_back({ m.id, m.state, DVector3(m.x, m.y, m.z) });
		return true;
	}
	case DFB_KIND_MONSTERS_END:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		if (acceptedGeneration && b.generation == acceptedGeneration) incoming = accepted;
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
		wantList = inSpace && context == DFB_WORLD_DUNGEON;
	}
	if (wantList && gamestate == GS_LEVEL)
	{
		wantList = false;
		SendRequest(session);
	}
}

// A load replaced every actor, so what this session reported no longer describes them.
void DD_MonstersResync()
{
	reported.clear();
	claims.clear();
	incoming.clear();
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
