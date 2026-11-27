// [Doomerfall] Opt-in static mesh layer for converted Daggerfall maps.
//
// A map has this layer only when a loaded DFMESH lump names it. The whole mesh is one static vertex
// buffer, batched by texture and drawn every frame, so it does not depend on Doom sector visibility.
// Without the lump every entry point returns immediately. F1 and dfmesh_view switch between the
// mesh and the Doom collider view. Collision and game logic are not touched.

#include <algorithm>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <vector>

#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_event.h"
#include "d_eventbase.h"
#include "menustate.h"
#include "doomstat.h"
#include "filesystem.h"
#include "g_levellocals.h"
#include "hw_dfmesh.h"
#include "playsim/dd_treadmill.h"
#include "hw_material.h"
#include "hw_modelvertexbuffer.h"
#include "hw_portal.h"
#include "hw_renderstate.h"
#include "i_time.h"
#include "keydef.h"
#include "printf.h"
#include "texturemanager.h"
#include "v_video.h"
#include "flatvertices.h"
#include "hw_dynlightdata.h"
#include "hw_lightbuffer.h"
#include "a_dynlight.h"
#include "playsim/dd_log.h" // [Doomerfall]

void AddLightToList(FDynLightData &dld, int group, FDynamicLight *light, bool forceAttenuate);	// hw_dynlightdata.cpp

CVAR(Bool, dfmesh_view, true, 0)	// true: Daggerfall mesh. false: Doom collider view.

namespace
{
	// texture is an ID, so ANIMDEFS can pick the current frame. window is the texture's window mask (dfwin/...), if it has one.
	struct Batch { FTextureID texture; int first, count; FTextureID window; };
	// Daggerfall's window emission colour (MaterialReader's window colour x intensity for the current WindowStyle),
	// sent as "windows <r> <g> <b>". All zero (the default, and Daggerfall's Disabled style) draws no window pass.
	float windowColor[3];
	// Dynamic lights: the mesh is split into square cells, each with its own light list, so a fragment only
	// evaluates the lights that can reach its cell. Cells hold their own batches, in vertex order.
	constexpr float LIGHT_CELL = 1024.f;
	struct Cell { float lo[3], hi[3]; int firstBatch, batchCount; };
	std::vector<Cell> cells;

	FModelVertexBuffer *buffer;
	DFrameBuffer *bufferOwner;
	std::vector<Batch> batches;
	FString checkedMap, meshMap;
	int loadedLump = -1, headerLump = -1;
	bool checked, present;
	int triangles;

	bool benchOn;
	uint64_t benchLast;
	std::vector<double> benchFrames;
	int benchMinTriangles = INT_MAX, benchMaxTriangles;

	// A key identifies the loaded mesh: a lump number, or a generated location's key from the town cache.
	void LoadBytes(const uint8_t *bytes, int key)
	{
		uint64_t start = I_nsTime();
		loadedLump = key;
		int textures, batchCount, vertices;
		memcpy(&textures, bytes + 12, 4);
		memcpy(&batchCount, bytes + 16, 4);
		memcpy(&vertices, bytes + 20, 4);
		const uint8_t *names = bytes + 24;
		const uint8_t *table = names + textures * 32;
		const float *source = (const float *)(table + batchCount * 12);

		std::vector<Batch> loaded;
		for (int i = 0; i < batchCount; i++)
		{
			int entry[3];
			memcpy(entry, table + i * 12, 12);
			char name[33] = {};
			memcpy(name, names + entry[0] * 32, 32);
			FTextureID id = TexMan.CheckForTexture(name, ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup);
			if (!id.isValid() || !TexMan.GetGameTexture(id)) { DD_DebugPrintf(TEXTCOLOR_RED "DFMesh: missing texture %s\n", name); id.SetInvalid(); }
			FTextureID window;
			window.SetInvalid();
			if (!strncmp(name, "dfmesh/", 7))	// window masks are written only for Daggerfall's exterior window textures
			{
				FString mask = FString("dfwin/") + (name + 7);
				window = TexMan.CheckForTexture(mask.GetChars(), ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup);
			}
			loaded.push_back({ id, entry[1], entry[2], window });
		}

		// Vertices are x, height, y (GL order), 8 floats each. A triangle goes to the cell of its first corner,
		// then batches by texture inside the cell.
		struct Key { int cell, batch, tri; };
		std::vector<Key> order;
		order.reserve(vertices / 3);
		std::vector<std::pair<int, int>> cellIds;
		auto cellOf = [&](const float *v) {
			std::pair<int, int> c(int(floorf(v[0] / LIGHT_CELL)), int(floorf(v[2] / LIGHT_CELL)));
			auto found = std::find(cellIds.begin(), cellIds.end(), c);
			if (found != cellIds.end()) return int(found - cellIds.begin());
			cellIds.push_back(c);
			return int(cellIds.size()) - 1;
		};
		for (int b = 0; b < batchCount; b++)
			for (int t = loaded[b].first / 3; t < (loaded[b].first + loaded[b].count) / 3; t++)
				order.push_back({ cellOf(source + t * 24), b, t });
		std::stable_sort(order.begin(), order.end(), [](const Key &a, const Key &b) { return a.cell != b.cell ? a.cell < b.cell : a.batch < b.batch; });

		delete buffer;
		buffer = new FModelVertexBuffer(false, true);
		bufferOwner = screen;
		FModelVertex *out = buffer->LockVertexBuffer(vertices);
		memset(out, 0, vertices * sizeof(FModelVertex));
		batches.clear();
		cells.clear();
		int at = 0;
		for (size_t k = 0; k < order.size(); k++)
		{
			const Key &key = order[k];
			const bool newCell = k == 0 || order[k - 1].cell != key.cell;
			if (newCell) cells.push_back({ { 1e30f, 1e30f, 1e30f }, { -1e30f, -1e30f, -1e30f }, int(batches.size()), 0 });
			Cell &cell = cells.back();
			if (newCell || order[k - 1].batch != key.batch)
			{
				batches.push_back({ loaded[key.batch].texture, at, 0, loaded[key.batch].window });
				cell.batchCount++;
			}
			for (int c = 0; c < 3; c++, at++)
			{
				const float *v = source + (key.tri * 3 + c) * 8;
				out[at].Set(v[0], v[1], v[2], v[3], v[4]);
				out[at].SetNormal(v[5], v[6], v[7]);
				for (int a = 0; a < 3; a++) { cell.lo[a] = std::min(cell.lo[a], v[a]); cell.hi[a] = std::max(cell.hi[a], v[a]); }
			}
			batches.back().count += 3;
		}
		buffer->UnlockVertexBuffer();
		triangles = vertices / 3;
		DD_DebugPrintf("DFMesh: loaded %d triangles, %d draw batches in %.1f ms\n", triangles, batchCount, (I_nsTime() - start) / 1e6);
	}

