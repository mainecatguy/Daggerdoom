// [Doomerfall] Doom's side of NPC identity and presence. A generated map names each NPC, and the id lives in
// args[0] (low half) and args[1] (high half), which saves already keep. Inside a building, Daggerfall lists who is
// present, so a closed shop stays empty. Nothing here runs without a generated map that contains NPCs.

#include <cstring>
#include <unordered_set>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "printf.h"

namespace
{
std::unordered_set<uint64_t> incoming, accepted;
uint32_t acceptedGeneration, currentContext;
int32_t currentTarget = -1;
bool spaceValid, wantList, haveList;

uint64_t NpcId(const AActor *mo) { return uint64_t(uint32_t(mo->args[1])) << 32 | uint32_t(mo->args[0]); }
bool IsNpcId(uint64_t id) { return (id >> DFB_NPC_TAG_SHIFT) == DFB_NPC_TAG; }

void SendRequest(dfb_session *session)
{
	dfb_event e{};
	e.kind = DFB_KIND_NPCS_REQUEST;
	e.tic = gametic;
	const dfb_world_items body{ 0, currentContext, currentTarget, 0 };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

void ApplyList()
{
	PClassActor *cls = PClass::FindActor("DFNpc");
	if (!cls || !primaryLevel) return;
	int shown = 0, hidden = 0;
	auto it = primaryLevel->GetThinkerIterator<AActor>(cls->TypeName);
	while (AActor *mo = it.Next())
	{
		if (incoming.count(NpcId(mo))) { mo->renderflags &= ~RF_INVISIBLE; shown++; }
		else { mo->renderflags |= RF_INVISIBLE; hidden++; }
	}
	Printf("DDNPC list shown=%d hidden=%d\n", shown, hidden);
}
}

// Called for each NPC a generated map spawns. A building's people stay hidden until Daggerfall lists them.
void DD_NpcSetup(AActor *mo, uint64_t id, bool awaitList)
{
	mo->args[0] = int(uint32_t(id));
	mo->args[1] = int(uint32_t(id >> 32));
	if (awaitList && IsNpcId(id)) mo->renderflags |= RF_INVISIBLE;
}

bool DD_NpcsEvent(const dfb_event &e)
{
	switch (e.kind)
	{
	case DFB_KIND_NPCS_BEGIN:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		acceptedGeneration = spaceValid && b.context == currentContext && b.target == currentTarget ? b.generation : 0;
		accepted.clear();
		return true;
	}
	case DFB_KIND_NPC:
	{
		dfb_npc n;
		memcpy(&n, e.payload, sizeof(n));
		if (acceptedGeneration && n.generation == acceptedGeneration) accepted.insert(n.id);
		return true;
	}
	case DFB_KIND_NPCS_END:
	{
		dfb_world_items b;
		memcpy(&b, e.payload, sizeof(b));
		if (acceptedGeneration && b.generation == acceptedGeneration) { incoming = accepted; haveList = true; }
		return true;
	}
	default:
		return false;
	}
}

void DD_NpcsFrame(dfb_session *session, uint32_t context, bool inSpace, int32_t target)
{
	if (context != currentContext || inSpace != spaceValid || (inSpace && target != currentTarget))
	{
		currentContext = context;
		spaceValid = inSpace;
		currentTarget = inSpace ? target : -1;
		acceptedGeneration = 0;
		accepted.clear();
		incoming.clear();
		haveList = false;
		wantList = inSpace && context == DFB_WORLD_INTERIOR;
	}
	if (gamestate != GS_LEVEL) return;
	if (wantList)
	{
		wantList = false;
		SendRequest(session);
	}
	if (haveList)
	{
		haveList = false;
		ApplyList();
	}
}

// A load replaced every actor, so the list must be applied again.
void DD_NpcsResync()
{
	incoming.clear();
	haveList = false;
	wantList = spaceValid && currentContext == DFB_WORLD_INTERIOR;
}
