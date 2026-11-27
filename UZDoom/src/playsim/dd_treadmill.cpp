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

#include <cinttypes>
#include "dd_lootrng.h" // [Doomerfall] fixed loot
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <limits>
#include <map>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../../../bridge/doomerfall_bridge.h"
#include "dd_treadmill.h"
#include "dd_towncache.h"
#include "dd_nature.h"
#include "../dd_locations.h"
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
#include "playsim/dd_log.h" // [Doomerfall]

FString DD_MonstersSavePlans();	// dd_monsters.cpp: each dungeon's first encounter request, so a revisit rebuilds the same mooks.
void DD_MonstersLoadPlans(const FString &text);

CVAR(Int, dd_tm_originx, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_originy, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_shifts, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_records, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_intown, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_stitches, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_nearest, -1, CVAR_NOSAVE)		// Nearest generated location group.
CVAR(Int, dd_tm_neareststate, 0, CVAR_NOSAVE)	// Its DDTownCache::State.
CVAR(Int, dd_tm_use, 0, CVAR_NOSAVE | CVAR_MOD)	// Test hook: one press of Use on a location door.
CVAR(Bool, dd_natureflats, true, CVAR_NOSAVE)	// Wilderness nature flats; off for frame time comparisons. Applies to ground laid out after it changes.
static int doorPressTic = -1;	// DDTreadmill_PressDoor. A press counts only on the next tic, in case no town door tick runs.
CVAR(String, dd_tm_warp, "", CVAR_NOSAVE | CVAR_MOD)		// "tileX tileY": moves the player through the overworld handoff. The path fast travel can use.

