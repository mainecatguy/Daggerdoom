// [Doomerfall] Distant terrain view for Daggerfall exteriors.
//
// Daggerfall Unity streams terrain for several map pixels around the player. A Doom map only holds the loaded
// window (the overworld treadmill) or a location's own area (a town or dungeon exterior map), so beyond it this pass
// draws a render-only ring of terrain from the same height function, out to about 60,000 Doom units.
//
// Everything is computed from world tile coordinates, so the ring is the same ground on every map that shows it and
// stays put across treadmill shifts. Nothing is stored. Inside the map's own tiles nothing is drawn; a fine band (one
// tile per quad) meets the map's terrain edge exactly, and coarse quads (four tiles) cover the rest.
// The wilderness nature flats the map does not spawn itself stand on the ring as quads, from the same layout rule
// (dd_nature.cpp) as the actors, so every map that shows a piece of ground shows the same trees there.
// Inactive unless dd_treadmill.cpp reports a Daggerfall exterior. Collision and game logic are not touched.

#include <algorithm>
#include <cmath>
#include <unordered_map>
#include <vector>

#include "c_cvars.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "hw_ddhorizon.h"
#include "hw_dfmesh.h"
#include "hw_drawinfo.h"
#include "playsim/dd_treadmill.h"
#include "playsim/dd_towncache.h"
#include "playsim/dd_log.h"
#include "hw_material.h"
#include "hw_modelvertexbuffer.h"
#include "hw_portal.h"
#include "hw_renderstate.h"
#include "i_time.h"
#include "texturemanager.h"
#include "v_video.h"
#include "flatvertices.h"

CVAR(Bool, dd_horizon, true, CVAR_ARCHIVE)	// the distant terrain view on Daggerfall exteriors

bool DD_WeatherFog(PalEntry &color, float &density);	// playsim/dd_weather.cpp
bool DD_WeatherMeshLight(float &brightness);

namespace
{
	constexpr int CHUNK = 32, STEP = 4, FINE_BAND = 32;
	constexpr double TILE = 192, RADIUS = 60000;	// Doom's far clip plane is 65,536 units.
	constexpr int RADIUS_TILES = int(RADIUS / TILE);

	int FloorDiv(int a, int b) { return a >= 0 ? a / b : -((-a + b - 1) / b); }
	int FloorTo(int a, int b) { return FloorDiv(a, b) * b; }
	int CeilTo(int a, int b) { return -FloorDiv(-a, b) * b; }

	// Sampled heights, by world chunk. Heights never change, so this is only a cache; it is dropped when it grows.
	std::unordered_map<int64_t, std::vector<float>> heights;

	float Height(int gx, int gy)
	{
		const int cx = FloorDiv(gx, CHUNK), cy = FloorDiv(gy, CHUNK);
		auto &chunk = heights[(int64_t(cy) << 32) | uint32_t(cx)];
		if (chunk.empty()) chunk.assign((CHUNK + 1) * (CHUNK + 1), NAN);
		float &h = chunk[(gy - cy * CHUNK) * (CHUNK + 1) + (gx - cx * CHUNK)];
		if (std::isnan(h)) h = DDTreadmill_HorizonHeight(gx, gy);
		return h;
	}

	struct Key
	{
		int x0, x1, y0, y1, cx, cy;
		bool operator==(const Key &o) const { return x0 == o.x0 && x1 == o.x1 && y0 == o.y0 && y1 == o.y1 && cx == o.cx && cy == o.cy; }
	};

	FModelVertexBuffer *buffer;
	DFrameBuffer *bufferOwner;
	Key built;
	bool haveBuilt, builtWinter;
	int vertexCount, anchorX, anchorY;
	std::vector<FModelVertex> verts;

	// The ground of a coarse quad (STEP tiles, on the world grid) at a tile corner, on the same diagonal as quad() below.
	float CoarseHeight(int x, int y)
	{
		const int qx = FloorTo(x, STEP), qy = FloorTo(y, STEP);
		const float u = float(x - qx) / STEP, v = float(y - qy) / STEP;
		const float h00 = Height(qx, qy), h10 = Height(qx + STEP, qy), h11 = Height(qx + STEP, qy + STEP), h01 = Height(qx, qy + STEP);
		return u >= v ? h00 + u * (h10 - h00) + v * (h11 - h10) : h00 + v * (h01 - h00) + u * (h11 - h01);
	}

