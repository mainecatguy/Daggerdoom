// [DoomDaggerfall] Opt-in static mesh layer for converted Daggerfall maps.
//
// A map has this layer only when a loaded DFMESH lump names it. The whole mesh is one static vertex
// buffer, batched by texture and drawn every frame, so it does not depend on Doom sector visibility.
// Without the lump every entry point returns immediately. F1 and dfmesh_view switch between the
// mesh and the Doom collider view. Collision and game logic are not touched.

#include <algorithm>
#include <string.h>
#include <vector>

#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_event.h"
#include "doomstat.h"
#include "filesystem.h"
#include "g_levellocals.h"
#include "hw_dfmesh.h"
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

CVAR(Bool, dfmesh_view, true, 0)	// true: Daggerfall mesh. false: Doom collider view.

namespace
{
	struct Batch { FGameTexture *texture; int first, count; };

	FModelVertexBuffer *buffer;
	DFrameBuffer *bufferOwner;
	std::vector<Batch> batches;
	FString checkedMap;
	bool checked, present;
	int triangles;

	bool benchOn;
	uint64_t benchLast;
	std::vector<double> benchFrames;

	void Load(int lump)
	{
		uint64_t start = I_nsTime();
		auto data = fileSystem.ReadFile(lump);
		auto bytes = data.bytes();
		int textures, batchCount, vertices;
		memcpy(&textures, bytes + 12, 4);
		memcpy(&batchCount, bytes + 16, 4);
		memcpy(&vertices, bytes + 20, 4);
		const uint8_t *names = bytes + 24;
		const uint8_t *table = names + textures * 32;
		const float *source = (const float *)(table + batchCount * 12);

		batches.clear();
		for (int i = 0; i < batchCount; i++)
		{
			int entry[3];
			memcpy(entry, table + i * 12, 12);
			char name[33] = {};
			memcpy(name, names + entry[0] * 32, 32);
			FTextureID id = TexMan.CheckForTexture(name, ETextureType::Any, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_ForceLookup);
			FGameTexture *texture = id.isValid() ? TexMan.GetGameTexture(id) : nullptr;
			if (!texture) Printf(TEXTCOLOR_RED "DFMesh: missing texture %s\n", name);
			batches.push_back({ texture, entry[1], entry[2] });
		}

		delete buffer;
		buffer = new FModelVertexBuffer(false, true);
		bufferOwner = screen;
		FModelVertex *out = buffer->LockVertexBuffer(vertices);
		memset(out, 0, vertices * sizeof(FModelVertex));
		for (int i = 0; i < vertices; i++, source += 8)
		{
			out[i].Set(source[0], source[1], source[2], source[3], source[4]);
			out[i].SetNormal(source[5], source[6], source[7]);
		}
		buffer->UnlockVertexBuffer();
		triangles = vertices / 3;
		Printf("DFMesh: loaded %d triangles, %d draw batches in %.1f ms\n", triangles, batchCount, (I_nsTime() - start) / 1e6);
	}

	bool Active(FLevelLocals *level)
	{
		if (level != primaryLevel) return false;
		if (!checked || checkedMap.CompareNoCase(level->MapName) != 0)
		{
			checked = true;
			checkedMap = level->MapName;
			present = false;
			int lump = fileSystem.CheckNumForName("DFMESH");
			if (lump >= 0 && fileSystem.FileLength(lump) >= 24)
			{
				auto data = fileSystem.ReadFile(lump);
				auto bytes = data.bytes();
				char map[9] = {};
				memcpy(map, bytes + 4, 8);
				present = !memcmp(bytes, "DFM1", 4) && level->MapName.CompareNoCase(map) == 0;
				if (present) Load(lump);
			}
		}
		if (present && bufferOwner != screen) Load(fileSystem.CheckNumForName("DFMESH"));
		return present;
	}
}

bool DFMesh_HideCollider(FLevelLocals *level)
{
	return Active(level) && dfmesh_view;
}

void DFMesh_Draw(FRenderState &state)
{
	state.SetVertexBuffer(buffer->vertexBuffer(), 0, 0);
	state.SetCulling(portalState.isMirrored() ? Cull_CCW : Cull_CW);
	state.EnableFog(false);
	state.SetFog(0, 0);
	state.SetSoftLightLevel(255);
	state.SetColor(1.f, 1.f, 1.f, 1.f);
	state.SetObjectColor(0xffffffff);
	state.SetAddColor(0);
	state.SetDynLight(0, 0, 0);
	state.SetLightIndex(-1);
	state.EnableTextureMatrix(false);
	state.SetRenderStyle(STYLE_Source);
	state.AlphaFunc(Alpha_GEqual, 0.f);
	for (const Batch &batch : batches)
	{
		if (!batch.texture) continue;
		state.SetMaterial(batch.texture, UF_Skin, 0, CLAMP_NONE, NO_TRANSLATION, -1);
		state.Draw(DT_Triangles, batch.first, batch.count);
	}
	state.SetCulling(Cull_None);
	state.EnableFog(true);
	state.SetVertexBuffer(screen->mVertexData);
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

// dfmesh_bench 1 starts recording frame intervals. dfmesh_bench 0 stops and prints them.
CCMD(dfmesh_bench)
{
	if (argv.argc() < 2) return;
	if (atoi(argv[1]))
	{
		benchFrames.clear();
		benchLast = 0;
		benchOn = true;
		return;
	}
	benchOn = false;
	if (benchFrames.empty()) { Printf("DFBENCH no frames\n"); return; }
	std::sort(benchFrames.begin(), benchFrames.end());
	size_t n = benchFrames.size();
	Printf("DFBENCH view=%s frames=%zu median=%.2f p95=%.2f worst=%.2f triangles=%d batches=%zu res=%dx%d\n",
		dfmesh_view ? "mesh" : "collider", n, benchFrames[n / 2], benchFrames[std::min(n - 1, n * 95 / 100)], benchFrames[n - 1],
		dfmesh_view ? triangles : 0, dfmesh_view ? batches.size() : 0, screen->GetWidth(), screen->GetHeight());
}
