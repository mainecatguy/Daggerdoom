// [DoomDaggerfall] Terrain treadmill kill test. Inactive unless the map is
// TREADM01 and the game was started with -ddtreadmill <heights.bin>.
#pragma once

struct FLevelLocals;

extern bool DDTreadmill_Active;

void DDTreadmill_Tick(FLevelLocals *Level);
void DDTreadmill_FrameEnd();
void DDTreadmill_UploadBegin();
void DDTreadmill_UploadEnd();

struct DDTreadmillUploadScope
{
	bool timed;
	DDTreadmillUploadScope() : timed(DDTreadmill_Active) { if (timed) DDTreadmill_UploadBegin(); }
	~DDTreadmillUploadScope() { if (timed) DDTreadmill_UploadEnd(); }
};