void DD_MonstersEnterDungeon(FLevelLocals *Level, int mapId, bool firstVisit, bool bridged);
void DD_MonstersTick(FLevelLocals *Level);
void DD_NpcSetup(AActor *mo, uint64_t id, bool awaitList);
void DD_TownsfolkTick(FLevelLocals *Level);
bool DD_BridgeHasSession();
bool DD_BridgeArrivalFrozen();	// dd_bridge.cpp: a map change waits for its setup; Use and townspeople are held
void DD_LoadingHold(const char *name, bool on);	// dd_loading.cpp: freezes the game behind a loading message
double DD_LoadingAgeMs();
bool DD_LoadingActive();
bool DD_UsePress(player_t *player);
void DD_UseWall(player_t *player);
void DD_LightsFlat(AActor *mo, bool interior);	// dd_lights.cpp
void DD_LightsInterior(FLevelLocals *Level);
void DD_LightsTick(FLevelLocals *Level);
void DD_LightsReset();
void DD_WeatherTick(FLevelLocals *Level);	// dd_weather.cpp
void DD_LightsTextureName(const char *name, FTextureID tex);

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
	// Doom's own ids for this session (drops, replacement items) are tag 4 with bit 60 set. Daggerfall's guard ids are
	// tag 4 too (a spawn serial, far below bit 60), so the mark keeps the two apart.
	constexpr uint64_t SESSION_MARK = 1ull << 60, SESSION_ID = DYNAMIC_BIT | SESSION_MARK;
	// Items the map itself places get tag 1 (bit 61 alone, which no other id uses): a hash of the class and the spot in
	// world units, so the id is the same on every visit and a take leaves a tombstone.
	constexpr uint64_t MAP_ITEM_TAG = 1ull << 61, TAG_MASK = 7ull << 61;
	// A map item id: the tag, 41 bits naming the map, and the item's index in map order (Daggerfall packs taken ones as bits).
	constexpr int MAP_ITEM_INDEX_BITS = 20;
	constexpr uint64_t MAP_ITEM_PLACE_MASK = (1ull << (61 - MAP_ITEM_INDEX_BITS)) - 1;
	bool IsMapItemId(uint64_t id) { return (id & TAG_MASK) == MAP_ITEM_TAG; }
	// Rebuilt on every visit by the encounter plan (5) or by Daggerfall's lists (6 stationary NPCs, 7 townspeople).
	bool IsRebuiltId(uint64_t id) { const uint64_t tag = id >> 61; return tag == DFB_MONSTER_TAG || tag == DFB_NPC_TAG || tag == DFB_TOWNSPERSON_TAG; }
	constexpr int SPAWNS_PER_TIC = 64;
	constexpr double SKY_HEIGHT = 40000;

	enum RecordKind { KMonster, KCorpse, KItem, KGone };

	// The world table row. Coordinates are Daggerfall world units so that
	// Daggerfall can take over as the authority for this data. Only changes from what a seed, the map, or a Daggerfall
	// placement rebuilds are stored: dead, taken, dropped, moved or hurt.
	struct Record
	{
		uint64_t id = 0;
		FName cls = NAME_None;
		FString death;	// A corpse's death state label, such as "Death" or "XDeath.Fire". Never a state index. For an item:
						// what it carries (CarriedText), such as a DRLA modded gun's mods.
		double x = 0, y = 0, z = 0, angle = 0, height = 0;
		int health = 0, kind = KGone, amount = 0;
		bool dropped = false;
	};
	constexpr int TABLE_FORMAT = 2;	// Rows carry a death label. Format 1 (a state index) is not read.
	constexpr const char *REVIVED_LABEL = "Revived";	// A living monster's death label: it died once and was revived.

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
		// The space id and map name follow the converter's group order and are for this session only. History is keyed
		// by Daggerfall's own place key ("D<map id>" or "B<map id>:<building key>"), which also fixes where the space
		// sits in the world table.
		bool space = false;
		int spaceId = -1, dungeonMapId = 0;
		int buildingMapId = 0, buildingKey = -1;	// A building interior's Daggerfall place key.
		FString place;
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
	constexpr int WINTER_MESH_KEY = 1 << 30;	// [Doomerfall] added for a winter mesh, so a season change uploads the other one
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
		DDPlayerArea area = DD_AREA_EXTERIOR;	// What the player is arriving in.
		std::chrono::steady_clock::time_point started;
	} handoff;
	int stitches;

	// Doors between towns, building interiors, and dungeons.
	constexpr int SPACE_BASE = 1000000, DUNGEON_SPACE = 17000000, DOOR_PREFETCH = 2;
	// [Doomerfall] A dungeon converted during play: cache group DUNGEON_GROUP + location id (the low 20 bits of its map id,
	// as DungeonSlot). It is also its space id, and its map is named like an interior (SpaceMapName).
	constexpr int DUNGEON_GROUP = 30000000;
	int DungeonGroup(int mapId) { return DUNGEON_GROUP + (mapId & 0xFFFFF); }
	constexpr double USE_REACH = 96, DOOR_CANCEL = 768, EXIT_STEP = 31.5;	// 128 Daggerfall units of reach. The step is three player radii. A door still converting is dropped only past the prefetch range.
	struct DoorSpot { int kind, target, index; double x, y, z, nx, ny; };
	struct ReturnPoint { bool valid = false; FString map; double x = 0, y = 0, z = 0, yaw = 0; };
	std::vector<DoorSpot> townDoors;
	ReturnPoint returnPoint;
	std::unordered_set<std::string> visitedSpaces;
	int pendingDoor = -1;
	bool useHeld;

	// The town's billboards, so trees and props look the same from the overworld. Global Doom coordinates.
	struct TownFlat { FTextureID tex; double x, y, z; float sx, sy; uint64_t npc; };
	std::unordered_map<int64_t, std::vector<TownFlat>> townFlats;
	bool flatsLoaded;
	PClassActor *flatClass = nullptr, *npcClass = nullptr;
	std::vector<float> window;
	std::vector<Tri> tris;
	int originX, originY, startTileX, startTileY, shifts, startAngle;
	FTextureID baseFloor;

	std::unordered_map<uint64_t, Record> table;
	std::unordered_map<int64_t, std::vector<uint64_t>> buckets;
	std::unordered_set<uint64_t> expected;	// Records and seeds that currently have a live actor.
	std::unordered_map<uint64_t, DVector3> itemSpots;	// Where each map item stood (world units), so a take's tombstone belongs to its place.
	bool resumedSnapshot;	// The current space came back from a save's snapshot; its record only refills the cache.
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

	// [Doomerfall] Daggerfall Unity's ground tiles (DefaultTerrainTexturing, dd_nature.cpp) in the pixel's climate and
	// season, as the town meshes draw them, so the open ground meets a town with no seam. baseFloor without DDNATURE.
	std::unordered_map<int, std::vector<uint8_t>> tileCache;	// key north * WORLD_W + px
	std::unordered_map<int, FTextureID> groundTextures;			// key archive * 64 + record
	bool groundWinter;

	const float *PixelHeights(int px, int north, short *rect, bool &hasRect);
	FTextureID FlatTexture(const char *name);

	const uint8_t *TilesOf(int px, int north)
	{
		const int key = north * WORLD_W + px;
		auto found = tileCache.find(key);
		if (found != tileCache.end()) return found->second.data();
		if (tileCache.size() >= 16) tileCache.clear();
		short rect[4];
		bool hasRect;
		const float *heights = PixelHeights(px, north, rect, hasRect);
		std::vector<uint8_t> &tiles = tileCache[key];
		tiles.resize(size_t(PIXEL_TILES) * PIXEL_TILES);
		DDNature_Tiles(px, north, heights, tiles.data());
		return tiles.data();
	}

	// The floor texture and its rotation for global tile gx, gy. The flat's 192-unit repeat matches the tile grid, and
	// Daggerfall Unity's rotate and flip are quarter turns of the tile image.
	FTextureID GroundAt(int gx, int gy, DAngle &angle)
	{
		angle = nullAngle;
		DDNature_Load();	// the climates; without DDNATURE every pixel is woodland, as for the nature flats
		const int px = std::clamp(gx / PIXEL_TILES, 0, WORLD_W - 1), north = std::clamp(gy / PIXEL_TILES, 0, WORLD_H - 1);
		const uint8_t tile = TilesOf(px, north)[std::clamp(gx - px * PIXEL_TILES, 0, PIXEL_TILES - 1) + std::clamp(gy - north * PIXEL_TILES, 0, PIXEL_TILES - 1) * PIXEL_TILES];
		const int key = DDNature_GroundArchive(px, north, groundWinter) * 64 + (tile & 63);
		auto id = groundTextures.find(key);
		if (id == groundTextures.end())
			id = groundTextures.emplace(key, FlatTexture(FStringf("dfmesh/a%03dr%02d.png", key / 64, key % 64).GetChars())).first;
		if (!id->second.isValid()) return baseFloor;
		static const double turns[4] = { 0, 270, 180, 90 };	// none, rotate, flip, both (CityExport.AddTerrain's UVs)
		angle = DAngle::fromDeg(turns[tile >> 6]);
		return id->second;
	}

	void RewriteGrid()
	{
		const Town *lod = LodTown();
		groundWinter = DDTownCache::IsWinter();
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
			DAngle angle;
			const FTextureID ground = covered ? FNullTextureID() : GroundAt(int(floor(cx)), int(floor(cy)), angle);
			t.sec->SetTexture(sector_t::floor, ground, false);
			if (!covered) t.sec->SetAngle(sector_t::floor, angle);
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

	// Exterior rows (towns and the overworld) are in real world units; interiors and dungeons sit far beyond the world.
	bool IsExterior(const Record &r) { return r.x < 2097152.0 * 256; }

	// Exterior chunks whose rows changed since Daggerfall's location ledger last got them (dd_locations.cpp).
	std::unordered_set<int64_t> dirtyChunks;
	bool quietStore;	// rows that came from Daggerfall's ledger do not need to go back to it
	void MarkDirty(const Record &r) { if (!quietStore && IsExterior(r)) dirtyChunks.insert(RecordChunk(r)); }

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
		if (it != table.end()) MarkDirty(it->second);
		MarkDirty(r);
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
				MarkDirty(it->second);
				table.erase(it);
			}
			dd_tm_records = int(table.size());
			return;
		}
		Record gone = it != table.end() ? it->second : Record();
		if (it == table.end())
			if (auto spot = itemSpots.find(id); spot != itemSpots.end()) { gone.x = spot->second.X; gone.y = spot->second.Y; gone.z = spot->second.Z; }
		gone.id = id;
		gone.kind = KGone;
		Store(gone);
	}

	bool IsOwned(AActor *mo)
	{
		return mo->IsKindOf(NAME_Inventory) && mo->PointerVar<AActor>(NAME_Owner) != nullptr;
	}

	// Records anything that vanished since the last check, such as a picked-up item.
	DVector3 ToLocal(double x, double y, double z);
	void SpawnNatureChunk(FLevelLocals *Level, int cx, int cy);	// [Doomerfall] nature flats, below

	void Reconcile(FLevelLocals *Level)
	{
		std::unordered_set<uint64_t> live;
		std::vector<AActor *> loose;	// unowned items without an id: drops, or a map item's replacement
		live.reserve(expected.size() * 2);
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (!mo->ddRecordId)
			{
				if (mo->ddHandoffId) live.insert(mo->ddHandoffId);	// [Doomerfall] A spawner that has not made its monster yet.
				else if (mo->IsKindOf(NAME_Inventory) && !IsOwned(mo)) loose.push_back(mo);
				continue;
			}
			if (IsOwned(mo)) mo->ddRecordId = 0;
			else live.insert(mo->ddRecordId);
		}
		for (auto e = expected.begin(); e != expected.end();)
		{
			if (live.count(*e)) { ++e; continue; }
			// DoomerfallAmmo replaces a placed ammo pickup with a tiered one on the same spot a few tics after the map
			// loads. The replacement is still the map's item: it takes the id, so it is neither a take nor a drop. Only an
			// item that never moved counts (a tossed jackpot pickup stays a loose item).
			if (IsMapItemId(*e))
				if (auto spot = itemSpots.find(*e); spot != itemSpots.end())
				{
					const DVector3 at = ToLocal(spot->second.X, spot->second.Y, spot->second.Z);
					auto heir = std::find_if(loose.begin(), loose.end(), [&](AActor *mo) {
						return (mo->Pos().XY() - at.XY()).LengthSquared() <= 1 && fabs(mo->Z() - at.Z) <= 8; });
					if (heir != loose.end())
					{
						(*heir)->ddRecordId = *e;
						(*heir)->SpawnPoint = (*heir)->Pos();
						loose.erase(heir);
						++e;
						continue;
					}
				}
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
		return mo->health < mo->SpawnHealth() || mo->target != nullptr || mo->ddDied	// Revived: kept, so it keeps the mark.
			|| (mo->Pos().XY() - mo->SpawnPoint.XY()).LengthSquared() > 1;
	}

	// Whatever rebuilds this actor on the next visit puts it back exactly as it is now, so storing it adds nothing.
	bool IsUnchanged(AActor *mo, bool monster)
	{
		const uint64_t id = mo->ddRecordId;
		if (!id || table.count(id)) return false;
		if (!monster)	// A map item still on its spot, with its default amount.
			return IsMapItemId(id) && (mo->Pos().XY() - mo->SpawnPoint.XY()).LengthSquared() <= 1
				&& mo->IntVar(NAME_Amount) == GetDefaultByType(mo->GetClass())->IntVar(NAME_Amount);
		if (mo->health <= 0) return false;
		const uint64_t tag = id >> 61;
		if (tag == DFB_NPC_TAG || tag == DFB_TOWNSPERSON_TAG)	// Daggerfall decides where they are, so walking is no change.
			return mo->health >= mo->SpawnHealth();
		return ((id & SEED_BIT) && !(id & DYNAMIC_BIT)) || tag == DFB_MONSTER_TAG ? !IsTouched(mo) : false;
	}

	// Where a death sequence settles, following each state's own next link: a frame with infinite tics, or the loop a
	// corpse ticks in (DRLA Monsters' corpses loop a 1-tic CanRaise frame and never rest). A loop is named by its first
	// state in memory, so any point in it gives the same answer. Those frames keep ("####" "#") the sprite and frame
	// shown before them, so the look is the last sprite and frame the sequence set. rest is null when it ends in Stop.
	// DRLA's base class jumps by name ("A_JumpIf(1, "DeathMain")", then Goto DeathMain for the parser), which the game
	// resolves in the dying actor's own class, where its death frames are; the Goto's link is the base class's state.
	// So a state an ancestor owns under a label the class redefines is followed into the class's own state instead.
	struct Settled { FState *rest = nullptr; int sprite = -1, frame = -1; };
	FState *ClassVersion(PClassActor *cls, FState *st)
	{
		PClassActor *owner = FState::StaticFindStateOwner(st, cls);
		if (!owner || owner == cls) return st;
		const FStateLabels *labels = owner->GetStateLabels();
		for (int i = 0; labels && i < labels->NumLabels; i++)
		{
			const FStateLabel &l = labels->Labels[i];
			if (l.State == st)
				if (FState *own = cls->FindState(1, const_cast<FName *>(&l.Label), true); own && own != st) return own;
			for (int j = 0; l.Children && j < l.Children->NumLabels; j++)
				if (l.Children->Labels[j].State == st)
				{
					FName names[2] = { l.Label, l.Children->Labels[j].Label };
					if (FState *own = cls->FindState(2, names, true); own && own != st) return own;
				}
		}
		return st;
	}
	Settled SettleWalk(PClassActor *cls, FState *st)
	{
		Settled out;
		std::vector<FState *> seen;
		for (int n = 0; st && n < 1024; n++)
		{
			st = ClassVersion(cls, st);
			if (st->sprite != SPR_FIXED)
			{
				if (!st->GetSameFrame()) out.frame = st->GetFrame();
				if (st->sprite != SPR_NOCHANGE) out.sprite = st->sprite;
			}
			if (st->Tics == -1)
			{
				out.rest = st;
				return out;
			}
			auto again = std::find(seen.begin(), seen.end(), st);
			if (again != seen.end())
			{
				out.rest = *std::min_element(again, seen.end(), std::less<FState *>());
				return out;
			}
			seen.push_back(st);
			st = st->GetNextState();
		}
		return out;
	}
	std::map<std::pair<PClassActor *, FState *>, Settled> settledCache;	// States live as long as the process.
	Settled Settle(PClassActor *cls, FState *st)
	{
		if (!st) return Settled();
		auto key = std::make_pair(cls, st);
		auto found = settledCache.find(key);
		if (found == settledCache.end()) found = settledCache.emplace(key, SettleWalk(cls, st)).first;
		return found->second;
	}
	FState *FinalFrame(AActor *mo, FState *st) { return Settle(mo->GetClass(), st).rest; }

	// The state a stored death label names: "Death", "XDeath", "Death.Fire" or "XDeath.Fire". The engine keeps XDeath as
	// Death.Extreme (p_interaction.cpp), so "XDeath" alone found nothing and every gibbed corpse came back as a Death.
	FState *LabelState(AActor *mo, const FString &label)
	{
		FName names[3];
		int n = 0;
		for (auto &part : label.Split("."))
		{
			if (n == 0 && part.CompareNoCase("XDeath") == 0) { names[n++] = NAME_Death; names[n++] = NAME_Extreme; }
			else if (n < 3) names[n++] = FName(part);
		}
		if (n == 0) return nullptr;
		return mo->GetClass()->FindState(n, names, n > 1);
	}

	// The death label whose sequence settles where this corpse does. A label is a name, so it survives a mod
	// reordering its states.
	FString DeathLabel(AActor *mo, FState *final)
	{
		if (!final) return "Death";
		const FName type = mo->DamageTypeReceived;
		const bool typed = type != NAME_None && type != NAME_Normal && type != NAME_Extreme;
		if (typed)
			for (const char *label : { "XDeath", "Death" })
			{
				const FString name = FStringf("%s.%s", label, type.GetChars());
				if (FinalFrame(mo, LabelState(mo, name)) == final) return name;
			}
		if (FinalFrame(mo, LabelState(mo, "XDeath")) == final) return "XDeath";
		return "Death";	// Death, or a sequence reached some other way (a crush or a script), shown as an ordinary death.
	}

	int unchangedCount, missingClassCount;	// For the table summary in the log.

	// What an item lying on the ground carries as its own inventory, as "Class=amount;Class=amount", the text a gun's
	// state uses in Daggerfall (dd_items.cpp). A DRLA modded pickup carries its gun's mods this way (+INVENTORY.TRANSFER).
	FString CarriedText(AActor *mo)
	{
		FString out;
		for (AActor *inv = mo->Inventory; inv; inv = inv->Inventory)
		{
			const int amount = inv->IntVar(NAME_Amount);
			if (amount <= 0) continue;
			if (!out.IsEmpty()) out += ";";
			out.AppendFormat("%s=%d", inv->GetClass()->TypeName.GetChars(), amount);
		}
		return out;
	}

	// Gives a restored item what it carried. DRLA's modded pickup also asks for its mods when it spawns
	// (GetWeaponMods), but only from the player who dropped it (its master); a restored pickup has none, so the script
	// stops and these stay.
	void GiveCarried(AActor *mo, const FString &text)
	{
		if (text.IsEmpty()) return;
		for (auto &part : text.Split(";"))
		{
			const long eq = part.IndexOf('=');
			if (eq <= 0) continue;
			PClassActor *cls = PClass::FindActor(FName(part.Left(eq)));
			const int amount = atoi(part.Mid(eq + 1).GetChars());
			if (!cls || !cls->IsDescendantOf(NAME_Inventory) || amount <= 0) continue;
			if (AActor *inv = mo->GiveInventoryType(cls)) inv->IntVar(NAME_Amount) = amount;
		}
	}

	enum class Parked { Skip, Unchanged, Stored, Gone };

	// What a row for this actor would be. Shared by Park and the location ledger's snapshot (DDTreadmill_SnapshotPlace).
	// r.id stays 0 for an actor without an id.
	Parked MakeRecord(AActor *mo, int fromX, int fromY, Record &r)
	{
		const bool monster = (mo->flags3 & MF3_ISMONSTER) != 0, item = mo->IsKindOf(NAME_Inventory);
		if (!monster && !item) return Parked::Skip;	// Projectiles and effects do not persist.
		if (DD_IsDrlaSpawner(mo)) return Parked::Skip;	// A spawner is not a monster: restored, it would spawn another one.
		if (IsUnchanged(mo, monster)) return Parked::Unchanged;	// Its seed, the map, or Daggerfall's placement rebuilds it.
		r = Record();
		r.id = mo->ddRecordId;
		if (!r.id) r.id = DD_LootItemId(mo);	// A drop from a fixed loot roll keeps the same id in every game.
		if (!r.id && item) r.id = DD_LootIsGunClass(mo->GetClass()->TypeName) ? DD_LootFixItemId(mo) : 0;	// [Doomerfall] a gun gets a lasting id
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
			r.death = CarriedText(mo);
		}
		else if (mo->health <= 0)
		{
			// A corpse is stored as dead, with the label of its death. Its look comes from that label in the class when
			// it is restored, so a corpse that is still settling (or burning, or looping) is kept all the same.
			r.kind = KCorpse;
			r.death = DeathLabel(mo, FinalFrame(mo, mo->state));
		}
		else
		{
			r.kind = KMonster;
			if (mo->ddDied) r.death = REVIVED_LABEL;	// Its seeded loot already dropped (dd_lootrng.cpp).
		}
		return Parked::Stored;
	}

	void ParkAs(AActor *mo, Parked decided, Record &r)
	{
		if (mo->ddRecordId) expected.erase(mo->ddRecordId);
		switch (decided)
		{
		case Parked::Unchanged:
			unchangedCount++;
			break;
		case Parked::Gone:
			if (r.id) MarkGone(r.id);
			break;
		case Parked::Stored:
			if (!r.id) r.id = SESSION_ID | ++nextDynamic;
			Store(r);
			parkCount++;
			break;
		default:
			break;
		}
		mo->Destroy();
	}

	void Park(AActor *mo, int fromX, int fromY)
	{
		Record r;
		const Parked decided = MakeRecord(mo, fromX, fromY, r);
		ParkAs(mo, decided, r);
	}

	// Decides every row before destroying anything: destroying a monster clears other monsters' target pointers, which
	// would turn alerted monsters "unchanged" partway through, unlike the location ledger's snapshot of the same moment.
	void ParkAll(const std::vector<AActor *> &actors, int fromX, int fromY)
	{
		std::vector<std::pair<Parked, Record>> decided(actors.size());
		for (size_t n = 0; n < actors.size(); n++) decided[n].first = MakeRecord(actors[n], fromX, fromY, decided[n].second);
		for (size_t n = 0; n < actors.size(); n++) ParkAs(actors[n], decided[n].first, decided[n].second);
	}

	void Restore(FLevelLocals *Level, const Record &r)
	{
		PClassActor *cls = PClass::FindActor(r.cls);
		if (!cls)
		{
			// Kept in the table, so the row comes back if the class does (for example after a mod is restored).
			missingClassCount++;
			DD_DebugPrintf(TEXTCOLOR_ORANGE "DDTM row %016" PRIx64 " kind %d: class %s no longer exists, not restored\n", r.id, r.kind, r.cls.GetChars());
			return;
		}
		AActor *mo = Spawn(Level, cls, ToLocal(r.x, r.y, r.z), NO_REPLACE);
		if (!mo) return;
		mo->ddRecordId = r.id;
		mo->Angles.Yaw = DAngle::fromDeg(r.angle);
		mo->health = r.health;
		if (r.dropped) mo->flags |= MF_DROPPED;
		// Its seeded loot already dropped (dd_lootrng.cpp): a corpse an Arch-vile raises, or a revived monster, drops nothing again.
		if (r.kind == KCorpse || (r.kind == KMonster && r.death.Compare(REVIVED_LABEL) == 0)) mo->ddDied = 1;
		if (r.kind == KItem)
		{
			mo->IntVar(NAME_Amount) = r.amount;
			GiveCarried(mo, r.death);
		}
		if (r.kind == KCorpse)
		{
			// The class's own death sequence, by label, to its resting frame.
			FState *st = LabelState(mo, r.death);
			Settled look = Settle(mo->GetClass(), st);
			if (!look.rest) look = Settle(mo->GetClass(), mo->FindState(NAME_Death));
			if (!look.rest)
			{
				DD_DebugPrintf(TEXTCOLOR_ORANGE "DDTM corpse %016" PRIx64 " %s has no resting %s frame, not restored\n", r.id, r.cls.GetChars(), r.death.GetChars());
				mo->Destroy();
				return;
			}
			mo->SetState(look.rest, true);
			if (look.sprite >= 0 && (look.rest->sprite == SPR_FIXED || look.rest->sprite == SPR_NOCHANGE)) mo->sprite = look.sprite;
			if (look.frame >= 0 && (look.rest->sprite == SPR_FIXED || look.rest->GetSameFrame())) mo->frame = look.frame;
			mo->ClearCounters();
			mo->flags &= ~(MF_SOLID | MF_SHOOTABLE | MF_FLOAT | MF_SKULLFLY);
			mo->flags |= MF_CORPSE | MF_DROPOFF;
			if (r.height > 0) mo->Height = r.height;
			else	// Daggerfall's saved record keeps no height: the class's own death height
			{
				IFVIRTUALPTR(mo, AActor, GetDeathHeight)
				{
					VMValue params[] = { mo };
					VMReturn ret(&mo->Height);
					VMCall(func, params, 1, &ret, 1);
				}
			}
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
			if (id == ids.end()) { id = ids.emplace(name, TexMan.CheckForTexture(name, ETextureType::Any)).first; DD_LightsTextureName(name, id->second); }
			const double gx = t.originX * DOOM_PER_DF + x, gy = t.originY * DOOM_PER_DF + y;
			townFlats[ChunkKey(int(floor(gx / chunkDoom)), int(floor(gy / chunkDoom)))].push_back({ id->second, gx, gy, z + t.ground * DOOM_PER_DF - Z_BASE, sx, sy, 0 });
		}
	}

	void SpawnFlats(FLevelLocals *Level, int cx, int cy)
	{
		if (runtimeTowns && !flatSpawned.insert(ChunkKey(cx, cy)).second) return;
		auto found = townFlats.find(ChunkKey(cx, cy));
		if (found == townFlats.end()) return;
		for (const TownFlat &f : found->second)
		{
			PClassActor *cls = f.npc && npcClass ? npcClass : flatClass;
			AActor *mo = Spawn(Level, cls, DVector3(f.x - originX * double(SPACING) - HALF, f.y - originY * double(SPACING) - HALF, f.z), NO_REPLACE);
			if (!mo) continue;
			mo->picnum = f.tex;
			mo->Scale = DVector2(f.sx, f.sy);
			if (f.npc && npcClass) DD_NpcSetup(mo, f.npc, false);
			else DD_LightsFlat(mo, false);
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
		if (DD_LocationsWorldWaiting()) return;	// After a load, Daggerfall's exterior chunks come first.
		while (!pending.empty() && budget > 0)
		{
			PendingChunk &p = pending.front();
			if (!ChunkInWindow(p.cx, p.cy)) { pending.pop_front(); continue; }
			if (!p.prepared)
			{
				BuildSeeds(p.cx, p.cy, p.seeds);
				SpawnFlats(Level, p.cx, p.cy);
				SpawnNatureChunk(Level, p.cx, p.cy);
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
				uint64_t variant = DD_LootSeedOf(s.id, 0x7370776eull);	// A mod's spawner picks the same variant every time.
				DDLootScope scope(&variant);
				if (AActor *mo = Spawn(Level, cls, pos, ALLOW_REPLACE))
				{
					// [Doomerfall] A mod's spawner (DRLA's RandomSpawners) hands the id to the monster it makes (DD_SpawnerHandoff).
					if (DD_IsDrlaSpawner(mo) || !(mo->flags3 & MF3_ISMONSTER)) mo->ddHandoffId = s.id;
					else mo->ddRecordId = s.id;
					mo->SpawnPoint = mo->Pos();	// Spawn() leaves it at zero, which made every seeded monster look moved.
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
			if (flatClass && mo->IsKindOf(flatClass)) continue;	// Billboards keep their exact height.
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
		DD_DebugPrintf("DDTCACHE index: %d location groups\n", int(groups.size()));
	}

	// The world-table slot of a place, from Daggerfall's keys only: 20 bits of map id, then for a building the block's
	// layout position (3 bits each, a location is at most 8 by 8 blocks) and its record index (8 bits). Dungeons use bit 34.
	uint64_t InteriorSlot(int mapId, int buildingKey)
	{
		const int x = (buildingKey >> 16) & 0xFF, y = (buildingKey >> 8) & 0xFF;
		if (x > 7 || y > 7) DD_DebugPrintf(TEXTCOLOR_ORANGE "DDTM building key %d of map %d is outside an 8 by 8 location\n", buildingKey, mapId);
		return (uint64_t(mapId & 0xFFFFF) << 14) | uint64_t((x & 7) << 11) | uint64_t((y & 7) << 8) | uint64_t(buildingKey & 0xFF);
	}
	uint64_t DungeonSlot(int mapId) { return (1ull << 34) | uint64_t(mapId & 0xFFFFF); }

	// Gives a space its own rectangle of world-table coordinates, beyond the 128,000-tile world. The rectangle comes from
	// the place's slot, so a place keeps its history when the converter numbers its spaces differently.
	void PlaceSpace(Town &t, int id, uint64_t slot, const FString &place)
	{
		const int tileX = (1 << 22) + int(slot & 0x3FFFF) * 1024, tileY = int(slot >> 18) * 1024;
		t.space = true;
		t.spaceId = id;
		t.place = place;
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
			FString text((const char *)data.data(), data.size());
			for (auto &line : text.Split("\n"))
			{
				char name[16];
				SpaceExit e;
				if (sscanf(line.GetChars(), "mapid %d", &t.dungeonMapId) == 1) continue;	// First, because "map %s" also matches this line.
				else if (sscanf(line.GetChars(), "map %15s", name) == 1) t.map = name;
				else if (sscanf(line.GetChars(), "exit %lf %lf %lf %lf %lf", &e.x, &e.y, &e.z, &e.nx, &e.ny) == 5) t.exits.push_back(e);
			}
			if (t.map.IsEmpty()) continue;
			if (!t.dungeonMapId) DD_DebugPrintf(TEXTCOLOR_ORANGE "DDTM dungeon %s has no map id; its history is kept under map id 0\n", t.map.GetChars());
			PlaceSpace(t, DUNGEON_SPACE + n, DungeonSlot(t.dungeonMapId), FStringf("D%d", t.dungeonMapId));
			towns.push_back(std::move(t));
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

	// [Doomerfall] The town entry for a dungeon converted during play, from its cache file's DDDUNGN.
	int TownForRuntimeDungeon(int group, const DDTownCache::EntryPtr &entry)
	{
		const auto *info = entry ? entry->Find("DDDUNGN") : nullptr;
		if (!info || !entry->Find("MAPWAD")) return -1;
		Town t;
		FString text((const char *)info->data(), info->size());
		for (auto &line : text.Split("\n"))
		{
			SpaceExit e;
			if (sscanf(line.GetChars(), "mapid %d", &t.dungeonMapId) == 1) continue;
			if (sscanf(line.GetChars(), "exit %lf %lf %lf %lf %lf", &e.x, &e.y, &e.z, &e.nx, &e.ny) == 5) t.exits.push_back(e);
		}
		if (DungeonGroup(t.dungeonMapId) != group) return -1;
		PlaceSpace(t, group, DungeonSlot(t.dungeonMapId), FStringf("D%d", t.dungeonMapId));
		t.map = SpaceMapName(group);
		DD_DebugPrintf("DDTM runtime dungeon %d is %s, %d exits\n", t.dungeonMapId, t.map.GetChars(), int(t.exits.size()));
		towns.push_back(std::move(t));
		return int(towns.size()) - 1;
	}

	// The town entry for an interior, built from its cache file.
	int TownForSpace(int id, const DDTownCache::EntryPtr &entry)
	{
		for (size_t i = 0; i < towns.size(); i++)
			if (towns[i].space && towns[i].spaceId == id) return int(i);
		if (id >= DUNGEON_GROUP) return TownForRuntimeDungeon(id, entry);
		const auto *info = entry ? entry->Find("DDTOWN") : nullptr;
		if (!info) return -1;
		Town t;
		FString text((const char *)info->data(), info->size());
		int mapId = 0, buildingKey = -1;
		for (auto &line : text.Split("\n"))
		{
			SpaceLanding l;
			SpaceExit e;
			if (sscanf(line.GetChars(), "entry %d %lf %lf %lf %lf", &l.index, &l.x, &l.y, &l.z, &l.yaw) == 5) t.landings.push_back(l);
			else if (sscanf(line.GetChars(), "exit %lf %lf %lf %lf %lf", &e.x, &e.y, &e.z, &e.nx, &e.ny) == 5) t.exits.push_back(e);
			else sscanf(line.GetChars(), "place %d %d", &mapId, &buildingKey);
		}
		if (t.landings.empty()) return -1;
		if (buildingKey < 0)	// The cache reader rebuilds such files, so this is a converter without place keys.
		{
			DD_DebugPrintf(TEXTCOLOR_RED "DDTM interior %d has no Daggerfall place key; refusing it so its history cannot land on another building\n", id);
			return -1;
		}
		PlaceSpace(t, id, InteriorSlot(mapId, buildingKey), FStringf("B%d:%d", mapId, buildingKey));
		t.buildingMapId = mapId;
		t.buildingKey = buildingKey;
		t.map = SpaceMapName(id);
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
		{
			id = flatTextures.emplace(name, TexMan.CheckForTexture(name, ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup)).first;
			DD_LightsTextureName(name, id->second);
		}
		return id->second;
	}

	//--------------------------------------------------------------------
	// [Doomerfall] Wilderness nature flats (dd_nature.cpp). Client-side actors, so a save never holds them: each chunk of
	// the overworld, and the ground around a generated town, gets its flats from the same rule whenever it is shown.
	//--------------------------------------------------------------------
	PClassActor *natureClass;
	std::unordered_map<int, std::vector<DDNatureFlat>> natureCache;	// key north * WORLD_W + px
	std::unordered_map<int64_t, std::vector<TObjPtr<AActor *>>> natureActors;	// by overworld chunk
	std::vector<TObjPtr<AActor *>> townNature;
	int natureSpawned;

	void LayoutNature(int px, int north, std::vector<DDNatureFlat> &out);
	// The pixel's 129 x 129 heights after location blending (valid until the next call), and its location rectangle.
	const float *PixelHeights(int px, int north, short *rect, bool &hasRect)
	{
		static std::vector<float> raw;
		auto loc = locRects.find(north * WORLD_W + px);
		hasRect = loc != locRects.end();
		if (hasRect)
		{
			rect[0] = loc->second.x0; rect[1] = loc->second.x1; rect[2] = loc->second.y0; rect[3] = loc->second.y1;
			return BlendedPixel(px, north, loc->second).data();
		}
		raw.resize(size_t(PIXEL_TILES + 1) * (PIXEL_TILES + 1));
		for (int x = 0; x <= PIXEL_TILES; x++)
			for (int y = 0; y <= PIXEL_TILES; y++) raw[size_t(x) * (PIXEL_TILES + 1) + y] = RawHeight(px, north, x, y);
		return raw.data();
	}

	const std::vector<DDNatureFlat> &NatureOf(int px, int north)
	{
		const int key = north * WORLD_W + px;
		auto found = natureCache.find(key);
		if (found != natureCache.end()) return found->second;
		if (natureCache.size() >= 16) natureCache.clear();
		std::vector<DDNatureFlat> &out = natureCache[key];
		LayoutNature(px, north, out);
		return out;
	}

	// The pixel's flats from the rule, without the cache (the distant view keeps its own).
	void LayoutNature(int px, int north, std::vector<DDNatureFlat> &out)
	{
		short rect[4];
		bool hasRect;
		const float *heights = PixelHeights(px, north, rect, hasRect);
		DDNature_Layout(px, north, heights, int(SmallAt(px, WORLD_H - 1 - north)), hasRect ? rect : nullptr, out);
	}

	// The flats whose tile corner lies in global tiles [gx0, gx1) x [gy0, gy1), and on the town's ground if one is given.
	void SpawnNature(FLevelLocals *Level, int gx0, int gx1, int gy0, int gy1, const Town *town, std::vector<TObjPtr<AActor *>> &into)
	{
		if (!natureClass) natureClass = PClass::FindActor("DFNatureFlat");
		if (!natureClass || !dd_natureflats || !DDNature_Load()) return;
		const bool winter = DDTownCache::IsWinter();
		for (int north = std::max(gy0 / PIXEL_TILES, 0); north <= std::min((gy1 - 1) / PIXEL_TILES, WORLD_H - 1); north++)
			for (int px = std::max(gx0 / PIXEL_TILES, 0); px <= std::min((gx1 - 1) / PIXEL_TILES, WORLD_W - 1); px++)
			{
				const int archive = DDNature_Archive(px, north, winter);
				FTextureID tex[32];
				for (int r = 0; r < 32; r++) tex[r] = FlatTexture(FStringf("dfflat/F%03dR%02d.png", archive, r).GetChars());
				for (const DDNatureFlat &f : NatureOf(px, north))
				{
					const int gx = px * PIXEL_TILES + f.x, gy = north * PIXEL_TILES + f.y;
					if (gx < gx0 || gx >= gx1 || gy < gy0 || gy >= gy1 || (town && !town->Near(gx, gy, town->margin))) continue;
					float sx, sy;
					if (!tex[f.record].isValid() || !DDNature_Scale(archive, f.record, sx, sy)) continue;
					const double z = (SampleVertex(gx, gy) + Z_BASE) / DOOM_PER_DF - f.sink;
					AActor *mo = Spawn(Level, natureClass, ToLocal(gx * 256.0, gy * 256.0, z), NO_REPLACE);
					if (!mo) continue;
					mo->picnum = tex[f.record];
					mo->Scale = DVector2(sx, sy);
					into.emplace_back();
					into.back() = mo;
					natureSpawned++;
				}
			}
	}

	void SpawnNatureChunk(FLevelLocals *Level, int cx, int cy)
	{
		auto &into = natureActors[ChunkKey(cx, cy)];
		if (into.empty()) SpawnNature(Level, cx * CHUNK_TILES, (cx + 1) * CHUNK_TILES, cy * CHUNK_TILES, (cy + 1) * CHUNK_TILES, nullptr, into);
	}

	// After a shift: flats in chunks that left the window go, and the rest move with it.
	void ShiftNature(const DVector3 &delta)
	{
		for (auto it = natureActors.begin(); it != natureActors.end();)
		{
			const bool keep = ChunkInWindow(int(uint32_t(it->first)), int(it->first >> 32));
			for (auto &ptr : it->second)
			{
				AActor *mo = ptr.Get();
				if (!mo) continue;
				if (!keep) { mo->Destroy(); continue; }
				FLinkContext ctx;
				mo->UnlinkFromWorld(&ctx);
				mo->SetXYZ(mo->Pos() - delta);
				mo->LinkToWorld(&ctx);
				mo->Prev -= delta;
			}
			it = keep ? std::next(it) : natureActors.erase(it);
		}
	}

	// [Doomerfall] Daggerfall's season changed (or first arrived after the overworld loaded): the ground tiles and the
	// nature flats in the window take the new season's sets now, not only as new chunks stream in.
	void RefreshSeason(FLevelLocals *Level)
	{
		RewriteGrid();
		for (auto &chunk : natureActors)
			for (auto &ptr : chunk.second)
				if (AActor *mo = ptr.Get()) mo->Destroy();
		natureActors.clear();
		for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)
			for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++) SpawnNatureChunk(Level, cx, cy);
		DD_DebugPrintf("DDTM season %s: ground and nature redrawn\n", groundWinter ? "winter" : "summer");
	}

	// [Doomerfall] Daggerfall's season changed while the player is in a town (or its first season line came after the
	// town loaded): the other season's conversion is requested, and once ready its mesh is drawn and the plain
	// billboards (trees, rocks, lamps) are replaced by its own. The map and the people (DFNpc, with their state) stay.
	void RefreshTownSeason(FLevelLocals *Level, int group)
	{
		if (group < 0 || !mapEntry || mapEntry->winter == DDTownCache::IsWinter()) return;
		if (Level->maptime % SCAN_TICS == 0) DDTownCache::Request(group, 0);
		const auto fresh = DDTownCache::Get(group);
		if (!fresh || fresh->winter != DDTownCache::IsWinter() || !fresh->Find("DFMESH")) return;
		mapEntry = fresh;
		PClassActor *flat = PClass::FindActor("DFCityFlat"), *npc = PClass::FindActor("DFNpc");
		const auto *body = fresh->Find("DFFLATS");
		int replaced = 0;
		if (flat && body)
		{
			std::vector<AActor *> old;
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next()) if (mo->GetClass() == flat) old.push_back(mo);
			for (AActor *mo : old) mo->Destroy();
			FString text((const char *)body->data(), body->size());
			for (auto &line : text.Split("\n"))
			{
				char name[40];
				double x, y, z;
				float sx, sy;
				uint64_t id = 0;
				if (sscanf(line.GetChars(), "%39s %lf %lf %lf %f %f %" SCNx64, name, &x, &y, &z, &sx, &sy, &id) < 6 || (id && npc)) continue;	// people are DFNpc, left as they are
				const FTextureID tex = FlatTexture(name);
				if (!tex.isValid()) continue;
				AActor *mo = Spawn(Level, flat, DVector3(x, y, z), NO_REPLACE);
				if (!mo) continue;
				mo->picnum = tex;
				mo->Scale = DVector2(sx, sy);
				DD_LightsFlat(mo, false);
				replaced++;
			}
		}
		DD_DebugPrintf("DDTOWN season %s: town mesh and %d billboards replaced\n", fresh->winter ? "winter" : "summer", replaced);
	}

	// A generated town's ground: the flats within its walkable margin.
	void SpawnTownNature(FLevelLocals *Level, const Town &t)
	{
		townNature.clear();
		if (t.space || t.rects.empty()) return;
		int x0 = std::numeric_limits<int>::max(), x1 = std::numeric_limits<int>::min(), y0 = x0, y1 = x1;
		for (const TileRect &r : t.rects) { x0 = std::min(x0, r.x0); x1 = std::max(x1, r.x1); y0 = std::min(y0, r.y0); y1 = std::max(y1, r.y1); }
		natureSpawned = 0;
		SpawnNature(Level, x0 - t.margin, x1 + t.margin, y0 - t.margin, y1 + t.margin, &t, townNature);
		DD_DebugPrintf("DDNATURE town %s flats=%d\n", t.map.GetChars(), natureSpawned);
	}

	// Fresh entry to a generated location: its billboards and gates. Saves restore these as ordinary actors.
	void SpawnTownContents(FLevelLocals *Level, bool interior)
	{
		if (!mapEntry) return;
		PClassActor *flat = PClass::FindActor("DFCityFlat"), *npc = PClass::FindActor("DFNpc");
		const bool awaitList = interior && DD_BridgeHasSession();	// Daggerfall says who is in a building.
		int spawned = 0, people = 0;
		if (const auto *body = mapEntry->Find("DFFLATS"); body && flat)
		{
			FString text((const char *)body->data(), body->size());
			for (auto &line : text.Split("\n"))
			{
				char name[40];
				double x, y, z;
				float sx, sy;
				uint64_t id = 0;
				if (sscanf(line.GetChars(), "%39s %lf %lf %lf %f %f %" SCNx64, name, &x, &y, &z, &sx, &sy, &id) < 6) continue;
				const FTextureID tex = FlatTexture(name);
				if (!tex.isValid()) continue;
				AActor *mo = Spawn(Level, id && npc ? npc : flat, DVector3(x, y, z), NO_REPLACE);
				if (!mo) continue;
				mo->picnum = tex;
				mo->Scale = DVector2(sx, sy);
				if (id && npc) { DD_NpcSetup(mo, id, awaitList); people++; }
				else DD_LightsFlat(mo, interior);
				spawned++;
			}
		}
		if (interior) DD_LightsInterior(Level);
		VMFunction *func = nullptr;
		PClass::FindFunction(&func, "DFRuntimeTown", "SpawnGates");
		const auto *gates = mapEntry->Find("DFGATES");
		if (func && gates && gates->size() > 1)
		{
			FString text((const char *)gates->data(), gates->size());
			VMValue params[] = { &text };
			VMCall(func, params, 1, nullptr, 0);
		}
		DD_DebugPrintf("DDTOWN contents billboards=%d npcs=%d\n", spawned, people);
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
		npcClass = PClass::FindActor("DFNpc");
		if (flatClass)
		{
			std::vector<AActor *> old;
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next()) if (mo->IsKindOf(flatClass)) old.push_back(mo);
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
					uint64_t id = 0;
					if (sscanf(line.GetChars(), "%39s %lf %lf %lf %f %f %" SCNx64, name, &x, &y, &z, &sx, &sy, &id) < 6) continue;
					const FTextureID tex = FlatTexture(name);
					if (!tex.isValid()) continue;
					const double gx = t.originX * DOOM_PER_DF + x, gy = t.originY * DOOM_PER_DF + y;
					townFlats[ChunkKey(int(floor(gx / chunkDoom)), int(floor(gy / chunkDoom)))].push_back({ tex, gx, gy, z + t.ground * DOOM_PER_DF - Z_BASE, sx, sy, id });
				}
			}
			for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)
				for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++)
					flatQueue.push_back(ChunkKey(cx, cy));
		}
		RewriteGrid();
		DD_DebugPrintf("DDTLOD town=%s ms=%.1f\n", lodTown >= 0 ? towns[lodTown].map.GetChars() : "none", NsSince(start) / 1e6);
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
			// [Doomerfall] after a season change the distant town stays drawn in the old season while the new one loads
			const bool shown = lodTown >= 0 && lodEntry && towns[lodTown].group == n;
			if (DDTownCache::Status(n) != DDTownCache::State::Ready && !shown) continue;
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
		if (bestLod >= 0 && bestLod == lodTown && lodEntry && lodEntry->winter != DDTownCache::IsWinter())	// [Doomerfall] new season ready: reload
			if (const auto fresh = DDTownCache::Get(towns[bestLod].group); fresh && fresh->winter == DDTownCache::IsWinter()) lodTown = -2;
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
			DD_DebugPrintf("DDTM failed to start\n");
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
	// The one place Daggerfall is told about a door transition. x and y are the outside door in world units.
	// Actions are the bridge's DFB_TRANSITION_* values.
	enum { TRANSITION_ENTER_BUILDING = 1, TRANSITION_EXIT_BUILDING, TRANSITION_ENTER_DUNGEON, TRANSITION_EXIT_DUNGEON };

	void NotifyTransition(int action, const char *from, const char *to, double x, double y, int target)
	{
		static const char *const names[] = { "", "enter-building", "exit-building", "enter-dungeon", "exit-dungeon" };
		DD_DebugPrintf("DDTRANSITION %s from=%s to=%s door=%.2f,%.2f target=%d\n", names[action], from, to, x, y, target);
		DD_BridgeTransition(action, x, y, target);
	}

	// The return point is one step out from the door, along the direction the player faces on leaving.
	DVector2 ReturnDoor()
	{
		const double yaw = returnPoint.yaw * M_PI / 180;
		return DVector2(returnPoint.x - cos(yaw) * EXIT_STEP / DOOM_PER_DF, returnPoint.y - sin(yaw) * EXIT_STEP / DOOM_PER_DF);
	}

	struct DoorTarget { double x, y, z, yaw; bool atMapStart; DDPlayerArea area; };

	void BeginHandoff(FLevelLocals *Level, AActor *pmo, const char *map, const int *warpTile = nullptr, const DoorTarget *door = nullptr)
	{
		Reconcile(Level);
		if (DDPlaceKey place; DD_BridgeHasSession() && DDTreadmill_CurrentSpace(place)) DD_LocationsLeaving(Level);	// Daggerfall's record of the place.
		std::vector<AActor *> keep;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (!mo->player && !IsOwned(mo) && ((mo->flags3 & MF3_ISMONSTER) || mo->IsKindOf(NAME_Inventory)))
				keep.push_back(mo);
		unchangedCount = 0;
		const int parkedBefore = parkCount;
		ParkAll(keep, originX, originY);
		DD_DebugPrintf("DDTM left %s: %d stored as changed, %d unchanged not stored, table rows %d\n", Level->MapName.GetChars(), parkCount - parkedBefore, unchangedCount, int(table.size()));
		if (DD_BridgeHasSession()) DD_LocationsLeftExterior(Level);	// Every exterior chunk this visit changed.

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
		handoff.area = DD_AREA_EXTERIOR;
		if (door)	// Through a door: world position in the destination's coordinates, standing still.
		{
			handoff.area = door->area;
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
		DD_DebugPrintf("DDSTITCH leave %s tic=%d world=%.2f,%.2f,%.2f vel=%.2f,%.2f,%.2f records=%d\n", Level->MapName.GetChars(), Level->maptime, world.X, world.Y, world.Z, pmo->Vel.X, pmo->Vel.Y, pmo->Vel.Z, int(table.size()));
		Level->ChangeLevel(map, 0, CHANGELEVEL_NOINTERMISSION | CHANGELEVEL_KEEPFACING | CHANGELEVEL_PRERAISEWEAPON);
	}

	// A fast travel arrival. Lands in the location's map when the point is inside its entry band, so the
	// player never stands in the overworld's flattened copy of a town.
	struct TravelRequest { bool pending = false; double x = 0, y = 0, yaw = 0; } travel;
	int dungeonRequest = -1;
	bool dungeonRequestHasStart = false;
	double dungeonRequestStart[4];
	struct BuildingRequest { bool pending = false; double x = 0, y = 0, tolerance = 0, start[4] = {}; } buildingRequest;	// [Doomerfall]

	void BeginTravel(FLevelLocals *Level, AActor *pmo)
	{
		travel.pending = false;
		const double tx = travel.x / 256, ty = travel.y / 256;
		int bestGroup = -1;
		double bestDist = 1e30;
		for (int n = 0; n < int(groups.size()); n++)
		{
			if (groups[n].tooLarge) continue;
			for (const TileRect &r : groups[n].rects)
			{
				const double dist = std::max({ r.x0 - tx, tx - r.x1, r.y0 - ty, ty - r.y1, 0.0 });
				if (dist < bestDist) { bestDist = dist; bestGroup = n; }
			}
		}
		int town = -1;
		if (bestGroup >= 0 && bestDist <= REQUEST_TILES)
		{
			const int candidate = TownForGroup(bestGroup, DDTownCache::GetBlocking(bestGroup));
			if (candidate >= 0 && towns[candidate].Near(tx, ty, towns[candidate].EntryMargin())) town = candidate;
		}
		returnPoint.valid = false;
		const double ground = town >= 0 ? towns[town].ground : (SampleVertex(int(floor(tx)), int(floor(ty))) + Z_BASE) / DOOM_PER_DF;
		const DoorTarget target{ travel.x, travel.y, ground, travel.yaw, false, DD_AREA_EXTERIOR };
		const FString map = town >= 0 ? towns[town].map : FString("DDOVER01");
		DD_DebugPrintf("DDTRAVEL to %s world=%.2f,%.2f yaw=%.1f\n", map.GetChars(), travel.x, travel.y, travel.yaw);
		BeginHandoff(Level, pmo, map.GetChars(), nullptr, &target);
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
		DD_DebugPrintf("DDSTITCH arrive %s ms=%.1f local=%.2f,%.2f,%.2f dz=%.3f records=%d stitches=%d\n", Level->MapName.GetChars(),
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
							DD_DebugPrintf("DDSEAM far tile=%d,%d f=%.2f,%.2f local=%.0f,%.0f floor=%.2f expected=%.2f sector=%d lines=%d center=%.0f,%.0f\n", gx, gy, fx, fy, lx, ly, actual, expected, sec->Index(), int(sec->Lines.Size()), sec->centerspot.X, sec->centerspot.Y);
						}
						if (err > worst) { worst = err; worstX = gx; worstY = gy; }
					}
				}
		DD_DebugPrintf("DDSEAM points=%d mean=%.4f worst=%.4f at tile %d,%d over0.1=%d over1=%d over10=%d\n", count, count ? sum / count : 0.0, worst, worstX, worstY, over01, over1, over10);
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
		DD_DebugPrintf("DDDOORS %d doors\n", int(townDoors.size()));
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
		if (!runtimeTowns) return -1;
		const int group = DungeonGroup(mapId);	// [Doomerfall] Converted during play.
		return DDTownCache::Status(group) == DDTownCache::State::Ready ? TownForSpace(group, DDTownCache::Get(group)) : -1;
	}

	// The cache group a town door needs: an interior's space id, or a dungeon's runtime group.
	int DoorGroup(const DoorSpot &d) { return d.kind == 0 ? d.target : DungeonGroup(d.target); }

	// Goes through a town door. False means the destination is not ready yet.
	bool EnterDoor(FLevelLocals *Level, AActor *pmo, const DoorSpot &d, const double *dungeonStart = nullptr)
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
			target = { landing->x / DOOM_PER_DF + space.originX, landing->y / DOOM_PER_DF + space.originY, landing->z / DOOM_PER_DF, landing->yaw, false, DD_AREA_INTERIOR };
			if (dungeonStart)	// [Doomerfall] Plain Daggerfall load: where the save had the player in the building.
				target = { dungeonStart[0] + space.originX, dungeonStart[1] + space.originY, dungeonStart[2], dungeonStart[3], false, DD_AREA_INTERIOR };
			map = space.map;
		}
		else
		{
			const int index = DungeonTown(d.target);
			if (index < 0) return false;
			const Town &space = towns[index];
			target = { space.originX, space.originY, 0, space.exits.empty() ? pmo->Angles.Yaw.Degrees() : atan2(space.exits[0].ny, space.exits[0].nx) * 180 / M_PI, true, DD_AREA_DUNGEON };
			if (dungeonStart)	// [Doomerfall] New Game: where Daggerfall placed the character, not the entrance.
			{
				target = { dungeonStart[0] + space.originX, dungeonStart[1] + space.originY, dungeonStart[2], dungeonStart[3], false, DD_AREA_DUNGEON };
				DD_DebugPrintf("DDNEWGAME dungeon start %.1f,%.1f,%.1f yaw %.1f\n", dungeonStart[0], dungeonStart[1], dungeonStart[2], dungeonStart[3]);
			}
			map = space.map;
		}
		const Town &origin = towns[currentTown];	// TownForSpace can grow the list.
		returnPoint.valid = true;
		returnPoint.map = fromMap;
		returnPoint.x = (d.x + d.nx * EXIT_STEP) / DOOM_PER_DF + origin.originX;
		returnPoint.y = (d.y + d.ny * EXIT_STEP) / DOOM_PER_DF + origin.originY;
		returnPoint.z = d.z / DOOM_PER_DF + origin.ground;
		returnPoint.yaw = atan2(d.ny, d.nx) * 180 / M_PI;
		const DVector2 door = ReturnDoor();
		NotifyTransition(d.kind == 0 ? TRANSITION_ENTER_BUILDING : TRANSITION_ENTER_DUNGEON, fromMap.GetChars(), map.GetChars(), door.X, door.Y, d.target);
		BeginHandoff(Level, pmo, map.GetChars(), nullptr, &target);
		return true;
	}

	void TickTownDoors(FLevelLocals *Level, AActor *pmo)
	{
		const bool down = (pmo->player->cmd.buttons & BT_USE) != 0, fresh = down && !useHeld;
		bool pressed = fresh || dd_tm_use != 0 || (doorPressTic >= 0 && gametic - doorPressTic <= 1);
		doorPressTic = -1;
		useHeld = down;
		if (dd_tm_use != 0) dd_tm_use = 0;
		if (handoff.pending || pmo->health <= 0 || DD_BridgeArrivalFrozen()) return; // A press during the arrival wait is dropped.
		if (DD_LoadingActive()) pressed = false; // [Doomerfall] A press behind the loading screen is dropped; a pending door still opens.
		else if (fresh && DD_UsePress(pmo->player)) pressed = false; // An item in view takes the press.
		const Town &t = towns[currentTown];
		if (t.space)
		{
			if (runtimeTowns && returnPoint.valid && Level->maptime % SCAN_TICS == 0)	// After a load indoors, the town is read in the background.
				if (const int home = GroupOfMap(returnPoint.map.GetChars()); home >= 0)
				{
					DDTownCache::BeginScan();
					DDTownCache::Request(home, 0);
				}
			if (!pressed || !returnPoint.valid) return;
			double distance;
			for (const SpaceExit &e : t.exits)
				if (CanUse(pmo, e.x, e.y, e.z, e.nx, e.ny, distance))
				{
					const DoorTarget target{ returnPoint.x, returnPoint.y, returnPoint.z, returnPoint.yaw, false, DD_AREA_EXTERIOR };
					const FString back = returnPoint.map;
					const DVector2 door = ReturnDoor();
					returnPoint.valid = false;
					NotifyTransition(t.spaceId >= DUNGEON_SPACE ? TRANSITION_EXIT_DUNGEON : TRANSITION_EXIT_BUILDING, t.map.GetChars(), back.GetChars(), door.X, door.Y, t.spaceId);
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
				if (d.kind == 0 || DungeonTown(d.target) < 0)	// [Doomerfall] and dungeons not converted yet
				{
					const double dist = (DVector2(d.x, d.y) - pmo->Pos().XY()).Length();
					if (dist < 768) near.push_back({ dist, DoorGroup(d) });
				}
			std::sort(near.begin(), near.end());
			DDTownCache::BeginScan();
			int requested = 0, lastId = -1;
			for (auto &n : near)
				if (n.second != lastId && requested < DOOR_PREFETCH) { DDTownCache::Request(n.second, n.first + 1); lastId = n.second; requested++; }
			if (pendingDoor >= 0) DDTownCache::Request(DoorGroup(townDoors[pendingDoor]), 0);
			if (dungeonRequest >= 0) DDTownCache::Request(DungeonGroup(dungeonRequest), 0);	// New Game or a load into a dungeon not converted yet	// Last, so the pressed door outranks prefetching.
		}
		if (pendingDoor >= 0)
		{
			const DoorSpot d = townDoors[pendingDoor];
			if ((DVector2(d.x, d.y) - pmo->Pos().XY()).Length() > DOOR_CANCEL) { Printf(PRINT_HIGH, "You left the door.\n"); pendingDoor = -1; }
			else if (DDTownCache::Status(DoorGroup(d)) == DDTownCache::State::Failed) { Printf(PRINT_HIGH, "This door will not open.\n"); pendingDoor = -1; }
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
		if (best < 0) { if (fresh) DD_UseWall(pmo->player); return; }	// Use on a building's wall names it, as Daggerfall's Info does.
		const DoorSpot d = townDoors[best];
		if (d.kind == 1 && DungeonTown(d.target) < 0 && !runtimeTowns) { Printf(PRINT_HIGH, "This dungeon is not available yet.\n"); return; }
		if (EnterDoor(Level, pmo, d)) return;
		pendingDoor = best;
		DDTownCache::Request(DoorGroup(d), 0);
		Printf(PRINT_HIGH, "Opening...\n");
	}

	// Keeps the outdoor location in memory while the player is in it or in one of its interiors.
	void PinHomeTown(const Town &t)
	{
		if (!runtimeTowns) return;
		DDTownCache::Pin(t.group >= 0 ? t.group : t.space && returnPoint.valid ? GroupOfMap(returnPoint.map.GetChars()) : -1);
	}

	uint64_t MixId(uint64_t h, uint64_t v)
	{
		h ^= v + 0x9E3779B97F4A7C15ull + (h << 6) + (h >> 2);
		h ^= h >> 30; h *= 0xBF58476D1CE4E5B9ull;
		h ^= h >> 27; h *= 0x94D049BB133111EBull;
		return h ^ (h >> 31);
	}

	// Gives each item the map placed a stable id: the map and the item's index in map order (thinkers are created in
	// the map's thing order, and a marker spawns its item as it is created), so the same item gets the same id on every
	// visit and Daggerfall's record keeps a taken map item as one bit (MAP_ITEM_INDEX_BITS).
	int AssignMapItemIds(FLevelLocals *Level)
	{
		uint64_t place = 0xCBF29CE484222325ull;
		for (const char *c = Level->MapName.GetChars(); *c; c++) place = (place ^ uint8_t(toupper(*c))) * 0x100000001B3ull;
		place = MixId(place, 0x4D41504954454D53ull) & MAP_ITEM_PLACE_MASK;
		int count = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			// Everything loose at map start is the map's, before the rows are restored. MF_DROPPED cannot tell: items a
			// map marker spawns keep it (Inventory.BeginPlay sets it, and only map things clear it in LevelSpawned).
			if (mo->ddRecordId || mo->player || !mo->IsKindOf(NAME_Inventory) || IsOwned(mo)) continue;
			if (count >= (1 << MAP_ITEM_INDEX_BITS)) break;
			const DVector3 w = ToWorld(mo->Pos(), originX, originY);
			const uint64_t id = MAP_ITEM_TAG | (place << MAP_ITEM_INDEX_BITS) | uint64_t(count);
			mo->ddRecordId = id;
			mo->SpawnPoint = mo->Pos();
			itemSpots[id] = w;
			expected.insert(id);	// So a take becomes a tombstone (Reconcile).
			count++;
		}
		return count;
	}

	// After a load: a kept actor is expected again, and a map item gets back where it stood (not in the save), so a take
	// after the load still has its spot.
	void ExpectLoaded(AActor *mo)
	{
		const uint64_t id = mo->ddRecordId;
		expected.insert(id);
		if (IsMapItemId(id)) itemSpots.emplace(id, ToWorld(mo->SpawnPoint, originX, originY));
	}

	void StartTown(FLevelLocals *Level, int index)
	{
		if (multiplayer || !LoadWorld()) return;
		currentTown = index;
		townActive = true;
		dd_tm_intown = 1;
		resumedSnapshot = false;
		expected.clear();
		pending.clear();
		const Town &t = towns[index];
		pendingDoor = -1;
		useHeld = true;	// The press that opened the door must not also use the door on the far side.
		PinHomeTown(t);
		LoadTownDoors(t);
		const int mapItems = AssignMapItemIds(Level);
		// What the map places by default stays unless the table has a row for it (taken, moved, changed). On a revisit,
		// map things without an id, such as a mod's spawner standing in for a monster, came back from the table instead.
		const bool firstVisit = t.space && !visitedSpaces.count(t.place.GetChars());
		if (t.space) visitedSpaces.insert(t.place.GetChars());
		int replaced = 0;
		{
			std::vector<AActor *> stale;
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next())
			{
				if (mo->player || IsOwned(mo) || !((mo->flags3 & MF3_ISMONSTER) || mo->IsKindOf(NAME_Inventory)
					|| (GetDefaultByType(mo->GetClass()->GetReplacee(Level))->flags3 & MF3_ISMONSTER))) continue;
				if (mo->ddRecordId ? table.count(mo->ddRecordId) != 0 : t.space && !firstVisit) stale.push_back(mo);
			}
			for (AActor *mo : stale) { expected.erase(mo->ddRecordId); mo->Destroy(); }
			replaced = int(stale.size());
		}
		int restored = 0;
		unchangedCount = missingClassCount = 0;
		for (auto &kv : table)
		{
			const Record &r = kv.second;
			if (r.kind == KGone || !t.Near(r.x / 256, r.y / 256, t.margin - 1)) continue;
			Restore(Level, r);
			restored++;
		}
		// After the rows, so a monster the table brought back counts as present and is not placed twice. With a bridge,
		// Daggerfall's record of the place is applied before any mook is planned (DD_LocationsTick, then ApplyRows).
		if (DDPlaceKey place; t.space && DD_BridgeHasSession() && DDTreadmill_CurrentSpace(place)) DD_LocationsEntered(place);
		if (t.space && t.spaceId >= DUNGEON_SPACE) DD_MonstersEnterDungeon(Level, t.dungeonMapId, firstVisit, DD_BridgeHasSession());
		if (t.space) DD_DebugPrintf("DDTM place %s map %s %s: map items %d, replaced by rows %d, restored %d, missing classes %d\n", t.place.GetChars(), t.map.GetChars(),
			firstVisit ? "first visit" : "revisit", mapItems, replaced, restored, missingClassCount);
		if (t.group >= 0 || (t.space && t.spaceId < DUNGEON_SPACE)) SpawnTownContents(Level, t.space);
		SpawnTownNature(Level, t);
		FinishHandoff(Level);
		if (FindArg("-ddtmverify")) VerifySeam(Level, t);
		DD_DebugPrintf("DDTOWN active %s restored=%d records=%d\n", t.map.GetChars(), restored, int(table.size()));
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
		if (runtimeTowns) DDTownCache::Pin(-1);
		const bool returning = handoff.pending;
		if (!returning)
		{
			table.clear();
			buckets.clear();
			visitedSpaces.clear();
			DD_MonstersLoadPlans("");
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
		DD_DebugPrintf("DDTM active origin=%d,%d spacing=%d sectors=%d packs=%.2f/%d\n", originX, originY, SPACING, int(tris.size()), packChance, packSize);
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
			PinHomeTown(towns[town]);
			LoadTownDoors(towns[town]);
			SpawnTownNature(Level, towns[town]);	// never saved, so laid out again
			expected.clear();
			auto it = Level->GetThinkerIterator<AActor>();
			while (AActor *mo = it.Next())
				if (mo->ddRecordId && !IsOwned(mo)) ExpectLoaded(mo);
			// The save keeps no world table, so without Daggerfall's record leaving would forget what is gone (taken
			// pickups). The snapshot stands; the record only refills the cache behind it (DDTreadmill_ApplyPlace).
			resumedSnapshot = towns[town].space;
			if (DDPlaceKey place; resumedSnapshot && DD_BridgeHasSession() && DDTreadmill_CurrentSpace(place)) DD_LocationsEntered(place);
			DD_DebugPrintf("DDTOWN resumed %s records=%d\n", Level->MapName.GetChars(), int(table.size()));
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
			if (mo->ddRecordId && !IsOwned(mo)) ExpectLoaded(mo);
		SettleActors(Level, false);
		for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)	// nature is never saved
			for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++) SpawnNatureChunk(Level, cx, cy);
		DDTreadmill_Active = true;
		groundWinter = !DDTownCache::IsWinter();	// [Doomerfall] the next tick redraws the ground: the save may hold older floors
		int drawn = 0;
		for (auto &t : tris) drawn += t.sec->GetTexture(sector_t::floor).isValid();
		DD_DebugPrintf("DDTM resumed origin=%d,%d records=%d pending=%d floors drawn=%d of %d\n", originX, originY, int(table.size()), int(pending.size()), drawn, int(tris.size()));
	}

	FString EncodeState(bool rows = true)
	{
		FString out;
		out.AppendFormat("%d %d %d %llu %d\n", originX, originY, shifts, (unsigned long long)nextDynamic, int(pending.size()));
		for (auto &p : pending) out.AppendFormat("%d %d\n", p.cx, p.cy);
		if (rows) for (auto &kv : table)
		{
			const Record &r = kv.second;
			out.AppendFormat("%llu %s %s %.17g %.17g %.17g %.17g %.17g %d %d %d %d\n", (unsigned long long)r.id, r.cls.GetChars(),
				r.death.IsEmpty() ? "-" : r.death.GetChars(), r.x, r.y, r.z, r.angle, r.height, r.health, r.kind, r.amount, int(r.dropped));
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
		char cls[128], death[128];
		unsigned long long id;
		int dropped;
		Record r;
		while (nextLine() && sscanf(line, "%llu %127s %127s %lf %lf %lf %lf %lf %d %d %d %d", &id, cls, death, &r.x, &r.y, &r.z, &r.angle, &r.height,
			&r.health, &r.kind, &r.amount, &dropped) >= 12)
		{
			r.id = id;
			r.cls = FName(cls);
			r.death = strcmp(death, "-") ? death : "";
			r.dropped = dropped != 0;
			Store(r);
		}
		dirtyChunks.clear();	// The table came from a save, and Daggerfall's ledger from the same one.
		resumePending = true;
	}
}