	void Load(int lump)
	{
		auto data = fileSystem.ReadFile(lump);
		LoadBytes(data.bytes(), lump);
	}

	bool Active(FLevelLocals *level)
	{
		if (level != primaryLevel) return false;
		if (DDTreadmill_RuntimeTowns())
		{
			const uint8_t *data;
			size_t size;
			int key;
			if (DDTreadmill_MapMesh(level->MapName.GetChars(), data, size, key))
			{
				if (!buffer || loadedLump != key || bufferOwner != screen) LoadBytes(data, key);
				return true;
			}
		}
		if (!checked || checkedMap.CompareNoCase(level->MapName) != 0)
		{
			checked = true;
			checkedMap = level->MapName;
			present = false;
			int lump = fileSystem.CheckNumForName("DFMESH");
			if (lump >= 0 && fileSystem.FileLength(lump) >= 24)
			{
				if (lump != headerLump)
				{
					auto data = fileSystem.ReadFile(lump);
					auto bytes = data.bytes();
					char map[9] = {};
					memcpy(map, bytes + 4, 8);
					headerLump = lump;
					meshMap = memcmp(bytes, "DFM1", 4) ? "" : map;
				}
				present = level->MapName.CompareNoCase(meshMap) == 0;
			}
		}
		// Checked every time: a town shares this buffer without updating checkedMap, so returning to the same map can find the town's mesh here.
		if (present && (!buffer || loadedLump != headerLump || bufferOwner != screen)) Load(headerLump);
		return present;
	}
}

bool DFMesh_HideCollider(FLevelLocals *level)
{
	return Active(level) && dfmesh_view;
}

CVAR(Bool, dfmesh_lights, true, CVAR_ARCHIVE)	// dynamic lights and sector-light ambient on the mesh

bool DD_WeatherFog(PalEntry &color, float &density);	// playsim/dd_weather.cpp
bool DD_WeatherMeshLight(float &brightness);

// The mesh's brightness follows the light level of the viewer's sector: the converter's 176 (and above) is full
// brightness, as before lights. Doomerfall darkens sectors in lit dungeons and interiors (dd_lights.cpp), and outdoors
// the mesh takes Daggerfall's daylight (dd_weather.cpp).
static float Ambient()
{
	if (!dfmesh_lights || !primaryLevel) return 1.f;
	if (float daylight; DD_WeatherMeshLight(daylight)) return daylight;	// [Doomerfall] Daggerfall's daylight outdoors
	auto *player = primaryLevel->Players[consoleplayer];
	AActor *camera = player ? player->camera.Get() : nullptr;
	if (!camera || !camera->Sector) return 1.f;
	return std::min(1.f, camera->Sector->lightlevel / 176.f);
}

