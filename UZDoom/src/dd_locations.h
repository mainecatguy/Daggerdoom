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

// One quest placement of a dungeon's first encounter request (dd_monsters.cpp DungeonPlan), in Doom units.
struct DDPlanQuest { uint64_t placement; double x, y, z; int enemyType; };

// dd_treadmill.cpp
bool DDTreadmill_CurrentDungeon(int &mapId);
void DDTreadmill_SnapshotPlace(FLevelLocals *Level, std::vector<DDPlaceFact> &out);
void DDTreadmill_ApplyPlace(FLevelLocals *Level, int mapId, const std::vector<DDPlaceFact> &facts);

// dd_monsters.cpp
bool DD_MonstersPlanOf(int mapId, int &mooks, std::vector<DDPlanQuest> &quests);
void DD_MonstersSetPlan(int mapId, int mooks, const std::vector<DDPlanQuest> &quests);

// dd_locations.cpp
void DD_LocationsLeaving(FLevelLocals *Level);	// before the world table parks a dungeon's actors
void DD_LocationsEntered(int mapId);			// a dungeon started; Daggerfall's record is requested
bool DD_LocationsWaiting();						// the entered dungeon's record has not been applied yet
void DD_LocationsTick(FLevelLocals *Level);		// applies an arrived record, in the playsim
void DD_LocationsBeforeSave(dfb_session *session);	// sends the current dungeon's record ahead of the save request
void DD_LocationsFrame(dfb_session *session);
bool DD_LocationsEvent(const dfb_event &e);
void DD_LocationsResync();