//--------------------------------------------------------------------
// Location ledger (dd_locations.cpp): Daggerfall holds each dungeon's record, and this table is its cache.
//--------------------------------------------------------------------

namespace
{
	// A Doom drop or a replacement item: an id this session made up, which means nothing to Daggerfall.
	bool IsSessionId(uint64_t id) { return (id & (TAG_MASK | SESSION_MARK)) == SESSION_ID; }
	bool InPlace(const Record &r, const Town &t) { return t.Near(r.x / 256, r.y / 256, t.margin - 1); }

	DDPlaceFact ToFact(const Record &r, const Town &t)
	{
		DDPlaceFact f;
		f.id = r.id;
		f.cls = r.cls;
		f.death = r.death;
		f.x = r.x - t.originX;
		f.y = r.y - t.originY;
		f.z = r.z - t.ground;
		f.angle = r.angle;
		f.height = r.height;
		f.health = r.health;
		f.kind = r.kind;
		f.amount = r.amount;
		f.dropped = r.dropped;
		f.session = IsSessionId(r.id) && !DD_LootGunKeepsId(r.id, r.cls);	// [Doomerfall] a floor gun keeps its lasting id
		return f;
	}

	Record FromFact(const DDPlaceFact &f, const Town &t)
	{
		Record r;
		r.id = f.id;
		r.cls = f.cls;
		r.death = f.death;
		r.x = f.x + t.originX;
		r.y = f.y + t.originY;
		r.z = f.z + t.ground;
		r.angle = f.angle;
		r.height = f.height;
		r.health = f.health;
		r.kind = f.kind;
		r.amount = f.amount;
		r.dropped = f.dropped;
		return r;
	}