// One light list per cell: every active light whose sphere touches the cell's box. offset is the mesh's world position.
static int CellLights(const Cell &cell, const float offset[3])
{
	static FDynLightData lightdata;
	lightdata.Clear();
	for (FDynamicLight *light = primaryLevel->lights; light; light = light->next)
	{
		const float r = light->GetRadius();
		if (r <= 0) continue;
		const float p[3] = { float(light->Pos.X), float(light->Pos.Z), float(light->Pos.Y) };
		float d2 = 0;
		for (int a = 0; a < 3; a++)
		{
			const float lo = cell.lo[a] + offset[a], hi = cell.hi[a] + offset[a];
			const float d = p[a] < lo ? lo - p[a] : p[a] > hi ? p[a] - hi : 0;
			d2 += d * d;
		}
		if (d2 < r * r) AddLightToList(lightdata, 0, light, false);
	}
	return lightdata.arrays[0].Size() + lightdata.arrays[1].Size() + lightdata.arrays[2].Size() ? screen->mLights->UploadLights(lightdata) : -1;
}

static void DrawWith(FRenderState &state, const float offset[3]);

// Daggerfall's window emission: its window materials add the window colour where the texture's palette index is 255
// (BaseImageFile.GetWindowColors32). The window batches are drawn again over themselves, additive and unlit, with the
// mask texture tinted by the window colour. Fog fades the added light to nothing, as Unity's fog covers emission.
static int DrawWindows(FRenderState &state, float fogDensity)
{
	int drawn = 0;
	state.SetFog(PalEntry(1, 1, 1), fogDensity);	// near black: Doom treats pure black fade as light-level shading, not fog
	state.SetColor(windowColor[0], windowColor[1], windowColor[2], 1.f);
	state.SetRenderStyle(STYLE_Add);	// adds colour x mask alpha: far away the mipmaps average the glow, as Unity's emission does
	state.AlphaFunc(Alpha_GEqual, 0.f);	// an alpha test would drop most of a distant window's lattice
	state.SetDepthMask(false);
	state.SetDepthFunc(DF_LEqual);
	for (const Batch &batch : batches)
	{
		if (!batch.window.isValid()) continue;
		state.SetMaterial(TexMan.GetGameTexture(batch.window, true), UF_Skin, 0, CLAMP_NONE, NO_TRANSLATION, -1);
		state.Draw(DT_Triangles, batch.first, batch.count);
		drawn += batch.count / 3;
	}
	state.SetDepthFunc(DF_Less);
	state.SetDepthMask(true);
	state.SetRenderStyle(STYLE_Source);
	state.AlphaFunc(Alpha_GEqual, 0.f);
	return drawn;
}

// "windows <r> <g> <b>" from Daggerfall (0 to 255). Returns false for any other text.
bool DFMesh_WindowText(const char *text)
{
	float c[3];
	if (sscanf(text, "windows %f %f %f", &c[0], &c[1], &c[2]) != 3) return false;
	if (c[0] != windowColor[0] * 255 || c[1] != windowColor[1] * 255 || c[2] != windowColor[2] * 255)
		DD_DebugPrintf("DFMESH windows %.0f %.0f %.0f\n", c[0], c[1], c[2]);
	for (int i = 0; i < 3; i++) windowColor[i] = std::clamp(c[i], 0.f, 255.f) / 255.f;
	return true;
}

CCMD(dfmesh_windows)	// the same line by hand, for runs without Daggerfall: dfmesh_windows "windows 204 146 45"
{
	if (argv.argc() < 2 || !DFMesh_WindowText(argv[1])) Printf("usage: dfmesh_windows \"windows <r> <g> <b>\"\n");
}

void DFMesh_Draw(FRenderState &state)
{
	const float none[3] = { 0, 0, 0 };
	DrawWith(state, none);
}