	// Distant nature flats: the same layout the maps spawn as actors (dd_nature.cpp), by map pixel, with the sprite's
	// size and offsets and the coarse ground under it. Only a cache: the layout is a pure function of the pixel.
	struct RingFlat { int gx, gy, texture; float coarseZ, sink, left, right, top, bottom; };
	std::unordered_map<int, std::vector<RingFlat>> pixelFlats;
	struct FlatBatch { int texture, first, count; };
	std::vector<FlatBatch> flatBatches;	// flat quads follow the terrain in the same buffer, one batch per texture
	bool flatsIncomplete;	// the last build lacked pixels that were not laid out yet
	Key flatsBuilt;

	constexpr int PIXEL = 128;
	int PixelKey(int px, int north) { return north * 1000 + px; }

	void LayOut(int px, int north)
	{
		static std::vector<DDHorizonFlat> raw;
		raw.clear();
		DDTreadmill_HorizonFlats(px, north, raw);
		auto &out = pixelFlats[PixelKey(px, north)];
		out.clear();
		out.reserve(raw.size());
		for (const DDHorizonFlat &fl : raw)
		{
			FGameTexture *tex = TexMan.GameByIndex(fl.texture);
			if (!tex) continue;
			const float left = -tex->GetDisplayLeftOffset() * fl.sx, top = tex->GetDisplayTopOffset() * fl.sy;
			out.push_back({ fl.gx, fl.gy, fl.texture, CoarseHeight(fl.gx, fl.gy), fl.sink,
				left, left + tex->GetDisplayWidth() * fl.sx, top, top - tex->GetDisplayHeight() * fl.sy });
		}
	}

	// The map pixels that reach into the ring around a key's chunk, nearest first.
	void RingPixels(const Key &key, std::vector<int> &out)
	{
		out.clear();
		const int c = key.cx, d = key.cy;	// the ring's centre, as in Build
		std::vector<std::pair<double, int>> found;
		for (int north = std::max(FloorDiv(d - RADIUS_TILES, PIXEL), 0); north <= std::min(FloorDiv(d + RADIUS_TILES, PIXEL), 499); north++)
			for (int px = std::max(FloorDiv(c - RADIUS_TILES, PIXEL), 0); px <= std::min(FloorDiv(c + RADIUS_TILES, PIXEL), 999); px++)
			{
				const double dx = std::max({ px * PIXEL - c, 0, c - (px + 1) * PIXEL }), dy = std::max({ north * PIXEL - d, 0, d - (north + 1) * PIXEL });
				if (dx * dx + dy * dy <= double(RADIUS_TILES) * RADIUS_TILES) found.push_back({ dx * dx + dy * dy, PixelKey(px, north) });
			}
		std::sort(found.begin(), found.end());
		for (auto &p : found) out.push_back(p.second);
	}

	// The fine band around the map's own tiles, on the coarse grid.
	struct Band
	{
		int fx0, fx1, fy0, fy1;
		explicit Band(const Key &key) : fx0(FloorTo(key.x0 - FINE_BAND, STEP)), fx1(CeilTo(key.x1 + FINE_BAND, STEP)),
			fy0(FloorTo(key.y0 - FINE_BAND, STEP)), fy1(CeilTo(key.y1 + FINE_BAND, STEP)) {}
		// A fine vertex on the band's outer edge takes the coarse edge's height there, so the two meet without cracks.
		float FineHeight(int x, int y) const
		{
			if ((x == fx0 || x == fx1) && y % STEP)
			{
				const int a = FloorTo(y, STEP);
				const float t = float(y - a) / STEP;
				return Height(x, a) * (1 - t) + Height(x, a + STEP) * t;
			}
			if ((y == fy0 || y == fy1) && x % STEP)
			{
				const int a = FloorTo(x, STEP);
				const float t = float(x - a) / STEP;
				return Height(a, y) * (1 - t) + Height(a + STEP, y) * t;
			}
			return Height(x, y);
		}
	};