	// A fact as the bridge carries it (floats, 65536 angle steps), so Doom's cache and Daggerfall's copy compare equal.
	std::string Canon(const DDPlaceFact &f)
	{
		double turns = f.angle / 360.0;
		turns -= floor(turns);
		FString id = f.session ? FString("S") : FStringf("%016" PRIx64, f.id);
		FString s = FStringf("%d %s %s %s %.2f %.2f %.2f %d %.1f %d %d %d", f.kind, id.GetChars(), f.cls.GetChars(), f.death.GetChars(),
			double(float(f.x)), double(float(f.y)), double(float(f.z)), int(llround(turns * 65536) & 0xFFFF), double(float(f.height)), f.health, f.amount, int(f.dropped));
		return s.GetChars();
	}

	void DDTreadmill_TestDropTable()
	{
		Printf("DDLOC test: loading without Doom's world table (%d rows, %d visited places dropped)\n", int(table.size()), int(visitedSpaces.size()));
		table.clear();
		buckets.clear();
		visitedSpaces.clear();
		DD_MonstersLoadPlans("");
		dd_tm_records = 0;
		dirtyChunks.clear();
	}
}

bool DDTreadmill_CurrentSpace(DDPlaceKey &place)
{
	if (!townActive || currentTown < 0 || currentTown >= int(towns.size())) return false;
	const Town &t = towns[currentTown];
	if (!t.space) return false;
	if (t.spaceId >= DUNGEON_SPACE) place = DDPlaceKey{ DFB_PLACE_DUNGEON, t.dungeonMapId, 0 };
	else if (t.buildingKey >= 0) place = DDPlaceKey{ DFB_PLACE_INTERIOR, t.buildingMapId, t.buildingKey };
	else return false;
	return true;
}

