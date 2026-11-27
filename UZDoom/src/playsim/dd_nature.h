// [Doomerfall] Daggerfall Unity's wilderness nature flats (DefaultTerrainNature), laid out by Doom from the same rule.
// Nothing about them is stored: the same map pixel always gives the same flats. Inactive without the DDNATURE lump.
#pragma once

#include <cstdint>
#include <vector>

struct DDNatureFlat
{
	uint8_t x, y;	// tile corner inside the map pixel, x east and y north (0..127)
	uint8_t record;	// 1..31 in the pixel's nature archive
	float sink;		// Daggerfall units the flat sits below the ground, from the slope
};

bool DDNature_Load();	// Reads DDNATURE once. False when it is missing.
// heights: the pixel's 129 x 129 normalized heights after location blending, index x * 129 + y (x east, y north).
// worldHeight: the pixel's small height map value. rect: the location's tiles x0, x1, y0, y1, or null.
// north: map pixel row counted from the south.
void DDNature_Layout(int px, int north, const float *heights, int worldHeight, const short *rect, std::vector<DDNatureFlat> &out);
int DDNature_Archive(int px, int north, bool winter);
// DefaultTerrainTexturing's ground tile of each of the pixel's 128 x 128 tiles, index x + y * 128 (x east, y north):
// the record (low 6 bits) in DDNature_GroundArchive, 64 = rotate, 128 = flip. Same heights as DDNature_Layout.
void DDNature_Tiles(int px, int north, const float *heights, uint8_t *tiles);
// TerrainMaterialProvider.GetClimateInfo: the pixel's ground archive, its snow set in winter outside deserts.
int DDNature_GroundArchive(int px, int north, bool winter);
bool DDNature_Scale(int archive, int record, float &sx, float &sy);