	// The terrain ring. The flats are built on a later frame (BuildFlats), so one frame never does both.
	void Build(const Key &key)
	{
		const uint64_t start = I_nsTime();
		if (heights.size() > 4000) heights.clear();
		anchorX = key.cx;
		anchorY = key.cy;
		const Band band(key);
		auto fineHeight = [&](int x, int y) { return band.FineHeight(x, y); };
		const int fx0 = band.fx0, fx1 = band.fx1, fy0 = band.fy0, fy1 = band.fy1;
		verts.clear();
		auto emit = [&](int x, int y, float h) {
			FModelVertex v;
			v.Set(float((x - anchorX) * TILE), h, float((y - anchorY) * TILE), float(x - anchorX), float(y - anchorY));
			v.SetNormal(0, 1, 0);
			verts.push_back(v);
		};
		// Two triangles per quad, split along the same diagonal as the overworld grid.
		auto quad = [&](int x, int y, int s, float h00, float h10, float h11, float h01) {
			emit(x, y, h00); emit(x + s, y + s, h11); emit(x + s, y, h10);
			emit(x, y, h00); emit(x, y + s, h01); emit(x + s, y + s, h11);
		};
		const int bx0 = FloorTo(key.cx - RADIUS_TILES, STEP), bx1 = CeilTo(key.cx + RADIUS_TILES, STEP);
		const int by0 = FloorTo(key.cy - RADIUS_TILES, STEP), by1 = CeilTo(key.cy + RADIUS_TILES, STEP);
		const double r2 = double(RADIUS_TILES) * RADIUS_TILES;
		for (int y = by0; y < by1; y += STEP)
			for (int x = bx0; x < bx1; x += STEP)
			{
				const double dx = x + STEP / 2 - key.cx, dy = y + STEP / 2 - key.cy;
				if (dx * dx + dy * dy > r2) continue;
				if (x >= fx0 && x < fx1 && y >= fy0 && y < fy1)
				{
					for (int ty = y; ty < y + STEP; ty++)
						for (int tx = x; tx < x + STEP; tx++)
							if (tx < key.x0 || tx >= key.x1 || ty < key.y0 || ty >= key.y1)
								quad(tx, ty, 1, fineHeight(tx, ty), fineHeight(tx + 1, ty), fineHeight(tx + 1, ty + 1), fineHeight(tx, ty + 1));
				}
				else quad(x, y, STEP, Height(x, y), Height(x + STEP, y), Height(x + STEP, y + STEP), Height(x, y + STEP));
			}
		delete buffer;
		buffer = new FModelVertexBuffer(false, true);
		bufferOwner = screen;
		vertexCount = int(verts.size());
		FModelVertex *out = buffer->LockVertexBuffer(vertexCount);
		std::copy(verts.begin(), verts.end(), out);
		buffer->UnlockVertexBuffer();
		built = key;
		haveBuilt = true;
		DD_DebugPrintf("DDHORIZON built %d triangles around tile %d,%d (map tiles %d..%d x %d..%d) in %.1f ms\n",
			vertexCount / 3, key.cx, key.cy, key.x0, key.x1, key.y0, key.y1, (I_nsTime() - start) / 1e6);
	}

	FModelVertexBuffer *flatBuffer;
	DFrameBuffer *flatBufferOwner;
	int flatAnchorX, flatAnchorY;

	// Flats within NEAR_TILES of the chunk's middle face the camera itself: they are kept apart and their quads are
	// rebuilt whenever the camera has moved a tile, so none can turn edge-on. On a town or dungeon exterior map the ring
	// starts a few tiles from the player (beyond the map's 24-tile nature margin). Farther flats face the chunk's
	// middle; the camera is at most 23 tiles from it, so they turn at most about 14 degrees away from it.
	constexpr int NEAR_TILES = 96;
	constexpr double NEAR_MOVE = TILE;	// Doom units the camera may move before the near quads turn again
	struct NearFlat { int texture; float x, y, z, left, right, top, bottom; };	// x, y from the flat anchor
	std::vector<NearFlat> nearFlats;	// grouped by texture
	std::vector<FlatBatch> nearBatches;
	FModelVertexBuffer *nearBuffer;
	DFrameBuffer *nearBufferOwner;
	bool nearDirty;
	double nearCamX, nearCamY;

