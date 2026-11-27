// [Doomerfall] Distant terrain view for Daggerfall exteriors.
//
// Daggerfall Unity streams terrain for several map pixels around the player. A Doom map only holds the loaded
// window (the overworld treadmill) or a location's own area (a town or dungeon exterior map), so beyond it this pass
// draws a render-only ring of terrain from the same height function, out to about 60,000 Doom units.
//
// Everything is computed from world tile coordinates, so the ring is the same ground on every map that shows it and
// stays put across treadmill shifts. Nothing is stored. Inside the map's own tiles nothing is drawn; a fine band (one
// tile per quad) meets the map's terrain edge exactly, and coarse quads (four tiles) cover the rest.
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
	bool haveBuilt;
	int vertexCount, anchorX, anchorY;
	std::vector<FModelVertex> verts;

	void Build(const Key &key, const DDHorizonFrame &f)
	{
		const uint64_t start = I_nsTime();
		if (heights.size() > 4000) heights.clear();
		anchorX = key.cx;
		anchorY = key.cy;
		// The fine band around the map's own tiles, on the coarse grid.
		const int fx0 = FloorTo(key.x0 - FINE_BAND, STEP), fx1 = CeilTo(key.x1 + FINE_BAND, STEP);
		const int fy0 = FloorTo(key.y0 - FINE_BAND, STEP), fy1 = CeilTo(key.y1 + FINE_BAND, STEP);
		// A fine vertex on the band's outer edge takes the coarse edge's height there, so the two meet without cracks.
		auto fineHeight = [&](int x, int y) {
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
		};
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
	if (!haveBuilt || !(built == key) || !buffer || bufferOwner != screen) Build(key, f);
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
	state.EnableModelMatrix(false);
	state.EnableFog(true);
	state.SetVertexBuffer(screen->mVertexData);
}
