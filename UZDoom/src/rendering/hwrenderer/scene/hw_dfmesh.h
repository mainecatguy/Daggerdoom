// [DoomDaggerfall] Opt-in static mesh layer for converted Daggerfall maps. See hw_dfmesh.cpp.
#pragma once

struct FLevelLocals;
class FRenderState;

bool DFMesh_HideCollider(FLevelLocals *level);	// true only on a Daggerfall-layer map in mesh view
void DFMesh_Draw(FRenderState &state);
void DFMesh_FrameTick(FLevelLocals *level);
