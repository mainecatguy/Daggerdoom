// [Doomerfall] Loading holds: one way to wait for a long operation without the game running on. While any system holds
// it, the playsim is frozen (P_Ticker, through DD_BridgeArrivalFreeze: no actor, player, weapon or sector special runs,
// so nothing moves or takes damage), saving is refused (dd_bridge.cpp SaveReady), and each frame draws "Loading..." with
// the console and menus over it (DD_BridgeDrawLoading), so the window stays live and the player can still quit.
// Work the system needs still runs: DDTreadmill_Tick and network events come before the freeze.
//
// A system holds by name while its condition lasts: DD_LoadingHold(name, true) when it starts (calling it again each tic
// is fine) and DD_LoadingHold(name, false) when it ends. A level load drops every hold; a system still waiting holds again.
// Work that blocks the main thread for a long time asks DD_LoadingShown first, so the message is on screen before it.
// Only Doomerfall maps hold (the treadmill and the dungeon spawn); stock maps never reach this.

#include <map>
#include <string>

#include "../../bridge/doomerfall_bridge.h"
#include "printf.h"
#include "zstring.h"

void DD_BridgeLog(const char *text);

namespace
{
std::map<std::string, int64_t> holds; // name -> when it started
int64_t sinceNs;		// when the current run of holds started
bool shown;				// a frame with the message was presented during this run
int frozenTics;
}

void DD_LoadingHold(const char *name, bool on)
{
	if (on)
	{
		const int64_t now = dfb_now_ns();
		if (holds.empty()) { sinceNs = now; shown = false; frozenTics = 0; }
		if (holds.emplace(name, now).second) DD_BridgeLog(FStringf("loading: %s holds the game", name).GetChars());
		return;
	}
	const auto it = holds.find(name);
	if (it == holds.end()) return;
	const int64_t now = dfb_now_ns();
	DD_BridgeLog(FStringf("loading: %s released after %.1f ms%s", name, (now - it->second) / 1e6, holds.size() == 1 ?
		FStringf(", game frozen %d tics, message %s", frozenTics, shown ? "shown" : "not shown").GetChars() : "").GetChars());
	holds.erase(it);
}

bool DD_LoadingActive() { return !holds.empty(); }

// For logs and safety limits: how long the current run of holds has lasted.
double DD_LoadingAgeMs() { return holds.empty() ? 0.0 : (dfb_now_ns() - sinceNs) / 1e6; }

// DD_BridgeDrawLoading, after it presented a frame with the message.
void DD_LoadingFramePresented()
{
	if (holds.empty() || shown) return;
	shown = true;
	DD_BridgeLog(FStringf("loading: message on screen, %.1f ms after the hold began", DD_LoadingAgeMs()).GetChars());
}

// True once the message has been on screen during the current hold. Blocking work holds and waits a tic for it.
bool DD_LoadingShown() { return !holds.empty() && shown; }

// DD_BridgeArrivalFreeze: a frozen tic under a hold.
void DD_LoadingFrozenTic()
{
	if (!frozenTics++) DD_BridgeLog(FStringf("loading: playsim frozen, %.1f ms after the hold began", DD_LoadingAgeMs()).GetChars());
}

// G_DoLoadLevel (DD_BridgeLevelLoaded): a new map starts with no holds.
void DD_LoadingLevelLoaded()
{
	while (!holds.empty()) DD_LoadingHold(holds.begin()->first.c_str(), false);
}