	// One flat's quad, sized and offset as its sprite, across the line from the eye (both from the anchor).
	void FlatQuad(float x, float y, float z, float left, float right, float top, float bottom, float eyeX, float eyeY)
	{
		float rx = y - eyeY, ry = eyeX - x;	// the viewer's right, across the line of sight
		const float len = std::sqrt(rx * rx + ry * ry);
		if (len > 0) { rx /= len; ry /= len; } else { rx = 1; ry = 0; }
		auto corner = [&](float a, float h, float u, float v) {
			FModelVertex vx;
			vx.Set(x + rx * a, z + h, y + ry * a, u, v);
			vx.SetNormal(0, 1, 0);
			verts.push_back(vx);
		};
		corner(left, top, 0, 0); corner(right, top, 1, 0); corner(right, bottom, 1, 1);
		corner(left, top, 0, 0); corner(right, bottom, 1, 1); corner(left, bottom, 0, 1);
	}

	void BuildNear(double camX, double camY)
	{
		verts.clear();
		nearBatches.clear();
		for (const NearFlat &n : nearFlats)
		{
			if (nearBatches.empty() || nearBatches.back().texture != n.texture) nearBatches.push_back({ n.texture, int(verts.size()), 0 });
			FlatQuad(n.x, n.y, n.z, n.left, n.right, n.top, n.bottom, float(camX), float(camY));
			nearBatches.back().count += 6;
		}
		delete nearBuffer;
		nearBuffer = nullptr;
		nearBufferOwner = screen;
		if (!verts.empty())
		{
			nearBuffer = new FModelVertexBuffer(false, true);
			FModelVertex *out = nearBuffer->LockVertexBuffer(int(verts.size()));
			std::copy(verts.begin(), verts.end(), out);
			nearBuffer->UnlockVertexBuffer();
		}
		nearCamX = camX;
		nearCamY = camY;
		nearDirty = false;
	}

