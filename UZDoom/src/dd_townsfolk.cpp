// [Doomerfall] Doom's side of persistent townspeople. Daggerfall generates each town's people from a seed and the
// world time, and lists the ones near the player with their motion. This keeps one passive actor per listed person,
// moves it between lists, and picks Daggerfall's facing sprite. The id lives in ddRecordId, so a death reaches
// Daggerfall through the same hook as a monster's. Nothing here runs until Daggerfall sends a townsfolk list.
// Inside a building, Daggerfall lists the people at home there instead, already in the interior map's units.

#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "d_player.h"
#include "doomstat.h"
#include "filesystem.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "p_local.h"
#include "printf.h"
#include "texturemanager.h"
#include "playsim/dd_log.h" // [Doomerfall]

bool DDTreadmill_WorldToLocal(double x, double y, double &doomX, double &doomY);

namespace
{
constexpr double DoomPerDf = 0.75;
constexpr double SnapDistance = 128;
constexpr int Records = 20;	// An enemy archive such as the guard's has move, attack, hurt, and idle groups of five.

struct Row { uint16_t archive, flags; double x, y, vx, vy; float facing, z; };
struct Look { FTextureID tex[Records]; DVector2 scale[Records]; };

std::unordered_map<uint64_t, Row> accepted, rows;
std::unordered_set<uint64_t> killed;
std::unordered_map<int, Look> looks;
std::unordered_map<int64_t, DVector2> mobileScales;
uint32_t acceptedGeneration;
double acceptedOx, acceptedOz, originX, originZ;
int listTic;
bool listPending, everListed, wantList, scalesLoaded, acceptedIndoors, indoors;
bool snapList; // The pending list comes after a menu ran the clock (dd_resync.cpp): place everyone at once.
uint32_t currentContext;

bool IsTownspersonId(uint64_t id) { return (id >> 61) == DFB_TOWNSPERSON_TAG; }

void SendRequest(dfb_session *session)
{
	dfb_event e{};
	e.kind = DFB_KIND_TOWNSFOLK_REQUEST;
	e.tic = gametic;
	dfb_send(session, &e);
}

// DFMOBILE, written by the converter: "archive record sx sy" for each mobile billboard record.
void LoadScales()
{
	if (scalesLoaded) return;
	scalesLoaded = true;
	const int lump = fileSystem.CheckNumForName("DFMOBILE");
	if (lump < 0) { DD_DebugPrintf("DDTOWNSFOLK no DFMOBILE lump, so townspeople use unit scale\n"); return; }
	auto data = fileSystem.ReadFile(lump);
	FString text((const char *)data.data(), data.size());
	for (auto &line : text.Split("\n"))
	{
		int archive, record;
		double sx, sy;
		if (sscanf(line.GetChars(), "%d %d %lf %lf", &archive, &record, &sx, &sy) == 4) mobileScales[int64_t(archive) << 8 | record] = DVector2(sx, sy);
	}
}

const Look &LookFor(int archive)
{
	auto found = looks.find(archive);
	if (found != looks.end()) return found->second;
	LoadScales();
	Look look;
	for (int r = 0; r < Records; r++)
	{
		char name[40];
		snprintf(name, sizeof(name), "dfflat/F%03dR%02d.png", archive, r);
		look.tex[r] = TexMan.CheckForTexture(name, ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup);
		auto s = mobileScales.find(int64_t(archive) << 8 | r);
		look.scale[r] = s != mobileScales.end() ? s->second : DVector2(1, 1);
	}
	return looks.emplace(archive, look).first->second;
}

// Daggerfall's mobile billboards: records 0-4 walk from front to back, mirrored for the other side; 5 idles (15 for guards).
void ChooseSprite(AActor *mo, const Row &r, AActor *camera, bool walking)
{
	const Look &look = LookFor(r.archive);
	int record = (r.flags & DFB_TOWNSPERSON_GUARD) ? 15 : 5;
	bool flip = false;
	if (walking || !look.tex[record].isValid())
	{
		double toCamera = camera ? atan2(camera->Y() - mo->Y(), camera->X() - mo->X()) * (180 / M_PI) : r.facing;
		double rel = fmod(toCamera - r.facing + 720 + 22.5, 360);
		const int k = int(rel / 45) & 7;
		record = k <= 4 ? k : 8 - k;
		flip = k > 4;
	}
	if (!look.tex[record].isValid()) return;
	mo->picnum = look.tex[record];
	mo->Scale = look.scale[record];
	if (flip) mo->renderflags |= RF_XFLIP;
	else mo->renderflags &= ~RF_XFLIP;
}

}