bool DDTreadmill_CurrentDungeon(int &mapId)
{
	if (!townActive || currentTown < 0 || currentTown >= int(towns.size())) return false;
	const Town &t = towns[currentTown];
	if (!t.space || t.spaceId < DUNGEON_SPACE) return false;
	mapId = t.dungeonMapId;
	return true;
}

// [Doomerfall] Hinged doors keep their position: one fact whose name text is door_objects.zs's "<stamp> <bits>".
static FString DoorRecord()
{
	VMFunction *func = nullptr;
	FString text;
	PClass::FindFunction(&func, "DFDoorHandler", "Distill");
	if (func) { VMReturn ret(&text); VMCall(func, nullptr, 0, &ret, 1); }
	return text;
}

static void RestoreDoors(const char *place, FString text)
{
	VMFunction *func = nullptr;
	int open = -2;
	PClass::FindFunction(&func, "DFDoorHandler", "Restore");
	if (func) { VMValue params[] = { &text }; VMReturn ret(&open); VMCall(func, params, 1, &ret, 1); }
	if (open >= 0) Printf("DDLOC %s: doors restored, %d open\n", place, open);
	else Printf("DDLOC %s: the doors were recorded from another conversion; they reset\n", place);
}

// The current dungeon's record as it stands: its cached rows, overridden by what every live actor would park as.
void DDTreadmill_SnapshotPlace(FLevelLocals *Level, std::vector<DDPlaceFact> &out)
{
	out.clear();
	DDPlaceKey place;
	if (!DDTreadmill_CurrentSpace(place)) return;
	const Town &t = towns[currentTown];
	Reconcile(Level);
	std::unordered_map<uint64_t, Record> rows;
	for (auto &kv : table)
		if (InPlace(kv.second, t)) rows[kv.first] = kv.second;
	uint64_t temp = 0;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (mo->player || IsOwned(mo)) continue;
		Record r;
		switch (MakeRecord(mo, originX, originY, r))
		{
		case Parked::Stored:
			if (!r.id) r.id = SESSION_ID | (1ull << 59) | ++temp;	// Park would give it a session id too.
			rows[r.id] = r;
			break;
		case Parked::Gone:	// As MarkGone: a tombstone, except for ids that are not kept.
			if (!r.id) break;
			if (r.id & DYNAMIC_BIT) rows.erase(r.id);
			else
			{
				auto old = rows.find(r.id);
				Record gone = old != rows.end() ? old->second : r;
				gone.kind = KGone;
				rows[r.id] = gone;
			}
			break;
		default:
			break;
		}
	}
	out.reserve(rows.size() + 1);
	for (auto &kv : rows) out.push_back(ToFact(kv.second, t));
	DDPlaceFact doors;
	doors.death = DoorRecord();
	doors.kind = DFB_FACT_DOORS;
	doors.cls = "DFDOORS";
	if (doors.death.IsNotEmpty()) out.push_back(doors);
}

