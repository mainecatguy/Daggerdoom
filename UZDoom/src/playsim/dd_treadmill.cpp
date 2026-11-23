// [Doomerfall] Overworld terrain treadmill.
//
// A fixed 128x128 triangle grid shows a window of real Daggerfall terrain. When
// the player nears the window edge, the floor planes are rewritten and live
// actors move back by a whole number of tiles, so travel needs no map load.
//
// Actors that leave the window are parked in a world table, in Daggerfall world
// units, and frozen there. Only things the player affected get a record.
// Untouched monsters are dropped and rebuilt from their chunk's seed.
//
// Active only on map DDOVER01 when a loaded file has a DDWORLD lump.
// Test options: -ddtmlog <frames.csv>, -ddtmverify.
//
// Town stitch: a DDTOWN lump places a generated exterior map in the world. Walking
// into its entry zone parks the window in the table and loads the town with the
// player's position, facing, and momentum. Walking past its farther exit zone does
// the reverse. Both maps read the same heights, including Daggerfall's location
// flattening (DDLOCS), so the ground matches across the handoff.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <limits>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "dd_treadmill.h"
#include "dd_towncache.h"
#include "fs_files.h"
#include "gi.h"
#include "vm.h"
#include "a_sharedglobal.h"
#include "actor.h"
#include "actorinlines.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_player.h"
#include "d_event.h"
#include "doomstat.h"
#include "filesystem.h"
#include "g_level.h"
#include "g_levellocals.h"
#include "info.h"
#include "m_argv.h"
#include "p_effect.h"
#include "p_local.h"
#include "printf.h"
#include "r_utility.h"
#include "s_sound.h"
#include "texturemanager.h"
#include "serializer.h"
#include "serializer_doom.h"

CVAR(Int, dd_tm_originx, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_originy, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_shifts, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_records, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_intown, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_stitches, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_nearest, -1, CVAR_NOSAVE)		// Nearest generated location group.
CVAR(Int, dd_tm_neareststate, 0, CVAR_NOSAVE)	// Its DDTownCache::State.
CVAR(Int, dd_tm_use, 0, CVAR_NOSAVE | CVAR_MOD)	// Test hook: one press of Use on a location door.
CVAR(String, dd_tm_warp, "", CVAR_NOSAVE | CVAR_MOD)		// "tileX tileY": moves the player through the overworld handoff. The path fast travel can use.

bool DDTreadmill_Active = false;
bool DDTreadmill_WideNodes = false;

extern gamestate_t wipegamestate;

namespace
{
	// Window layout. One tile is 256 Daggerfall units, or 192 Doom units at 75% scale.
	constexpr int CELLS = 128, VERTS = CELLS + 1, CHUNK_TILES = 32, SPACING = 192;
	constexpr double HALF = CELLS * double(SPACING) / 2;
	constexpr double SHIFT_AT = CHUNK_TILES * double(SPACING) / 2;

	// Daggerfall to Doom: doomXY = dfXY * 0.75, doomZ = dfHeight * 0.75 - Z_BASE.
	constexpr double DOOM_PER_DF = 0.75, Z_BASE = 35240;
	constexpr double DF_PER_CHUNK = CHUNK_TILES * 256.0;

	// Daggerfall Unity DefaultTerrainSampler constants.
	constexpr int WORLD_W = 1000, WORLD_H = 500, PIXEL_TILES = 128;
	constexpr float BASE_SCALE = 8, NOISE_SCALE = 4, EXTRA_SCALE = 10, OCEAN = 3.4f * BASE_SCALE, MAX_HEIGHT = 1539;
	constexpr double UNITS_PER_SAMPLE = 1.5 * 40.0;	// Daggerfall Unity's vertical terrain scale, in Daggerfall units.

	constexpr uint64_t SEED_BIT = 1ull << 62, DYNAMIC_BIT = 1ull << 63;
	constexpr int SPAWNS_PER_TIC = 64;
	constexpr double SKY_HEIGHT = 40000;

	enum RecordKind { KMonster, KCorpse, KItem, KGone };

	// The world table row. Coordinates are Daggerfall world units so that
	// Daggerfall can take over as the authority for this data.
	struct Record
	{
		uint64_t id = 0;
		FName cls = NAME_None, stateOwner = NAME_None;
		double x = 0, y = 0, z = 0, angle = 0, height = 0;
		int health = 0, kind = KGone, amount = 0, stateIdx = -1;
		bool dropped = false;
	};

	struct SeedSpawn { uint64_t id; FName cls; double x, y; };	// Global Doom XY.
	struct PendingChunk
	{
		int cx, cy;
		bool prepared = false;
		std::vector<SeedSpawn> seeds;
		std::vector<uint64_t> recs;
		size_t seedPos = 0, recPos = 0;
	};
	struct Tri { sector_t *sec; int v[3]; };

	std::vector<uint8_t> smallMap, largeMap;

	// Daggerfall's location flattening, from the DDLOCS lump. Rectangles are tiles inside the map pixel.
	struct LocRect { short x0, x1, y0, y1; };
	std::unordered_map<int, LocRect> locRects;
	std::unordered_map<int, std::vector<float>> blendCache;

	// A generated exterior map and where it sits in the world. Rectangles are global tiles.
	struct TileRect { int x0, x1, y0, y1; };
	struct SpaceLanding { int index; double x, y, z, yaw; };	// Local map units, for one exterior door.
	struct SpaceExit { double x, y, z, nx, ny; };
	struct Town
	{
		FString map;
		double originX = 0, originY = 0, ground = 0;
		int margin = 24;
		int group = -1;			// A location from the town cache. -1 for a package named on the command line.
		bool holdEntry = false;	// The player was already inside when it became ready, so it waits until they walk clear.
		TileRect visual{};
		std::vector<TileRect> rects;
		// A building interior or dungeon. It has a private area of the world table, far outside the real world.
		bool space = false;
		int spaceId = -1, dungeonMapId = 0;
		std::vector<SpaceLanding> landings;
		std::vector<SpaceExit> exits;
		// The exit line is farther out than the entry line, so the border cannot cause repeated loads.
		int EntryMargin() const { return margin - 12; }
		int ExitMargin() const { return margin - 4; }
		bool Near(double tx, double ty, double by) const
		{
			for (auto &r : rects)
				if (tx >= r.x0 - by && tx < r.x1 + by && ty >= r.y0 - by && ty < r.y1 + by) return true;
			return false;
		}
	};
	std::vector<Town> towns;
	bool townsLoaded, townActive;
	int currentTown = -1, resumeTown = -1;

	// Generated locations. The index comes from the DDGROUPS lump, and map data comes from the town cache.
	constexpr int REQUEST_TILES = 100, SCAN_TICS = 8, FLAT_CHUNKS_PER_TIC = 2, RUNTIME_MESH_KEY = 1 << 24;
	struct RuntimeGroup { std::vector<TileRect> rects; TileRect box{}; bool tooLarge = false; int town = -1; };
	std::vector<RuntimeGroup> groups;
	bool runtimeTowns;
	int lodTown = -1;
	DDTownCache::EntryPtr mapEntry, lodEntry;	// Kept alive while the current map or the distant view uses them.
	std::deque<int64_t> flatQueue;
	std::unordered_set<int64_t> flatSpawned;
	std::unordered_map<std::string, FTextureID> flatTextures;
	std::unordered_map<std::string, level_info_t *> runtimeInfoByName;
	std::deque<level_info_t> runtimeInfos;	// A deque, because the engine keeps pointers to these.

	// The player's state in world units while a map change is in flight.
	struct Handoff
	{
		bool pending = false;
		double x = 0, y = 0, z = 0, feet = 0, aboveFloor = 0;
		DVector3 vel;
		DVector2 playerVel;
		DAngle yaw, pitch;
		bool atMapStart = false;	// A dungeon entry: stay on the map's start spot and only take the facing.
		std::chrono::steady_clock::time_point started;
	} handoff;
	int stitches;

	// Doors between towns, building interiors, and dungeons.
	constexpr int SPACE_BASE = 1000000, DUNGEON_SPACE = 17000000, DOOR_PREFETCH = 2;
	constexpr double USE_REACH = 96, DOOR_CANCEL = 160, EXIT_STEP = 31.5;	// 128 Daggerfall units of reach. The step is three player radii.
	struct DoorSpot { int kind, target, index; double x, y, z, nx, ny; };
	struct ReturnPoint { bool valid = false; FString map; double x = 0, y = 0, z = 0, yaw = 0; };
	std::vector<DoorSpot> townDoors;
	ReturnPoint returnPoint;
	std::unordered_set<std::string> visitedSpaces;
	int pendingDoor = -1;
	bool useHeld;

	// The town's billboards, so trees and props look the same from the overworld. Global Doom coordinates.
	struct TownFlat { FTextureID tex; double x, y, z; float sx, sy; };
	std::unordered_map<int64_t, std::vector<TownFlat>> townFlats;
	bool flatsLoaded;
	PClassActor *flatClass;
	std::vector<float> window;
	std::vector<Tri> tris;
	int originX, originY, startTileX, startTileY, shifts, startAngle;
	FTextureID baseFloor;

	std::unordered_map<uint64_t, Record> table;
	std::unordered_map<int64_t, std::vector<uint64_t>> buckets;
	std::unordered_set<uint64_t> expected;	// Records and seeds that currently have a live actor.
	std::deque<PendingChunk> pending;
	uint64_t nextDynamic;
	bool resumePending;

	// Placeholder encounter settings from the DDWLDCFG lump. Encounter design belongs to the owner.
	double packChance = 0.2;
	int packSize = 12;
	std::vector<FName> packClasses;

	bool verify;
	FILE *frameLog, *shiftLog;
	using Clock = std::chrono::steady_clock;
	Clock::time_point lastFrame, uploadStart;
	int64_t simNs, uploadNs, uploadCount, frameNo;
	int shiftFlag, moveCount, parkCount, restoreCount;

	int FindArg(const char *name)
	{
		for (int i = 1; i < Args->NumArgs(); i++)
			if (!stricmp(Args->GetArg(i), name)) return i;
		return 0;
	}

	const char *ArgValue(const char *name)
	{
		const int i = FindArg(name);
		return i && i + 1 < Args->NumArgs() ? Args->GetArg(i + 1) : nullptr;
	}

