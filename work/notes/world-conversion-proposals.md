# Putting the Daggerfall world inside UZDoom: research and proposals

Run `20261121-214123`. Research and throwaway experiments only. No production converter was built and no final architecture is chosen.

**Evidence labels:** **[M]** measured in this run, **[C]** read from code, **[I]** inferred or general engine knowledge not checked here, **[W]** web. No web sources were used, because the vendored engine source answered the questions directly.

## Summary

- **A single Doom map cannot hold the world.** UDMF coordinates stop at ±32768 [C], so one map spans about 0.2% of Daggerfall's east-west width at 1:1 [M]. Any solution must move a local window through a global coordinate system.
- **Stock UZDoom can already load a generated map at runtime.** `level.ChangeLevel("file:<path>")` from ZScript loaded a WAD written after the engine started, with no restart and no engine patch [M]. This is most of architecture hurdle 1.
- **The owner's registry model worked in its first test.** 2,000 monsters were restored from double-precision global positions in about 2.9 ms, and the player's position error was zero over 8 swaps [M]. Monster AI state and projectiles were not tested.
- **The main cost is the load hitch.** A full-detail 32,768-sector window takes about 0.6 s to swap. Straight-line running would trigger that about every 21 s [M, derived]. Reducing it is the most important open engineering question.
- **Recommendation:** prototype **Proposal A, rolling map windows**, on real terrain. Move to **Proposal B, a reusable terrain mesh**, only if A's hitch cannot be made acceptable. A's converter and registry carry over to B.

## Limits of this evidence

- All map timings use **synthetic terrain** with no real textures, buildings, or Daggerfall bridge. Real content will change them.
- Timings come from one machine, the hardware renderer, a 1280x720 window, and few repetitions. Treat them as orders of magnitude.
- Frame times below 2 ms were hidden by a frame cap.
- Terrain relief uses **base elevation only**. It leaves out Daggerfall's detail noise, so real local slopes are steeper.
- Game feel has not been judged by a human.

---

## 1. Doom map system

### Representation and loading

| Topic | Finding | Evidence |
|---|---|---|
| UDMF | Text map format. Coordinates and heights outside ±32768 mark the map as unstartable. | [C] `UZDoom/src/maploader/udmf.cpp:265`, `:1701`, `:2354` |
| Exact limit | A map with a vertex at exactly +32768 passes the parser, then crashed with heap corruption. A map spanning 65,472 units ran normally. **Use a span under 65,536.** | [M]. Cause inferred from 16.16 `fixed_t` in `nodebuild.h:78` |
| Sectors, lines | Stored in flat per-level arrays built at load. ZScript cannot add geometry. | [C] `g_levellocals.h:492`, [I] |
| Slopes | Vertex-height slopes work only on triangular sectors, so a heightfield needs 2 sectors per terrain tile. | [C] `maploader/slopes.cpp:298` |
| 3D floors | Extra solid or liquid planes in a sector. Useful for bridges and overhangs, at added cost. | [C] `p_3dfloors.cpp:94`, [I] |
| Polyobjects | Moving line groups, limited in shape and height. A poor fit for general buildings. | [C] `po_man.cpp:117`, [I] |
| Models | Render as actors. They have no per-polygon collision, so visible buildings need separate collision. | [I] |
| BSP/nodes | Built at load when absent. 64,896 segs took 0.172 s, so BSP is only part of the load cost. | [M] |
| Blockmap | 128-unit cells for collision queries. | [C] `gamedata/p_blockmap.h:69` |
| Actor positions | Stored as doubles, so the simulation is not the coordinate limit. | [C] `playsim/actor.h:1142` |

### Simulation

- **Collision:** sector planes, lines, and blockmap queries [I]. Adjacent triangles in a continuous mesh have no step between them, so step height matters less than **slope steepness**.
- **Steep slopes:** floors steeper than about 45° are not walkable by default [C `p_local.h:50`]. `MaxSlopeSteepness` and `MaxStepHeight` are actor properties, so both can be tuned from a mod [C `actor.zs:333-334`, `:445-447`].
- **Line of sight:** `P_CheckSight` works against level geometry and cannot see past the loaded window [C `p_sight.cpp:840`, I].
- **Sound propagation:** monster alerts recursively flood through connected sectors and stop at sound-blocking lines [C `p_enemy.cpp:145`, `:207`]. Cost grows with terrain density: 6.3 ms at 32,768 sectors, 18.1 ms at 73,728, and 31 ms at 131,072 [M, one sample each]. **A rapid-fire weapon could make this a serious frame-time problem** unless terrain is divided with sound-blocking lines. That mitigation is untested.

### A stock crash on dense maps, with a map-data workaround

