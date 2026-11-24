// [Doomerfall] The mook placer (encounter card 5). See dd_encounter_placer.cpp.
#pragma once

#include <cstdint>
#include <vector>
#include "vectors.h"
#include "zstring.h"

class PClassActor;
struct FLevelLocals;

struct DDEncPlacementIn { uint64_t placement; DVector3 pos; int enemyType; bool quest; };
// side: -1 in a united dungeon, else the Civil War army (0 or 1); stance: Thing_Hate's type toward the player (card 6).
struct DDEncMookOut { uint64_t id; PClassActor *cls; DVector3 pos; int placement; int member; int side = -1; int stance = 0; };

// Plans the request (header = the area, location and region lines) and finds a spot for every mook. Member 0 of each
// placement is its leader, on the placement's exact point. Returns false when there is no planner.
bool DD_PlaceEncounters(FLevelLocals *Level, const FString &header, const std::vector<DDEncPlacementIn> &list, std::vector<DDEncMookOut> &out);