	int64_t NsSince(Clock::time_point t)
	{
		return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - t).count();
	}

	//--------------------------------------------------------------------
	// Terrain sampling: a port of DefaultTerrainSampler.GenerateSamplesJob.
	// Mathf.PerlinNoise is native Unity code, so the small extra-noise term
	// uses a classic Perlin surrogate with the same frequencies and scale.
	//--------------------------------------------------------------------

	float Cubic(float v0, float v1, float v2, float v3, float t)
	{
		const float a = (v3 - v2) - (v0 - v1), b = (v0 - v1) - a;
		return a * t * t * t + b * t * t + (v2 - v0) * t + v1;
	}

	float SmallAt(int x, int y)
	{
		x = std::clamp(x, 0, WORLD_W - 1);
		y = std::clamp(y, 0, WORLD_H - 1);
		return smallMap[size_t(y) * WORLD_W + x];
	}

	// (a, b) index the 9x9 block that GetLargeHeightMapValuesRange(mx - 1, my, 3) returns.
	float LargeAt(int mx, int my, int a, int b)
	{
		const int px = std::clamp(mx - 1 + a / 3, 0, WORLD_W - 1), py = std::clamp(my - b / 3, 0, WORLD_H - 1);
		return largeMap[(size_t(py) * WORLD_W + px) * 9 + (b % 3) * 3 + a % 3];
	}

	const uint8_t *Permutation()
	{
		static uint8_t table[512];
		static bool ready = false;
		if (!ready)
		{
			for (int i = 0; i < 256; i++) table[i] = uint8_t(i);
			uint32_t seed = 0x5DEECE6u;
			for (int i = 255; i > 0; i--)
			{
				seed = seed * 1664525u + 1013904223u;
				std::swap(table[i], table[(seed >> 8) % (i + 1)]);
			}
			memcpy(table + 256, table, 256);
			ready = true;
		}
		return table;
	}

	float Perlin(float x, float y)
	{
		const uint8_t *p = Permutation();
		const float fx = floorf(x), fy = floorf(y);
		const int xi = int(fx) & 255, yi = int(fy) & 255;
		const float xf = x - fx, yf = y - fy;
		const float u = xf * xf * xf * (xf * (xf * 6 - 15) + 10), v = yf * yf * yf * (yf * (yf * 6 - 15) + 10);
		auto grad = [](int h, float dx, float dy) { return ((h & 1) ? -dx : dx) + ((h & 2) ? -dy : dy); };
		const float n00 = grad(p[p[xi] + yi], xf, yf), n10 = grad(p[p[xi + 1] + yi], xf - 1, yf);
		const float n01 = grad(p[p[xi] + yi + 1], xf, yf - 1), n11 = grad(p[p[xi + 1] + yi + 1], xf - 1, yf - 1);
		const float a = n00 + u * (n10 - n00), b = n01 + u * (n11 - n01);
		return std::clamp((a + v * (b - a)) * 0.5f + 0.5f, 0.f, 1.f);
	}

	// Normalized height before location flattening. (x, y) run 0..128 inside the map pixel.
	float RawHeight(int px, int north, int x, int y)
	{
		const int my = WORLD_H - 1 - north;
		const float div = PIXEL_TILES / 3.f;
		const int ix = int(floorf(x / div)), iy = int(floorf(y / div));
		const float sx = x / float(PIXEL_TILES), sy = y / float(PIXEL_TILES);
		const float fx = (x - ix * div) / div, fy = (y - iy * div) / div;

		float row[4];
		for (int r = 0; r < 4; r++)
			row[r] = Cubic(SmallAt(px - 2, my + 1 - r), SmallAt(px - 1, my + 1 - r), SmallAt(px, my + 1 - r), SmallAt(px + 1, my + 1 - r), sx);
		float h = Cubic(row[0], row[1], row[2], row[3], sy) * BASE_SCALE;

		for (int r = 0; r < 4; r++)
			row[r] = Cubic(LargeAt(px, my, ix, iy + r), LargeAt(px, my, ix + 1, iy + r), LargeAt(px, my, ix + 2, iy + r), LargeAt(px, my, ix + 3, iy + r), fx);
		h += Cubic(row[0], row[1], row[2], row[3], fy) * NOISE_SCALE;

		const int nx = px * PIXEL_TILES + x, ny = (WORLD_H - my) * PIXEL_TILES + y;	// MaxMapPixelY is 500 in Daggerfall Unity.
		h += Perlin(nx * 0.3f, ny * 0.3f) * 0.5f * Perlin(nx * 0.9f, ny * 0.9f) * 0.5f * EXTRA_SCALE;
		if (h < OCEAN) h = OCEAN;
		return std::clamp(h / MAX_HEIGHT, 0.f, 1.f);
	}

	// BlendLocationTerrainJob for one location pixel. Matches WorldTerrain.cs in the converter.
	const std::vector<float> &BlendedPixel(int px, int north, const LocRect &rect)
	{
		const int key = north * WORLD_W + px, dim = PIXEL_TILES + 1;
		auto found = blendCache.find(key);
		if (found != blendCache.end()) return found->second;
		if (blendCache.size() >= 64) blendCache.clear();
		std::vector<float> &h = blendCache[key];
		h.resize(size_t(dim) * dim);
		float sum = 0;
		for (int x = 0; x < dim; x++)
			for (int y = 0; y < dim; y++)
				sum += h[size_t(x) * dim + y] = RawHeight(px, north, x, y);
		const float target = sum / (dim * dim);
		const float x0 = rect.x0 / float(PIXEL_TILES), x1 = rect.x1 / float(PIXEL_TILES), y0 = rect.y0 / float(PIXEL_TILES), y1 = rect.y1 / float(PIXEL_TILES);
		const float left = 1 / x0, right = 1 / (1 - x1), top = 1 / y0, bottom = 1 / (1 - y1);
		for (int y = 0; y < dim; y++)
		{
			const float v = y / float(dim - 1);
			const bool insideY = v >= y0 && v <= y1;
			for (int x = 0; x < dim; x++)
			{
				const float u = x / float(dim - 1);
				const bool insideX = u >= x0 && u <= x1;
				float &value = h[size_t(x) * dim + y];
				if (insideX && insideY) { value = target; continue; }
				float strength;
				if (insideY) strength = u <= x0 ? u * left : (1 - u) * right;
				else if (insideX) strength = v <= y0 ? v * top : (1 - v) * bottom;
				else strength = (u <= x0 ? u * left : (1 - u) * right) * (v <= y0 ? v * top : (1 - v) * bottom);
				value += (target - value) * std::clamp(strength, 0.f, 1.f);
			}
		}
		return h;
	}

	// Height in Doom units at a global tile vertex (north is +Y).
	float SampleVertex(int gx, int gy)
	{
		const int px = std::min(gx / PIXEL_TILES, WORLD_W - 1), north = std::min(gy / PIXEL_TILES, WORLD_H - 1);
		const int x = gx - px * PIXEL_TILES, y = gy - north * PIXEL_TILES;
		float h;
		auto loc = locRects.find(north * WORLD_W + px);
		if (loc != locRects.end()) h = BlendedPixel(px, north, loc->second)[size_t(x) * (PIXEL_TILES + 1) + y];
		else h = RawHeight(px, north, x, y);
		return float(h * MAX_HEIGHT * UNITS_PER_SAMPLE * DOOM_PER_DF - Z_BASE);
	}

	float &WindowAt(int i, int j) { return window[size_t(j) * VERTS + i]; }

	void FillWindow(int fromI, int toI, int fromJ, int toJ)
	{
		for (int j = fromJ; j < toJ; j++)
			for (int i = fromI; i < toI; i++)
				WindowAt(i, j) = SampleVertex(originX + i, originY + j);
	}

	// Moves kept heights and samples only the newly exposed strips.
	void ScrollWindow(int dx, int dy)
	{
		std::vector<float> old = window;
		for (int j = 0; j < VERTS; j++)
			for (int i = 0; i < VERTS; i++)
			{
				const int si = i + dx, sj = j + dy;
				if (si >= 0 && si < VERTS && sj >= 0 && sj < VERTS) WindowAt(i, j) = old[size_t(sj) * VERTS + si];
			}
		if (dx > 0) FillWindow(VERTS - dx, VERTS, 0, VERTS);
		if (dx < 0) FillWindow(0, -dx, 0, VERTS);
		if (dy > 0) FillWindow(0, VERTS, VERTS - dy, VERTS);
		if (dy < 0) FillWindow(0, VERTS, 0, -dy);
	}

	double LocalCoord(int index) { return index * double(SPACING) - HALF; }

	// The town whose mesh covers part of the current window, if any.
	const Town *LodTown()
	{
		if (runtimeTowns) return lodTown >= 0 ? &towns[lodTown] : nullptr;
		for (const Town &t : towns)
			if (t.visual.x1 > originX && t.visual.x0 < originX + CELLS && t.visual.y1 > originY && t.visual.y0 < originY + CELLS) return &t;
		return nullptr;
	}

	void RewriteGrid()
	{
		const Town *lod = LodTown();
		for (auto &t : tris)
		{
			DVector3 p[3];
			for (int k = 0; k < 3; k++)
			{
				const int i = t.v[k] % VERTS, j = t.v[k] / VERTS;
				p[k] = DVector3(LocalCoord(i), LocalCoord(j), WindowAt(i, j));
			}
			DVector3 n = (p[1] - p[0]) ^ (p[2] - p[0]);
			if (n.Z < 0) n = -n;
			n /= n.Length();
			t.sec->floorplane.set(n.X, n.Y, n.Z, -(n | p[0]));
			// Where a town's mesh supplies the ground, the grid's own floor is not drawn. Collision is unchanged.
			const double cx = originX + ((p[0].X + p[1].X + p[2].X) / 3 + HALF) / SPACING, cy = originY + ((p[0].Y + p[1].Y + p[2].Y) / 3 + HALF) / SPACING;
			const bool covered = lod && cx >= lod->visual.x0 && cx < lod->visual.x1 && cy >= lod->visual.y0 && cy < lod->visual.y1;
			t.sec->SetTexture(sector_t::floor, covered ? FNullTextureID() : baseFloor, false);
			// NaN never equals the plane's TexZ, so the renderer re-uploads
			// this floor the next time the sector is actually drawn.
			for (auto &vbo : t.sec->vboheight)
				vbo[sector_t::floor] = std::numeric_limits<double>::quiet_NaN();
		}
	}

	double ExpectedZ(double x, double y)
	{
		const double s = SPACING;
		int i = std::clamp(int(floor((x + HALF) / s)), 0, CELLS - 1);
		int j = std::clamp(int(floor((y + HALF) / s)), 0, CELLS - 1);
		const double fx = (x + HALF) / s - i, fy = (y + HALF) / s - j;
		const double a = WindowAt(i, j), b = WindowAt(i + 1, j), c = WindowAt(i + 1, j + 1), d = WindowAt(i, j + 1);
		return fx >= fy ? a + fx * (b - a) + fy * (c - b) : a + fy * (d - a) + fx * (c - d);
	}

	double VerifyGrid(FLevelLocals *Level)
	{
		uint32_t seed = 12345u + shifts;
		const double range = CELLS * double(SPACING) - 2;
		double worst = 0;
		for (int n = 0; n < 512; n++)
		{
			seed = seed * 1664525u + 1013904223u;
			const double x = (seed >> 8) / double(1 << 24) * range - range / 2;
			seed = seed * 1664525u + 1013904223u;
			const double y = (seed >> 8) / double(1 << 24) * range - range / 2;
			const double z = Level->PointInSector(DVector2(x, y))->floorplane.ZatPoint(x, y);
			worst = std::max(worst, fabs(z - ExpectedZ(x, y)));
		}
		return worst;
	}

	//--------------------------------------------------------------------
	// World table
	//--------------------------------------------------------------------

	int64_t ChunkKey(int cx, int cy) { return (int64_t(cy) << 32) | uint32_t(cx); }
	int64_t RecordChunk(const Record &r)
	{
		return ChunkKey(int(floor(r.x / DF_PER_CHUNK)), int(floor(r.y / DF_PER_CHUNK)));
	}

	void Unbucket(const Record &r)
	{
		auto b = buckets.find(RecordChunk(r));
		if (b == buckets.end()) return;
		auto &v = b->second;
		v.erase(std::remove(v.begin(), v.end(), r.id), v.end());
		if (v.empty()) buckets.erase(b);
	}

	void Store(const Record &r)
	{
		auto it = table.find(r.id);
		if (it != table.end() && it->second.kind != KGone) Unbucket(it->second);
		table[r.id] = r;
		if (r.kind != KGone) buckets[RecordChunk(r)].push_back(r.id);
		dd_tm_records = int(table.size());
	}

	void MarkGone(uint64_t id)
	{
		auto it = table.find(id);
		if (id & DYNAMIC_BIT)
		{
			if (it != table.end())
			{
				if (it->second.kind != KGone) Unbucket(it->second);
				table.erase(it);
			}
			dd_tm_records = int(table.size());
			return;
		}
		Record gone = it != table.end() ? it->second : Record();
		gone.id = id;
		gone.kind = KGone;
		Store(gone);
	}

	bool IsOwned(AActor *mo)
	{
		return mo->IsKindOf(NAME_Inventory) && mo->PointerVar<AActor>(NAME_Owner) != nullptr;
	}

	// Records anything that vanished since the last check, such as a picked-up item.
	void Reconcile(FLevelLocals *Level)
	{
		std::unordered_set<uint64_t> live;
		live.reserve(expected.size() * 2);
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (!mo->ddRecordId) continue;
			if (IsOwned(mo)) mo->ddRecordId = 0;
			else live.insert(mo->ddRecordId);
		}
		for (auto e = expected.begin(); e != expected.end();)
		{
			if (live.count(*e)) { ++e; continue; }
			MarkGone(*e);
			e = expected.erase(e);
		}
	}

	// Local map position to Daggerfall world units, on whichever map is running.
	DVector3 ToWorld(const DVector3 &p, int fromX, int fromY)
	{
		if (townActive)
		{
			const Town &t = towns[currentTown];
			return DVector3(p.X / DOOM_PER_DF + t.originX, p.Y / DOOM_PER_DF + t.originY, p.Z / DOOM_PER_DF + t.ground);
		}
		return DVector3((fromX * double(SPACING) + HALF + p.X) / DOOM_PER_DF, (fromY * double(SPACING) + HALF + p.Y) / DOOM_PER_DF, (p.Z + Z_BASE) / DOOM_PER_DF);
	}

	DVector3 ToLocal(double x, double y, double z)
	{
		if (townActive)
		{
			const Town &t = towns[currentTown];
			return DVector3((x - t.originX) * DOOM_PER_DF, (y - t.originY) * DOOM_PER_DF, (z - t.ground) * DOOM_PER_DF);
		}
		return DVector3(x * DOOM_PER_DF - originX * double(SPACING) - HALF, y * DOOM_PER_DF - originY * double(SPACING) - HALF, z * DOOM_PER_DF - Z_BASE);
	}

	bool IsTouched(AActor *mo)
	{
		return mo->health < mo->SpawnHealth() || mo->target != nullptr
			|| (mo->Pos().XY() - mo->SpawnPoint.XY()).LengthSquared() > 1;
	}

	void Park(AActor *mo, int fromX, int fromY)
	{
		const bool monster = (mo->flags3 & MF3_ISMONSTER) != 0, item = mo->IsKindOf(NAME_Inventory);
		if (!monster && !item)
		{
			mo->Destroy();	// Projectiles and effects do not persist.
			return;
		}
		uint64_t id = mo->ddRecordId;
		if (id) expected.erase(id);
		if (monster && mo->health > 0 && (id & SEED_BIT) && !table.count(id) && !IsTouched(mo))
		{
			mo->Destroy();	// Untouched: its chunk seed rebuilds it.
			return;
		}
		if (!id) id = DYNAMIC_BIT | ++nextDynamic;

		Record r;
		r.id = id;
		r.cls = mo->GetClass()->TypeName;
		const DVector3 world = ToWorld(mo->Pos(), fromX, fromY);
		r.x = world.X;
		r.y = world.Y;
		r.z = world.Z;
		r.angle = mo->Angles.Yaw.Degrees();
		r.health = mo->health;
		r.height = mo->Height;
		r.dropped = (mo->flags & MF_DROPPED) != 0;
		if (item)
		{
			r.kind = KItem;
			r.amount = mo->IntVar(NAME_Amount);
		}
		else if (mo->health <= 0)
		{
			// Corpses are stored in their final frame. A death that ends in Stop leaves nothing behind.
			FState *st = mo->state;
			for (int n = 0; st && st->Tics != -1 && n < 256; n++) st = st->GetNextState();
			if (!st || st->Tics != -1)
			{
				mo->Destroy();
				MarkGone(id);
				return;
			}
			PClassActor *owner = FState::StaticFindStateOwner(st);
			if (!owner)
			{
				mo->Destroy();
				MarkGone(id);
				return;
			}
			r.kind = KCorpse;
			r.stateOwner = owner->TypeName;
			r.stateIdx = int(st - owner->GetStates());
		}
		else r.kind = KMonster;
		Store(r);
		parkCount++;
		mo->Destroy();
	}

	void Restore(FLevelLocals *Level, const Record &r)
	{
		PClassActor *cls = PClass::FindActor(r.cls);
		if (!cls) return;
		AActor *mo = Spawn(Level, cls, ToLocal(r.x, r.y, r.z), NO_REPLACE);
		if (!mo) return;
		mo->ddRecordId = r.id;
		mo->Angles.Yaw = DAngle::fromDeg(r.angle);
		mo->health = r.health;
		if (r.dropped) mo->flags |= MF_DROPPED;
		if (r.kind == KItem) mo->IntVar(NAME_Amount) = r.amount;
		if (r.kind == KCorpse)
		{
			PClassActor *owner = PClass::FindActor(r.stateOwner);
			if (owner && r.stateIdx >= 0 && r.stateIdx < owner->GetStateCount())
				mo->SetState(owner->GetStates() + r.stateIdx, true);
			mo->ClearCounters();
			mo->flags &= ~(MF_SOLID | MF_SHOOTABLE | MF_FLOAT | MF_SKULLFLY);
			mo->flags |= MF_CORPSE | MF_DROPOFF;
			mo->Height = r.height;
		}
		expected.insert(r.id);
		restoreCount++;
	}

	void LoadTownFlats()
	{
		if (flatsLoaded) return;
		flatsLoaded = true;
		flatClass = PClass::FindActor("DFCityFlat");
		const int lump = fileSystem.CheckNumForName("DFFLATS");
		if (lump < 0 || !flatClass || towns.empty()) return;
		const Town &t = towns[0];
		auto data = fileSystem.ReadFile(lump);
		FString text((const char *)data.data(), data.size());
		std::unordered_map<std::string, FTextureID> ids;
		const double chunkDoom = CHUNK_TILES * double(SPACING);
		for (auto &line : text.Split("\n"))
		{
			char name[32];
			double x, y, z;
			float sx, sy;
			if (sscanf(line.GetChars(), "%31s %lf %lf %lf %f %f", name, &x, &y, &z, &sx, &sy) != 6) continue;
			auto id = ids.find(name);
			if (id == ids.end()) id = ids.emplace(name, TexMan.CheckForTexture(name, ETextureType::Any)).first;
			const double gx = t.originX * DOOM_PER_DF + x, gy = t.originY * DOOM_PER_DF + y;
			townFlats[ChunkKey(int(floor(gx / chunkDoom)), int(floor(gy / chunkDoom)))].push_back({ id->second, gx, gy, z + t.ground * DOOM_PER_DF - Z_BASE, sx, sy });
		}
	}

	void SpawnFlats(FLevelLocals *Level, int cx, int cy)
	{
		if (runtimeTowns && !flatSpawned.insert(ChunkKey(cx, cy)).second) return;
		auto found = townFlats.find(ChunkKey(cx, cy));
		if (found == townFlats.end()) return;
		for (const TownFlat &f : found->second)
		{
			AActor *mo = Spawn(Level, flatClass, DVector3(f.x - originX * double(SPACING) - HALF, f.y - originY * double(SPACING) - HALF, f.z), NO_REPLACE);
			if (!mo) continue;
			mo->picnum = f.tex;
			mo->Scale = DVector2(f.sx, f.sy);
		}
	}

	// Deterministic placeholder pack for one chunk.
	void BuildSeeds(int cx, int cy, std::vector<SeedSpawn> &out)
	{
		out.clear();
		if (packClasses.empty() || packSize <= 0) return;
		uint64_t h = (uint64_t(uint32_t(cx)) << 32 | uint32_t(cy)) * 0x9E3779B97F4A7C15ull;
		auto next = [&h]() { h ^= h >> 29; h *= 0xBF58476D1CE4E5B9ull; h ^= h >> 32; h *= 0x94D049BB133111EBull; h ^= h >> 29; return h; };
		auto unit = [&next]() { return (next() >> 11) / double(1ull << 53); };
		if (unit() >= packChance) return;

		const double chunkDoom = CHUNK_TILES * double(SPACING), margin = 1024;
		const double cxDoom = cx * chunkDoom + margin + unit() * (chunkDoom - 2 * margin);
		const double cyDoom = cy * chunkDoom + margin + unit() * (chunkDoom - 2 * margin);
		const double start[2] = { (startTileX + CELLS / 2) * double(SPACING), (startTileY + CELLS / 2) * double(SPACING) };
		if (hypot(cxDoom - start[0], cyDoom - start[1]) < 1600) return;	// Keep the arrival point clear.
		for (const Town &t : towns)	// Placeholder packs stay out of generated towns.
			if (t.group < 0 && t.Near(cxDoom / SPACING, cyDoom / SPACING, t.margin)) return;
		// From the index, so a chunk's pack does not depend on which locations happen to be converted.
		for (const RuntimeGroup &g : groups)
		{
			const double tx = cxDoom / SPACING, ty = cyDoom / SPACING;
			if (tx < g.box.x0 - 24 || tx >= g.box.x1 + 24 || ty < g.box.y0 - 24 || ty >= g.box.y1 + 24) continue;
			for (const TileRect &r : g.rects)
				if (tx >= r.x0 - 24 && tx < r.x1 + 24 && ty >= r.y0 - 24 && ty < r.y1 + 24) return;
		}
		if (SampleVertex(int(cxDoom / SPACING), int(cyDoom / SPACING)) <= OCEAN * UNITS_PER_SAMPLE * DOOM_PER_DF - Z_BASE + 0.5) return;

		const int side = int(ceil(sqrt(double(packSize))));
		for (int n = 0; n < packSize; n++)
		{
			const double px = cxDoom + (n % side - (side - 1) / 2.0) * 80 + (unit() - 0.5) * 16;
			const double py = cyDoom + (n / side - (side - 1) / 2.0) * 80 + (unit() - 0.5) * 16;
			out.push_back({ SEED_BIT | (uint64_t(uint32_t(cy)) << 40) | (uint64_t(uint32_t(cx)) << 16) | uint64_t(n), packClasses[next() % packClasses.size()], px, py });
		}
	}

	bool ChunkInWindow(int cx, int cy)
	{
		const int x = cx * CHUNK_TILES, y = cy * CHUNK_TILES;
		return x >= originX && x < originX + CELLS && y >= originY && y < originY + CELLS;
	}

	void QueueChunk(int cx, int cy)
	{
		PendingChunk p;
		p.cx = cx;
		p.cy = cy;
		pending.push_back(std::move(p));
	}

	void ProcessPending(FLevelLocals *Level, int budget)
	{
		while (!pending.empty() && budget > 0)
		{
			PendingChunk &p = pending.front();
			if (!ChunkInWindow(p.cx, p.cy)) { pending.pop_front(); continue; }
			if (!p.prepared)
			{
				BuildSeeds(p.cx, p.cy, p.seeds);
				SpawnFlats(Level, p.cx, p.cy);
				auto b = buckets.find(ChunkKey(p.cx, p.cy));
				if (b != buckets.end()) p.recs = b->second;
				p.prepared = true;
			}
			for (; p.seedPos < p.seeds.size() && budget > 0; p.seedPos++)
			{
				const SeedSpawn &s = p.seeds[p.seedPos];
				if (table.count(s.id) || expected.count(s.id)) continue;
				PClassActor *cls = PClass::FindActor(s.cls);
				if (!cls) continue;
				const DVector3 pos(s.x - originX * double(SPACING) - HALF, s.y - originY * double(SPACING) - HALF, ONFLOORZ);
				if (AActor *mo = Spawn(Level, cls, pos, ALLOW_REPLACE))
				{
					mo->ddRecordId = s.id;
					expected.insert(s.id);
				}
				budget--;
			}
			for (; p.recPos < p.recs.size() && budget > 0; p.recPos++)
			{
				auto it = table.find(p.recs[p.recPos]);
				if (it == table.end() || it->second.kind == KGone || expected.count(it->first)) continue;
				Restore(Level, it->second);
				budget--;
			}
			if (p.seedPos >= p.seeds.size() && p.recPos >= p.recs.size()) pending.pop_front();
		}
	}

	void MoveActors(FLevelLocals *Level, const DVector3 &delta, int fromX, int fromY)
	{
		struct Moved { AActor *mo; bool onFloor; };
		static std::vector<Moved> moved;
		static std::vector<AActor *> leaving;
		moved.clear();
		leaving.clear();

		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (IsOwned(mo)) continue;
			const DVector3 target = mo->Pos() - delta;
			// Park exactly when the actor's chunk leaves. A chunk that stays is never queued again.
			if (!mo->player && (target.X < -HALF || target.X >= HALF || target.Y < -HALF || target.Y >= HALF))
			{
				leaving.push_back(mo);
				continue;
			}
			const bool onFloor = mo->Z() <= mo->floorz + 0.01;
			FLinkContext ctx;
			mo->UnlinkFromWorld(&ctx);
			mo->SetXYZ(target);
			mo->LinkToWorld(&ctx);
			mo->Prev -= delta;
			mo->SpawnPoint.X -= delta.X;
			mo->SpawnPoint.Y -= delta.Y;
			if (flatClass && mo->GetClass() == flatClass) continue;	// Billboards keep their exact height.
			moved.push_back({ mo, onFloor });
		}
		for (AActor *mo : leaving) Park(mo, fromX, fromY);
		moveCount = int(moved.size());
		for (auto &m : moved)
		{
			P_FindFloorCeiling(m.mo, FFCF_ONLYSPAWNPOS);
			if (m.onFloor) m.mo->SetZ(m.mo->floorz);
		}

		for (uint32_t p = Level->ActiveParticles; p != NO_PARTICLE; p = Level->Particles[p].tnext)
			Level->Particles[p].Pos -= delta;
		soundEngine->EnumerateChannels([&](FSoundChan *chan)
		{
			if (chan->SourceType == SOURCE_Unattached)
			{
				chan->Point[0] -= float(delta.X);
				chan->Point[2] -= float(delta.Y);
			}
			return 0;
		});
		R_ShiftPastViewers(delta);

		// Wall decals cannot follow a rewrite, and the grid's only walls are its outer border.
		for (int stat : { STAT_DECAL, STAT_AUTODECAL })
		{
			std::vector<DBaseDecal *> decals;
			auto dit = Level->GetThinkerIterator<DBaseDecal>(NAME_None, stat);
			while (DBaseDecal *d = dit.Next()) decals.push_back(d);
			for (DBaseDecal *d : decals) d->Destroy();
		}
	}

	//--------------------------------------------------------------------
	// Startup and saves
	//--------------------------------------------------------------------

	bool LoadWorld()
	{
		if (!smallMap.empty()) return true;
		const int lump = fileSystem.CheckNumForName("DDWORLD");
		if (lump < 0) return false;
		auto data = fileSystem.ReadFile(lump);
		const size_t expectSize = 8 + size_t(WORLD_W) * WORLD_H * 10;
		if (size_t(data.size()) != expectSize || memcmp(data.data(), "DDW1", 4) != 0) return false;
		const uint8_t *p = (const uint8_t *)data.data() + 8;
		smallMap.assign(p, p + size_t(WORLD_W) * WORLD_H);
		p += smallMap.size();
		largeMap.assign(p, p + size_t(WORLD_W) * WORLD_H * 9);
		locRects.clear();
		blendCache.clear();
		const int locLump = fileSystem.CheckNumForName("DDLOCS");
		if (locLump >= 0)
		{
			auto locs = fileSystem.ReadFile(locLump);
			const uint8_t *q = (const uint8_t *)locs.data();
			int count = 0;
			if (locs.size() >= 8 && !memcmp(q, "DDL1", 4)) memcpy(&count, q + 4, 4);
			if (size_t(locs.size()) == 8 + size_t(count) * 12)
				for (int i = 0; i < count; i++)
				{
					int16_t v[6];
					memcpy(v, q + 8 + i * 12, 12);
					locRects[(WORLD_H - 1 - v[1]) * WORLD_W + v[0]] = { v[2], v[3], v[4], v[5] };
				}
		}
		return true;
	}

	Town ParseTown(const char *body, size_t size)
	{
		FString text(body, size);
		Town t;
		for (auto &line : text.Split("\n"))
		{
			char key[32], a[64];
			double v1, v2;
			TileRect r;
			const char *l = line.GetChars();
			if (sscanf(l, "%31s", key) != 1) continue;
			if (!stricmp(key, "map") && sscanf(l, "%*s %63s", a) == 1) t.map = a;
			else if (!stricmp(key, "origin") && sscanf(l, "%*s %lf %lf", &v1, &v2) == 2) { t.originX = v1; t.originY = v2; }
			else if (!stricmp(key, "ground") && sscanf(l, "%*s %lf", &v1) == 1) t.ground = v1;
			else if (!stricmp(key, "margin") && sscanf(l, "%*s %lf", &v1) == 1) t.margin = int(v1);
			else if (!stricmp(key, "visual") && sscanf(l, "%*s %d %d %d %d", &r.x0, &r.x1, &r.y0, &r.y1) == 4) t.visual = r;
			else if (!stricmp(key, "rect") && sscanf(l, "%*s %d %d %d %d", &r.x0, &r.x1, &r.y0, &r.y1) == 4) t.rects.push_back(r);
		}
		return t;
	}

	void LoadGroupIndex()
	{
		const int lump = fileSystem.CheckNumForName("DDGROUPS");
		if (lump < 0 || !DDTownCache::Init()) return;
		auto data = fileSystem.ReadFile(lump);
		const uint8_t *p = (const uint8_t *)data.data(), *end = p + data.size();
		int count = 0;
		if (data.size() < 8 || memcmp(p, "DDG1", 4)) return;
		memcpy(&count, p + 4, 4);
		p += 8;
		groups.resize(count);
		for (RuntimeGroup &g : groups)
		{
			int16_t head[2];
			if (p + 4 > end) { groups.clear(); return; }
			memcpy(head, p, 4);
			p += 4;
			if (p + head[0] * 16 > end) { groups.clear(); return; }
			g.tooLarge = head[1] != 0;
			g.rects.resize(head[0]);
			memcpy(g.rects.data(), p, head[0] * 16);
			p += head[0] * 16;
			g.box = g.rects[0];
			for (const TileRect &r : g.rects)
			{
				g.box.x0 = std::min(g.box.x0, r.x0); g.box.x1 = std::max(g.box.x1, r.x1);
				g.box.y0 = std::min(g.box.y0, r.y0); g.box.y1 = std::max(g.box.y1, r.y1);
			}
		}
		runtimeTowns = !groups.empty();
		Printf("DDTCACHE index: %d location groups\n", int(groups.size()));
	}

	// Gives a space its own rectangle of world-table coordinates, beyond the 128,000-tile world.
	void PlaceSpace(Town &t, int id)
	{
		const int tileX = (1 << 22) + (id & 0xFFF) * 1024, tileY = (id >> 12) * 1024;
		t.space = true;
		t.spaceId = id;
		t.originX = tileX * 256.0;
		t.originY = tileY * 256.0;
		t.margin = 1;
		t.rects.push_back({ tileX - 400, tileX + 400, tileY - 400, tileY + 400 });
		t.visual = t.rects[0];
	}

	void LoadTowns()
	{
		if (townsLoaded) return;
		townsLoaded = true;
		int last = 0, lump;
		while ((lump = fileSystem.FindLump("DDTOWN", &last)) >= 0)
		{
			auto data = fileSystem.ReadFile(lump);
			Town t = ParseTown((const char *)data.data(), data.size());
			if (t.map.IsNotEmpty() && !t.rects.empty()) towns.push_back(std::move(t));
		}
		LoadGroupIndex();
		last = 0;
		for (int n = 0; (lump = fileSystem.FindLump("DDDUNGN", &last)) >= 0; n++)
		{
			auto data = fileSystem.ReadFile(lump);
			Town t;
			PlaceSpace(t, DUNGEON_SPACE + n);
			FString text((const char *)data.data(), data.size());
			for (auto &line : text.Split("\n"))
			{
				char name[16];
				SpaceExit e;
				if (sscanf(line.GetChars(), "mapid %d", &t.dungeonMapId) == 1) continue;	// First, because "map %s" also matches this line.
				else if (sscanf(line.GetChars(), "map %15s", name) == 1) t.map = name;
				else if (sscanf(line.GetChars(), "exit %lf %lf %lf %lf %lf", &e.x, &e.y, &e.z, &e.nx, &e.ny) == 5) t.exits.push_back(e);
			}
			if (t.map.IsNotEmpty()) towns.push_back(std::move(t));
		}
	}

	// The map name of a building interior (DDS + five base-36 digits), as a space id, or -1.
	int SpaceOfMap(const char *name)
	{
		if (strnicmp(name, "DDS", 3) || strlen(name) != 8) return -1;
		int v = 0;
		for (int i = 3; i < 8; i++)
		{
			const char c = char(toupper((unsigned char)name[i]));
			if (c >= '0' && c <= '9') v = v * 36 + (c - '0');
			else if (c >= 'A' && c <= 'Z') v = v * 36 + (c - 'A' + 10);
			else return -1;
		}
		return v + SPACE_BASE;
	}

	FString SpaceMapName(int id)
	{
		char text[9] = "DDS00000";
		for (int i = 7, v = id - SPACE_BASE; i >= 3; i--, v /= 36) text[i] = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[v % 36];
		return text;
	}

	// The town entry for an interior, built from its cache file.
	int TownForSpace(int id, const DDTownCache::EntryPtr &entry)
	{
		for (size_t i = 0; i < towns.size(); i++)
			if (towns[i].space && towns[i].spaceId == id) return int(i);
		const auto *info = entry ? entry->Find("DDTOWN") : nullptr;
		if (!info) return -1;
		Town t;
		PlaceSpace(t, id);
		t.map = SpaceMapName(id);
		FString text((const char *)info->data(), info->size());
		for (auto &line : text.Split("\n"))
		{
			SpaceLanding l;
			SpaceExit e;
			if (sscanf(line.GetChars(), "entry %d %lf %lf %lf %lf", &l.index, &l.x, &l.y, &l.z, &l.yaw) == 5) t.landings.push_back(l);
			else if (sscanf(line.GetChars(), "exit %lf %lf %lf %lf %lf", &e.x, &e.y, &e.z, &e.nx, &e.ny) == 5) t.exits.push_back(e);
		}
		if (t.landings.empty()) return -1;
		towns.push_back(std::move(t));
		return int(towns.size()) - 1;
	}

	// The group id in a generated map name (DDT + five digits), or -1.
	int GroupOfMap(const char *name)
	{
		if (strnicmp(name, "DDT", 3) || strlen(name) != 8) return -1;
		for (int i = 3; i < 8; i++) if (name[i] < '0' || name[i] > '9') return -1;
		return atoi(name + 3);
	}

	// Gives a ready group its place in the town list. Returns the town, or -1.
	int TownForGroup(int group, const DDTownCache::EntryPtr &entry)
	{
		RuntimeGroup &g = groups[group];
		if (g.town >= 0) return g.town;
		const auto *info = entry ? entry->Find("DDTOWN") : nullptr;
		if (!info) return -1;
		Town t = ParseTown((const char *)info->data(), info->size());
		if (t.map.IsEmpty() || t.rects.empty()) return -1;
		t.group = group;
		towns.push_back(std::move(t));
		return g.town = int(towns.size()) - 1;
	}

	int TownForMap(const FString &name)
	{
		for (size_t i = 0; i < towns.size(); i++)
			if (towns[i].map.CompareNoCase(name) == 0) return int(i);
		if (runtimeTowns)
			if (const int space = SpaceOfMap(name.GetChars()); space >= 0) return TownForSpace(space, DDTownCache::GetBlocking(space));
		const int group = runtimeTowns ? GroupOfMap(name.GetChars()) : -1;
		if (group < 0 || group >= int(groups.size())) return -1;
		return TownForGroup(group, DDTownCache::GetBlocking(group));
	}

	FTextureID FlatTexture(const char *name)
	{
		auto id = flatTextures.find(name);
		if (id == flatTextures.end())
			id = flatTextures.emplace(name, TexMan.CheckForTexture(name, ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup)).first;
		return id->second;
	}

	// Fresh entry to a generated location: its billboards and gates. Saves restore these as ordinary actors.
	void SpawnTownContents(FLevelLocals *Level)
	{
		if (!mapEntry) return;
		PClassActor *flat = PClass::FindActor("DFCityFlat");
		int spawned = 0;
		if (const auto *body = mapEntry->Find("DFFLATS"); body && flat)
		{
			FString text((const char *)body->data(), body->size());
			for (auto &line : text.Split("\n"))
			{
				char name[40];
				double x, y, z;
				float sx, sy;
				if (sscanf(line.GetChars(), "%39s %lf %lf %lf %f %f", name, &x, &y, &z, &sx, &sy) != 6) continue;
				const FTextureID tex = FlatTexture(name);
				if (!tex.isValid()) continue;
				AActor *mo = Spawn(Level, flat, DVector3(x, y, z), NO_REPLACE);
				if (!mo) continue;
				mo->picnum = tex;
				mo->Scale = DVector2(sx, sy);
				spawned++;
			}
		}
		VMFunction *func = nullptr;
		PClass::FindFunction(&func, "DFRuntimeTown", "SpawnGates");
		const auto *gates = mapEntry->Find("DFGATES");
		if (func && gates && gates->size() > 1)
		{
			FString text((const char *)gates->data(), gates->size());
			VMValue params[] = { &text };
			VMCall(func, params, 1, nullptr, 0);
		}
		Printf("DDTOWN contents billboards=%d\n", spawned);
	}

	// Switches which location the overworld draws in the distance.
	void SetLodTown(FLevelLocals *Level, int town)
	{
		if (town == lodTown) return;
		const auto start = Clock::now();
		lodTown = town;
		lodEntry = town >= 0 ? DDTownCache::Get(towns[town].group) : nullptr;
		if (town >= 0 && !lodEntry) lodTown = -1;
		if (!flatClass) flatClass = PClass::FindActor("DFCityFlat");
		if (flatClass)
		{
			std::vector<AActor *> old;
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next()) if (mo->GetClass() == flatClass) old.push_back(mo);
			for (AActor *mo : old) mo->Destroy();
		}
		townFlats.clear();
		flatSpawned.clear();
		flatQueue.clear();
		if (lodTown >= 0 && flatClass)
		{
			const Town &t = towns[lodTown];
			const double chunkDoom = CHUNK_TILES * double(SPACING);
			if (const auto *body = lodEntry->Find("DFFLATS"))
			{
				FString text((const char *)body->data(), body->size());
				for (auto &line : text.Split("\n"))
				{
					char name[40];
					double x, y, z;
					float sx, sy;
					if (sscanf(line.GetChars(), "%39s %lf %lf %lf %f %f", name, &x, &y, &z, &sx, &sy) != 6) continue;
					const FTextureID tex = FlatTexture(name);
					if (!tex.isValid()) continue;
					const double gx = t.originX * DOOM_PER_DF + x, gy = t.originY * DOOM_PER_DF + y;
					townFlats[ChunkKey(int(floor(gx / chunkDoom)), int(floor(gy / chunkDoom)))].push_back({ tex, gx, gy, z + t.ground * DOOM_PER_DF - Z_BASE, sx, sy });
				}
			}
			for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)
				for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++)
					flatQueue.push_back(ChunkKey(cx, cy));
		}
		RewriteGrid();
		Printf("DDTLOD town=%s ms=%.1f\n", lodTown >= 0 ? towns[lodTown].map.GetChars() : "none", NsSince(start) / 1e6);
	}

	void ProcessFlatQueue(FLevelLocals *Level, int chunks)
	{
		while (!flatQueue.empty() && chunks-- > 0)
		{
			const int64_t key = flatQueue.front();
			flatQueue.pop_front();
			const int cx = int(uint32_t(key)), cy = int(key >> 32);
			if (ChunkInWindow(cx, cy)) SpawnFlats(Level, cx, cy);
		}
	}

	// Requests nearby locations, picks the one to draw in the distance, and reports the nearest.
	void ScanLocations(FLevelLocals *Level, AActor *pmo)
	{
		const double tx = originX + (pmo->X() + HALF) / SPACING, ty = originY + (pmo->Y() + HALF) / SPACING;
		int nearest = -1, bestLod = -1;
		double nearestDist = 1e30, bestLodDist = 1e30;
		DDTownCache::BeginScan();
		for (int n = 0; n < int(groups.size()); n++)
		{
			RuntimeGroup &g = groups[n];
			const double dx = std::max({ g.box.x0 - tx, tx - g.box.x1, 0.0 }), dy = std::max({ g.box.y0 - ty, ty - g.box.y1, 0.0 });
			const double dist = std::max(dx, dy);
			if (dist > REQUEST_TILES) continue;
			if (dist < nearestDist) { nearestDist = dist; nearest = n; }
			if (g.tooLarge) continue;
			DDTownCache::Request(n, dist);
			if (DDTownCache::Status(n) != DDTownCache::State::Ready) continue;
			const int town = TownForGroup(n, DDTownCache::Get(n));
			if (town < 0) continue;
			Town &t = towns[town];
			// A location that finished while the player stands in it appears only after they walk clear.
			if (t.Near(tx, ty, 0)) t.holdEntry = true;
			else if (!t.Near(tx, ty, t.EntryMargin())) t.holdEntry = false;
			const bool inWindow = t.visual.x1 > originX && t.visual.x0 < originX + CELLS && t.visual.y1 > originY && t.visual.y0 < originY + CELLS;
			if (inWindow && !t.holdEntry && dist < bestLodDist) { bestLodDist = dist; bestLod = town; }
		}
		dd_tm_nearest = nearest;
		dd_tm_neareststate = nearest >= 0 ? int(DDTownCache::Status(nearest)) : 0;
		SetLodTown(Level, bestLod);
	}

	// Text settings, one "key value" per line.
	void LoadConfig()
	{
		startTileX = 862 * PIXEL_TILES;
		startTileY = (WORLD_H - 1 - 442) * PIXEL_TILES;
		startAngle = 0;
		packClasses.clear();
		const int lump = fileSystem.CheckNumForName("DDWLDCFG");
		if (lump < 0) return;
		auto data = fileSystem.ReadFile(lump);
		FString text((const char *)data.data(), data.size());
		for (auto &line : text.Split("\n"))
		{
			char key[32], value[512];
			if (sscanf(line.GetChars(), "%31s %511s", key, value) != 2) continue;
			if (!stricmp(key, "starttilex")) startTileX = atoi(value);
			else if (!stricmp(key, "starttiley")) startTileY = atoi(value);
			else if (!stricmp(key, "startangle")) startAngle = atoi(value);
			else if (!stricmp(key, "packchance")) packChance = atof(value);
			else if (!stricmp(key, "packsize")) packSize = atoi(value);
			else if (!stricmp(key, "classes"))
				for (auto &name : FString(value).Split(",")) packClasses.push_back(FName(name.GetChars()));
		}
		startTileX = std::clamp(startTileX & ~(CHUNK_TILES - 1), 0, WORLD_W * PIXEL_TILES - CELLS);
		startTileY = std::clamp(startTileY & ~(CHUNK_TILES - 1), 0, WORLD_H * PIXEL_TILES - CELLS);
	}

	bool BuildTriangles(FLevelLocals *Level)
	{
		tris.clear();
		tris.reserve(Level->sectors.Size());
		for (auto &sec : Level->sectors)
		{
			if (sec.Lines.Size() != 3) return false;
			vertex_t *a = sec.Lines[0]->v1, *b = sec.Lines[0]->v2, *l = sec.Lines[1]->v1;
			vertex_t *c = (l == a || l == b) ? sec.Lines[1]->v2 : l;
			Tri t{ &sec, {} };
			vertex_t *vs[3] = { a, b, c };
			for (int k = 0; k < 3; k++)
			{
				const double fi = (vs[k]->fX() + HALF) / SPACING, fj = (vs[k]->fY() + HALF) / SPACING;
				const int i = int(lround(fi)), j = int(lround(fj));
				if (fabs(fi - i) > 1e-6 || fabs(fj - j) > 1e-6 || i < 0 || j < 0 || i > CELLS || j > CELLS) return false;
				t.v[k] = j * VERTS + i;
			}
			tris.push_back(t);
		}
		return true;
	}

	bool PrepareLevel(FLevelLocals *Level)
	{
		if (multiplayer || Level->MapName.CompareNoCase("DDOVER01") != 0 || Level->sectors.Size() != size_t(CELLS) * CELLS * 2) return false;
		if (!LoadWorld() || !BuildTriangles(Level))
		{
			Printf("DDTM failed to start\n");
			return false;
		}
		verify = FindArg("-ddtmverify") != 0;
		if (const char *logPath = ArgValue("-ddtmlog"); logPath && !frameLog)
		{
			frameLog = fopen(logPath, "w");
			if (frameLog) fputs("frame,tic,frame_us,sim_us,upload_us,uploads,shift,converting\n", frameLog);
			shiftLog = fopen((FString(logPath) + ".shifts.csv").GetChars(), "w");
			if (shiftLog) fputs("shift,origin_x,origin_y,rewrite_us,total_us,moved,parked,plane_err\n", shiftLog);
		}
		// UDMF rejects heights past 32768, but the highest terrain reaches about 34015.
		for (auto &t : tris)
		{
			t.sec->ceilingplane.set(0, 0, -1, SKY_HEIGHT);
			for (auto &vbo : t.sec->vboheight)
				vbo[sector_t::ceiling] = std::numeric_limits<double>::quiet_NaN();
		}
		// A restored save can have this sector's floor hidden under a town mesh, so look the ground up by name.
		baseFloor = TexMan.CheckForTexture("DFGROUND", ETextureType::Flat);
		if (!baseFloor.isValid()) baseFloor = TexMan.CheckForTexture("RROCK19", ETextureType::Flat);
		window.resize(size_t(VERTS) * VERTS);
		FillWindow(0, VERTS, 0, VERTS);
		RewriteGrid();
		dd_tm_originx = originX;
		dd_tm_originy = originY;
		dd_tm_shifts = shifts;
		dd_tm_records = int(table.size());
		lastFrame = Clock::now();
		return true;
	}

	void SettleActors(FLevelLocals *Level, bool snapToFloor)
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (IsOwned(mo)) continue;
			P_FindFloorCeiling(mo, FFCF_ONLYSPAWNPOS);
			if (snapToFloor && !(mo->flags & MF_NOGRAVITY)) mo->SetZ(mo->floorz);
			mo->ClearInterpolation();
		}
		for (int i = 0; i < MAXPLAYERS; i++)
			if (Level->PlayerInGame(i) && Level->Players[i]->mo)
				Level->Players[i]->viewz = Level->Players[i]->mo->Z() + Level->Players[i]->viewheight;
	}

	//--------------------------------------------------------------------
	// Town stitch
	//--------------------------------------------------------------------

	// Parks every monster and item, then records the player and requests the other map.
	// The one place Daggerfall will be told about a door transition. Position sync is a separate lane.
	void NotifyTransition(const char *kind, const char *from, const char *to)
	{
		Printf("DDTRANSITION %s from=%s to=%s\n", kind, from, to);
	}

	struct DoorTarget { double x, y, z, yaw; bool atMapStart; };

	void BeginHandoff(FLevelLocals *Level, AActor *pmo, const char *map, const int *warpTile = nullptr, const DoorTarget *door = nullptr)
	{
		Reconcile(Level);
		std::vector<AActor *> keep;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (!mo->player && !IsOwned(mo) && ((mo->flags3 & MF3_ISMONSTER) || mo->IsKindOf(NAME_Inventory)))
				keep.push_back(mo);
		for (AActor *mo : keep) Park(mo, originX, originY);

		// This tic's move still happens on the old map, so the arrival point is one tic ahead.
		const DVector3 world = ToWorld(pmo->Pos() + pmo->Vel, originX, originY);
		handoff.pending = true;
		handoff.x = world.X;
		handoff.y = world.Y;
		handoff.z = world.Z;
		handoff.feet = world.Z - pmo->Vel.Z / DOOM_PER_DF;
		handoff.aboveFloor = std::max(0.0, pmo->Z() + pmo->Vel.Z - pmo->floorz);
		handoff.vel = pmo->Vel;
		handoff.playerVel = pmo->player->Vel;
		handoff.yaw = pmo->Angles.Yaw;
		handoff.pitch = pmo->Angles.Pitch;
		handoff.started = Clock::now();
		if (warpTile)	// A direct move to a world position, standing still on the ground there.
		{
			handoff.x = (warpTile[0] + 0.5) * 256;
			handoff.y = (warpTile[1] + 0.5) * 256;
			handoff.z = handoff.feet = (SampleVertex(warpTile[0], warpTile[1]) + Z_BASE) / DOOM_PER_DF;
			handoff.aboveFloor = 0;
			handoff.vel = DVector3(0, 0, 0);
			handoff.playerVel = DVector2(0, 0);
		}
		handoff.atMapStart = false;
		if (door)	// Through a door: world position in the destination's coordinates, standing still.
		{
			handoff.x = door->x;
			handoff.y = door->y;
			handoff.z = handoff.feet = door->z;
			handoff.aboveFloor = 0;
			handoff.vel = DVector3(0, 0, 0);
			handoff.playerVel = DVector2(0, 0);
			handoff.yaw = DAngle::fromDeg(door->yaw);
			handoff.pitch = nullAngle;
			handoff.atMapStart = door->atMapStart;
		}
		Printf("DDSTITCH leave %s tic=%d world=%.2f,%.2f,%.2f vel=%.2f,%.2f,%.2f records=%d\n", Level->MapName.GetChars(), Level->maptime, world.X, world.Y, world.Z, pmo->Vel.X, pmo->Vel.Y, pmo->Vel.Z, int(table.size()));
		Level->ChangeLevel(map, 0, CHANGELEVEL_NOINTERMISSION | CHANGELEVEL_KEEPFACING | CHANGELEVEL_PRERAISEWEAPON);
	}

	void FinishHandoff(FLevelLocals *Level)
	{
		if (!handoff.pending) return;
		handoff.pending = false;
		player_t *player = Level->Players[consoleplayer];
		AActor *pmo = player->mo;
		if (!pmo) return;
		const DVector3 target = handoff.atMapStart ? pmo->Pos() : ToLocal(handoff.x, handoff.y, handoff.z);
		FLinkContext ctx;
		pmo->UnlinkFromWorld(&ctx);
		pmo->SetXYZ(target);
		pmo->LinkToWorld(&ctx);
		P_FindFloorCeiling(pmo, FFCF_ONLYSPAWNPOS);
		if (handoff.atMapStart) handoff.feet = handoff.z = pmo->floorz / DOOM_PER_DF + towns[currentTown].ground;
		// Keep the feet the same distance above whatever ground is here. The mismatch is reported, not shown.
		const double z = pmo->floorz + handoff.aboveFloor;
		const double dz = z - ToLocal(handoff.x, handoff.y, handoff.feet).Z;	// Height change across the handoff, including one tic of slope.
		pmo->SetZ(z);
		pmo->Vel = handoff.vel;
		player->Vel = handoff.playerVel;
		pmo->Angles.Yaw = handoff.yaw;
		pmo->Angles.Pitch = handoff.pitch;
		pmo->ClearInterpolation();
		player->viewz = z + player->viewheight;
		wipegamestate = gamestate;	// No screen wipe on a stitched change.
		dd_tm_stitches = ++stitches;
		Printf("DDSTITCH arrive %s ms=%.1f local=%.2f,%.2f,%.2f dz=%.3f records=%d stitches=%d\n", Level->MapName.GetChars(),
			NsSince(handoff.started) / 1e6, target.X, target.Y, z, dz, int(table.size()), stitches);
	}

	// Compares the town map's real floors with the overworld height function across the handoff band.
	void VerifySeam(FLevelLocals *Level, const Town &t)
	{
		const int band = t.margin - 1;
		double worst = 0, sum = 0;
		int count = 0, worstX = 0, worstY = 0, over01 = 0, over1 = 0, over10 = 0, logged = 0;
		const double zShift = t.ground * DOOM_PER_DF - Z_BASE;
		for (const TileRect &r : t.rects)
			for (int gy = r.y0 - band; gy < r.y1 + band; gy++)
				for (int gx = r.x0 - band; gx < r.x1 + band; gx++)
				{
					if (t.Near(gx, gy, 0) || t.Near(gx + 1, gy, 0) || t.Near(gx, gy + 1, 0) || t.Near(gx + 1, gy + 1, 0)) continue;
					const double a = SampleVertex(gx, gy), b = SampleVertex(gx + 1, gy), c = SampleVertex(gx + 1, gy + 1), d = SampleVertex(gx, gy + 1);
					for (int k = 0; k < 2; k++)
					{
						const double fx = k ? 0.25 : 0.75, fy = k ? 0.75 : 0.25;
						const double expected = (fx >= fy ? a + fx * (b - a) + fy * (c - b) : a + fy * (d - a) + fx * (c - d)) - zShift;
						const double x = (gx + fx) * 256 - t.originX, y = (gy + fy) * 256 - t.originY;
						const double lx = x * DOOM_PER_DF, ly = y * DOOM_PER_DF;
						const double actual = Level->PointInSector(DVector2(lx, ly))->floorplane.ZatPoint(lx, ly);
						const double err = fabs(actual - expected);
						sum += err;
						count++;
						over01 += err > 0.1;
						over1 += err > 1;
						over10 += err > 10;
						if (err > 10 && logged < 6)
						{
							logged++;
							const sector_t *sec = Level->PointInSector(DVector2(lx, ly));
							Printf("DDSEAM far tile=%d,%d f=%.2f,%.2f local=%.0f,%.0f floor=%.2f expected=%.2f sector=%d lines=%d center=%.0f,%.0f\n", gx, gy, fx, fy, lx, ly, actual, expected, sec->Index(), int(sec->Lines.Size()), sec->centerspot.X, sec->centerspot.Y);
						}
						if (err > worst) { worst = err; worstX = gx; worstY = gy; }
					}
				}
		Printf("DDSEAM points=%d mean=%.4f worst=%.4f at tile %d,%d over0.1=%d over1=%d over10=%d\n", count, count ? sum / count : 0.0, worst, worstX, worstY, over01, over1, over10);
	}

	void LoadTownDoors(const Town &t)
	{
		townDoors.clear();
		if (t.space || t.group < 0 || !mapEntry) return;
		const auto *body = mapEntry->Find("DDDOORS");
		if (!body) return;
		FString text((const char *)body->data(), body->size());
		for (auto &line : text.Split("\n"))
		{
			DoorSpot d;
			if (sscanf(line.GetChars(), "%d %d %d %lf %lf %lf %lf %lf", &d.kind, &d.target, &d.index, &d.x, &d.y, &d.z, &d.nx, &d.ny) == 8) townDoors.push_back(d);
		}
		Printf("DDDOORS %d doors\n", int(townDoors.size()));
	}

	// True when the player can reach a door: close, on its front side, and looking toward it.
	bool CanUse(AActor *pmo, double x, double y, double z, double nx, double ny, double &distance)
	{
		const double dx = x - pmo->X(), dy = y - pmo->Y();
		distance = sqrt(dx * dx + dy * dy);
		if (distance > USE_REACH || fabs(z - pmo->Z()) > USE_REACH) return false;
		if (dx * nx + dy * ny > 0) return false;	// Behind the door.
		if (distance < 1) return true;
		const DVector2 view = pmo->Angles.Yaw.ToVector();
		return (dx * view.X + dy * view.Y) / distance > 0.5;
	}

	int DungeonTown(int mapId)
	{
		for (size_t i = 0; i < towns.size(); i++)
			if (towns[i].space && towns[i].dungeonMapId == mapId) return int(i);
		return -1;
	}

	// Goes through a town door. False means the destination is not ready yet.
	bool EnterDoor(FLevelLocals *Level, AActor *pmo, const DoorSpot &d)
	{
		const Town &from = towns[currentTown];
		const FString fromMap = from.map;
		DoorTarget target{};
		FString map;
		if (d.kind == 0)
		{
			if (DDTownCache::Status(d.target) != DDTownCache::State::Ready) return false;
			const int index = TownForSpace(d.target, DDTownCache::Get(d.target));
			if (index < 0) return false;
			const Town &space = towns[index];
			const SpaceLanding *landing = &space.landings[0];
			for (const SpaceLanding &l : space.landings) if (l.index == d.index) landing = &l;
			target = { landing->x / DOOM_PER_DF + space.originX, landing->y / DOOM_PER_DF + space.originY, landing->z / DOOM_PER_DF, landing->yaw, false };
			map = space.map;
		}
		else
		{
			const int index = DungeonTown(d.target);
			if (index < 0) return false;
			const Town &space = towns[index];
			target = { space.originX, space.originY, 0, space.exits.empty() ? pmo->Angles.Yaw.Degrees() : atan2(space.exits[0].ny, space.exits[0].nx) * 180 / M_PI, true };
			map = space.map;
		}
		const Town &origin = towns[currentTown];	// TownForSpace can grow the list.
		returnPoint.valid = true;
		returnPoint.map = fromMap;
		returnPoint.x = (d.x + d.nx * EXIT_STEP) / DOOM_PER_DF + origin.originX;
		returnPoint.y = (d.y + d.ny * EXIT_STEP) / DOOM_PER_DF + origin.originY;
		returnPoint.z = d.z / DOOM_PER_DF + origin.ground;
		returnPoint.yaw = atan2(d.ny, d.nx) * 180 / M_PI;
		NotifyTransition(d.kind == 0 ? "enter-building" : "enter-dungeon", fromMap.GetChars(), map.GetChars());
		BeginHandoff(Level, pmo, map.GetChars(), nullptr, &target);
		return true;
	}

	void TickTownDoors(FLevelLocals *Level, AActor *pmo)
	{
		const bool down = (pmo->player->cmd.buttons & BT_USE) != 0, pressed = (down && !useHeld) || dd_tm_use != 0;
		useHeld = down;
		if (dd_tm_use != 0) dd_tm_use = 0;
		if (handoff.pending || pmo->health <= 0) return;
		const Town &t = towns[currentTown];
		if (t.space)
		{
			if (!pressed || !returnPoint.valid) return;
			double distance;
			for (const SpaceExit &e : t.exits)
				if (CanUse(pmo, e.x, e.y, e.z, e.nx, e.ny, distance))
				{
					const DoorTarget target{ returnPoint.x, returnPoint.y, returnPoint.z, returnPoint.yaw, false };
					const FString back = returnPoint.map;
					returnPoint.valid = false;
					NotifyTransition(t.spaceId >= DUNGEON_SPACE ? "exit-dungeon" : "exit-building", t.map.GetChars(), back.GetChars());
					BeginHandoff(Level, pmo, back.GetChars(), nullptr, &target);
					return;
				}
			return;
		}
		if (townDoors.empty()) return;
		if (Level->maptime % SCAN_TICS == 0)	// Convert the nearest interiors before the player reaches them.
		{
			std::vector<std::pair<double, int>> near;
			for (const DoorSpot &d : townDoors)
				if (d.kind == 0)
				{
					const double dist = (DVector2(d.x, d.y) - pmo->Pos().XY()).Length();
					if (dist < 768) near.push_back({ dist, d.target });
				}
			std::sort(near.begin(), near.end());
			DDTownCache::BeginScan();
			if (pendingDoor >= 0 && townDoors[pendingDoor].kind == 0) DDTownCache::Request(townDoors[pendingDoor].target, 0);
			int requested = 0, lastId = -1;
			for (auto &n : near)
				if (n.second != lastId && requested < DOOR_PREFETCH) { DDTownCache::Request(n.second, n.first + 1); lastId = n.second; requested++; }
		}
		if (pendingDoor >= 0)
		{
			const DoorSpot d = townDoors[pendingDoor];
			if ((DVector2(d.x, d.y) - pmo->Pos().XY()).Length() > DOOR_CANCEL) pendingDoor = -1;
			else if (DDTownCache::Status(d.target) == DDTownCache::State::Failed) { Printf(PRINT_HIGH, "This door will not open.\n"); pendingDoor = -1; }
			else if (EnterDoor(Level, pmo, d)) pendingDoor = -1;
			return;
		}
		if (!pressed) return;
		int best = -1;
		double bestDistance = USE_REACH + 1, distance;
		for (size_t i = 0; i < townDoors.size(); i++)
		{
			const DoorSpot &d = townDoors[i];
			if (CanUse(pmo, d.x, d.y, d.z, d.nx, d.ny, distance) && distance < bestDistance) { best = int(i); bestDistance = distance; }
		}
		if (best < 0) return;
		const DoorSpot d = townDoors[best];
		if (d.kind == 1 && DungeonTown(d.target) < 0) { Printf(PRINT_HIGH, "This dungeon is not available yet.\n"); return; }
		if (EnterDoor(Level, pmo, d)) return;
		pendingDoor = best;
		DDTownCache::Request(d.target, 0);
		Printf(PRINT_HIGH, "Opening...\n");
	}

	void StartTown(FLevelLocals *Level, int index)
	{
		if (multiplayer || !LoadWorld()) return;
		currentTown = index;
		townActive = true;
		dd_tm_intown = 1;
		expected.clear();
		pending.clear();
		const Town &t = towns[index];
		pendingDoor = -1;
		useHeld = true;	// The press that opened the door must not also use the door on the far side.
		LoadTownDoors(t);
		// A revisited space comes back from the table, so what the map places by default must not return.
		if (t.space && !visitedSpaces.insert(t.map.GetChars()).second)
		{
			std::vector<AActor *> stale;
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next())
				if (!mo->player && !IsOwned(mo) && ((mo->flags3 & MF3_ISMONSTER) || mo->IsKindOf(NAME_Inventory))) stale.push_back(mo);
			for (AActor *mo : stale) mo->Destroy();
		}
		int restored = 0;
		for (auto &kv : table)
		{
			const Record &r = kv.second;
			if (r.kind == KGone || !t.Near(r.x / 256, r.y / 256, t.margin - 1)) continue;
			Restore(Level, r);
			restored++;
		}
		if (t.group >= 0 || (t.space && t.spaceId < DUNGEON_SPACE)) SpawnTownContents(Level);
		FinishHandoff(Level);
		if (FindArg("-ddtmverify")) VerifySeam(Level, t);
		Printf("DDTOWN active %s restored=%d records=%d\n", t.map.GetChars(), restored, int(table.size()));
	}

	void Start(FLevelLocals *Level)
	{
		DDTreadmill_Active = false;
		townActive = false;
		dd_tm_intown = 0;
		LoadTowns();
		const int town = TownForMap(Level->MapName);
		if (town >= 0)
		{
			StartTown(Level, town);
			return;
		}
		if (Level->MapName.CompareNoCase("DDOVER01") != 0) return;
		const bool returning = handoff.pending;
		if (!returning)
		{
			table.clear();
			buckets.clear();
			visitedSpaces.clear();
			returnPoint = ReturnPoint();
			nextDynamic = 0;
			shifts = 0;
			stitches = 0;
			dd_tm_stitches = 0;
		}
		expected.clear();
		pending.clear();
		lodTown = -1;
		lodEntry = nullptr;
		if (runtimeTowns)
		{
			townFlats.clear();
			flatSpawned.clear();
			flatQueue.clear();
		}
		LoadConfig();
		originX = startTileX;
		originY = startTileY;
		if (returning)
		{
			// Whole chunks, with the player inside the band that does not shift.
			const int tileX = int(floor(handoff.x / 256)), tileY = int(floor(handoff.y / 256));
			originX = std::clamp(((tileX - CELLS / 2 + CHUNK_TILES / 2) / CHUNK_TILES) * CHUNK_TILES, 0, WORLD_W * PIXEL_TILES - CELLS);
			originY = std::clamp(((tileY - CELLS / 2 + CHUNK_TILES / 2) / CHUNK_TILES) * CHUNK_TILES, 0, WORLD_H * PIXEL_TILES - CELLS);
		}
		if (!PrepareLevel(Level)) return;
		LoadTownFlats();
		SettleActors(Level, true);
		if (returning) FinishHandoff(Level);
		else if (AActor *start = Level->Players[consoleplayer]->mo) start->Angles.Yaw = DAngle::fromDeg(startAngle);
		for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)
			for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++)
				QueueChunk(cx, cy);
		ProcessPending(Level, std::numeric_limits<int>::max());
		if (runtimeTowns)
		{
			DDTownCache::Poll();
			if (AActor *pmo = Level->Players[consoleplayer]->mo) ScanLocations(Level, pmo);
			ProcessFlatQueue(Level, std::numeric_limits<int>::max());
		}
		DDTreadmill_Active = true;
		Printf("DDTM active origin=%d,%d spacing=%d sectors=%d packs=%.2f/%d\n", originX, originY, SPACING, int(tris.size()), packChance, packSize);
	}

	void Resume(FLevelLocals *Level)
	{
		resumePending = false;
		LoadTowns();
		if (resumeTown >= 0)
		{
			const int town = TownForMap(Level->MapName);
			resumeTown = -1;
			if (town < 0 || !LoadWorld()) return;
			currentTown = town;
			townActive = true;
			dd_tm_intown = 1;
			pendingDoor = -1;
			useHeld = true;
			LoadTownDoors(towns[town]);
			expected.clear();
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next())
				if (mo->ddRecordId && !IsOwned(mo)) expected.insert(mo->ddRecordId);
			Printf("DDTOWN resumed %s records=%d\n", Level->MapName.GetChars(), int(table.size()));
			return;
		}
		LoadConfig();
		if (!PrepareLevel(Level)) return;
		LoadTownFlats();
		lodTown = -2;	// The next scan replaces the billboards the save restored.
		lodEntry = nullptr;
		expected.clear();
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (mo->ddRecordId && !IsOwned(mo)) expected.insert(mo->ddRecordId);
		SettleActors(Level, false);
		DDTreadmill_Active = true;
		int drawn = 0;
		for (auto &t : tris) drawn += t.sec->GetTexture(sector_t::floor) == baseFloor;
		Printf("DDTM resumed origin=%d,%d records=%d pending=%d floors drawn=%d of %d\n", originX, originY, int(table.size()), int(pending.size()), drawn, int(tris.size()));
	}

	FString EncodeState()
	{
		FString out;
		out.AppendFormat("%d %d %d %llu %d\n", originX, originY, shifts, (unsigned long long)nextDynamic, int(pending.size()));
		for (auto &p : pending) out.AppendFormat("%d %d\n", p.cx, p.cy);
		for (auto &kv : table)
		{
			const Record &r = kv.second;
			out.AppendFormat("%llu %s %s %.17g %.17g %.17g %.17g %.17g %d %d %d %d %d\n", (unsigned long long)r.id, r.cls.GetChars(),
				r.stateOwner.GetChars(), r.x, r.y, r.z, r.angle, r.height, r.health, r.kind, r.amount, r.stateIdx, int(r.dropped));
		}
		return out;
	}

	void DecodeState(const FString &text)
	{
		table.clear();
		buckets.clear();
		expected.clear();
		pending.clear();
		const char *s = text.GetChars();
		char line[640];
		auto nextLine = [&]()
		{
			const char *end = strchr(s, 10);
			if (!end) return false;
			const size_t len = std::min(size_t(end - s), sizeof(line) - 1);
			memcpy(line, s, len);
			line[len] = 0;
			s = end + 1;
			return true;
		};
		int pendingCount = 0;
		unsigned long long dyn = 0;
		if (!nextLine() || sscanf(line, "%d %d %d %llu %d", &originX, &originY, &shifts, &dyn, &pendingCount) < 5) return;
		nextDynamic = dyn;
		for (int n = 0; n < pendingCount; n++)
		{
			int cx, cy;
			if (!nextLine() || sscanf(line, "%d %d", &cx, &cy) < 2) return;
			QueueChunk(cx, cy);
		}
		char cls[128], owner[128];
		unsigned long long id;
		int dropped;
		Record r;
		while (nextLine() && sscanf(line, "%llu %127s %127s %lf %lf %lf %lf %lf %d %d %d %d %d", &id, cls, owner, &r.x, &r.y, &r.z, &r.angle, &r.height,
			&r.health, &r.kind, &r.amount, &r.stateIdx, &dropped) >= 13)
		{
			r.id = id;
			r.cls = FName(cls);
			r.stateOwner = FName(owner);
			r.dropped = dropped != 0;
			Store(r);
		}
		resumePending = true;
	}
}