// Draws mo with a Daggerfall mobile archive: records base to base+4 run from front to back, mirrored for the other side.
// Shared with dd_guards.cpp. False if the archive has no such records.
bool DD_MobileSprite(AActor *mo, int archive, int base, double facing, AActor *camera)
{
	const Look &look = LookFor(archive);
	const double toCamera = camera ? atan2(camera->Y() - mo->Y(), camera->X() - mo->X()) * (180 / M_PI) : facing;
	const int k = int(fmod(toCamera - facing + 720 + 22.5, 360) / 45) & 7;
	const int record = base + (k <= 4 ? k : 8 - k);
	if (record >= Records || !look.tex[record].isValid()) return false;
	mo->picnum = look.tex[record];
	mo->Scale = look.scale[record];
	if (k > 4) mo->renderflags |= RF_XFLIP;
	else mo->renderflags &= ~RF_XFLIP;
	return true;
}

namespace
{
bool Target(const Row &r, int tics, DVector2 &out)
{
	const double dt = tics / double(TICRATE);
	if (indoors) { out = DVector2(r.x, r.y); return true; }
	return DDTreadmill_WorldToLocal(originX + r.x + r.vx * dt, originZ + r.y + r.vy * dt, out.X, out.Y);
}

void Place(AActor *mo, const DVector2 &at, bool snap, double z)
{
	DVector2 to = at;
	if (!snap)
	{
		const DVector2 d = at - mo->Pos().XY();
		if (d.LengthSquared() < SnapDistance * SnapDistance) to = mo->Pos().XY() + d * 0.35;
	}
	// Indoors, start from the spot's height so a storey above or below is not picked.
	mo->SetOrigin(DVector3(to, indoors ? z + 8 : mo->Z()), !snap);
	P_FindFloorCeiling(mo, FFCF_ONLYSPAWNPOS);
	mo->SetZ(mo->floorz);
	if (snap) mo->ClearInterpolation();
}

// Daggerfall kills a wandering townsperson with any weapon hit (WeaponManager.WeaponDamage), so it has one point of
// health. Its box follows the billboard, as the mobile's collider does. It still blocks no one, and autoaim and
// monsters ignore it. DD_TownsfolkRefuseDamage keeps everyone but the player from hurting it.
void MakeKillable(AActor *mo)
{
	mo->UnlinkFromWorld(nullptr);
	mo->flags &= ~MF_NOBLOCKMAP;
	mo->flags |= MF_SHOOTABLE;
	mo->flags5 &= ~MF5_NOINTERACTION;
	mo->flags6 |= MF6_NOTAUTOAIMED;
	mo->flags7 |= MF7_NEVERTARGET | MF7_DONTTHRUST;
	mo->health = 1;
	if (mo->picnum.isValid())
	{
		auto tex = TexMan.GetGameTexture(mo->picnum);
		mo->radius = clamp(tex->GetDisplayWidth() * fabs(mo->Scale.X) * 0.3, 6., 20.);
		mo->Height = clamp(tex->GetDisplayHeight() * mo->Scale.Y, 16., 96.);
	}
	mo->LinkToWorld(nullptr);
}
}

// Called by P_DamageMobj for any actor with a ddRecordId. Daggerfall only lets the player hurt townspeople
// (DaggerfallEntityBehaviour.HandleAttackFromSource); enemies never attack them.
bool DD_TownsfolkRefuseDamage(AActor *target, AActor *source)
{
	return IsTownspersonId(target->ddRecordId) && !(source && source->player);
}

