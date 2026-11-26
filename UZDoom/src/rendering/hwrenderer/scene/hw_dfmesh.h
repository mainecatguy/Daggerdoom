// [Doomerfall] Opt-in static mesh layer for converted Daggerfall maps. See hw_dfmesh.cpp.
#pragma once

struct FLevelLocals;
class FRenderState;

bool DFMesh_HideCollider(FLevelLocals *level);	// true only on a Daggerfall-layer map in mesh view
void DFMesh_Draw(FRenderState &state);
void DFMesh_DrawLod(FLevelLocals *level, FRenderState &state);	// the town mesh, seen from the overworld
void DFMesh_FrameTick(FLevelLocals *level);
bool DFMesh_WindowText(const char *text);	// [Doomerfall] "windows <r> <g> <b>": Daggerfall's window emission colour
