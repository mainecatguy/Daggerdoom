// [Doomerfall] Holding the view after a menu that ran Daggerfall's clock (a rest, a loiter, a rented room).
//
// Daggerfall moves its people with the clock, so after hours pass they stand elsewhere. It sends its fresh townsfolk and
// NPC lists just before the menu's close (DFB_UI_CLOSED_TIME_PASSED). Until the next tic has placed them, the screen
// keeps the menu's last frame and the playsim is frozen as in the arrival wait (DD_BridgeArrivalFreeze), so nobody is
// seen jumping to a new place. Townspeople are snapped to their new places, not walked there. Nothing here runs
// without a bridge session and that flag.

#include <cstdint>
#include <cstdio>

#include "../../bridge/doomerfall_bridge.h"

struct FLevelLocals;

void DD_BridgeLog(const char *text);
bool DD_TownsfolkSnapPending();
bool DD_TownsfolkSettled();

namespace
{
constexpr int64_t ResyncLimitNs = 3000000000LL; // A list that never comes must not keep the view held.
bool pending;
int64_t startNs;
int frozenTics;

void End(const char *why)
{
	char line[160];
	snprintf(line, sizeof(line), "resync: view held %d tics, %.1f ms after the menu closed, until %s", frozenTics,
		(dfb_now_ns() - startNs) / 1e6, why);
	DD_BridgeLog(line);
	pending = false;
}
}

// HandleUiState: Daggerfall closed a menu during which game time passed.
void DD_ResyncBegin()
{
	pending = true;
	startNs = dfb_now_ns();
	frozenTics = 0;
	const bool list = DD_TownsfolkSnapPending();
	DD_BridgeLog(list ? "resync: game time passed in the menu; holding the view until the new townsfolk list is placed"
		: "resync: game time passed in the menu; no townsfolk list to place, holding the view for one tic");
}

bool DD_ResyncHolding() { return pending && dfb_now_ns() - startNs <= ResyncLimitNs; }
int64_t DD_ResyncStartNs() { return startNs; }

// From DD_BridgeArrivalFreeze in P_Ticker, after DDTreadmill_Tick has run this tic's townsfolk placement. True freezes
// the rest of the tic. The tic that placed the list is frozen too and then the hold ends, so the next frame shows it.
bool DD_ResyncFreeze(FLevelLocals *Level)
{
	if (!pending) return false;
	if (dfb_now_ns() - startNs > ResyncLimitNs)
	{
		End("the hold limit");
		return false;
	}
	frozenTics++;
	if (DD_TownsfolkSettled()) End("the people were placed");
	return true;
}
