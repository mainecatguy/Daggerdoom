// [Doomerfall] Locked doors. Daggerfall owns every lock (DFB_KIND_DOOR_*); this file relays between the bridge and the
// Doomerfall mod's door actors (door_objects.zs) and lockpicking minigame (zscript/DoomerfallLockpick.zs):
//   mod "dfdoor_use:<id>:<state>"        -> DFB_KIND_DOOR_USE
//   mod "dflp_result:<id>:<hit|miss|cancel>" -> DFB_KIND_LOCKPICK
//   DFB_KIND_DOOR_STATE                   -> "dfdoor_clear", "dfdoor_lock:<id>:<state>[:open]", "dflp_start:<chance>:<id>"
//   DFB_KIND_DOOR_TEXT                    -> Daggerfall's HUD message
// Doom never decides a lock by itself. Nothing here runs without a bridge session.

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
void DD_LookForgetDoor(uint64_t id);

namespace
{
constexpr int MaxEventsPerFrame = 16;

std::deque<FString> toMod;
std::string pendingText;
bool wantList = true;
uint32_t lastContext = ~0u;
int32_t lastTarget = -2;
bool lastInSpace;

void Send(dfb_session *session, uint16_t kind, const dfb_door &body)
{
	dfb_event e{};
	e.kind = kind;
	e.tic = gametic;
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}
}

// From DD_BridgeItemNetEvent. True for the door and minigame events.
bool DD_DoorsNetEvent(dfb_session *session, const char *name)
{
	const bool use = !strncmp(name, "dfdoor_use:", 11);
	const bool pick = !use && !strncmp(name, "dflp_result:", 12);
	if (!use && !pick) return false;
	char *end = nullptr;
	dfb_door d{};
	d.kind = DFB_DOOR_DUNGEON;
	d.id = strtoull(name + (use ? 11 : 12), &end, 10);
	if (d.id == 0 || !end || *end != ':') return true; // an old map without LoadIDs, or the minigame's own test token
	if (use) d.state = uint32_t(strtoul(end + 1, nullptr, 10));
	else d.state = !strcmp(end + 1, "hit") ? DFB_PICK_HIT : !strcmp(end + 1, "miss") ? DFB_PICK_MISS : DFB_PICK_CANCEL;
	Send(session, use ? DFB_KIND_DOOR_USE : DFB_KIND_LOCKPICK, d);
	DD_BridgeLog(FStringf("doors: %s %llu state %u", use ? "use" : "lockpick", (unsigned long long)d.id, d.state).GetChars());
	return true;
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
	if (d.flags & DFB_DOOR_LIST_BEGIN) toMod.push_back("dfdoor_clear");
	if (d.id != 0)
	{
		DD_LookForgetDoor(d.id);
		if (d.flags & DFB_DOOR_PICK) toMod.push_back(FStringf("dflp_start:%d:%llu", d.chance, (unsigned long long)d.id));
		else toMod.push_back(FStringf("dfdoor_lock:%llu:%u%s", (unsigned long long)d.id, d.state, (d.flags & DFB_DOOR_OPEN) ? ":open" : ""));
	}
	return true;
}

// Each frame. Asks for the locked list when the space changes, and passes Daggerfall's answers to the mod.
void DD_DoorsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target)
{
	if (context != lastContext || inSpace != lastInSpace || target != lastTarget)
	{
		lastContext = context;
		lastInSpace = inSpace;
		lastTarget = target;
		wantList = context == DFB_WORLD_DUNGEON && inSpace;
		toMod.clear();
	}
	if (gamestate != GS_LEVEL || !primaryLevel) return;
	if (wantList)
	{
		wantList = false;
		Send(session, DFB_KIND_DOORS_REQUEST, dfb_door{});
	}
	for (int i = 0; i < MaxEventsPerFrame && !toMod.empty(); i++)
	{
		if (!primaryLevel->localEventManager->SendNetworkEvent(toMod.front(), 0, 0, 0, false)) break;
		toMod.pop_front();
	}
}

// After a load: Doom's restored doors may not match Daggerfall's restored locks until a fresh list arrives.
void DD_DoorsResync()
{
	wantList = lastContext == DFB_WORLD_DUNGEON && lastInSpace;
}