void DDTreadmill_Serialize(FLevelLocals *Level, FSerializer &arc)
{
	if (arc.isWriting())
	{
		if ((!DDTreadmill_Active && !townActive) || Level != primaryLevel) return;
		Reconcile(Level);
		FString state = EncodeState();
		arc("ddoverworld", state);
		FString spaces;
		if (returnPoint.valid) spaces.AppendFormat("R %s %.17g %.17g %.17g %.17g\n", returnPoint.map.GetChars(), returnPoint.x, returnPoint.y, returnPoint.z, returnPoint.yaw);
		for (const std::string &name : visitedSpaces) spaces.AppendFormat("V %s\n", name.c_str());
		arc("ddspaces", spaces);
		if (townActive)
		{
			int inTown = 1;
			arc("ddintown", inTown);
		}
		return;
	}
	if (Level != primaryLevel) return;
	DDTreadmill_Active = false;	// Sector pointers from the previous level are no longer valid.
	townActive = false;
	dd_tm_intown = 0;
	handoff.pending = false;
	resumePending = false;
	resumeTown = -1;
	if (arc.HasKey("ddoverworld"))
	{
		FString state;
		arc("ddoverworld", state);
		DecodeState(state);
		if (arc.HasKey("ddintown")) resumeTown = 1;
		returnPoint = ReturnPoint();
		visitedSpaces.clear();
		if (arc.HasKey("ddspaces"))
		{
			FString spaces;
			arc("ddspaces", spaces);
			for (auto &line : spaces.Split("\n"))
			{
				char name[16];
				if (sscanf(line.GetChars(), "R %15s %lf %lf %lf %lf", name, &returnPoint.x, &returnPoint.y, &returnPoint.z, &returnPoint.yaw) == 5)
				{
					returnPoint.map = name;
					returnPoint.valid = true;
				}
				else if (sscanf(line.GetChars(), "V %15s", name) == 1) visitedSpaces.insert(name);
			}
		}
	}
}