Fully connected maps of 21,632 sectors or more crashed at load, while 18,432 sectors worked [M]. `MapLoader::FloodZone` recurses once per connected sector [C `maploader.cpp:337-365`]. Adding `zoneboundary=true` on a 32-cell grid of lines removed the crash up to 131,072 sectors, with **no engine change** [M]. The stack-overflow cause is inferred, because no debugger or crash log was available.

`P_RecursiveSound` has a similar recursive shape. It did not crash at 131,072 sectors in the one layout tested, which does not prove it safe [M].

### Level changes and what can change at runtime

- **Map changes:** `ChangeLevel` is exposed to ZScript [C `doombase.zs:663`, `g_level.cpp:719`]. External `file:` maps are handled by `P_OpenMapData` [C `p_openmap.cpp:106-117`].
- **Hubs and snapshots:** hub levels are saved and restored by `SnapshotLevel` and `UnSnapshotLevel` [C `p_saveg.cpp:1068`, `:1092`]. A hub return of a 32,768-sector map took 741 ms, so a snapshot does not avoid the geometry load [M].
- **Portals:** linked portals connect areas in one level [C `portal.cpp:851`]. They do not extend the coordinate range [I].
- **Changeable from ZScript:** actors, textures, lights, and flat plane heights.
- **Not changeable from ZScript:** sector slopes, because plane normals and `D` are read-only [C `mapdata.zs:284-286`]. The renderer also re-uploads planes only when texture Z changes [C `hw_vertexbuilder.cpp:441-451`]. **Rewriting sloped terrain in place needs a small engine patch.**

### Measured map scaling

Each cell is one Daggerfall ground tile, split into 2 triangular sectors.

| Window | Sectors | Lines | Swap time | Frame time |
|---|---:|---:|---:|---:|
| 64 cells | 8,192 | 12,416 | 157-162 ms | at most 2.0 ms (capped) |
| 128 cells (1 map pixel) | 32,768 | 49,408 | 594-700 ms | 2.6-3.1 ms |
| 192 cells | 73,728 | 110,976 | 1,542 ms | 7.6 ms |
| 256 cells at 255 units | 131,072 | 197,120 | 3,349 ms | 21.7-24.1 ms |

One 128-cell swap took 5,976 ms. It did not recur in the later 16 swaps, and its cause is unknown.

---

## 2. Daggerfall world system

### Coordinates and scale

| Quantity | Value | Evidence |
|---|---|---|
| World | 1000 x 500 map pixels | [C] `API/MapsFile.cs:44-47` |
| World units | 32,768,000 x 16,384,000 | [C] `MapsFile.cs:38-39` |
| Map pixel | 32,768 units, 8 RMB blocks, 128 ground tiles | [C] `MapsFile.cs:33-35` |
| RMB block, tile | 4,096 and 256 units | [C] `API/BlocksFile.cs:151-162` |
| RDB dungeon block | 2,048 units | [C] `BlocksFile.cs:167` |
| Unity scale | 1 Daggerfall unit = 0.025 Unity units | [C] `MeshReader.cs:58` |

This report assumes **1 Daggerfall unit = 1 Doom map unit** (question 4).

**Crossing time:** the Doom player's measured top running speed is 16.666 units/tic, or 583.3 units/s [M]. At that speed:

- One map pixel takes **56 s**.
- Crossing north-south takes **7.8 hours**.
- Crossing east-west takes **15.6 hours**.

These are straight-line times that ignore terrain, water, and combat. Fast travel stays on Daggerfall's calendar through `TravelTimeCalculator` [C `Game/Utility/TravelTimeCalculator.cs:64`].

### Terrain, climate, and height

- `WOODS.WLD` holds a 1000 x 500 elevation map plus noise data per pixel [M, C `API/WoodsFile.cs`].
- Height combines base elevation, a noise map, and procedural noise, then clamps at the ocean level and at 1539 [C `Terrain/DefaultTerrainSampler.cs:89-119`, `:32`]. Daggerfall Unity then applies a 1.5 terrain scale [C `TerrainHelper.cs:42`, `DaggerfallTerrain.cs:307`].
- At 1:1 this gives 480 Doom units per elevation byte and a maximum clamped height of about 92,340 units [derived from C].
- **Vertical range exceeds UDMF:** 34,663 land pixels, 10.8% of land, have base height over 32,768 [M]. Each window therefore needs its own Z offset.
- **Relief inside a window is usually small:** across 2x2 pixel windows, median base relief is 0 and the 95th percentile is 2,400 units. Only 4 windows exceed 60,000 and need special handling [M].
- Climate and politics live in `CLIMATE.PAK` and `POLITIC.PAK` [M, files present]. They choose textures and region behavior and do not affect the geometry approach [I].

