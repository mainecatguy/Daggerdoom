// [Doomerfall] Daggerfall creatures shown in Doom. A DFCreature (mods/doomerfall/src/zscript/DoomerfallCorpses.zs) is
// drawn with a Daggerfall mobile archive read at run time from Daggerfall's own files or a texture pack (dd_dftextures):
// args[0] is the archive, args[1] the creature's Daggerfall MobileTypes value. Its state picks the record group, as
// Daggerfall's MobileUnit does: attack while in its Melee or Missile sequence, hurt in Pain, moving in See, idle
// otherwise (an archive without idle records shows its move records). How a creature fights comes from the DFCreature
// subclass. When it dies, Doom plays Daggerfall's blood splash and tells Daggerfall where the body fell with the
// creature's type, and Daggerfall decides and keeps its corpse (DoomerfallTownspeople.OnCorpsePlace), as for a
// townsperson. Nothing here runs unless a DFCreature exists in a bridge session.

#include <chrono>
#include <cinttypes>
#include <cmath>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "d_player.h"
#include "g_levellocals.h"
#include "info.h"
#include "playsim/dd_log.h"
#include "playsim/dd_treadmill.h"

bool DD_MobileSprite(AActor *mo, int archive, int base, double facing, AActor *camera);
void DD_CorpseFellAs(dfb_session *session, AActor *mo, uint64_t id, bool interior, double worldX, double worldZ, uint32_t creature);

namespace
{
constexpr int MoveRecords = 0, AttackRecords = 5, HurtRecords = 10, IdleRecords = 15;
uint64_t serial;

PClassActor *CreatureClass() { return PClass::FindActor("DFCreature"); }

// Whether mo's state is in the run of consecutive states from base (as p_mobj.cpp's InStateSequence).
bool In(AActor *mo, FState *base)
{
	for (FState *s = base, *prev = nullptr; s && (!prev || s == prev + 1); prev = s, s = s->GetNextState())
		if (s == mo->state) return true;
	return false;
}

int RecordsFor(AActor *mo)
{
	if (In(mo, mo->FindState(NAME_Melee)) || In(mo, mo->FindState(NAME_Missile))) return AttackRecords;
	if (In(mo, mo->FindState(NAME_Pain))) return HurtRecords;
	if (In(mo, mo->SeeState) || mo->Vel.XY().LengthSquared() > 0.25) return MoveRecords;
	return IdleRecords;
}

// Outdoors, Doom's map is a window on Daggerfall's world: find mo's world position by probing the treadmill's
// world-to-Doom mapping around the player (it is linear).
bool WorldOf(AActor *mo, double &wx, double &wz)
{
	double px, py, pz, yaw;
	if (DDTreadmill_PlayerWorld(px, py, pz, yaw) != DD_AREA_EXTERIOR) return false;
	constexpr double Step = 1000;
	double x0, y0, x1, y1, x2, y2;
	if (!DDTreadmill_WorldToLocal(px, py, x0, y0) || !DDTreadmill_WorldToLocal(px + Step, py, x1, y1) || !DDTreadmill_WorldToLocal(px, py + Step, x2, y2)) return false;
	const double ax = x1 - x0, ay = y1 - y0, bx = x2 - x0, by = y2 - y0, det = ax * by - ay * bx;
	if (fabs(det) < 1e-9) return false;
	const double dx = mo->X() - x0, dy = mo->Y() - y0;
	wx = px + Step * (dx * by - dy * bx) / det;
	wz = py + Step * (ax * dy - ay * dx) / det;
	return true;
}
}

void DD_CreaturesTick(FLevelLocals *Level)
{
	PClassActor *cls = CreatureClass();
	if (!cls) return;
	AActor *camera = Level->Players[consoleplayer]->camera;
	auto it = Level->GetThinkerIterator<AActor>(cls->TypeName);
	while (AActor *mo = it.Next())
	{
		if (mo->health <= 0) continue;
		// A Daggerfall corpse is kept under the body's id. One not given an id by its spawner gets one that no earlier
		// session used (tag 0, a clock-based serial), so a saved corpse never matches a new creature.
		if (!mo->ddRecordId)
		{
			if (!serial) serial = uint64_t(std::chrono::system_clock::now().time_since_epoch().count());
			mo->ddRecordId = ++serial & ((1ull << 60) - 1);
		}
		const double yaw = mo->Angles.Yaw.Degrees();
		if (!DD_MobileSprite(mo, mo->args[0], RecordsFor(mo), yaw, camera))
			DD_MobileSprite(mo, mo->args[0], MoveRecords, yaw, camera);
	}
}

void DD_CreatureDied(dfb_session *session, AActor *mo)
{
	PClassActor *cls = CreatureClass();
	if (!cls || !mo->IsKindOf(cls)) return;
	double wx = 0, wz = 0;
	const bool outdoors = WorldOf(mo, wx, wz);
	DD_CorpseFellAs(session, mo, mo->ddRecordId, !outdoors, wx, wz, uint32_t(mo->args[1]) + 1);
	mo->picnum.SetNull();	// Daggerfall's corpse takes its place
	mo->renderflags |= RF_INVISIBLE;
	DD_DebugPrintf("DDCREATURE died %016" PRIx64 " archive %d type %d\n", mo->ddRecordId, mo->args[0], mo->args[1]);
}