void DDTreadmill_BeginMap(FLevelLocals *Level)
{
	DDTreadmill_WideNodes = false;
	static const bool hasTowns = fileSystem.CheckNumForName("DDTOWN") >= 0 || fileSystem.CheckNumForName("DDGROUPS") >= 0;
	if (!hasTowns || !Level->isPrimaryLevel()) return;
	LoadTowns();
	DDTreadmill_WideNodes = TownForMap(Level->MapName) >= 0;
}

bool DDTreadmill_RuntimeTowns() { return runtimeTowns; }
level_info_t *DDTreadmill_LevelInfoAt(unsigned index) { return index < runtimeInfos.size() ? &runtimeInfos[index] : nullptr; }
bool DDTreadmill_HandoffPending() { return handoff.pending; }

// Each generated location gets its own copy of the DDTOWN template from the runtime package's MAPINFO.
level_info_t *DDTreadmill_FindLevelInfo(const char *mapname)
{
	if (strnicmp(mapname, "DDT", 3) != 0 && strnicmp(mapname, "DDS", 3) != 0) return nullptr;	// Every stock map name stops here.
	if ((GroupOfMap(mapname) < 0 && SpaceOfMap(mapname) < 0) || fileSystem.CheckNumForName("DDGROUPS") < 0) return nullptr;
	FString upper = mapname;
	upper.ToUpper();
	auto found = runtimeInfoByName.find(upper.GetChars());
	if (found != runtimeInfoByName.end()) return found->second;
	level_info_t *base = FindLevelInfo("DDTOWN", false);
	if (!base) return nullptr;
	runtimeInfos.push_back(*base);
	level_info_t *info = &runtimeInfos.back();
	info->MapName = upper;
	runtimeInfoByName[upper.GetChars()] = info;
	return info;
}

