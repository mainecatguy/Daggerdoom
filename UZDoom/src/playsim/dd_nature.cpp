// [Doomerfall] Daggerfall Unity's wilderness nature flats, laid out by Doom.
//
// A port of DefaultTerrainNature.LayoutNature and the parts of DefaultTerrainTexturing it reads (the tile type of each
// tile), with UnityEngine.Random, Unity.Mathematics.Random and Mathf.PerlinNoise reimplemented so the same map pixel
// gives the same flats, the same way, every time. Nothing is saved: dd_treadmill.cpp lays a pixel out again whenever
// its ground is shown, on the overworld and on generated town maps alike.
//
// DDNATURE (converter --world) holds each map pixel's climate and the nature archives' billboard scales.

#include "dd_nature.h"

#include <algorithm>
#include <cmath>
#include <cstring>

#include "c_dispatch.h"
#include "filesystem.h"

namespace
{
	constexpr int TDIM = 128, HDIM = 129, TDDIM = TDIM + 1;	// tiles, heightmap samples, tile data samples per map pixel
	constexpr int WORLD_W = 1000, WORLD_H = 500;
	constexpr float MAX_HEIGHT = 1539, OCEAN = 3.4f * 8, BEACH = 5.0f * 8;	// DefaultTerrainSampler
	constexpr float UNITS_PER_SAMPLE = 60;	// Daggerfall units per normalized height unit times MAX_HEIGHT (dd_treadmill.cpp)
	constexpr float MAX_STEEPNESS = 50, SLOPE_SINK = 70;	// DefaultTerrainNature
	constexpr float CHANCE_DIRT = 0.2f, CHANCE_GRASS = 0.9f, CHANCE_STONE = 0.05f;
	constexpr int CLEARANCE = 4, TILE_SEED = 417028, MAX_TILE_Z = 64000;

	bool loaded, present;
	std::vector<uint8_t> climate;	// rows from the north, as CLIMATE.PAK
	int firstArchive, archiveCount, recordCount;
	std::vector<float> scales;		// (archive, record) -> sx, sy

	// UnityEngine.Random: xorshift128, seeded as InitState does.
	struct UnityRandom
	{
		uint32_t x, y, z, w;
		explicit UnityRandom(int seed)
		{
			x = uint32_t(seed);
			y = x * 1812433253u + 1;
			z = y * 1812433253u + 1;
			w = z * 1812433253u + 1;
		}
		uint32_t Next()
		{
			const uint32_t t = x ^ (x << 11);
			x = y; y = z; z = w;
			return w = w ^ (w >> 19) ^ t ^ (t >> 8);
		}
		float Value() { return float(Next() & 0x7FFFFF) * (1.0f / 8388607.0f); }
		float Range(float lo, float hi) { return hi - (hi - lo) * Value(); }	// Range(0f, 1f) is 1 - value (checked against Unity)
		int Range(int lo, int hi) { return lo + int(Next() % uint32_t(hi - lo)); }
	};

	// Unity.Mathematics.Random.CreateFromIndex(index).NextFloat(lo, hi), as GenerateTileDataJob uses it for the beach line.
	float IndexedFloat(uint32_t index, float lo, float hi)
	{
		uint32_t n = index + 62u;
		n = (n ^ 61u) ^ (n >> 16);
		n *= 9u;
		n = n ^ (n >> 4);
		n *= 0x27d4eb2du;
		n = n ^ (n >> 15);
		uint32_t state = n;
		auto next = [&state]() { const uint32_t t = state; state ^= state << 13; state ^= state >> 17; state ^= state << 5; return t; };
		next();	// the constructor steps once
		const uint32_t bits = 0x3f800000u | (next() >> 9);
		float f;
		memcpy(&f, &bits, 4);
		return (f - 1.0f) * (hi - lo) + lo;
	}

	// Mathf.PerlinNoise: Ken Perlin's improved noise on the z = 0 plane, remapped to about 0..1.
	const uint8_t PERM[256] = {
		151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,
		247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,
		74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,
		65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,
		52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,
		119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,
		218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,
		184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180 };

