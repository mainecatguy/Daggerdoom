// [Doomerfall] Doom's side of Daggerfall's location ledger (dd_locations.cpp). Daggerfall keeps the permanent record
// of each place; Doom's world table (dd_treadmill.cpp) is a cache of it for this session.
#pragma once

#include <cstdint>
#include <vector>
#include "name.h"
#include "zstring.h"

class FLevelLocals;
struct dfb_session;
struct dfb_event;

// One fact about a place: a world table row, in Daggerfall units in the place's own frame.
struct DDPlaceFact
{
	uint64_t id = 0;
	FName cls = NAME_None;
	FString death;
	double x = 0, y = 0, z = 0, angle = 0, height = 0;
	int health = 0, kind = 3, amount = 0;
	bool dropped = false, session = false;	// session: the id is Doom's own for this session, not Daggerfall's
};

// A place in Daggerfall's terms (DFB_PLACE_*): a dungeon's map id, an interior's map id and building key, or an
// exterior world chunk's x and y.
struct DDPlaceKey
{
	uint32_t kind = 0;
	int mapId = 0, key = 0;
	bool operator==(const DDPlaceKey &o) const { return kind == o.kind && mapId == o.mapId && key == o.key; }
};

// One exterior chunk's facts, positions in the chunk's frame (x, y from its corner; z world height).
struct DDChunkFacts { int cx, cy; std::vector<DDPlaceFact> facts; };
struct DDChunkApplyStats { int matched = 0, rebuilt = 0, stored = 0, keptLive = 0, removed = 0; };

// One quest placement of a dungeon's first encounter request (dd_monsters.cpp DungeonPlan), in Doom units.
struct DDPlanQuest { uint64_t placement; double x, y, z; int enemyType; };

// dd_treadmill.cpp
bool DDTreadmill_CurrentDungeon(int &mapId);
bool DDTreadmill_CurrentSpace(DDPlaceKey &place);	// the dungeon or building interior the player is in
void DDTreadmill_SnapshotPlace(FLevelLocals *Level, std::vector<DDPlaceFact> &out);
void DDTreadmill_ApplyPlace(FLevelLocals *Level, const DDPlaceKey &place, const std::vector<DDPlaceFact> &facts);
void DDTreadmill_SnapshotChunks(FLevelLocals *Level, std::vector<DDChunkFacts> &out);	// changed exterior chunks; clears the change marks
void DDTreadmill_ApplyChunk(FLevelLocals *Level, int cx, int cy, const std::vector<DDPlaceFact> &facts, DDChunkApplyStats &stats);
void DDTreadmill_ForgetDirtyChunks();

// dd_monsters.cpp
bool DD_MonstersPlanOf(int mapId, int &mooks, std::vector<DDPlanQuest> &quests);
void DD_MonstersSetPlan(int mapId, int mooks, const std::vector<DDPlanQuest> &quests);

// dd_locations.cpp
void DD_LocationsLeaving(FLevelLocals *Level);	// before the world table parks a dungeon's or interior's actors
void DD_LocationsLeftExterior(FLevelLocals *Level);	// after any map's actors were parked: changed exterior chunks
void DD_LocationsEntered(const DDPlaceKey &place);	// a dungeon or interior started; Daggerfall's record is requested
bool DD_LocationsWaiting();						// the entered place's record has not been applied yet
bool DD_LocationsWorldWaiting();				// after a load, until Daggerfall's exterior chunks arrived
void DD_LocationsTick(FLevelLocals *Level);		// applies an arrived record, in the playsim
void DD_LocationsSave(dfb_session *session, const dfb_event &request);	// queues the current dungeon's record, then the save request
void DD_LocationsFrame(dfb_session *session);
bool DD_LocationsEvent(const dfb_event &e);
void DD_LocationsResync();
