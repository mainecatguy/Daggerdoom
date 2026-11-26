// [Doomerfall] Test only: the arrival freeze (DD_BridgeArrivalFreeze, dd_bridge.cpp). Does nothing without its flags.
//   -dfsetuptest <ms|lost>  every map's setup also waits for a fake system that answers after <ms>, or never (lost),
//                           so the arrival waits as for a slow or lost Daggerfall answer (the gate's 5 s timeout).
//   -dffreezetest           logs, to the bridge log, whether any monster, missile or player changed while the playsim
//                           was frozen, the player's health before and after, and how often frames ran meanwhile.
//   -dffreezeuse            presses Use (dd_tm_use) on every frozen frame: it must do nothing (no take, talk or exit).
// Lines start with "arrivaltest:". tools/arrival_freeze/run_freeze.py reads them.

#include <cstdlib>
#include <cstring>
#include <unordered_map>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "d_player.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "m_argv.h"
#include "printf.h"
#include "c_cvars.h"

FARG_ADVANCED(dfsetuptest, "Doomerfall", "ms|lost", "Arrival test only: each map's setup also waits this long for a fake answer, or forever (lost).");
FARG_ADVANCED(dffreezetest, "Doomerfall", "", "Arrival test only: logs whether anything moved while a map change's playsim was frozen.");
FARG_ADVANCED(dffreezeuse, "Doomerfall", "", "Arrival test only: presses Use (dd_tm_use) on every frame of the freeze.");
EXTERN_CVAR(Int, dd_tm_use)

void DD_BridgeLog(const char *text);
void DD_SetupWait(const char *system);
void DD_SetupDone(const char *system);
int DD_BridgeArrivalFrozenTics();

namespace
{
struct Snap
{
	DVector3 pos;
	DAngle yaw;
	int health;
	FState *state;
	int tics;
};

bool parsed, freezeTest, freezeUse;
int usePresses;
const char *setupTest;
int64_t setupDoneAtNs = -1;	// -1: no fake wait open
std::unordered_map<AActor *, Snap> snaps;
bool snapped;
int frames, playerHealthBefore, newcomers;
int64_t freezeStartNs, lastFrameNs, maxGapNs;

void Parse()
{
	parsed = true;
	setupTest = Args->CheckValue(FArg_dfsetuptest);
	freezeTest = Args->CheckParm(FArg_dffreezetest) > 0;
	freezeUse = Args->CheckParm(FArg_dffreezeuse) > 0;
}

void Log(const FString &text) { DD_BridgeLog(("arrivaltest: " + text).GetChars()); }

bool Watched(AActor *a) { return a->player || (a->flags3 & MF3_ISMONSTER) || (a->flags & MF_MISSILE); }

// Actors that appear during the freeze (the setup spawns the dungeon's monsters) are watched from the frame they are
// first seen.
void AddNewcomers()
{
	auto it = primaryLevel->GetThinkerIterator<AActor>();
	while (AActor *a = it.Next())
		if (Watched(a) && snaps.emplace(a, Snap{ a->Pos(), a->Angles.Yaw, a->health, a->state, a->tics }).second && snapped) newcomers++;
}

void TakeSnapshot(int64_t now)
{
	snaps.clear();
	newcomers = 0;
	AddNewcomers();
	AActor *pmo = players[consoleplayer].mo;
	playerHealthBefore = pmo ? pmo->health : -1;
	snapped = true;
	frames = 0;
	freezeStartNs = lastFrameNs = now;
	maxGapNs = 0;
	Log(FStringf("frozen, watching %d actors at maptime %d", int(snaps.size()), primaryLevel->maptime));
}

// The first frame after the freeze ended: every tic since the last frozen frame was still frozen (the freeze ends only
// in the bridge frame, before this call), so this compares the whole freeze.
void Compare(int64_t now)
{
	if (now - lastFrameNs > maxGapNs) maxGapNs = now - lastFrameNs;	// the last frozen tics ran just before this frame
	int changed = 0, monsters = 0, spawned = 0;
	auto it = primaryLevel->GetThinkerIterator<AActor>();
	while (AActor *a = it.Next())
	{
		if (!Watched(a)) continue;
		const auto s = snaps.find(a);
		if (s == snaps.end()) { spawned++; continue; }	// appeared in the last frozen tics: not seen before them
		if (a->flags3 & MF3_ISMONSTER) monsters++;
		const Snap &b = s->second;
		if (a->Pos() != b.pos || a->Angles.Yaw != b.yaw || a->health != b.health || a->state != b.state || a->tics != b.tics)
		{
			if (changed < 5) Log(FStringf("changed %s at %.1f,%.1f (was %.1f,%.1f), health %d (was %d)", a->GetClass()->TypeName.GetChars(),
				a->X(), a->Y(), b.pos.X, b.pos.Y, a->health, b.health));
			changed++;
		}
	}
	AActor *pmo = players[consoleplayer].mo;
	// The last press may come after the last frozen tic; it is taken back so the test never presses into play.
	Log(FStringf("use presses=%d unconsumed=%d", usePresses, *dd_tm_use));
	dd_tm_use = 0;
	usePresses = 0;
	Log(FStringf("result changed=%d monsters=%d newcomers=%d spawned=%d player_health=%d->%d frames=%d max_frame_gap_ms=%.1f frozen_ms=%.1f",
		changed, monsters, newcomers, spawned, playerHealthBefore, pmo ? pmo->health : -1, frames, maxGapNs / 1e6, (now - freezeStartNs) / 1e6));
	snaps.clear();
	snapped = false;
}
}

// dd_setup.cpp, when a map's setup starts.
void DD_ArrivalTestSetupStarted()
{
	if (!parsed) Parse();
	if (!setupTest) return;
	DD_SetupWait("arrivaltest");
	setupDoneAtNs = strcmp(setupTest, "lost") ? dfb_now_ns() + int64_t(atoi(setupTest)) * 1000000 : INT64_MAX;
}

// From DD_BridgeTestFrame, once per bridge frame between tics.
void DD_ArrivalTestFrame(int64_t now)
{
	if (!parsed) Parse();
	if (setupDoneAtNs >= 0 && now >= setupDoneAtNs)
	{
		setupDoneAtNs = -1;
		DD_SetupDone("arrivaltest");
	}
	if (!freezeTest || gamestate != GS_LEVEL || !primaryLevel) return;
	if (DD_BridgeArrivalFrozenTics() > 0)
	{
		if (!snapped) { TakeSnapshot(now); return; }
		AddNewcomers();
		frames++;
		if (freezeUse) { dd_tm_use = 1; usePresses++; }
		if (now - lastFrameNs > maxGapNs) maxGapNs = now - lastFrameNs;
		lastFrameNs = now;
	}
	else if (snapped) Compare(now);
}