	float Grad(int hash, float x, float y)
	{
		const int h = hash & 15;
		const float u = h < 8 ? x : y, v = h < 4 ? y : (h == 12 || h == 14) ? x : 0.f;
		return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
	}

	float UnityPerlin(float x, float y)
	{
		auto p = [](int i) { return int(PERM[i & 255]); };
		const float fx = floorf(x), fy = floorf(y);
		const int X = int(fx) & 255, Y = int(fy) & 255;
		x -= fx; y -= fy;
		const float u = x * x * x * (x * (x * 6 - 15) + 10), v = y * y * y * (y * (y * 6 - 15) + 10);
		const int A = p(X) + Y, B = p(X + 1) + Y;
		auto lerp = [](float t, float a, float b) { return a + t * (b - a); };
		// The 3D form at z = 0 keeps the z level's lookup: the hash is p(p(A) + 0), not p(A). Checked against Unity's values.
		const float n = lerp(v, lerp(u, Grad(p(p(A)), x, y), Grad(p(p(B)), x - 1, y)), lerp(u, Grad(p(p(A + 1)), x, y - 1), Grad(p(p(B + 1)), x - 1, y - 1)));
		return (n + 0.69f) / 1.483f;
	}

	// GenerateTileDataJob.GetNoise with NoiseWeight's settings.
	float TileNoise(float x, float y)
	{
		float value = 0, frequency = 0.05f, amplitude = 0.9f;
		for (int i = 0; i < 3; i++)
		{
			value += UnityPerlin(float(TILE_SEED) + x * frequency, float(TILE_SEED) + y * frequency) * amplitude;
			frequency *= 2.0f;
			amplitude *= 0.4f;
		}
		return std::clamp(value, -1.f, 1.f);
	}

	// DefaultTerrainTexturing.CreateLookupTable, without the rotate and flip bits (LayoutNature masks them off).
	struct Lookup
	{
		uint8_t t[64];
		void Range(int baseStart, int baseEnd, int shapeStart, int saddle, bool reverse, int o)
		{
			const int s = shapeStart;
			const int fwd[16] = { baseStart, s, s, s + 1, s, s + 1, saddle, s + 2, s, saddle, s + 1, s + 2, s + 1, s + 2, s + 2, baseEnd };
			const int rev[16] = { baseStart, s + 2, s + 2, s + 1, s + 2, s + 1, saddle, s, s + 2, saddle, s + 1, s, s + 1, s, s, baseEnd };
			for (int i = 0; i < 16; i++) t[o + i] = uint8_t(reverse ? rev[i] : fwd[i]);
		}
		Lookup()
		{
			Range(0, 1, 5, 48, false, 0);
			Range(2, 1, 10, 51, true, 16);
			Range(2, 3, 15, 53, false, 32);
			Range(3, 3, 15, 53, true, 48);
		}
	};

	// DefaultTerrainTexturing: tile types for one pixel (tileData), then the marching squares tile of each tile.
	void TileTypes(int px, int mapPixelY, const float *heights, uint8_t *tiles)
	{
		static const Lookup lookup;
		static uint8_t data[TDDIM * TDDIM];
		for (int index = 0; index < TDDIM * TDDIM; index++)
		{
			const int x = index % TDDIM, y = index / TDDIM;
			const int hx = int(std::clamp(float(HDIM) * (float(x) / float(TDDIM)), 0.f, float(HDIM - 1)));
			const int hy = int(std::clamp(float(HDIM) * (float(y) / float(TDDIM)), 0.f, float(HDIM - 1)));
			const float height = heights[hx * HDIM + hy] * MAX_HEIGHT;
			if (height <= OCEAN) { data[index] = 0; continue; }
			if (height <= BEACH + IndexedFloat(uint32_t(index), -1.5f, 1.5f)) { data[index] = 1; continue; }
			const int latitude = px * TDIM + x, longitude = MAX_TILE_Z - mapPixelY * TDIM + y;
			const float weight = TileNoise(float(latitude), float(longitude));
			data[index] = weight < 0.5f ? 1 : weight > 0.95f ? 3 : 2;
		}
		for (int y = 0; y < TDIM; y++)
			for (int x = 0; x < TDIM; x++)
			{
				const int i = x + y * TDDIM;
				const int b0 = data[i], b1 = data[i + 1], b2 = data[i + TDDIM], b3 = data[i + TDDIM + 1];
				const int shape = (b0 & 1) | (b1 & 1) << 1 | (b2 & 1) << 2 | (b3 & 1) << 3;
				const int ring = (b0 + b1 + b2 + b3) >> 2;
				tiles[x + y * TDIM] = lookup.t[shape | ring << 4];
			}
	}

