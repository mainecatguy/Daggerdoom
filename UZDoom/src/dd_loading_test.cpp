// [Doomerfall] Test only: loading holds (dd_loading.cpp). Does nothing without -ddloadingtest.
// On every frame while a hold lasts it compares the player, monsters and missiles with how they were on the hold's first
// frame, holds +forward down (the player must not move), and measures the longest gap between frames (the window stays
// live). 1.5 s into the hold it asks for a menu save and a quicksave; both must be refused. The result is logged when
// the hold ends, before any map change it leads to. Lines start with "loadingtest:" in the bridge log.
// -ddloadingblock <ms> (alone or with -ddloadingtest): once, 500 ms into the first hold, blocks the main thread for <ms>,
// as a long dungeon spawn does, so Doom publishes nothing for that time. Daggerfall must stay paused through it; a block
// longer than 60 s stands in for a dead Doom, which must release Daggerfall.

#include <chrono>
#include <thread>
#include <unordered_map>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "c_dispatch.h"
#include "d_event.h"
#include "d_player.h"
#include "doomstat.h"
#include "g_game.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "m_argv.h"
#include "c_cvars.h"

EXTERN_CVAR(Int, dd_tm_use)
#include "printf.h"

FARG_ADVANCED(ddloadingtest, "Doomerfall", "", "Loading hold test only: logs whether anything moved or saved while a long operation held the game.");
FARG_ADVANCED(ddloadingblock, "Doomerfall", "<ms>", "Loading hold test only: blocks the main thread once for <ms>, 500 ms into the first hold.");

void DD_BridgeLog(const char *text);
bool DD_LoadingActive();
double DD_LoadingAgeMs();
bool DD_BridgeSaveActive();
extern bool sendsave;	// g_game.cpp