	void BuildFlats(const Key &key)
	{
		const Band band(key);
		auto fineHeight = [&](int x, int y) { return band.FineHeight(x, y); };
		const int fx0 = band.fx0, fx1 = band.fx1, fy0 = band.fy0, fy1 = band.fy1;
		flatAnchorX = key.cx;
		flatAnchorY = key.cy;
		const int anchorX = flatAnchorX, anchorY = flatAnchorY;
		verts.clear();

		// Nature flats the running map does not spawn itself, inside the ring, from pixels already laid out (Draw lays
		// out one missing pixel per frame and builds again when they are all there). Each is a quad turned to face the
		// middle of the camera's chunk (rebuilt when the camera enters another chunk), sized and offset as its sprite.
		// On the map's own tiles and in the fine band the flat stands on the exact ground; elsewhere on the coarse quad.
		std::vector<int> ring;
		RingPixels(key, ring);
		std::unordered_map<int, std::vector<const RingFlat *>> byTexture, nearByTexture;
		const double flatR2 = double(RADIUS_TILES - STEP) * (RADIUS_TILES - STEP), nearR2 = double(NEAR_TILES) * NEAR_TILES;
		const int midX = key.cx + CHUNK / 2, midY = key.cy + CHUNK / 2;
		flatsIncomplete = false;
		for (int pixel : ring)
		{
			auto found = pixelFlats.find(pixel);
			if (found == pixelFlats.end()) { flatsIncomplete = true; continue; }
			for (const RingFlat &fl : found->second)
			{
				const double dx = fl.gx - key.cx, dy = fl.gy - key.cy;
				if (dx * dx + dy * dy > flatR2 || DDTreadmill_HorizonMapHasFlat(fl.gx, fl.gy)) continue;
				const double mx = fl.gx - midX, my = fl.gy - midY;
				(mx * mx + my * my < nearR2 ? nearByTexture : byTexture)[fl.texture].push_back(&fl);
			}
		}
		auto groundZ = [&](const RingFlat *fl) {
			const bool exact = (fl->gx >= key.x0 && fl->gx <= key.x1 && fl->gy >= key.y0 && fl->gy <= key.y1)
				|| (fl->gx >= fx0 && fl->gx <= fx1 && fl->gy >= fy0 && fl->gy <= fy1);
			return (exact ? fineHeight(fl->gx, fl->gy) : fl->coarseZ) - fl->sink;
		};
		flatBatches.clear();
		const float eyeX = float((midX - anchorX) * TILE), eyeY = float((midY - anchorY) * TILE);
		for (auto &group : byTexture)
		{
			flatBatches.push_back({ group.first, int(verts.size()), int(group.second.size()) * 6 });
			for (const RingFlat *fl : group.second)
				FlatQuad(float((fl->gx - anchorX) * TILE), float((fl->gy - anchorY) * TILE), groundZ(fl), fl->left, fl->right, fl->top, fl->bottom, eyeX, eyeY);
		}
		nearFlats.clear();
		for (auto &group : nearByTexture)
			for (const RingFlat *fl : group.second)
				nearFlats.push_back({ fl->texture, float((fl->gx - anchorX) * TILE), float((fl->gy - anchorY) * TILE), groundZ(fl), fl->left, fl->right, fl->top, fl->bottom });
		nearDirty = true;

		delete flatBuffer;
		flatBuffer = nullptr;
		flatBufferOwner = screen;
		flatsBuilt = key;
		if (!verts.empty())
		{
			flatBuffer = new FModelVertexBuffer(false, true);
			FModelVertex *out = flatBuffer->LockVertexBuffer(int(verts.size()));
			std::copy(verts.begin(), verts.end(), out);
			flatBuffer->UnlockVertexBuffer();
		}
		DD_DebugPrintf("DDHORIZON built flats around tile %d,%d: %d near, %d textures far\n", key.cx, key.cy, int(nearFlats.size()), int(flatBatches.size()));
	}
}