	// TerrainData.GetSteepness at a heightmap sample: Unity's Sobel normal, in degrees.
	float Steepness(const float *heights, int x, int y)
	{
		auto h = [heights](int i, int j) { return heights[std::clamp(i, 0, HDIM - 1) * HDIM + std::clamp(j, 0, HDIM - 1)]; };
		const float dx = (h(x + 1, y - 1) + 2 * h(x + 1, y) + h(x + 1, y + 1)) - (h(x - 1, y - 1) + 2 * h(x - 1, y) + h(x - 1, y + 1));
		const float dy = (h(x - 1, y + 1) + 2 * h(x, y + 1) + h(x + 1, y + 1)) - (h(x - 1, y - 1) + 2 * h(x, y - 1) + h(x + 1, y - 1));
		const float rise = MAX_HEIGHT * UNITS_PER_SAMPLE / 256.f;	// height units per tile, in tiles
		const float nx = -dx * rise, ny = -dy * rise, up = 8;
		return acosf(up / sqrtf(nx * nx + ny * ny + up * up)) * (180.f / 3.14159265f);
	}
}

bool DDNature_Load()
{
	if (loaded) return present;
	loaded = true;
	const int lump = fileSystem.CheckNumForName("DDNATURE");
	if (lump < 0) return false;
	auto data = fileSystem.ReadFile(lump);
	const uint8_t *p = (const uint8_t *)data.data();
	const size_t size = data.size();
	auto u16 = [p](size_t at) { return int(p[at] | p[at + 1] << 8); };
	if (size < 8 || memcmp(p, "DDN1", 4) || u16(4) != WORLD_W || u16(6) != WORLD_H) return false;
	size_t at = 8 + size_t(WORLD_W) * WORLD_H;
	if (size < at + 6) return false;
	climate.assign(p + 8, p + at);
	firstArchive = u16(at); archiveCount = u16(at + 2); recordCount = u16(at + 4);
	at += 6;
	const size_t count = size_t(archiveCount) * recordCount * 2;
	if (size < at + count * 4) return false;
	scales.resize(count);
	memcpy(scales.data(), p + at, count * 4);
	present = true;
	return true;
}

int DDNature_Archive(int px, int north, bool winter)
{
	const int mapPixelY = WORLD_H - 1 - north;
	const int c = present ? climate[size_t(mapPixelY) * WORLD_W + px] : 231;
	// MapsFile.GetWorldClimateSettings' nature set, then ClimateSwaps.GetNatureArchive.
	int archive;
	switch (c)
	{
	case 224: case 225: archive = 503; break;	// desert
	case 226: archive = 510; break;				// mountain
	case 227: archive = 500; break;				// rainforest
	case 228: archive = 502; break;				// swamp
	case 229: archive = 501; break;				// subtropical
	case 230: archive = 506; break;				// mountain woods
	case 232: archive = 508; break;				// haunted woodlands
	default: archive = 504; break;				// ocean, woodlands
	}
	if (winter && (archive == 504 || archive == 506 || archive == 508 || archive == 510)) archive++;
	return archive;
}

