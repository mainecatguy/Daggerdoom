// [DoomDaggerfall] Overworld terrain treadmill.
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

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <limits>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "dd_treadmill.h"
#include "a_sharedglobal.h"
#include "actor.h"
#include "actorinlines.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "filesystem.h"
#include "g_levellocals.h"
#include "info.h"
#include "m_argv.h"
#include "p_effect.h"
#include "p_local.h"
#include "printf.h"
#include "r_utility.h"
#include "s_sound.h"
#include "serializer.h"
#include "serializer_doom.h"

CVAR(Int, dd_tm_originx, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_originy, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_shifts, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_records, 0, CVAR_NOSAVE)

bool DDTreadmill_Active = false;

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
	std::vector<float> window;
	std::vector<Tri> tris;
	int originX, originY, startTileX, startTileY, shifts;

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

	// Height in Doom units at a global tile vertex (north is +Y).
	float SampleVertex(int gx, int gy)
	{
		const int px = std::min(gx / PIXEL_TILES, WORLD_W - 1), north = std::min(gy / PIXEL_TILES, WORLD_H - 1);
		const int x = gx - px * PIXEL_TILES, y = gy - north * PIXEL_TILES, my = WORLD_H - 1 - north;
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
		h = std::clamp(h, OCEAN, MAX_HEIGHT);
		return float(h * UNITS_PER_SAMPLE * DOOM_PER_DF - Z_BASE);
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

	void RewriteGrid()
	{
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
		r.x = (fromX * double(SPACING) + HALF + mo->X()) / DOOM_PER_DF;
		r.y = (fromY * double(SPACING) + HALF + mo->Y()) / DOOM_PER_DF;
		r.z = (mo->Z() + Z_BASE) / DOOM_PER_DF;
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
		const DVector3 pos(r.x * DOOM_PER_DF - originX * double(SPACING) - HALF, r.y * DOOM_PER_DF - originY * double(SPACING) - HALF, r.z * DOOM_PER_DF - Z_BASE);
		AActor *mo = Spawn(Level, cls, pos, NO_REPLACE);
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
		return true;
	}

	// Text settings, one "key value" per line.
	void LoadConfig()
	{
		startTileX = 862 * PIXEL_TILES;
		startTileY = (WORLD_H - 1 - 442) * PIXEL_TILES;
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
			if (frameLog) fputs("frame,tic,frame_us,sim_us,upload_us,uploads,shift\n", frameLog);
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

	void Start(FLevelLocals *Level)
	{
		DDTreadmill_Active = false;
		if (Level->MapName.CompareNoCase("DDOVER01") != 0) return;
		table.clear();
		buckets.clear();
		expected.clear();
		pending.clear();
		nextDynamic = 0;
		shifts = 0;
		LoadConfig();
		originX = startTileX;
		originY = startTileY;
		if (!PrepareLevel(Level)) return;
		SettleActors(Level, true);
		for (int cy = originY / CHUNK_TILES; cy < (originY + CELLS) / CHUNK_TILES; cy++)
			for (int cx = originX / CHUNK_TILES; cx < (originX + CELLS) / CHUNK_TILES; cx++)
				QueueChunk(cx, cy);
		ProcessPending(Level, std::numeric_limits<int>::max());
		DDTreadmill_Active = true;
		Printf("DDTM active origin=%d,%d spacing=%d sectors=%d packs=%.2f/%d\n", originX, originY, SPACING, int(tris.size()), packChance, packSize);
	}

	void Resume(FLevelLocals *Level)
	{
		resumePending = false;
		LoadConfig();
		if (!PrepareLevel(Level)) return;
		expected.clear();
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
			if (mo->ddRecordId && !IsOwned(mo)) expected.insert(mo->ddRecordId);
		SettleActors(Level, false);
		DDTreadmill_Active = true;
		Printf("DDTM resumed origin=%d,%d records=%d pending=%d\n", originX, originY, int(table.size()), int(pending.size()));
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
		if (!DDTreadmill_Active || Level != primaryLevel) return;
		Reconcile(Level);
		FString state = EncodeState();
		arc("ddoverworld", state);
		return;
	}
	if (Level != primaryLevel) return;
	DDTreadmill_Active = false;	// Sector pointers from the previous level are no longer valid.
	resumePending = false;
	if (arc.HasKey("ddoverworld"))
	{
		FString state;
		arc("ddoverworld", state);
		DecodeState(state);
	}
}

void DDTreadmill_Tick(FLevelLocals *Level)
{
	static const bool requested = fileSystem.CheckNumForName("DDWORLD") >= 0;
	if (!requested || Level != primaryLevel) return;
	if (resumePending) Resume(Level);
	else if (Level->maptime == 0) Start(Level);
	if (!DDTreadmill_Active) return;

	AActor *pmo = Level->Players[consoleplayer]->mo;
	if (!pmo) return;

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
		fprintf(frameLog, "%lld,%d,%.1f,%.1f,%.1f,%lld,%d\n", (long long)frameNo++, primaryLevel->maptime, frameNs / 1000.0,
			simNs / 1000.0, uploadNs / 1000.0, (long long)uploadCount, shiftFlag);
		if ((frameNo & 255) == 0) { fflush(frameLog); if (shiftLog) fflush(shiftLog); }
	}
	simNs = uploadNs = uploadCount = 0;
	shiftFlag = 0;
}