bool DDTreadmill_OpenTownMap(const char *mapname, FileSys::FileReader &reader)
{
	if (strnicmp(mapname, "DDT", 3) != 0 && strnicmp(mapname, "DDS", 3) != 0) return false;
	const int space = SpaceOfMap(mapname), group = space >= 0 ? space : GroupOfMap(mapname);
	if (group < 0) return false;
	LoadTowns();
	if (!runtimeTowns || (space < 0 && (group >= int(groups.size()) || groups[group].tooLarge))) return false;
	DDTownCache::EntryPtr entry = DDTownCache::GetBlocking(group);
	const auto *wad = entry ? entry->Find("MAPWAD") : nullptr;
	if (!wad) return false;
	mapEntry = entry;
	return reader.OpenMemory(wad->data(), wad->size());
}

bool DDTreadmill_MapMesh(const char *mapname, const uint8_t *&data, size_t &size, int &key)
{
	const int space = SpaceOfMap(mapname), group = space >= 0 ? space : GroupOfMap(mapname);
	if (group < 0 || !mapEntry) return false;
	const auto *mesh = mapEntry->Find("DFMESH");
	if (!mesh) return false;
	data = mesh->data();
	size = mesh->size();
	key = RUNTIME_MESH_KEY + group;
	return true;
}