bool DDNature_Scale(int archive, int record, float &sx, float &sy)
{
	const int a = archive - firstArchive;
	if (!present || a < 0 || a >= archiveCount || record < 0 || record >= recordCount) return false;
	sx = scales[(size_t(a) * recordCount + record) * 2];
	sy = scales[(size_t(a) * recordCount + record) * 2 + 1];
	return sx > 0 && sy > 0;
}

void DDNature_Layout(int px, int north, const float *heights, int worldHeight, const short *rect, std::vector<DDNatureFlat> &out)
{
	out.clear();
	if (!present) return;
	const int mapPixelY = WORLD_H - 1 - north;
	const int c = climate[size_t(mapPixelY) * WORLD_W + px];
	const float elevation = std::clamp(float(worldHeight) / 128.f, 0.4f, 1.0f);
	const float climateScale = (c == 224 || c == 225 || c == 229) ? 0.25f : 1.0f;	// desert base type
	const float dirt = CHANCE_DIRT * elevation * climateScale, grass = CHANCE_GRASS * elevation * climateScale, stone = CHANCE_STONE * elevation * climateScale;
	// The location rectangle, widened for clearance. Unity's Rect.Contains: min inclusive, max exclusive.
	const bool hasRect = rect && rect[0] > 0 && rect[2] > 0;
	const int rx0 = hasRect ? rect[0] - CLEARANCE : 0, rx1 = hasRect ? rect[1] + CLEARANCE : 0;
	const int ry0 = hasRect ? rect[2] - CLEARANCE : 0, ry1 = hasRect ? rect[3] + CLEARANCE : 0;

	static uint8_t tiles[TDIM * TDIM];
	TileTypes(px, mapPixelY, heights, tiles);

	UnityRandom random((short(mapPixelY) << 16) + short(px));	// TerrainHelper.MakeTerrainKey
	for (int y = 0; y < TDIM; y++)
		for (int x = 0; x < TDIM; x++)
		{
			const float steepness = Steepness(heights, x, y);
			if (steepness > MAX_STEEPNESS) continue;
			if (hasRect && x >= rx0 && x < rx1 && y >= ry0 && y < ry1) continue;
			const int tile = tiles[x + y * TDIM] & 0x3F;
			float chance;
			if (tile == 1) chance = dirt;
			else if (tile == 2) chance = grass;
			else if (tile == 3) chance = stone;
			else continue;
			if (random.Range(0.f, 1.f) > chance) continue;
			const int hx = int(std::clamp(float(HDIM) * (float(x) / float(TDIM)), 0.f, float(HDIM - 1)));
			const int hy = int(std::clamp(float(HDIM) * (float(y) / float(TDIM)), 0.f, float(HDIM - 1)));
			if (heights[hx * HDIM + hy] * MAX_HEIGHT < BEACH) continue;
			const int record = random.Range(1, 32);
			out.push_back({ uint8_t(x), uint8_t(y), uint8_t(record), steepness / SLOPE_SINK * 40.f });	// metres to Daggerfall units
		}
}

// Test only: dd_nature_dump <mapPixelX> <mapPixelY> <file> writes a pixel's layout (Daggerfall Unity's map pixel numbering),
// which tools/nature compares with Daggerfall Unity's own. Needs a running overworld.
const std::vector<DDNatureFlat> *DDTreadmill_NatureOf(int px, int north);	// dd_treadmill.cpp
CCMD(dd_nature_dump)
{
	if (argv.argc() < 4) return;
	const int px = atoi(argv[1]), north = WORLD_H - 1 - atoi(argv[2]);
	const std::vector<DDNatureFlat> *flats = DDTreadmill_NatureOf(px, north);
	FILE *f = fopen(argv[3], "w");
	if (!f) return;
	fprintf(f, "pixel %d %d archive %d flats %d\n", px, atoi(argv[2]), DDNature_Archive(px, north, false), flats ? int(flats->size()) : -1);
	if (flats) for (const DDNatureFlat &n : *flats) fprintf(f, "%d %d %d\n", n.x, n.y, n.record);
	fclose(f);
}
