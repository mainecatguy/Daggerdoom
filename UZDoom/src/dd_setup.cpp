// [Doomerfall] Level setup gate. Some systems finish setting up a freshly loaded map only after Daggerfall answers
// (Daggerfall's arm sets the door locks; the place record brings the doors' open state and lock changes). A save taken before that would keep the half-built map, and loading it would keep
// it that way. Such a system calls DD_SetupWait when it asks and DD_SetupDone once its answer is applied; the arrival
// autosave and held autosaves wait for DD_SetupReady. A missing answer never blocks saving for longer than SetupTimeoutNs.
//
// Ordering: DD_SetupLevelLoaded runs after the map's WorldLoaded handlers and queues the network event "dd_setup_settled"
// behind every event those handlers sent. When it runs, every system that asks from WorldLoaded has already called
// DD_SetupWait. Nothing here runs without a bridge session.

#include <cstring>
#include <map>
#include <string>

#include "../../bridge/doomerfall_bridge.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "printf.h"

void DD_BridgeLog(const char *text);

namespace
{
constexpr int64_t SetupTimeoutNs = 5000000000LL;
constexpr const char *SettledEvent = "dd_setup_settled";

bool active, settled, timedOut;
int64_t loadedNs, readyNs;
std::map<std::string, int64_t> waiting; // system -> when it asked
}

// G_DoLoadLevel, after WorldLoaded, in a bridge session: a new map (or a restored one) starts its setup.
void DD_SetupLevelLoaded(bool fromSave)
{
	waiting.clear();
	timedOut = false;
	loadedNs = dfb_now_ns();
	readyNs = 0;
	active = !fromSave && primaryLevel && primaryLevel->localEventManager;
	settled = !active; // A restored map was saved after its setup, or the save was taken without it.
	if (active) primaryLevel->localEventManager->SendNetworkEvent(SettledEvent, 0, 0, 0, false);
}

void DD_SetupWait(const char *system)
{
	if (!active) return;
	waiting.emplace(system, dfb_now_ns());
	DD_BridgeLog(FStringf("setup: %s waits for Daggerfall", system).GetChars());
}

void DD_SetupDone(const char *system)
{
	const auto it = waiting.find(system);
	if (it == waiting.end()) return;
	DD_BridgeLog(FStringf("setup: %s ready, %.1f ms after it asked", system, (dfb_now_ns() - it->second) / 1e6).GetChars());
	waiting.erase(it);
}

// From DD_BridgeItemNetEvent. True for the gate's own event.
bool DD_SetupNetEvent(const char *name)
{
	if (strcmp(name, SettledEvent)) return false;
	if (active && !settled)
	{
		settled = true;
		DD_BridgeLog(FStringf("setup: map settled, %d system(s) waiting", int(waiting.size())).GetChars());
	}
	return true;
}

// True once every system that asked has its answer, or the timeout ran out.
bool DD_SetupReady(int64_t now)
{
	if (!active) return true;
	if (settled && waiting.empty())
	{
		if (!readyNs) readyNs = now;
		return true;
	}
	if (now - loadedNs <= SetupTimeoutNs) return false;
	if (!timedOut)
	{
		timedOut = true;
		FString who;
		for (const auto &w : waiting) who.AppendFormat(" %s", w.first.c_str());
		DD_BridgeLog(FStringf("setup: gave up waiting after %.1f s (settled %d, waiting:%s); saving the map as it is",
			SetupTimeoutNs / 1e9, int(settled), who.IsEmpty() ? " none" : who.GetChars()).GetChars());
	}
	return true;
}

// For the save log: how long ago the map loaded, and when its setup was first seen done (-1: not seen, or no gate).
double DD_SetupAgeMs(int64_t now) { return (now - loadedNs) / 1e6; }
double DD_SetupReadyMs() { return readyNs ? (readyNs - loadedNs) / 1e6 : -1.0; }
