# Daggerfall mesh layer, stage 1 results

**Result: PASS for stage 1, with defects listed below.** Daggerfall's real models, textures, and UVs draw in UZDoom over the unchanged invisible Doom collision on Privateer's Hold. No human has played it yet. Game feel, the on-screen F1 message, and performance in a focused window still need the owner's check.

**Review page:** `D:\dev\DoomDaggerfall-loop\review\daggerfall-mesh\compare\index.html` (Daggerfall, mesh view, collider view). `all_views_df_mesh.png` in the same folder shows all 16 views on one sheet. Generated output, not committed.

## How to launch

```powershell
D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe -iwad D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD -file D:\dev\DoomDaggerfall-loop\review\daggerfall-mesh\map\privateershold.wad D:\dev\DoomDaggerfall-loop\review\daggerfall-mesh\map\privateershold_mesh.pk3 +map MAP01
```

Press **F1** to switch between Daggerfall mesh view and Doom collider view. The console equivalent is `dfmesh_view 1` or `dfmesh_view 0`.

## Rendering approach

Stock model actors were not tried. A small static-mesh pass was simpler and removes sector visibility from the problem.

- The exporter writes one `DFMESH` lump, with vertices batched by texture, plus PNG textures. It uses Daggerfall Unity's model placement, triangle fans, UV normalization, and classic dungeon texture table.
- The engine draws the whole mesh every frame, with back-face culling and no sector or frustum culling.
- Mesh view skips Doom walls, flats, and decals. Collision and game logic are not touched.
- The layer exists only when a loaded `DFMESH` lump names the current map.
- The mesh package sets `pixelratio = 1.0` for this map. Doom's default 1.2 vertical stretch visibly distorted the real mesh.

**Engine patch:** 232 lines added and 6 removed across 5 files. 215 of the added lines are the new `hw_dfmesh.cpp` and `hw_dfmesh.h`. All edits are marked `[DoomDaggerfall]`.

## Commands

```powershell
dotnet run -c Release -v q --project tools/dungeon_converter/DungeonConverter.csproj -- "Privateer's Hold" --out <out>\map
dotnet run -c Release -v q --project tools/dungeon_converter/DungeonConverter.csproj -- "Privateer's Hold" --out <out>\map --export-mesh
cmake --build D:/dev/DoomDaggerfall-build/uzdoom-mesh --config Release --parallel 6
python tools/dungeon_compare/mesh_compare.py --views tools/dungeon_compare/views/privateers_hold.txt --map <out>\map\privateershold.wad --mesh <out>\map\privateershold_mesh.pk3 --df D:\dev\DoomDaggerfall-loop\review\connectivity-fix --out <out>\compare --mode views
python tools/dungeon_compare/mesh_compare.py <same arguments> --mode sweep --width 480 --height 360 --timeout 140
python tools/dungeon_compare/mesh_compare.py <same arguments> --mode bench
python tools/dungeon_compare/mesh_f1_check.py --map <out>\map\privateershold.wad --mesh <out>\map\privateershold_mesh.pk3 --out <out>\f1
```

## Viewpoints

All 16 were inspected by eye. Geometry, placement, textures, and UVs match Daggerfall, including the v14 ramp view and the v16 angled cave tunnel. No missing faces, flipped faces, or seams were visible at these views. The v10 door-shaped hole into empty space also appears in the mesh, as it does in Daggerfall.

Scores are mean absolute color difference from the Daggerfall capture after matching overall brightness. Lower is closer. They include the lighting difference and missing sprites.

| View | Mesh | Collider | View | Mesh | Collider |
|---|---:|---:|---|---:|---:|
| v01 | 3.3 | 10.1 | v09 | 6.4 | 11.4 |
| v02 | 3.4 | 12.5 | v10 | 15.2 | 18.2 |
| v03 | 4.6 | 9.6 | v11 | 4.0 | 7.4 |
| v04 | 3.7 | 15.8 | v12 | 6.9 | 19.1 |
| v05 | 3.7 | 10.2 | v13 | 3.8 | 17.2 |
| v06 | 8.5 | 15.3 | v14 | 12.2 | 19.6 |
| v07 | 7.4 | 11.9 | v15 | 4.8 | 7.6 |
| v08 | 3.4 | 12.9 | v16 | 5.2 | 15.1 |

## Popping

No model disappearance was found on the tested path.

- **Submission:** all 9,079 triangles were submitted on every mesh-view frame of the timing path (minimum and maximum both 9,079, 50,827 frames).
- **Image sweep:** 786 camera steps with 1 degree turns and 4-unit walks through a room, a door, both ends of a stacked column, the ramp, and the cave.
- **Detector control:** it caught 78 of 78 injected one-frame disappearances covering 5% of the frame. An earlier detector caught only 2 of 31, so its result was discarded.
- **Flagged frames:** the detector flagged 40 frames, all in walking segments and none in turning segments. I inspected all 40 on a contact sheet. They show close textures sliding past or the camera passing through a door, with no model vanishing.

## Performance

Same 420-step camera path, 960x720, Vulkan, NVIDIA RTX 5080, vsync and frame cap off. The window was not minimized, was off-screen, and did not have focus.

| View | Frames | Median | 95th percentile | Worst | Triangles | Mesh draws |
|---|---:|---:|---:|---:|---:|---:|
| Daggerfall mesh | 50,827 | 0.32 ms | 1.35 ms | 5.01 ms | 9,079 | 81 |
| Doom collider | 36,424 | 0.33 ms | 2.73 ms | 7.46 ms | n/a | 0 |

Mesh loading took 3.0 ms, not counting texture upload on first draw. These are intervals between frames in a background window, so a focused run at real resolution is still on the play-test list. OpenGL was not tested.

## E1M1

`mesh_f1_check.py` posts a real F1 key event through the engine's event queue, without window focus.

- **Daggerfall map:** the layer is active, F1 changes the view, and no menu opens.
- **`DOOM.WAD` E1M1:** the patched engine starts and enters E1M1 with no layer. F1 opens the normal help menu, the menu closes, map time advances from 139 to 155 tics, and the engine exits with code 0.

## Remaining defects

1. **Doors do not move visually.** The mesh draws doors closed. In mesh view, a Doom door can open and let the player walk through a door that still looks shut. Moving objects are an open owner decision.
2. **Daggerfall flats are missing.** Torches, lamps, campfires, and other billboard sprites were not exported (visible at v10 and v12).
3. **Lighting is not Daggerfall's.** The mesh is flat and full bright, so it looks brighter than the captures, especially in the cave.
4. **Doom sprites are untested in mesh view.** Monsters and the player weapon were disabled in all captures. Sprites still use Doom sector visibility and may clip against the mesh where it differs from collision.
5. **Impact decals are hidden in mesh view,** because they sit on the hidden collider surfaces.
6. **Hardware renderer only.** The layer is not implemented in the software renderer.
7. **The map check is by name.** Loading the mesh package with a different `MAP01` would draw this mesh over that map.

## Play-test list

1. Walk the entrance, the v14 ramp, and the v16 tunnel in mesh view, and check for popping or a mismatch between what you see and where you collide.
2. Press F1 and confirm the mode message is readable.
3. Open a door in mesh view and judge how much defect 1 matters.
4. Fire a weapon and summon a monster in mesh view to check sprites against the mesh.
5. Check frame rate in a focused window at your normal resolution.
