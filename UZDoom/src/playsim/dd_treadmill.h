// [DoomDaggerfall] Overworld terrain treadmill. Inactive unless the current map
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

// Generated locations. All of these return false or null unless the map name is DDT<5 digits> and the runtime package is loaded.
level_info_t *DDTreadmill_FindLevelInfo(const char *mapname);
bool DDTreadmill_OpenTownMap(const char *mapname, FileSys::FileReader &reader);
bool DDTreadmill_MapMesh(const char *mapname, const uint8_t *&data, size_t &size, int &key);
bool DDTreadmill_LodMesh(const uint8_t *&data, size_t &size, int &key);
bool DDTreadmill_RuntimeTowns();

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