### Locations, blocks, and models

| Data | Measurement [M] |
|---|---|
| Locations | 15,251 across 45 populated regions (of 62 region slots) |
| Blocks | 920 RMB, 187 RDB, 188 other |
| RMB record size | median 28 KB, max 96 KB |
| Building records per RMB | mean 9.8, max 28 (first header byte, assumed from format) |
| ARCH3D models | 10,251 |
| Model planes | median 12, 95th percentile 57, max 712 |

ARCH3D models are arbitrary 3D polygon meshes, so they do not convert directly into Doom sectors. Simple extruded footprints can provide collision, while roofs, overhangs, and detail need 3D floors or models (question 2).

### Streaming, interiors, and travel

- Daggerfall Unity streams terrain around the player, by default 3 tiles in each direction, with up to 256 terrains in memory [C `Terrain/StreamingWorld.cs:44`, `:56`].
- It uses a floating origin through `WorldCompensation` [C `StreamingWorld.cs:146`, `:406-411`]. A floating origin is also the right model for Doom.
- World position is stored as integers in `PlayerGPS` [C `StreamingWorld.cs:309`]. Bridge code should use integers or doubles, because 32-bit floats lose precision to 2 units at this scale [I].
- Interiors and dungeons are entered through explicit transitions [C `Game/PlayerEnterExit.cs:667`, `:818`]. They map naturally to separately loaded Doom maps.

---

## 3. Proposals

### Proposal A: rolling map windows (recommended first)

**How it works.** Daggerfall generates a Doom map for a square window around the player and writes it to a local cache. When the player nears the edge, ZScript calls `ChangeLevel("file:...")`, then restores the player and nearby actors at the same global position in the new local coordinates.

| Criterion | Evaluation |
|---|---|
| Conversion path | Daggerfall's own terrain sampler produces heights. A generator writes triangulated UDMF with `zoneboundary` lines. Blocks and flats are placed in the same window. |
| Open-world behavior | Continuous world with a brief pause at each window swap. |
| Full-scale travel | Yes, 1:1. Only the window's global origin changes, so there is no practical size limit. |
| Fast travel | Daggerfall advances its calendar and Doom loads the destination window. |
| Terrain and collision | Full Doom collision on real sectors, at up to full tile resolution. |
| Memory and performance | Bounded by window size. 128 cells runs at about 3 ms per frame, while 256 cells is too heavy at about 22-24 ms [M]. |
| Load hitches | **Main weakness.** See the table below. |
| WAD and mod compatibility | Best available. Normal maps do not go through this path. Item, weapon, and monster mods work as usual, though mods that assume a persistent level may misbehave at swaps [I]. |
| Engine patch | **None needed for loading** [M]. Later patches are optional, for example faster loading. |
| Persistence | Daggerfall owns permanent state. A global registry holds overworld actors and items. |
| Risks | Hitch frequency, restoring AI and in-flight state, sound-alert cost, and generation speed. |
| Smallest kill test | Convert one real map pixel and walk across a swap. A is in trouble if a tuned swap stays well above about 0.5 s. |

**Hitch at running speed** [derived from M], swapping 4,096 units before the window edge:

| Window | Hitch | Straight-line time between swaps | Time lost |
|---|---:|---:|---:|
| 64 cells | 0.16 s | 7 s | 2.2% |
| 128 cells | 0.6 s | 21 s | 2.8% |
| 192 cells | 1.54 s | 35 s | 4.2% |
| 255 cells | 3.35 s | 49 s | 6.4% |

Likely reductions, none yet tested: merge flat terrain into fewer sectors, use coarser cells away from the window center, prebuild nodes, and load on a worker thread with a small engine patch.

### Proposal B: reusable terrain mesh with height rewrite

**How it works.** Load one fixed triangle grid once. When the player moves far enough, shift the player and actors back by a whole number of tiles and rewrite terrain heights and textures to match the new location. Wilderness travel then needs no map load.

| Criterion | Evaluation |
|---|---|
| Conversion path | Same height source as A, delivered as height arrays instead of maps. |
| Open-world behavior | Potentially seamless wilderness. |
| Full-scale travel | Yes, using the same global-origin model. |
| Fast travel | Rewrite the grid, or load a fresh window. |
| Terrain and collision | Real Doom slopes at the grid's resolution. |
| Memory and performance | Same steady-state cost as an equal A window. Rewrite cost is **unmeasured**. |
| Load hitches | None for wilderness if a rewrite fits in a frame or two. Towns remain a problem. |
| WAD and mod compatibility | Normal maps unaffected if the patch is inactive elsewhere. |
| Engine patch | **Small to moderate**, estimated at 100-300 lines [I]: native slope writes, renderer invalidation, and actor floor updates. |
| Persistence | Same registry as A. |
| Risks | **Buildings cannot be added to a fixed mesh.** Towns need a map swap, pooled geometry, or models with separate collision. Actors, decals, and interpolation must survive the shift. |
| Smallest kill test | Patch one native function, rewrite 32,768 sloped sectors during play, and measure frame time and collision. B fails if this cannot stay near one frame. |