static void DrawWith(FRenderState &state, const float offset[3])
{
	state.SetVertexBuffer(buffer->vertexBuffer(), 0, 0);
	state.SetCulling(portalState.isMirrored() ? Cull_CCW : Cull_CW);
	PalEntry fogColor;
	float fogDensity;
	const bool fog = DD_WeatherFog(fogColor, fogDensity);	// [Doomerfall] Daggerfall's weather fog outdoors
	state.EnableFog(fog);
	state.SetFog(fog ? fogColor : PalEntry(0), fog ? fogDensity : 0);
	state.SetSoftLightLevel(255);
	const float ambient = Ambient();
	state.SetColor(ambient, ambient, ambient, 1.f);
	state.SetObjectColor(0xffffffff);
	state.SetAddColor(0);
	state.SetDynLight(0, 0, 0);
	state.SetLightIndex(-1);
	state.EnableTextureMatrix(false);
	state.SetRenderStyle(STYLE_Source);
	state.AlphaFunc(Alpha_GEqual, 0.f);
	int submitted = 0;
	const bool lit = dfmesh_lights && primaryLevel && primaryLevel->lights;
	for (const Cell &cell : cells)
	{
		const int lightIndex = lit ? CellLights(cell, offset) : -1;
		for (int i = cell.firstBatch; i < cell.firstBatch + cell.batchCount; i++)
		{
			const Batch &batch = batches[i];
			if (!batch.texture.isValid()) continue;
			state.SetMaterial(TexMan.GetGameTexture(batch.texture, true), UF_Skin, 0, CLAMP_NONE, NO_TRANSLATION, -1);
			state.SetLightIndex(lightIndex);
			state.Draw(DT_Triangles, batch.first, batch.count);
			submitted += batch.count / 3;
		}
	}
	state.SetLightIndex(-1);
	if (windowColor[0] + windowColor[1] + windowColor[2] > 0) submitted += DrawWindows(state, fog ? fogDensity : 0);
	if (benchOn)
	{
		benchMinTriangles = std::min(benchMinTriangles, submitted);
		benchMaxTriangles = std::max(benchMaxTriangles, submitted);
	}
	state.SetCulling(Cull_None);
	state.EnableFog(true);
	state.SetVertexBuffer(screen->mVertexData);
}

// Draws the town's mesh in the overworld at its true world position, over the grid tiles it replaces.
void DFMesh_DrawLod(FLevelLocals *level, FRenderState &state)
{
	double x, y, z;
	if (level != primaryLevel || !dfmesh_view || !DDTreadmill_MeshOffset(x, y, z)) return;
	if (DDTreadmill_RuntimeTowns())
	{
		const uint8_t *data;
		size_t size;
		int key;
		if (!DDTreadmill_LodMesh(data, size, key)) return;
		if (!buffer || loadedLump != key || bufferOwner != screen) LoadBytes(data, key);
	}
	else
	{
		const int lump = fileSystem.CheckNumForName("DFMESH");
		if (lump < 0) return;
		if (!buffer || loadedLump != lump || bufferOwner != screen) Load(lump);
	}
	state.mModelMatrix.loadIdentity();
	state.mModelMatrix.translate(float(x), float(z), float(y));
	state.EnableModelMatrix(true);
	const float offset[3] = { float(x), float(z), float(y) };
	DrawWith(state, offset);
	state.EnableModelMatrix(false);
}

void DFMesh_FrameTick(FLevelLocals *level)
{
	if (!benchOn || !Active(level)) return;
	uint64_t now = I_nsTime();
	if (benchLast) benchFrames.push_back((now - benchLast) / 1e6);
	benchLast = now;
}

bool DFMesh_Responder(event_t *ev)
{
	if (ev->type != EV_KeyDown || ev->data1 != KEY_F1 || gamestate != GS_LEVEL || !Active(primaryLevel)) return false;
	dfmesh_view = !dfmesh_view;
	Printf(PRINT_HIGH, "%s\n", dfmesh_view ? "Daggerfall mesh view" : "Doom collider view");
	return true;
}

// Test hooks: post a real F1 key press through the event queue, and report the resulting state.
CCMD(dfmesh_pressf1)
{
	event_t ev = {};
	ev.type = EV_KeyDown;
	ev.data1 = KEY_F1;
	D_PostEvent(&ev);
	ev.type = EV_KeyUp;
	D_PostEvent(&ev);
}

CCMD(dfmesh_status)
{
	Printf("DFSTATUS map=%s layer=%d view=%d menu=%d time=%d\n", primaryLevel->MapName.GetChars(), Active(primaryLevel), (int)*dfmesh_view, menuactive != MENU_Off, primaryLevel->maptime);
}

// dfmesh_bench 1 starts recording frame intervals. dfmesh_bench 0 stops and prints them.
CCMD(dfmesh_bench)
{
	if (argv.argc() < 2) return;
	if (atoi(argv[1]))
	{
		benchFrames.clear();
		benchLast = 0;
		benchMinTriangles = INT_MAX;
		benchMaxTriangles = 0;
		benchOn = true;
		return;
	}
	benchOn = false;
	if (benchFrames.empty()) { Printf("DFBENCH no frames\n"); return; }
	std::sort(benchFrames.begin(), benchFrames.end());
	size_t n = benchFrames.size();
	Printf("DFBENCH view=%s frames=%zu median=%.2f p95=%.2f worst=%.2f triangles=%d submitted_min=%d submitted_max=%d batches=%zu res=%dx%d\n",
		dfmesh_view ? "mesh" : "collider", n, benchFrames[n / 2], benchFrames[std::min(n - 1, n * 95 / 100)], benchFrames[n - 1],
		dfmesh_view ? triangles : 0, dfmesh_view ? benchMinTriangles : 0, benchMaxTriangles, dfmesh_view ? batches.size() : 0, screen->GetWidth(), screen->GetHeight());
}