bool DDTreadmill_LodMesh(const uint8_t *&data, size_t &size, int &key)
{
	if (lodTown < 0 || !lodEntry) return false;
	const auto *mesh = lodEntry->Find("DFMESH");
	if (!mesh) return false;
	data = mesh->data();
	size = mesh->size();
	key = RUNTIME_MESH_KEY + towns[lodTown].group;
	return true;
}

// Where the town mesh's origin sits in the overworld window, so distant towns can be drawn from it.
bool DDTreadmill_MeshOffset(double &x, double &y, double &z)
{
	const Town *t = DDTreadmill_Active ? LodTown() : nullptr;
	if (!t) return false;
	x = t->originX * DOOM_PER_DF - originX * double(SPACING) - HALF;
	y = t->originY * DOOM_PER_DF - originY * double(SPACING) - HALF;
	z = t->ground * DOOM_PER_DF - Z_BASE;
	return true;
}

void DDTreadmill_Tick(FLevelLocals *Level)
{
	static const bool requested = fileSystem.CheckNumForName("DDWORLD") >= 0;
	if (!requested || Level != primaryLevel) return;
	if (resumePending) Resume(Level);
	else if (Level->maptime == 0) Start(Level);
	if (!DDTreadmill_Active && !townActive) return;

	AActor *pmo = Level->Players[consoleplayer]->mo;
	if (!pmo) return;
	if (runtimeTowns) DDTownCache::Poll();

	if (townActive)
	{
		TickTownDoors(Level, pmo);
		const Town &t = towns[currentTown];
		if (t.space) return;	// Interiors and dungeons are left through their doors.
		const double tx = (pmo->X() / DOOM_PER_DF + t.originX) / 256, ty = (pmo->Y() / DOOM_PER_DF + t.originY) / 256;
		if (!handoff.pending && pmo->health > 0 && !t.Near(tx, ty, t.ExitMargin())) BeginHandoff(Level, pmo, "DDOVER01");
		return;
	}
	if (handoff.pending) return;
	if (runtimeTowns)
	{
		if (const char *warp = *dd_tm_warp; warp && *warp)
		{
			int tile[2];
			const bool valid = sscanf(warp, "%d %d", &tile[0], &tile[1]) == 2 && tile[0] >= 0 && tile[0] < WORLD_W * PIXEL_TILES && tile[1] >= 0 && tile[1] < WORLD_H * PIXEL_TILES;
			dd_tm_warp = "";
			if (valid)
			{
				BeginHandoff(Level, pmo, "DDOVER01", tile);
				return;
			}
		}
		if (Level->maptime % SCAN_TICS == 0) ScanLocations(Level, pmo);
		ProcessFlatQueue(Level, FLAT_CHUNKS_PER_TIC);
	}
	{
		const double tx = originX + (pmo->X() + HALF) / SPACING, ty = originY + (pmo->Y() + HALF) / SPACING;
		for (const Town &t : towns)
			if (pmo->health > 0 && t.Near(tx, ty, t.EntryMargin())
				&& (t.group < 0 || (!t.holdEntry && !t.Near(tx, ty, 0) && DDTownCache::Status(t.group) == DDTownCache::State::Ready)))
			{
				BeginHandoff(Level, pmo, t.map.GetChars());
				return;
			}
	}

	ProcessPending(Level, SPAWNS_PER_TIC);

	int dx = pmo->X() > SHIFT_AT ? CHUNK_TILES : pmo->X() < -SHIFT_AT ? -CHUNK_TILES : 0;
	int dy = pmo->Y() > SHIFT_AT ? CHUNK_TILES : pmo->Y() < -SHIFT_AT ? -CHUNK_TILES : 0;
	if (originX + dx < 0 || originX + dx + CELLS > WORLD_W * PIXEL_TILES) dx = 0;
	if (originY + dy < 0 || originY + dy + CELLS > WORLD_H * PIXEL_TILES) dy = 0;
	if (dx == 0 && dy == 0) return;

	const auto start = Clock::now();
	Reconcile(Level);
	parkCount = 0;
	const int oldX = originX, oldY = originY;
	originX += dx;
	originY += dy;
	const auto rewriteStart = Clock::now();
	ScrollWindow(dx, dy);
	RewriteGrid();	// Before the move, so actors find their floors on the new terrain.
	const int64_t rewriteNs = NsSince(rewriteStart);
	MoveActors(Level, DVector3(dx * double(SPACING), dy * double(SPACING), 0), oldX, oldY);
	if (runtimeTowns)	// Billboards in a chunk that left were destroyed with it, so its next entry spawns them again.
		for (auto it = flatSpawned.begin(); it != flatSpawned.end();)
			it = ChunkInWindow(int(uint32_t(*it)), int(*it >> 32)) ? std::next(it) : flatSpawned.erase(it);

	// Queue the chunks that just entered the window.
	for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)
		for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++)
		{
			const int x = cx * CHUNK_TILES, y = cy * CHUNK_TILES;
			if (x < oldX || x >= oldX + CELLS || y < oldY || y >= oldY + CELLS) QueueChunk(cx, cy);
		}

	const int64_t totalNs = NsSince(start);
	simNs += totalNs;
	shiftFlag = 1;
	shifts++;
	dd_tm_shifts = shifts;
	dd_tm_originx = originX;
	dd_tm_originy = originY;

	const double err = verify ? VerifyGrid(Level) : -1;
	if (shiftLog)	// Buffered, so logging does not add to the frame being measured.
		fprintf(shiftLog, "%d,%d,%d,%.1f,%.1f,%d,%d,%.6f\n", shifts, originX, originY, rewriteNs / 1000.0, totalNs / 1000.0, moveCount, parkCount, err);
}

void DDTreadmill_UploadBegin() { uploadStart = Clock::now(); }
void DDTreadmill_UploadEnd() { uploadNs += NsSince(uploadStart); uploadCount++; }

void DDTreadmill_FrameEnd()
{
	if (!DDTreadmill_Active) return;
	const auto now = Clock::now();
	const int64_t frameNs = std::chrono::duration_cast<std::chrono::nanoseconds>(now - lastFrame).count();
	lastFrame = now;
	if (frameLog)
	{
		fprintf(frameLog, "%lld,%d,%.1f,%.1f,%.1f,%lld,%d,%d\n", (long long)frameNo++, primaryLevel->maptime, frameNs / 1000.0,
			simNs / 1000.0, uploadNs / 1000.0, (long long)uploadCount, shiftFlag, runtimeTowns && DDTownCache::Converting() ? 1 : 0);
		if ((frameNo & 255) == 0) { fflush(frameLog); if (shiftLog) fflush(shiftLog); }
	}
	simNs = uploadNs = uploadCount = 0;
	shiftFlag = 0;
}