### Proposal C: true dynamic geometry streaming

**How it works.** Modify UZDoom to add and remove sectors, lines, BSP data, blockmap entries, and render data while a level runs.

| Criterion | Evaluation |
|---|---|
| Conversion path | Chunks of Doom geometry inserted directly. |
| Open-world behavior | Best possible, with no swaps. |
| Full-scale travel, fast travel | Yes, with a floating origin. |
| Terrain and collision | Full fidelity. |
| Memory and performance | Potentially excellent, but only after extensive work. |
| Load hitches | Potentially none. |
| WAD and mod compatibility | **Highest risk.** Much code and many mods assume stable indices and pointers for level geometry [I]. |
| Engine patch | **Deep**, likely thousands of lines across playsim, renderer, saves, and scripting [I]. Every UZDoom upgrade becomes a merge problem. |
| Persistence | Same registry, plus harder save handling. |
| Risks | Touches nearly every subsystem and conflicts with the "noninvasive" requirement. |
| Smallest kill test | Add one sector and its lines to a running level and survive rendering, collision, and a save. |

**Not recommended** unless A and B both fail. It does not clearly win today.

### Rejected alternatives

- **One giant map, or regional maps:** ruled out by the ±32768 limit at 1:1 [C, M].
- **Scaling the world down to fit:** violates the 1:1 distance requirement.
- **Non-sector heightfield terrain:** violates "Doom-engine level data" and would need custom collision everywhere.
- **Prebuilding every map:** one full-detail map pixel is 11.5 MB of UDMF text [M], so all 500,000 would be about 5.8 TB before compression. Generate on demand and cache.

### Actors, projectiles, and boundaries (A and B)

The owner's registry model fits both proposals:

1. The registry stores class, global double-precision position, velocity, angle, health, and persistent ID for overworld monsters and items.
2. At a swap, actors in the old window are written back to the registry. Actors inside the new window are spawned from it.
3. The swap happens at least one RMB block before the window edge, so nearby fights stay inside loaded geometry.

**Measured:** the player's position was restored exactly, and 2,000 `ZombieMan` actors spawned from the registry in about 2.9 ms [M].

**Not yet tested:** preserving AI targets and animation state, projectiles in flight, and fights straddling a swap. Monsters beyond the window cannot be simulated by Doom, and what they should do is a design choice (question 3). Sight, hitscan, and sound also end at the window edge, so window size sets the maximum engagement distance.

---

## 4. Recommendation and next experiments

**Recommendation:** build the next spike around **Proposal A**. It is the only option already demonstrated on the unmodified engine, and it best meets the noninvasive requirement. Its registry and terrain conversion remain useful if the project later moves to B.

Next experiments, in order:

1. **Real terrain:** convert one real map pixel using Daggerfall's sampler. Measure generation time, slopes, and walkability.
2. **Hitch reduction:** test flat-terrain merging, variable density, and prebuilt nodes. Target about 200 ms or less.
3. **One real town block:** convert an RMB block to find what buildings cost in sectors and load time.
4. **Combat across a swap:** moving monsters, projectiles, and rapid fire, including sound-blocking lines to control alert cost.
5. **Proposal B kill test:** run only if experiment 2 misses its target.

### Questions for the owner

1. **How much wilderness hitch is acceptable?** At full terrain detail, Proposal A currently pauses about 0.6 s every 21 s of straight running. If tuning cannot bring this to your limit, should the project accept lower terrain detail, or pay for the engine patch in Proposal B?
2. **How should building exteriors be built?** Option one is pure Doom sectors, which are consistent but simplify Daggerfall's shapes. Option two is simple sector collision with Daggerfall-shaped 3D models on top, which looks closer to the original but is not purely Doom geometry.
3. **What should happen to monsters and projectiles outside the loaded window?** Monsters could freeze in the registry until the player returns, move in a coarse off-screen simulation, or despawn and re-roll. Projectiles at a swap could be preserved or removed.
4. **Is 1 Daggerfall unit = 1 Doom map unit the right meaning of 1:1?** This report assumes it, along with Daggerfall Unity's 1.5 vertical terrain scale. It makes a map pixel take 56 s to run across and the full east-west crossing take 15.6 hours.