// Daggerfall's record of the dungeon just entered. When Doom's cache already holds the same facts, nothing changes.
// Otherwise (the cache is gone or older, as after a load without the world table) the place is rebuilt from the
// record: what the cache restored is removed, and every fact is applied. Mooks the record does not list are spawned
// afterwards by the encounter plan, as on any visit.
void DDTreadmill_ApplyPlace(FLevelLocals *Level, const DDPlaceKey &place, const std::vector<DDPlaceFact> &record)
{
	DDPlaceKey current;
	if (!DDTreadmill_CurrentSpace(current) || !(current == place))
	{
		Printf(TEXTCOLOR_ORANGE "DDLOC record of place kind %u %d:%d arrived outside that place; ignored\n", place.kind, place.mapId, place.key);
		return;
	}
	const Town &t = towns[currentTown];
	const char *name = t.place.GetChars();
	visitedSpaces.insert(t.place.GetChars());
	std::vector<DDPlaceFact> facts;
	for (const DDPlaceFact &f : record)
		if (f.kind != DFB_FACT_DOORS) facts.push_back(f);
		else RestoreDoors(name, f.death);
	std::vector<uint64_t> oldIds;
	std::vector<std::string> mine, theirs;
	for (auto &kv : table)
		if (InPlace(kv.second, t)) { oldIds.push_back(kv.first); mine.push_back(Canon(ToFact(kv.second, t))); }
	for (const DDPlaceFact &f : facts) theirs.push_back(Canon(f));
	std::sort(mine.begin(), mine.end());
	std::sort(theirs.begin(), theirs.end());
	if (mine == theirs)
	{
		Printf("DDLOC %s: Doom's cache matches Daggerfall's record (%d facts)\n", name, int(facts.size()));
		return;
	}
	// A save made in this place: its snapshot came back with the live actors (and their record ids), but the save keeps
	// no world table. The snapshot stands (architecture.md, Saves); Daggerfall's record only refills the cache behind it.
	if (mine.empty())
	{
		std::unordered_set<uint64_t> recorded;
		for (const DDPlaceFact &f : facts)
			if (!f.session && (f.kind == KMonster || f.kind == KCorpse)) recorded.insert(f.id);
		int live = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (!mo->player && mo->ddRecordId && !IsOwned(mo) && recorded.count(mo->ddRecordId)) live++;
		if (live > 0 || resumedSnapshot)	// Resumed: the snapshot stands even when only map items differ (a take).
		{
			resumedSnapshot = false;
			int stored = 0;
			for (const DDPlaceFact &f : facts)
			{
				if (f.session) continue;	// a drop in the snapshot keeps its own session id; leaving records it again
				Store(FromFact(f, t));
				stored++;
			}
			Printf("DDLOC %s: the save's snapshot stands (%d of the record's monsters and corpses are live); %d facts refill the cache, nothing rebuilt\n",
				name, live, stored);
			return;
		}
	}
	std::unordered_set<uint64_t> replace(oldIds.begin(), oldIds.end());
	for (const DDPlaceFact &f : facts) if (!f.session) replace.insert(f.id);
	std::vector<AActor *> stale;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
		if (!mo->player && mo->ddRecordId && !IsOwned(mo) && replace.count(mo->ddRecordId)) stale.push_back(mo);
	for (AActor *mo : stale) { expected.erase(mo->ddRecordId); mo->Destroy(); }
	for (uint64_t id : oldIds)
	{
		auto row = table.find(id);
		if (row == table.end()) continue;
		if (row->second.kind != KGone) Unbucket(row->second);
		table.erase(row);
	}
	int restored = 0, gone = 0;
	missingClassCount = 0;
	for (const DDPlaceFact &f : facts)
	{
		Record r = FromFact(f, t);
		if (f.session) { int k = 0; while ((r.id = DD_LootRestoredGunId(r.cls, r.x, r.y, r.z, k++)) && table.count(r.id)) {} if (!r.id) r.id = SESSION_ID | ++nextDynamic; }	// [Doomerfall] a gun gets a lasting id
		Store(r);
		if (r.kind == KGone) { gone++; continue; }
		Restore(Level, r);
		restored++;
	}
	Printf("DDLOC %s: rebuilt from Daggerfall's record (Doom's cache had %d rows, the record %d): removed %d, restored %d, gone %d, missing classes %d\n",
		name, int(mine.size()), int(facts.size()), int(stale.size()), restored, gone, missingClassCount);
}


namespace
{
	constexpr double CHUNK_DF = DFB_CHUNK_UNITS;
	static_assert(DFB_CHUNK_UNITS == int(DF_PER_CHUNK), "the bridge's exterior chunk is the world table's chunk");

	DDPlaceFact ToChunkFact(const Record &r, int cx, int cy)
	{
		Town frame;
		frame.originX = cx * CHUNK_DF;
		frame.originY = cy * CHUNK_DF;
		frame.ground = 0;
		return ToFact(r, frame);
	}

	Record FromChunkFact(const DDPlaceFact &f, int cx, int cy)
	{
		Town frame;
		frame.originX = cx * CHUNK_DF;
		frame.originY = cy * CHUNK_DF;
		frame.ground = 0;
		return FromFact(f, frame);
	}

	bool ExteriorMapRunning()
	{
		return DDTreadmill_Active || (townActive && currentTown >= 0 && currentTown < int(towns.size()) && !towns[currentTown].space);
	}