namespace
{
struct Snap { DVector3 pos; DAngle yaw; int health; };

int enabled = -1;
bool watching, askedSave;
FLevelLocals *heldLevel;
std::unordered_map<AActor *, Snap> snaps;
int frames, changed, watched, healthBefore, healthLast, usePresses, itemsBefore, itemsLast;

int MapItems()
{
	int n = 0;
	auto it = primaryLevel->GetThinkerIterator<AActor>();
	while (AActor *a = it.Next()) n += a->IsKindOf(NAME_Inventory) && !a->PointerVar<AActor>(NAME_Owner);
	return n;
}
int64_t startNs, lastNs, maxGapNs;
DVector3 playerStart, playerLast;

void Log(const FString &text) { DD_BridgeLog(("loadingtest: " + text).GetChars()); }
bool Watched(AActor *a) { return a->player || (a->flags3 & MF3_ISMONSTER) || (a->flags & MF_MISSILE); }

void Start(int64_t now)
{
	watching = true;
	askedSave = false;
	heldLevel = primaryLevel;
	snaps.clear();
	auto it = heldLevel->GetThinkerIterator<AActor>();
	while (AActor *a = it.Next()) if (Watched(a)) snaps.emplace(a, Snap{ a->Pos(), a->Angles.Yaw, a->health });
	AActor *pmo = players[consoleplayer].mo;
	playerStart = playerLast = pmo ? pmo->Pos() : DVector3();
	healthBefore = healthLast = pmo ? pmo->health : -1;
	frames = changed = 0;
	watched = int(snaps.size());
	startNs = lastNs = now;
	maxGapNs = 0;
	C_DoCommand("+forward");
	usePresses = 0;
	itemsBefore = itemsLast = MapItems();
	Log(FStringf("hold began on %s, watching %d actors, player at %.1f,%.1f,%.1f health %d", heldLevel->MapName.GetChars(), watched,
		playerStart.X, playerStart.Y, playerStart.Z, healthBefore));
}

// Each held frame: count actors whose position, facing or health differs from the first frame (new ones, such as the
// dungeon's spawn, are watched from when they appear).
void Check()
{
	int now = 0;
	auto it = heldLevel->GetThinkerIterator<AActor>();
	while (AActor *a = it.Next())
	{
		if (!Watched(a)) continue;
		const auto s = snaps.emplace(a, Snap{ a->Pos(), a->Angles.Yaw, a->health });
		if (s.second) continue;
		const Snap &b = s.first->second;
		if (a->Pos() != b.pos || a->Angles.Yaw != b.yaw || a->health != b.health)
		{
			if (changed + now < 5) Log(FStringf("changed %s at %.1f,%.1f (was %.1f,%.1f), health %d (was %d)", a->GetClass()->TypeName.GetChars(),
				a->X(), a->Y(), b.pos.X, b.pos.Y, a->health, b.health));
			now++;
		}
	}
	if (now > changed) changed = now;
	AActor *pmo = players[consoleplayer].mo;
	if (pmo) { playerLast = pmo->Pos(); healthLast = pmo->health; }
}

void AskSave()
{
	askedSave = true;
	G_SaveGame("ddloadingtest.zds", "loading test", false);
	const int menuAction = int(gameaction);
	G_SaveGame("ddloadingtest-quick.zds", "loading test quick", true);
	Log(FStringf("asked for a save and a quicksave %.0f ms into the hold: gameaction %d then %d, sendsave %d, bridge save active %d",
		DD_LoadingAgeMs(), menuAction, int(gameaction), int(sendsave), int(DD_BridgeSaveActive())));
}

void Finish(int64_t now)
{
	watching = false;
	C_DoCommand("-forward");
	Log(FStringf("result changed=%d watched=%d frames=%d max_frame_gap_ms=%.1f held_ms=%.1f player_moved=%.2f player_health=%d->%d saved=%d use_presses=%d map_items=%d->%d",
		changed, int(snaps.size()), frames, maxGapNs / 1e6, (lastNs - startNs) / 1e6, (playerLast - playerStart).Length(), healthBefore, healthLast,
		int(gameaction == ga_savegame || gameaction == ga_quicksave || DD_BridgeSaveActive()), usePresses, itemsBefore, itemsLast));
	dd_tm_use = 0;	// The last press is taken back so the test never presses into play.
	snaps.clear();
}
}

namespace
{
int blockMs = -1;	// -1 not read yet, 0 none or done

// -ddloadingblock: the injected block. Logged before and after with the shared clock, so the checker can see whether
// Daggerfall moved while Doom was blocked.
void Block()
{
	if (blockMs < 0)
	{
		const char *ms = Args->CheckValue(FArg_ddloadingblock);
		blockMs = ms ? atoi(ms) : 0;
	}
	if (blockMs <= 0 || !DD_LoadingActive() || DD_LoadingAgeMs() < 500) return;
	Log(FStringf("blocking the main thread for %d ms, %.0f ms into the hold", blockMs, DD_LoadingAgeMs()));
	std::this_thread::sleep_for(std::chrono::milliseconds(blockMs));
	Log(FStringf("block ended, hold active %d", int(DD_LoadingActive())));
	blockMs = 0;
}
}

// From DD_BridgeTestFrame, once per bridge frame between tics.
void DD_LoadingTestFrame(int64_t now)
{
	Block();
	if (enabled < 0) enabled = Args->CheckParm(FArg_ddloadingtest) > 0;
	if (!enabled) return;
	const bool held = DD_LoadingActive() && gamestate == GS_LEVEL && primaryLevel;
	if (watching && (!held || primaryLevel != heldLevel)) Finish(now);
	if (!held) return;
	if (!watching) { Start(now); return; }
	frames++;
	dd_tm_use = 1;	// Use on every held frame: it must take, talk or open nothing.
	usePresses++;
	itemsLast = MapItems();
	if (now - lastNs > maxGapNs) maxGapNs = now - lastNs;
	lastNs = now;
	Check();
	if (!askedSave && DD_LoadingAgeMs() > 1500) AskSave();
}