void DDHorizon_Draw(HWDrawInfo *di, FRenderState &state)
{
	FLevelLocals *level = di->Level;
	DDHorizonFrame f;
	if (!dd_horizon || level != primaryLevel || !DDTreadmill_HorizonFrame(f)) return;
	auto *player = level->Players[consoleplayer];
	AActor *camera = player ? player->camera.Get() : nullptr;
	if (!camera) return;
	// Rebuilt when the map's own tiles move (a treadmill shift or a new map) or the player enters another chunk.
	const Key key{ f.x0, f.x1, f.y0, f.y1,
		FloorTo(int(std::floor((camera->X() - f.offX) / TILE)), CHUNK), FloorTo(int(std::floor((camera->Y() - f.offY) / TILE)), CHUNK) };
	const bool winter = DDTownCache::IsWinter();
	if (winter != builtWinter) { pixelFlats.clear(); builtWinter = winter; flatsIncomplete = true; }	// the season picks the nature archive
	// One heavy step per frame at most: the terrain when the key changes, else laying out one missing pixel's flats
	// (nearest first), else the flats. Until the flats are built again the previous ones stay, in their own world place.
	if (!haveBuilt || !(built == key) || !buffer || bufferOwner != screen) Build(key);
	else if (flatsIncomplete || !(flatsBuilt == key) || flatBufferOwner != screen)
	{
		static std::vector<int> ring;
		RingPixels(key, ring);
		bool laid = false;
		for (int pixel : ring)
			if (!pixelFlats.count(pixel)) { LayOut(pixel % 1000, pixel / 1000); laid = true; break; }
		if (!laid) BuildFlats(key);
		if (pixelFlats.size() > ring.size() + 32)	// drop pixels the ring has left behind
			for (auto it = pixelFlats.begin(); it != pixelFlats.end();)
				it = std::find(ring.begin(), ring.end(), it->first) == ring.end() ? pixelFlats.erase(it) : std::next(it);
	}
	if (vertexCount == 0) return;

	static FTextureID ground;
	static bool looked;
	if (!looked)
	{
		looked = true;
		ground = TexMan.CheckForTexture("DFGROUND", ETextureType::Flat, FTextureManager::TEXMAN_TryAny);
		if (!ground.isValid()) ground = TexMan.CheckForTexture("RROCK19", ETextureType::Flat, FTextureManager::TEXMAN_TryAny);
	}
	if (!ground.isValid()) return;

	state.SetVertexBuffer(buffer->vertexBuffer(), 0, 0);
	state.SetCulling(Cull_None);
	PalEntry fogColor;
	float fogDensity, light;
	if (DFMesh_HideCollider(level))	// a location map: lit like its Daggerfall mesh
	{
		const bool fog = DD_WeatherFog(fogColor, fogDensity);
		if (!DD_WeatherMeshLight(light)) light = camera->Sector ? std::min(1.f, camera->Sector->lightlevel / 176.f) : 1.f;
		state.EnableFog(fog);
		state.SetFog(fog ? fogColor : PalEntry(0), fog ? fogDensity : 0);
		state.SetSoftLightLevel(255);
		state.SetColor(light, light, light, 1.f);
	}
	else if (camera->Sector)	// the overworld: lit like the window's floor, the player's sector, including Doom's distance fade
	{
		const int lightlevel = camera->Sector->lightlevel;
		SetColor(state, level, di->lightmode, lightlevel, 0, di->isFullbrightScene(), camera->Sector->Colormap, 1.f);
		SetFog(state, level, di->lightmode, lightlevel, 0, di->isFullbrightScene(), &camera->Sector->Colormap, false);
	}
	state.SetObjectColor(0xffffffff);
	state.SetAddColor(0);
	state.SetDynLight(0, 0, 0);
	state.SetLightIndex(-1);
	state.EnableTextureMatrix(false);
	state.SetRenderStyle(STYLE_Source);
	state.AlphaFunc(Alpha_GEqual, 0.f);
	state.mModelMatrix.loadIdentity();
	state.mModelMatrix.translate(float(anchorX * TILE + f.offX), float(f.offZ), float(anchorY * TILE + f.offY));
	state.EnableModelMatrix(true);
	state.SetMaterial(TexMan.GetGameTexture(ground, true), UF_Skin, 0, CLAMP_NONE, NO_TRANSLATION, -1);
	state.Draw(DT_Triangles, 0, vertexCount);
	if (flatBufferOwner == screen && (flatBuffer || !nearFlats.empty()))	// the distant nature flats, alpha tested like sprites
	{
		state.mModelMatrix.loadIdentity();
		state.mModelMatrix.translate(float(flatAnchorX * TILE + f.offX), float(f.offZ), float(flatAnchorY * TILE + f.offY));
		state.AlphaFunc(Alpha_GEqual, 0.5f);
		if (flatBuffer)
		{
			state.SetVertexBuffer(flatBuffer->vertexBuffer(), 0, 0);
			for (const FlatBatch &b : flatBatches)
			{
				state.SetMaterial(TexMan.GameByIndex(b.texture), UF_Skin, 0, CLAMP_XY, NO_TRANSLATION, -1);
				state.Draw(DT_Triangles, b.first, b.count);
			}
		}
		// The near flats, turned to the camera again once it has moved a tile.
		const double camX = camera->X() - f.offX - flatAnchorX * TILE, camY = camera->Y() - f.offY - flatAnchorY * TILE;
		if (nearDirty || nearBufferOwner != screen || std::hypot(camX - nearCamX, camY - nearCamY) > NEAR_MOVE) BuildNear(camX, camY);
		if (nearBuffer)
		{
			state.SetVertexBuffer(nearBuffer->vertexBuffer(), 0, 0);
			for (const FlatBatch &b : nearBatches)
			{
				state.SetMaterial(TexMan.GameByIndex(b.texture), UF_Skin, 0, CLAMP_XY, NO_TRANSLATION, -1);
				state.Draw(DT_Triangles, b.first, b.count);
			}
		}
		state.AlphaFunc(Alpha_GEqual, 0.f);
	}
	state.EnableModelMatrix(false);
	state.EnableFog(true);
	state.SetVertexBuffer(screen->mVertexData);
}