void DD_TownsfolkTick(FLevelLocals *Level)
{
	if (!everListed) return;
	bool snap = false;
	if (listPending)
	{
		listPending = false;
		snap = snapList;
		snapList = false;
		rows.swap(accepted);
		accepted.clear();
		originX = acceptedOx;
		originZ = acceptedOz;
		indoors = acceptedIndoors;
		listTic = Level->maptime;
	}
	PClassActor *cls = PClass::FindActor("DFTownsperson");
	if (!cls) cls = PClass::FindActor("DFCityFlat");
	if (!cls) return;
	AActor *camera = Level->Players[consoleplayer]->camera;
	const int tics = Level->maptime - listTic;
	std::unordered_set<uint64_t> present;
	auto it = Level->GetThinkerIterator<AActor>(cls->TypeName);
	while (AActor *mo = it.Next())
	{
		if (!IsTownspersonId(mo->ddRecordId)) continue;
		auto row = rows.find(mo->ddRecordId);
		DVector2 at;
		if (row == rows.end() || killed.count(mo->ddRecordId) || !present.insert(mo->ddRecordId).second || !Target(row->second, tics, at))
		{
			mo->Destroy();
			continue;
		}
		Place(mo, at, snap, row->second.z);
		ChooseSprite(mo, row->second, camera, row->second.vx != 0 || row->second.vy != 0);
	}
	int spawned = 0;
	for (auto &[id, r] : rows)
	{
		DVector2 at;
		if (present.count(id) || killed.count(id) || !Target(r, tics, at)) continue;
		AActor *mo = Spawn(Level, cls, DVector3(at, 0), NO_REPLACE);
		if (!mo) continue;
		mo->ddRecordId = id;
		mo->args[0] = int(uint32_t(id));
		mo->args[1] = int(uint32_t(id >> 32));
		Place(mo, at, true, r.z);
		ChooseSprite(mo, r, camera, r.vx != 0 || r.vy != 0);
		MakeKillable(mo);
		spawned++;
	}
	if (spawned) DD_DebugPrintf("DDTOWNSFOLK spawned %d, listed %d\n", spawned, int(rows.size()));
}

// dd_resync.cpp, when a menu that ran the clock closes: the list Daggerfall sent before the close is pending now, and
// is placed without walking. False if there is none.
bool DD_TownsfolkSnapPending()
{
	snapList = listPending;
	return listPending;
}

bool DD_TownsfolkSettled() { return !listPending && !snapList; }

bool DD_TownsfolkEvent(const dfb_event &e)
{
	switch (e.kind)
	{
	case DFB_KIND_TOWNSFOLK_BEGIN:
	{
		dfb_townsfolk b;
		memcpy(&b, e.payload, sizeof(b));
		acceptedGeneration = b.generation;
		acceptedOx = b.origin_x;
		acceptedOz = b.origin_z;
		acceptedIndoors = b.space == DFB_TOWNSFOLK_INTERIOR;
		accepted.clear();
		return true;
	}
	case DFB_KIND_TOWNSPERSON:
	{
		dfb_townsperson p;
		memcpy(&p, e.payload, sizeof(p));
		if (p.generation == acceptedGeneration) accepted[p.id] = { p.archive, p.flags, p.x, p.y, p.vx, p.vy, p.facing, p.z };
		return true;
	}
	case DFB_KIND_TOWNSFOLK_END:
	{
		dfb_townsfolk b;
		memcpy(&b, e.payload, sizeof(b));
		// A list for the other side of a door is stale: the street list must not land in a house, nor the reverse.
		const uint32_t want = acceptedIndoors ? DFB_WORLD_INTERIOR : DFB_WORLD_EXTERIOR;
		if (b.generation == acceptedGeneration && (currentContext == want || b.count == 0)) { listPending = true; everListed = true; }
		return true;
	}
	default:
		return false;
	}
}

void DD_TownsfolkFrame(dfb_session *session, uint32_t context)
{
	if (context != currentContext)
	{
		currentContext = context;
		accepted.clear();
		rows.clear();
		listPending = snapList = false;
		wantList = context == DFB_WORLD_EXTERIOR || context == DFB_WORLD_INTERIOR;
	}
	if (wantList && gamestate == GS_LEVEL)
	{
		wantList = false;
		SendRequest(session);
	}
}

// A load replaced every actor. The saved ones go on the next tic, and the next list brings the living back.
void DD_TownsfolkResync()
{
	rows.clear();
	accepted.clear();
	listPending = snapList = false;
	killed.clear();
	wantList = currentContext == DFB_WORLD_EXTERIOR || currentContext == DFB_WORLD_INTERIOR;
}

void DD_TownsfolkDied(dfb_session *session, AActor *mo)
{
	if (!IsTownspersonId(mo->ddRecordId) || !killed.insert(mo->ddRecordId).second) return;
	dfb_townsperson_death death{ mo->ddRecordId, 0, 0 };
	auto row = rows.find(mo->ddRecordId);
	if (row != rows.end() && !indoors) { death.world_x = originX + row->second.x; death.world_z = originZ + row->second.y; }
	dfb_event e{};
	e.kind = DFB_KIND_TOWNSPERSON_DEATH;
	e.tic = gametic;
	memcpy(e.payload, &death, sizeof(death));
	dfb_send(session, &e);
	DD_DebugPrintf("DDTOWNSFOLK died %016" PRIx64 "\n", death.id);
}
