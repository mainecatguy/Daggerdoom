// [Doomerfall] Locked doors. Doom owns the live lock (door_objects.zs DFDoor.lockValue): each door starts the map at the
// converted map's starting lock, the location record's door fact brings later changes (DFDoorHandler.Distill/Restore,
// dd_treadmill.cpp), and Doom runs Daggerfall's door order. Daggerfall answers only about the player's attempt.
// This file only relays:
//   mod "dfdoor_ask:<id>:<lock>"             -> DFB_KIND_DOOR_USE
//   mod "dflp_result:<id>:<hit|miss|cancel>" -> DFB_KIND_LOCKPICK, and still to the mod (it opens the door itself on a hit)
//   DFB_KIND_DOOR_STATE                      -> "dflp_start:<chance>:<id>", "dfdoor_open:<id>"
//   DFB_KIND_DOOR_TEXT                       -> Daggerfall's HUD message
// Locks hold only in a bridge session (dd_bridge_session, door_objects.zs DFDoorHandler.LocksHold).

#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>

#include "../../bridge/doomerfall_bridge.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "printf.h"

void DD_BridgeLog(const char *text);
void DD_InfoShow(const std::string &text, bool mid);

namespace
{
constexpr int MaxEventsPerFrame = 16;

std::deque<FString> toMod;
std::string pendingText;
uint32_t lastContext = ~0u;
int32_t lastTarget = -2;
bool lastInSpace;
}

// From DD_BridgeItemNetEvent. True for the door and minigame events.
bool DD_DoorsNetEvent(dfb_session *session, const char *name)
{
	const bool ask = !strncmp(name, "dfdoor_ask:", 11);
	const bool pick = !ask && !strncmp(name, "dflp_result:", 12);
	if (!ask && !pick) return false;
	dfb_door d{};
	d.kind = DFB_DOOR_DUNGEON;
	char *end = nullptr;
	d.id = strtoull(name + (ask ? 11 : 12), &end, 10);
	if (d.id == 0 || !end || *end != ':') return true; // the minigame's own test token
	if (ask) d.state = uint32_t(strtoul(end + 1, nullptr, 10));
	else d.state = !strcmp(end + 1, "hit") ? DFB_PICK_HIT : !strcmp(end + 1, "miss") ? DFB_PICK_MISS : DFB_PICK_CANCEL;
	dfb_event e{};
	e.kind = ask ? DFB_KIND_DOOR_USE : DFB_KIND_LOCKPICK;
	e.tic = gametic;
	memcpy(e.payload, &d, sizeof(d));
	dfb_send(session, &e);
	DD_BridgeLog(FStringf("doors: %s %llu state %u", ask ? "ask" : "lockpick", (unsigned long long)d.id, d.state).GetChars());
	return !pick; // the mod's door handler also hears a pick result: it opens the door on a hit
}

// Daggerfall's door events. True when the event was one.
bool DD_DoorsEvent(const dfb_event &e)
{
	if (e.kind == DFB_KIND_DOOR_TEXT)
	{
		dfb_info_text t;
		memcpy(&t, e.payload, sizeof(t));
		pendingText.append(t.text, strnlen(t.text, sizeof(t.text)));
		if (e.flags & DFB_INFO_MORE) return true;
		DD_InfoShow(pendingText, t.style == DFB_INFO_MID);
		pendingText.clear();
		return true;
	}
	if (e.kind != DFB_KIND_DOOR_STATE) return false;
	dfb_door d;
	memcpy(&d, e.payload, sizeof(d));
	const unsigned long long id = d.id;
	if (id == 0) return true;
	else if (d.flags & DFB_DOOR_PICK) toMod.push_back(FStringf("dflp_start:%d:%llu", d.chance, id));
	else if (d.flags & DFB_DOOR_OPEN) toMod.push_back(FStringf("dfdoor_open:%llu", id));
	return true;
}

// Each frame: passes Daggerfall's answers to the mod. A change of space drops answers meant for the old one.
void DD_DoorsFrame(uint32_t context, bool inSpace, int32_t target)
{
	if (context != lastContext || inSpace != lastInSpace || target != lastTarget)
	{
		lastContext = context;
		lastInSpace = inSpace;
		lastTarget = target;
		toMod.clear();
	}
	if (gamestate != GS_LEVEL || !primaryLevel) return;
	for (int i = 0; i < MaxEventsPerFrame && !toMod.empty(); i++)
	{
		if (!primaryLevel->localEventManager->SendNetworkEvent(toMod.front(), 0, 0, 0, false)) break;
		toMod.pop_front();
	}
}
