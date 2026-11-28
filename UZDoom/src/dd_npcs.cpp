// [Doomerfall] Doom's side of NPC identity and presence. A generated map names each NPC, and the id lives in
// args[0] (low half) and args[1] (high half), which saves already keep. Inside a building, Daggerfall lists who is
// present, so a closed shop stays empty. Nothing here runs without a generated map that contains NPCs.
// A quest Person Daggerfall placed at a quest marker is in no map: its list row (DFB_KIND_NPC_PLACED, sent in
// buildings and dungeons) says where Daggerfall's billboard stands, and this spawns a DFNpc there, marked by
// args[2], which moves it when Daggerfall does and removes it when a list leaves it out.

#include <cmath>
#include <cstring>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "printf.h"
#include "texturemanager.h"
#include "playsim/dd_log.h" // [Doomerfall]

namespace
{
constexpr int PlacedMark = 1; // args[2] of a DFNpc this file spawned for a quest Person
std::unordered_set<uint64_t> incoming, accepted;
std::unordered_map<uint64_t, dfb_world_item> placedIncoming, placedAccepted;
uint32_t acceptedGeneration, currentContext;
int32_t currentTarget = -1;
bool spaceValid, wantList, haveList;

uint64_t NpcId(const AActor *mo) { return uint64_t(uint32_t(mo->args[1])) << 32 | uint32_t(mo->args[0]); }
bool IsNpcId(uint64_t id) { return (id >> DFB_NPC_TAG_SHIFT) == DFB_NPC_TAG; }
bool Listed(uint32_t context) { return context == DFB_WORLD_INTERIOR || context == DFB_WORLD_DUNGEON; }

// Daggerfall's billboard for a quest Person, sized as Daggerfall draws it.
void ShowPlaced(AActor *mo, const dfb_world_item &p)
{
	mo->SetOrigin(DVector3(p.x, p.y, p.z), false);
	FTextureID tex = TexMan.CheckForTexture(FStringf("dfflat/F%03dR%02d.png", p.archive, p.record).GetChars(), ETextureType::Any, FTextureManager::TEXMAN_TryAny);
	if (!tex.isValid()) return; // The runtime package has no such billboard: the NPC keeps its picture or Doom's default.
	FGameTexture *pic = TexMan.GetGameTexture(tex);
	const double w = pic ? pic->GetDisplayWidth() : 0, h = pic ? pic->GetDisplayHeight() : 0;
	mo->picnum = tex;
	if (w > 0 && h > 0) mo->Scale = DVector2(p.width / w, p.height / h);
}

// Adds, moves and removes the quest Persons' DFNpcs to match the list. Returns how many the list holds.
int ApplyPlaced(PClassActor *cls)
{
	std::unordered_set<uint64_t> seen;
	std::vector<AActor *> gone;
	auto it = primaryLevel->GetThinkerIterator<AActor>(cls->TypeName);
	while (AActor *mo = it.Next())
	{
		if (mo->args[2] != PlacedMark) continue;
		auto row = placedIncoming.find(NpcId(mo));
		if (row == placedIncoming.end() || !seen.insert(row->first).second) { gone.push_back(mo); continue; }
		ShowPlaced(mo, row->second);
		mo->renderflags &= ~RF_INVISIBLE;
	}
	for (AActor *mo : gone) mo->Destroy();
	for (const auto &row : placedIncoming)
	{
		if (seen.count(row.first)) continue;
		AActor *mo = Spawn(primaryLevel, cls, DVector3(row.second.x, row.second.y, row.second.z), NO_REPLACE);
		if (!mo) continue;
		mo->args[0] = int(uint32_t(row.first));
		mo->args[1] = int(uint32_t(row.first >> 32));
		mo->args[2] = PlacedMark;
		ShowPlaced(mo, row.second);
		DD_DebugPrintf("DDNPC placed %016llx billboard %d/%d at %.1f,%.1f,%.1f\n", (unsigned long long)row.first, row.second.archive, row.second.record, row.second.x, row.second.y, row.second.z);
	}
	return int(placedIncoming.size());
}

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
		if (mo->args[2] == PlacedMark) continue;
		// A dungeon's list names only quest Persons; its own NPCs are DFDungeonNpc and always drawn.
		if (currentContext != DFB_WORLD_INTERIOR) continue;
		if (incoming.count(NpcId(mo))) { mo->renderflags &= ~RF_INVISIBLE; shown++; }
		else { mo->renderflags |= RF_INVISIBLE; hidden++; }
	}
	const int placed = ApplyPlaced(cls);
	DD_DebugPrintf("DDNPC list shown=%d hidden=%d placed=%d\n", shown, hidden, placed);
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
		placedAccepted.clear();
		return true;
	}
	case DFB_KIND_NPC_PLACED:
	{
		dfb_world_item p;
		memcpy(&p, e.payload, sizeof(p));
		if (acceptedGeneration && p.generation == acceptedGeneration && IsNpcId(p.id) && std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z))
			placedAccepted[p.id] = p;
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
		if (acceptedGeneration && b.generation == acceptedGeneration) { incoming = accepted; placedIncoming = placedAccepted; haveList = true; }
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
		placedAccepted.clear();
		placedIncoming.clear();
		haveList = false;
		wantList = inSpace && Listed(context);
	}
	if (gamestate != GS_LEVEL) return;
	if (wantList)
	{
		wantList = false;
		SendRequest(session);
	}
}

// The playsim tick (dd_treadmill): a list that arrived is applied here, because actors spawned outside the playsim
// do not last.
void DD_NpcsTick(FLevelLocals *Level)
{
	if (!haveList || Level != primaryLevel || gamestate != GS_LEVEL) return;
	haveList = false;
	ApplyList();
}

// A load replaced every actor, so the list must be applied again.
void DD_NpcsResync()
{
	incoming.clear();
	placedIncoming.clear();
	haveList = false;
	wantList = spaceValid && Listed(currentContext);
}
