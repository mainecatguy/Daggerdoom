# City of Daggerfall as a Doom map

## Result

The whole City of Daggerfall (8x8 blocks) and its nearby terrain now run as one UDMF map in the existing UZDoom build, with **no engine changes**. It shows Daggerfall's real models, ground tiles, billboards, and sky. The player can walk the streets, leave through all four sides, and reach the terrain outside.

Demo: `D:\dev\DoomDaggerfall-loop\review\city-demo\play.bat`. F1 shows the Doom collision sectors.

## What I built

`tools/dungeon_converter/CityExport.cs`, reached only through `--city`:

```powershell
dotnet run -c Release --project tools/dungeon_converter/DungeonConverter.csproj -- --city Daggerfall --region Daggerfall --out <dir outside the repo>
python tools/dungeon_converter/city_check.py <dir>   # load, screenshots, frame times
python tools/dungeon_converter/city_walk.py <dir>    # real player walks the test routes
```

- **Visuals.** RMB block models with Daggerfall Unity's placement and summer climate texture swaps, drawn by the existing mesh layer. Ground uses the real block tiles inside the city and a port of Daggerfall Unity's tile rules outside it. The sky is the real midday frame.
- **Terrain.** A port of `DefaultTerrainSampler` and the location blend, reading the real `WOODS.WLD`. The mesh covers 3x3 map pixels.
- **Billboards.** 4,029 real flats, spawned by a small ZScript handler in the city package. NPC flats are left out.
- **Collision.** The flat city area is an 8-unit raster that becomes sectors. It handles arches and low steps. Enclosed building interiors become void. Terrain outside is one sloped sector per triangle.
- **Coordinates.** At 75% scale, `doomX = 0.75 * (worldX - 6799360)`, `doomY = 0.75 * (worldZ - 9388032)`, and `doomZ = 0.75 * (dfHeight - groundHeight)`. Ground height is about 15342 Daggerfall units. The package's `DFCITY` lump stores these values for the overworld work.

## Why this approach

The dungeon pipeline casts rays into a fine multi-level grid and assumes RDB blocks. A city is mostly one flat level with buildings on it, so a single-level raster was simpler and converts in about 2 seconds. It reuses the mesh format, texture writer, and WAD writer.

## Measurements

| Item | Value |
|---|---|
| Sectors | 25,196 (1,038 city, 24,158 terrain) |
| Lines / vertices | 50,884 / 25,610 |
| Mesh | 359,849 triangles, 163 batches, 1,045 models, 4 gates |
| Files | WAD 18.4 MB, mesh package 8.8 MB |
| Conversion | about 2 s |
| Added load time | about 1.0 s (launch to exit, median of 3: 2.89 s against 1.90 s for stock MAP01) |
| Frame time, aerial view, 1920x1080 scene | median 4.54 ms, p95 7.04, worst 8.18 |
| Frame time, aerial view, 2560x1440 scene | median 4.61 ms, p95 7.07, worst 10.34 |

**The frame times are not a real windowed frame rate.** The game ran minimized with the 3D scene forced to the listed size. Times barely change between the two sizes, so they may not reflect full GPU cost. Please check the real rate in play.

## Checks

| Check | Result |
|---|---|
| Walk north, east, south, west through the walls onto terrain | All 4 reached the end, 0 position jumps, never below the floor |
| Stock `DOOM.WAD` startup | Exit 1337 |
| Stock E1M1 | Ran 350 tics with the mesh layer inactive. No engine files changed |
| Dungeon conversion | Privateer's Hold WAD is byte-identical to the angled-collision demo (SHA-256 `6958922D...`) |

North, south, and west each took two launches. The first hit the time limit while still moving (waypoints 300/416, 369/408, 435/512), and the second resumed just before that point.

## What I learned

- **Large connected maps can crash the engine at load.** With this layout, a 12-tile terrain margin loads and 16 crashes (access violation). The same build with its stack raised to 64 MB (`editbin /STACK`, on a private copy) loads the full 32-tile margin, so the cause is stack depth, not bad map data. I did not identify the recursive function. **The overworld work may hit the same limit.** The treadmill test's 32,768-sector grid did load, so sector count alone does not predict it.
- A minimized UZDoom renders at 320x200, but `vid_scalemode 5` with a custom size gives full-size screenshots while staying minimized.

## Known gaps

- Roofs and tops of city walls cannot be walked on. Collision has one walkable level per spot.
- Gates are always open. Building doors are visual only. Interiors are out of scope.
- Collision follows an 8-unit grid, so rotated building edges are small stair-steps.
- The walkable area ends about 12 tiles past the map pixel at an invisible wall. Terrain continues visually beyond it.
- Trees exist only in the walkable area, so distant hills are bare. Individual trees differ from Daggerfall Unity because Unity's random sequence is not reproduced.
- The fixed midday sky and full-bright lighting have no time of day, weather, or season.
- Water is a flat, walkable ground texture.

## Not verified

- Real windowed frame rate, and behavior with monsters or combat.
- Exact terrain match with Daggerfall Unity. `Mathf.PerlinNoise` is native code, so a surrogate is used, as in the treadmill spike. This affects small bumps and **slightly affects the city's ground height**, so overworld and city must share one height source before they connect.
- `SmoothLocationNeighbourhood` and `DilateCoastalClimate` are not ported, and neighboring locations are not flattened.
- Building blocking was only spot-checked: 6 straight-line runs, of which 2 stopped at walls and 4 ran their full distance. The 4 route walks show that streets connect, not that every wall is solid.
- No side-by-side comparison with Daggerfall Unity was made.

## Play-test list

1. Does it feel like Daggerfall? Compare streets, scale, and skyline.
2. What is the real frame rate? Does anything hitch while running?
3. Walk along buildings and through narrow alleys. Note any invisible walls, gaps, or snagging.
4. Go through each gate and out onto the hills. Do feet match the ground on slopes?
5. Do trees and other billboards stand on the ground at the right size?
6. Do ground tile transitions line up, especially at road and grass edges?
7. Press F1 anywhere that movement feels wrong, and note the location.

## Question for the owner

Should the engine's stack size be raised? It is a one-line linker setting, and it would allow much more walkable terrain per map. I did not change it because it is an engine build change and this demo does not need it.
