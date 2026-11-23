// [DoomDaggerfall] Overworld terrain treadmill. Inactive unless the current map
// is DDOVER01 and a loaded file provides the DDWORLD terrain lump.
#pragma once

struct FLevelLocals;
class FSerializer;

extern bool DDTreadmill_Active;

void DDTreadmill_BeginMap(FLevelLocals *Level);
void DDTreadmill_Tick(FLevelLocals *Level);
bool DDTreadmill_MeshOffset(double &x, double &y, double &z);
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
