// [Doomerfall] Overworld terrain treadmill. Inactive unless the current map
// is DDOVER01 and a loaded file provides the DDWORLD terrain lump.
#pragma once

#include <cstddef>
#include <cstdint>

struct FLevelLocals;
struct level_info_t;
class FSerializer;
namespace FileSys { class FileReader; }

extern bool DDTreadmill_Active;

void DDTreadmill_BeginMap(FLevelLocals *Level);
void DDTreadmill_Tick(FLevelLocals *Level);
bool DDTreadmill_MeshOffset(double &x, double &y, double &z);
enum DDPlayerArea { DD_AREA_NONE, DD_AREA_EXTERIOR, DD_AREA_INTERIOR, DD_AREA_DUNGEON };	// Same values as the bridge's DFB_WORLD_*.
DDPlayerArea DDTreadmill_PlayerWorld(double &x, double &y, double &z, double &yawDegrees);	// Position is Daggerfall world units, set only for DD_AREA_EXTERIOR.
bool DDTreadmill_WorldToLocal(double x, double y, double &doomX, double &doomY);	// Outdoors only: Daggerfall world units to Doom.
bool DDTreadmill_PlayerSpace(double &x, double &y, double &z, double &yawDegrees, int &target);	// Inside a building or dungeon: position in its own Daggerfall units. False between maps.
bool DDTreadmill_RequestTravel(double x, double y, double yawDegrees);	// Daggerfall world units. Moves the player on the next tic.
void DDTreadmill_PressDoor();	// Daggerfall's Info on a door also enters: one press of Use on a location door, on the next tic.
void DDTreadmill_RequestDungeon(int mapId, const double *start = nullptr);	// Doomerfall New Game: enters this dungeon through the current town's door on the next tic. start (x, y, z, yaw in Daggerfall space units and Doom degrees) replaces the map start.
void DDTreadmill_RequestBuilding(double doorX, double doorY, double tolerance, const double *start);	// Doomerfall plain load: enters the building whose town door is nearest this world point (within tolerance), landing at start (as RequestDungeon).
bool DDTreadmill_CurrentDoor(int &action, double &x, double &y, int &target);	// After a load: which side of which door the player is on. False off Daggerfall maps.
void DD_BridgeTransition(int action, double x, double y, int target);	// Tells Daggerfall about a door. Does nothing without a bridge session.

// Generated locations. All of these return false or null unless the map name is DDT<5 digits> and the runtime package is loaded.
level_info_t *DDTreadmill_FindLevelInfo(const char *mapname);
bool DDTreadmill_OpenTownMap(const char *mapname, FileSys::FileReader &reader);
bool DDTreadmill_MapMesh(const char *mapname, const uint8_t *&data, size_t &size, int &key);
bool DDTreadmill_LodMesh(const uint8_t *&data, size_t &size, int &key);
bool DDTreadmill_RuntimeTowns();
level_info_t *DDTreadmill_LevelInfoAt(unsigned index);	// Null past the end. Empty unless a generated location was used.
bool DDTreadmill_HandoffPending();	// True during a stitched map change. Its autosave runs before the first frame, not a tic later.

void DDTreadmill_Serialize(FLevelLocals *Level, FSerializer &arc);
void DDTreadmill_FrameEnd();
void DDTreadmill_UploadBegin();
void DDTreadmill_UploadEnd();

struct DDTreadmillUploadScope
{
	bool timed;
	DDTreadmillUploadScope() : timed(DDTreadmill_Active) { if (timed) DDTreadmill_UploadBegin(); }
	~DDTreadmillUploadScope() { if (timed) DDTreadmill_UploadEnd(); }
};