	// True when a row at this spot has (or had) a live actor on the running map: a town map restores rows inside its
	// place, the overworld every chunk of its window that is not still waiting to be built.
	bool LiveAt(const Record &r)
	{
		if (!IsExterior(r)) return false;
		if (townActive) return currentTown >= 0 && currentTown < int(towns.size()) && !towns[currentTown].space && InPlace(r, towns[currentTown]);
		if (!DDTreadmill_Active) return false;
		const int cx = int(floor(r.x / DF_PER_CHUNK)), cy = int(floor(r.y / DF_PER_CHUNK));
		if (!ChunkInWindow(cx, cy)) return false;
		for (const PendingChunk &p : pending)
			if (p.cx == cx && p.cy == cy && !p.prepared) return false;
		return true;
	}
}

void DDTreadmill_ForgetDirtyChunks() { dirtyChunks.clear(); }

// Every exterior chunk whose facts changed since the last report: the chunks the table changed in, and on a running
// exterior map the chunks of every actor that would park as a row. Each chunk's facts are complete: its cached rows,
// overridden by what every live actor would park as.
void DDTreadmill_SnapshotChunks(FLevelLocals *Level, std::vector<DDChunkFacts> &out)
{
	out.clear();
	std::unordered_set<int64_t> chunks = dirtyChunks;
	std::vector<Record> live, gone;
	if (ExteriorMapRunning() && Level)
	{
		Reconcile(Level);
		uint64_t temp = 0;
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (mo->player || IsOwned(mo)) continue;
			Record r;
			const Parked decided = MakeRecord(mo, originX, originY, r);
			if (decided != Parked::Stored && (decided != Parked::Gone || !r.id)) continue;
			if (!IsExterior(r)) continue;
			if (!r.id) r.id = SESSION_ID | (1ull << 59) | ++temp;
			chunks.insert(RecordChunk(r));
			if (auto old = table.find(r.id); old != table.end() && IsExterior(old->second)) chunks.insert(RecordChunk(old->second));	// it may have walked out of its chunk
			(decided == Parked::Stored ? live : gone).push_back(r);
		}
	}
	dirtyChunks.clear();
	if (chunks.empty()) return;
	std::unordered_map<uint64_t, Record> rows;
	for (auto &kv : table)
		if (IsExterior(kv.second) && chunks.count(RecordChunk(kv.second))) rows[kv.first] = kv.second;
	for (const Record &r : live) rows[r.id] = r;
	for (const Record &r : gone)	// As MarkGone: a tombstone, except for ids that are not kept.
	{
		if (r.id & DYNAMIC_BIT) { rows.erase(r.id); continue; }
		auto old = rows.find(r.id);
		Record g = old != rows.end() ? old->second : r;
		g.kind = KGone;
		rows[r.id] = g;
	}
	std::vector<int64_t> order(chunks.begin(), chunks.end());
	std::sort(order.begin(), order.end());
	std::unordered_map<int64_t, size_t> slot;
	for (int64_t key : order)
	{
		slot[key] = out.size();
		out.push_back({ int(uint32_t(key)), int(key >> 32), {} });
	}
	for (auto &kv : rows)
	{
		auto s = slot.find(RecordChunk(kv.second));
		if (s == slot.end()) continue;
		DDChunkFacts &c = out[s->second];
		c.facts.push_back(ToChunkFact(kv.second, c.cx, c.cy));
	}
}

// One exterior chunk's record from Daggerfall's ledger, after a load. When Doom's cache holds the same facts, nothing
// changes. Otherwise the cache's rows of the chunk are replaced by the record's. A row whose actor is live on the
// running map stays as Doom restored it from the save (which Daggerfall's ledger came from too); only tombstones are
// added there. Nothing is spawned here: the town map or the overworld window builds the chunk from the table.
void DDTreadmill_ApplyChunk(FLevelLocals *Level, int cx, int cy, const std::vector<DDPlaceFact> &facts, DDChunkApplyStats &stats)
{
	const int64_t key = ChunkKey(cx, cy);
	std::vector<uint64_t> oldIds;
	std::vector<std::string> mine, theirs;
	for (auto &kv : table)
		if (IsExterior(kv.second) && RecordChunk(kv.second) == key) { oldIds.push_back(kv.first); mine.push_back(Canon(ToChunkFact(kv.second, cx, cy))); }
	for (const DDPlaceFact &f : facts) theirs.push_back(Canon(f));
	std::sort(mine.begin(), mine.end());
	std::sort(theirs.begin(), theirs.end());
	if (mine == theirs) { stats.matched++; return; }
	stats.rebuilt++;
	quietStore = true;
	for (uint64_t id : oldIds)
	{
		if (expected.count(id)) continue;	// its actor is live; Park will store it
		auto row = table.find(id);
		if (row == table.end()) continue;
		if (row->second.kind != KGone) Unbucket(row->second);
		table.erase(row);
		stats.removed++;
	}
	for (const DDPlaceFact &f : facts)
	{
		Record r = FromChunkFact(f, cx, cy);
		if (!f.session && expected.count(r.id)) { stats.keptLive++; continue; }
		if (LiveAt(r) && (r.kind != KGone || f.session)) { stats.keptLive++; continue; }
		if (f.session) { int k = 0; while ((r.id = DD_LootRestoredGunId(r.cls, r.x, r.y, r.z, k++)) && table.count(r.id)) {} if (!r.id) r.id = SESSION_ID | ++nextDynamic; }	// [Doomerfall] a gun gets a lasting id
		Store(r);
		stats.stored++;
	}
	quietStore = false;
	dd_tm_records = int(table.size());
	Printf("DDLOC O%d,%d: rebuilt from Daggerfall's record (Doom's cache had %d rows, the record %d)\n", cx, cy, int(mine.size()), int(facts.size()));
}

// The overworld's terrain sectors are rewritten from Daggerfall's height map on every load (Resume -> PrepareLevel), so
// a save need not carry them. UZDoom saves sectors as differences from loadsectors; copying the treadmill-owned fields
// there makes the writer skip them. On DDOVER01 they are 88% of a save (5.45 MB of json, 1.33 MB packed).
void DDTreadmill_PrepareSectorSave(FLevelLocals *Level)
{
	if (!DDTreadmill_Active || townActive || Level != primaryLevel || Level->loadsectors.Size() != Level->sectors.Size()) return;
	for (auto &t : tris)
	{
		sector_t &base = Level->loadsectors[t.sec->Index()];
		base.floorplane = t.sec->floorplane;
		base.ceilingplane = t.sec->ceilingplane;
		for (int k = 0; k < 2; k++) base.planes[k] = t.sec->planes[k];
	}
	Printf("DDTM save skips the terrain of %d sectors (rebuilt on load)\n", int(tris.size()));
}

