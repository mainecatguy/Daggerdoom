// [Doomerfall] Doom's side of world items. Daggerfall lists the piles in the current space and performs
// each pickup. This file passes the list to ZScript and passes Interact back. Nothing here runs
// without a bridge session.

#include <cinttypes>
#include <cstdlib>
#include <cstring>
#include <deque>

#include "../../bridge/doomerfall_bridge.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "printf.h"

namespace
{
constexpr int MaxEventsPerFrame = 16; // Keeps a long list from overflowing one tic's network buffer.

std::deque<FString> outgoing;
uint32_t acceptedGeneration, nextRequest = 1, currentContext;
int32_t currentTarget = -1;
bool spaceValid, wantList;

void SendRequest(dfb_session *session)
{
	dfb_event e{};
	e.kind = DFB_KIND_ITEMS_REQUEST;
	e.tic = gametic;
	const dfb_world_items body{ 0, currentContext, currentTarget, 0 };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

void ShowResult(const dfb_item_result &r)
{
	char name[sizeof(r.name) + 1] = {};
	memcpy(name, r.name, sizeof(r.name));
	switch (r.status)
	{
	case DFB_ITEM_TAKEN:
		if (r.taken > 1) Printf(PRINT_HIGH, "You take %s and more (%d).\n", name, r.taken);
		else Printf(PRINT_HIGH, "You take %s.\n", name);
		break;
	case DFB_ITEM_PARTIAL:
		Printf(PRINT_HIGH, "You take what you can carry (%d). %d left.\n", r.taken, r.remaining);
		break;
	case DFB_ITEM_TOO_HEAVY:
		Printf(PRINT_HIGH, "You cannot carry any more.\n");
		break;
	case DFB_ITEM_GONE:
		Printf(PRINT_HIGH, "There is nothing there.\n");
		break;
	default:
		Printf(PRINT_HIGH, "You cannot take that now.\n");
		break;
	}
}
}

// True when the event belonged to world items.
bool DD_ItemsEvent(const dfb_event &e)
{
	switch (e.kind)
	{
	case DFB_KIND_ITEMS_BEGIN:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		// A list for a place Doom has already left is stale.
		acceptedGeneration = spaceValid && b.context == currentContext && b.target == currentTarget ? b.generation : 0;
		return true;
	}
	case DFB_KIND_ITEM:
	{
		dfb_world_item i;
		memcpy(&i, e.payload, sizeof(i));
		if (acceptedGeneration && i.generation == acceptedGeneration)
			outgoing.push_back(FStringf("dfi_item:%u:%016" PRIx64 ":%d:%d:%d:%.3f:%.3f:%.3f:%.3f:%.3f", i.generation, i.id, i.archive, i.record, i.item_count, i.x, i.y, i.z, i.width, i.height));
		return true;
	}
	case DFB_KIND_ITEMS_END:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		if (acceptedGeneration && b.generation == acceptedGeneration)
			outgoing.push_back(FStringf("dfi_end:%u:%u", b.generation, b.count));
		return true;
	}
	case DFB_KIND_ITEM_RESULT:
	{
		dfb_item_result r;
		memcpy(&r, e.payload, sizeof(r));
		ShowResult(r);
		return true;
	}
	default:
		return false;
	}
}

// Runs each frame, after Doom has published where the player is.
void DD_ItemsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target)
{
	if (context != currentContext || inSpace != spaceValid || (inSpace && target != currentTarget))
	{
		currentContext = context;
		spaceValid = inSpace;
		currentTarget = inSpace ? target : -1;
		acceptedGeneration = 0;
		outgoing.clear();
		outgoing.push_back("dfi_clear");
		wantList = inSpace;
	}
	if (wantList && gamestate == GS_LEVEL)
	{
		wantList = false;
		SendRequest(session);
	}
	if (gamestate != GS_LEVEL || !primaryLevel) return;
	for (int i = 0; i < MaxEventsPerFrame && !outgoing.empty(); i++)
	{
		if (!primaryLevel->localEventManager->SendNetworkEvent(outgoing.front(), 0, 0, 0, false)) break;
		outgoing.pop_front();
	}
}

// After a load, Doom's restored actors may not match Daggerfall until a fresh list arrives.
void DD_ItemsResync()
{
	wantList = spaceValid;
}

// ZScript names a pile with "dfi_take:<hex id>". True when the name was a take request.
bool DD_ItemsNetEvent(dfb_session *session, const char *name)
{
	static constexpr char prefix[] = "dfi_take:";
	if (strncmp(name, prefix, sizeof(prefix) - 1)) return false;
	if (!session) return true;
	dfb_item_take take{};
	take.id = strtoull(name + sizeof(prefix) - 1, nullptr, 16);
	take.request = nextRequest++;
	dfb_event e{};
	e.kind = DFB_KIND_ITEM_TAKE;
	e.tic = gametic;
	memcpy(e.payload, &take, sizeof(take));
	dfb_send(session, &e);
	return true;
}