void DDTreadmill_Serialize(FLevelLocals *Level, FSerializer &arc)
{
	if (arc.isReading()) DD_LightsReset();	// [Doomerfall] lamps come back as they were saved
	if (arc.isWriting())
	{
		if ((!DDTreadmill_Active && !townActive) || Level != primaryLevel) return;
		Reconcile(Level);
		// Daggerfall's location record is the only saved copy of every place (it got the current place's record just
		// before this save, dd_locations.cpp DD_LocationsSave). The save keeps the window's origin and the way back
		// out of a building; the table, the visited places and the plans are rebuilt from Daggerfall after a load.
		FString state = EncodeState(false);
		int format = TABLE_FORMAT;
		arc("ddtableformat", format);
		arc("ddoverworld", state);
		FString spaces;
		if (returnPoint.valid) spaces.AppendFormat("R %s %.17g %.17g %.17g %.17g\n", returnPoint.map.GetChars(), returnPoint.x, returnPoint.y, returnPoint.z, returnPoint.yaw);
		arc("ddspaces", spaces);
		DD_DebugPrintf("DDTM saved without the world table (%d rows stay with Daggerfall's record): state %d bytes, places %d bytes\n",
			int(table.size()), int(state.Len()), int(spaces.Len()));
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
	int format = 0;
	if (arc.HasKey("ddtableformat")) arc("ddtableformat", format);
	if (arc.HasKey("ddoverworld") && format != TABLE_FORMAT)
	{
		DD_DebugPrintf(TEXTCOLOR_RED "DDTM this save's world table is format %d, not %d; its history is not loaded\n", format, TABLE_FORMAT);
		DecodeState("");	// Empties the table rather than keep the previous session's.
		DD_MonstersLoadPlans("");
	}
	else if (arc.HasKey("ddoverworld"))
	{
		FString state;
		arc("ddoverworld", state);
		DecodeState(state);
		FString plans;
		if (arc.HasKey("ddplans")) arc("ddplans", plans);
		DD_MonstersLoadPlans(plans);
		if (arc.HasKey("ddintown")) resumeTown = 1;
		returnPoint = ReturnPoint();
		visitedSpaces.clear();
		if (arc.HasKey("ddspaces"))
		{
			FString spaces;
			arc("ddspaces", spaces);
			for (auto &line : spaces.Split("\n"))
			{
				char name[40];
				if (sscanf(line.GetChars(), "R %39s %lf %lf %lf %lf", name, &returnPoint.x, &returnPoint.y, &returnPoint.z, &returnPoint.yaw) == 5)
				{
					returnPoint.map = name;
					returnPoint.valid = true;
				}
				else if (sscanf(line.GetChars(), "V %39s", name) == 1) visitedSpaces.insert(name);
			}
		}
		if (FindArg("-ddlocnotable")) DDTreadmill_TestDropTable();	// Test hook: load as if the save had no world table.
	}
}

void DD_BodiesBeginMap(FLevelLocals *Level);

void DDTreadmill_BeginMap(FLevelLocals *Level)
{
	DD_BodiesBeginMap(Level);	// monster movement width (dd_monsters.cpp)
	natureActors.clear();	// [Doomerfall] the old map's nature flats went with it
	townNature.clear();
	DDTreadmill_WideNodes = false;
	static const bool hasTowns = fileSystem.CheckNumForName("DDTOWN") >= 0 || fileSystem.CheckNumForName("DDGROUPS") >= 0;
	if (!hasTowns || !Level->isPrimaryLevel()) return;
	LoadTowns();
	DDTreadmill_WideNodes = TownForMap(Level->MapName) >= 0;
}

bool DDTreadmill_RuntimeTowns() { return runtimeTowns; }
const std::vector<DDNatureFlat> *DDTreadmill_NatureOf(int px, int north) { return DDNature_Load() && !smallMap.empty() ? &NatureOf(px, north) : nullptr; }	// dd_nature_dump
// Where the player is, for Daggerfall's world look (dd_weather.cpp): 0 none, 1 exterior, 2 building interior, 3 dungeon.
int DDTreadmill_Place() { return DDTreadmill_Active ? 1 : !townActive || currentTown < 0 ? 0 : !towns[currentTown].space ? 1 : towns[currentTown].spaceId < DUNGEON_SPACE ? 2 : 3; }
bool DDTreadmill_OnDaggerfallMap() { return DDTreadmill_Active || townActive; }
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
	level_info_t *base = SpaceOfMap(mapname) >= DUNGEON_GROUP ? FindLevelInfo("DDDUNGN", false) : nullptr;	// [Doomerfall] runtime dungeon
	if (!base) base = FindLevelInfo("DDTOWN", false);
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

// [Doomerfall] With name null: whether mapname is a dungeon converted during play and its cache file is loaded. Otherwise
// also copies that dungeon's lump (cache names hold 8 characters; DFPOINTS is inside its map WAD) and says if it exists.
bool DDTreadmill_RuntimeLump(const char *mapname, const char *name, FString *out)
{
	if (SpaceOfMap(mapname) < DUNGEON_GROUP || !mapEntry || !mapEntry->Find("DDDUNGN")) return false;
	if (!name) return true;
	if (stricmp(name, "DFPOINTS") == 0)
	{
		const auto *wad = mapEntry->Find("MAPWAD");
		if (!wad || wad->size() < 12) return false;
		const uint8_t *w = wad->data();
		int32_t count, dir;
		memcpy(&count, w + 4, 4);
		memcpy(&dir, w + 8, 4);
		for (int32_t i = 0; i < count && dir >= 0 && size_t(dir) + 16 * size_t(i + 1) <= wad->size(); i++)
		{
			const uint8_t *e = w + dir + 16 * i;
			int32_t pos, size;
			memcpy(&pos, e, 4);
			memcpy(&size, e + 4, 4);
			if (strnicmp((const char *)e + 8, "DFPOINTS", 8) || pos < 0 || size < 0 || size_t(pos) + size_t(size) > wad->size()) continue;
			if (out) *out = FString((const char *)w + pos, size);
			return true;
		}
		return false;
	}
	char key[9] = {};
	strncpy(key, name, 8);
	const auto *body = mapEntry->Find(key);
	if (!body) return false;
	if (out) *out = FString((const char *)body->data(), body->size());
	return true;
}

bool DDTreadmill_MapMesh(const char *mapname, const uint8_t *&data, size_t &size, int &key)
{
	const int space = SpaceOfMap(mapname), group = space >= 0 ? space : GroupOfMap(mapname);
	if (group < 0 || !mapEntry) return false;
	const auto *mesh = mapEntry->Find("DFMESH");
	if (!mesh) return false;
	data = mesh->data();
	size = mesh->size();
	key = RUNTIME_MESH_KEY + group + (mapEntry->winter ? WINTER_MESH_KEY : 0);
	return true;
}

bool DDTreadmill_LodMesh(const uint8_t *&data, size_t &size, int &key)
{
	if (lodTown < 0 || !lodEntry) return false;
	const auto *mesh = lodEntry->Find("DFMESH");
	if (!mesh) return false;
	data = mesh->data();
	size = mesh->size();
	key = RUNTIME_MESH_KEY + towns[lodTown].group + (lodEntry->winter ? WINTER_MESH_KEY : 0);
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

// [Doomerfall] The distant terrain view (hw_ddhorizon.cpp): where world tiles sit on this map, and the tiles it draws itself.
bool DDTreadmill_HorizonFrame(DDHorizonFrame &f)
{
	if (!primaryLevel || handoff.pending) return false;
	if (DDTreadmill_Active)
	{
		f.offX = -originX * double(SPACING) - HALF;
		f.offY = -originY * double(SPACING) - HALF;
		f.offZ = 0;
		f.x0 = originX; f.x1 = originX + CELLS; f.y0 = originY; f.y1 = originY + CELLS;
	}
	else if (townActive && currentTown >= 0 && !towns[currentTown].space && LoadWorld())
	{
		const Town &t = towns[currentTown];
		f.offX = -t.originX * DOOM_PER_DF;
		f.offY = -t.originY * DOOM_PER_DF;
		f.offZ = Z_BASE - t.ground * DOOM_PER_DF;
		f.x0 = t.visual.x0; f.x1 = t.visual.x1; f.y0 = t.visual.y0; f.y1 = t.visual.y1;
	}
	else return false;
	return true;
}

// Doom height (overworld frame) at a global tile vertex, clamped to the world.
float DDTreadmill_HorizonHeight(int gx, int gy)
{
	return SampleVertex(std::clamp(gx, 0, WORLD_W * PIXEL_TILES), std::clamp(gy, 0, WORLD_H * PIXEL_TILES));
}

void DDTreadmill_HorizonFlats(int px, int north, std::vector<DDHorizonFlat> &out)
{
	if (!dd_natureflats || px < 0 || px >= WORLD_W || north < 0 || north >= WORLD_H || smallMap.empty() || !DDNature_Load()) return;
	const int archive = DDNature_Archive(px, north, DDTownCache::IsWinter());
	FTextureID tex[32];
	for (int r = 0; r < 32; r++) tex[r] = FlatTexture(FStringf("dfflat/F%03dR%02d.png", archive, r).GetChars());
	static std::vector<DDNatureFlat> flats;
	flats.clear();
	LayoutNature(px, north, flats);
	for (const DDNatureFlat &f : flats)
	{
		float sx, sy;
		if (!tex[f.record].isValid() || !DDNature_Scale(archive, f.record, sx, sy)) continue;
		out.push_back({ px * PIXEL_TILES + f.x, north * PIXEL_TILES + f.y, float(f.sink * DOOM_PER_DF), tex[f.record].GetIndex(), sx, sy });
	}
}

// The same tests as SpawnNature: the overworld window's chunks, or a town map's walkable margin.
bool DDTreadmill_HorizonMapHasFlat(int gx, int gy)
{
	if (DDTreadmill_Active) return gx >= originX && gx < originX + CELLS && gy >= originY && gy < originY + CELLS;
	if (townActive && currentTown >= 0) return towns[currentTown].Near(gx, gy, towns[currentTown].margin);
	return false;
}

void DD_QaTick(FLevelLocals *Level); // [Doomerfall] QA bot (dd_qa.cpp), inactive without -ddqa

// [Doomerfall] A pressed door, New Game or plain load waiting for its place to be converted holds the game frozen behind
// a loading message (dd_loading.cpp). A conversion that never ends gives up, as a failed one does.
static void HoldWhileConverting()
{
	constexpr double CONVERT_WAIT_MAX_MS = 180000;	// The slowest seen was 90 s on a loaded PC.
	// The door entered starts a handoff; the old map stays frozen until the new one loads, which drops every hold.
	bool converting = townActive && (handoff.pending ? DD_LoadingActive() : pendingDoor >= 0 || dungeonRequest >= 0 || buildingRequest.pending);
	if (converting && DD_LoadingAgeMs() > CONVERT_WAIT_MAX_MS)
	{
		DD_DebugPrintf("DDTCONV gave up waiting after %.0f ms (door %d, dungeon %d, building %d)\n", DD_LoadingAgeMs(), pendingDoor, dungeonRequest, int(buildingRequest.pending));
		Printf(PRINT_HIGH, "This door will not open.\n");
		pendingDoor = dungeonRequest = -1;
		buildingRequest.pending = converting = false;
	}
	DD_LoadingHold("conversion", converting);
}
void DDTreadmill_Tick(FLevelLocals *Level)
{
	DD_QaTick(Level);
	static const bool requested = fileSystem.CheckNumForName("DDWORLD") >= 0;
	if (!requested || Level != primaryLevel) return;
	HoldWhileConverting();
	if (resumePending) Resume(Level);
	else if (Level->maptime == 0) Start(Level);
	if (!DDTreadmill_Active && !townActive) return;
	if (DD_BridgeHasSession()) DD_LocationsTick(Level);	// Daggerfall's records, applied in the playsim.

	AActor *pmo = Level->Players[consoleplayer]->mo;
	if (!pmo) return;
	if (DD_BridgeHasSession() && !DD_BridgeArrivalFrozen() && !DD_LoadingActive()) DD_TownsfolkTick(Level);	// [Doomerfall] Idle until Daggerfall lists townspeople; held during the arrival wait and loading holds.
	DD_LightsTick(Level);
	DD_WeatherTick(Level);
	if (runtimeTowns) DDTownCache::Poll();
	if (travel.pending && !handoff.pending)
	{
		BeginTravel(Level, pmo);
		return;
	}
	if (dungeonRequest >= 0 && townActive && !handoff.pending)	// Doomerfall New Game: through this town's real door.
	{
		const int wanted = dungeonRequest;
		dungeonRequest = -1;
		for (const DoorSpot &d : townDoors)
			if (d.kind != 0 && d.target == wanted)
			{
				if (EnterDoor(Level, pmo, d, dungeonRequestHasStart ? dungeonRequestStart : nullptr)) return;
				if (runtimeTowns && DDTownCache::Status(DoorGroup(d)) != DDTownCache::State::Failed) { DDTownCache::Request(DoorGroup(d), 0); dungeonRequest = wanted; return; }	// [Doomerfall] Converting. The return skips TickTownDoors' scan, so ask here.
				break;
			}
		DD_DebugPrintf("DDTRAVEL no door to dungeon %d in %s\n", wanted, Level->MapName.GetChars());
	}
	if (buildingRequest.pending && townActive && !handoff.pending)	// [Doomerfall] Plain Daggerfall load: into the saved building.
	{
		buildingRequest.pending = false;
		const Town &t = towns[currentTown];
		const DoorSpot *best = nullptr;
		double bestDistance = 1e30;
		for (const DoorSpot &d : townDoors)
		{
			if (d.kind != 0) continue;
			const double dx = d.x / DOOM_PER_DF + t.originX - buildingRequest.x, dy = d.y / DOOM_PER_DF + t.originY - buildingRequest.y;
			const double distance = sqrt(dx * dx + dy * dy);
			if (distance < bestDistance) { bestDistance = distance; best = &d; }
		}
		if (best && bestDistance <= buildingRequest.tolerance)
		{
			DD_DebugPrintf("DDPLAINLOAD building door %d is %.1f units from the saved door\n", best->target, bestDistance);
			if (EnterDoor(Level, pmo, *best, buildingRequest.start)) return;
			DD_DebugPrintf("DDPLAINLOAD building %d is not converted yet, trying again\n", best->target);
			buildingRequest.pending = true;
		}
		else DD_DebugPrintf("DDPLAINLOAD no building door within %.0f units of %.1f,%.1f in %s (nearest %.1f)\n", buildingRequest.tolerance,
			buildingRequest.x, buildingRequest.y, Level->MapName.GetChars(), best ? bestDistance : -1.0);
	}

	if (townActive)
	{
		TickTownDoors(Level, pmo);
		const Town &t = towns[currentTown];
		if (!t.space && runtimeTowns) RefreshTownSeason(Level, t.group);
		if (t.space && t.spaceId >= DUNGEON_SPACE && DD_BridgeHasSession()) DD_MonstersTick(Level);
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

	if (DDTownCache::IsWinter() != groundWinter) RefreshSeason(Level);
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
	ShiftNature(DVector3(dx * double(SPACING), dy * double(SPACING), 0));
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

bool DDTreadmill_RequestTravel(double x, double y, double yawDegrees)
{
	if (!runtimeTowns || (!DDTreadmill_Active && !townActive) || x < 0 || y < 0 || x >= WORLD_W * PIXEL_TILES * 256.0 || y >= WORLD_H * PIXEL_TILES * 256.0) return false;
	travel = { true, x, y, yawDegrees };
	return true;
}

void DDTreadmill_RequestDungeon(int mapId, const double *start)
{
	dungeonRequest = mapId;
	dungeonRequestHasStart = start != nullptr;
	if (start) memcpy(dungeonRequestStart, start, sizeof(dungeonRequestStart));
}

void DDTreadmill_RequestBuilding(double doorX, double doorY, double tolerance, const double *start)
{
	buildingRequest.pending = true;
	buildingRequest.x = doorX;
	buildingRequest.y = doorY;
	buildingRequest.tolerance = tolerance;
	memcpy(buildingRequest.start, start, sizeof(buildingRequest.start));
}

bool DDTreadmill_CurrentDoor(int &action, double &x, double &y, int &target)
{
	if (!primaryLevel) return false;
	action = TRANSITION_EXIT_BUILDING;	// Outdoors: Daggerfall leaves whatever it is in, and ignores the door.
	x = y = 0;
	target = 0;
	const int index = TownForMap(primaryLevel->MapName);
	if (index < 0) return primaryLevel->MapName.CompareNoCase("DDOVER01") == 0;
	const Town &t = towns[index];
	if (!t.space) return true;
	if (!returnPoint.valid) return false;
	const DVector2 door = ReturnDoor();
	action = t.spaceId >= DUNGEON_SPACE ? TRANSITION_ENTER_DUNGEON : TRANSITION_ENTER_BUILDING;
	x = door.X;
	y = door.Y;
	target = t.spaceId >= DUNGEON_SPACE ? t.dungeonMapId : t.spaceId;
	return true;
}

void DDTreadmill_PressDoor()
{
	doorPressTic = gametic;
}

// [Doomerfall] The label under the crosshair (dd_look.cpp): the location door or exit a Use press would take now, by
// TickTownDoors' own rule. kind 0 is a building door, with a point just inside it in Daggerfall world units; 1 a dungeon
// entrance; 2 the exit of the building or dungeon the player is in. index tells doors apart within this map.
bool DDTreadmill_DoorInReach(AActor *pmo, int &kind, int &index, double &worldX, double &worldY)
{
	if (!pmo || !townActive || handoff.pending || pendingDoor >= 0) return false;
	const Town &t = towns[currentTown];
	double distance, bestDistance = USE_REACH + 1;
	index = -1;
	if (t.space)
	{
		if (!returnPoint.valid) return false;
		for (size_t i = 0; i < t.exits.size(); i++)
			if (CanUse(pmo, t.exits[i].x, t.exits[i].y, t.exits[i].z, t.exits[i].nx, t.exits[i].ny, distance)) { kind = 2; index = int(i); return true; }
		return false;
	}
	for (size_t i = 0; i < townDoors.size(); i++)
	{
		const DoorSpot &d = townDoors[i];
		if (CanUse(pmo, d.x, d.y, d.z, d.nx, d.ny, distance) && distance < bestDistance) { index = int(i); bestDistance = distance; }
	}
	if (index < 0) return false;
	const DoorSpot &d = townDoors[index];
	kind = d.kind == 0 ? 0 : 1;
	const DVector3 world = ToWorld(DVector3(d.x - d.nx * 12, d.y - d.ny * 12, d.z), originX, originY);
	worldX = world.X;
	worldY = world.Y;
	return true;
}

DDPlayerArea DDTreadmill_PlayerWorld(double &x, double &y, double &z, double &yawDegrees)
{
	if (!primaryLevel || (!DDTreadmill_Active && !townActive && !handoff.pending)) return DD_AREA_NONE;
	AActor *pmo = primaryLevel->Players[consoleplayer]->mo;
	if (!pmo) return DD_AREA_NONE;
	// Interiors and dungeons sit in a private part of the world table, so their coordinates are not map positions.
	if (handoff.pending ? handoff.area != DD_AREA_EXTERIOR : townActive && towns[currentTown].space)
		return handoff.pending ? handoff.area : towns[currentTown].spaceId >= DUNGEON_SPACE ? DD_AREA_DUNGEON : DD_AREA_INTERIOR;
	yawDegrees = pmo->Angles.Yaw.Degrees();
	if (handoff.pending)	// Between maps the actor is stale, so report where the player is arriving.
	{
		x = handoff.x;
		y = handoff.y;
		z = handoff.z;
		return DD_AREA_EXTERIOR;
	}
	const DVector3 world = ToWorld(pmo->Pos(), originX, originY);
	x = world.X;
	y = world.Y;
	z = world.Z;
	return DD_AREA_EXTERIOR;
}

// [Doomerfall] Daggerfall world units to this map's Doom position. False indoors and between maps.
bool DDTreadmill_WorldToLocal(double x, double y, double &doomX, double &doomY)
{
	if (!primaryLevel || handoff.pending || (!DDTreadmill_Active && !townActive)) return false;
	if (townActive && towns[currentTown].space) return false;
	const DVector3 local = ToLocal(x, y, 0);
	doomX = local.X;
	doomY = local.Y;
	return true;
}

bool DDTreadmill_PlayerSpace(double &x, double &y, double &z, double &yawDegrees, int &target)
{
	if (!primaryLevel || !townActive || handoff.pending || !towns[currentTown].space) return false;
	AActor *pmo = primaryLevel->Players[consoleplayer]->mo;
	if (!pmo) return false;
	const Town &t = towns[currentTown];
	x = pmo->X() / DOOM_PER_DF;
	y = pmo->Y() / DOOM_PER_DF;
	z = pmo->Z() / DOOM_PER_DF;
	yawDegrees = pmo->Angles.Yaw.Degrees();
	target = t.spaceId >= DUNGEON_SPACE ? t.dungeonMapId : t.spaceId;	// The same id the door event carried.
	return true;
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
