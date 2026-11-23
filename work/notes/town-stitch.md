# Overworld to City of Daggerfall stitch

## Result

The player can run across the overworld to the City of Daggerfall, open a gate, walk in, walk back out, and return to the wilderness. The handoff keeps position, facing, and momentum, and world-table state survives the round trip and saves.

Demo: `D:\dev\DoomDaggerfall-loop\review\town-stitch\play.bat`. You start in the wilderness east of the walls, facing them. Run west, press Use on a gate, and walk through.

**A short load remains:** about 1.0 s entering and 0.7 s leaving. The screen holds its last frame during it.

## How it works

- **One height function.** `tools/dungeon_converter/WorldTerrain.cs` and `UZDoom/src/playsim/dd_treadmill.cpp` hold the same port of `DefaultTerrainSampler`, `BlendLocationTerrainJob`, and `SmoothLocationNeighbourhood`, with the same Perlin stand-in. `--world` writes `DDWORLD` (smoothed heights) and `DDLOCS` (the blend rectangle of all 15,251 locations).
- **One exterior generator.** `--city <name> --map-name DDTOWN01` builds any location plus its adjacent locations into one map. Tested on the City of Daggerfall group (3 locations) and on Gothway Garden with Privateer's Hold.
- **Handoff.** A `DDTOWN` lump places the map in the world. Entry is 12 tiles outside a location's flat area, exit is 20, and walkable ground ends at 24, so the border cannot cause repeated loads.
- **World table.** Before a map change, monsters and items are parked in the table in Daggerfall world units. The table now works on town maps too and is written to saves made there.
- **Town seen from outside.** The overworld draws the town's real mesh and billboards at their true world position, and hides its own floor under them. Open ground uses Daggerfall's grass tile.
- **Gates.** Each gate's two leaves are door objects using the dungeon door runtime. They start closed, block the player, and swing open with Use.

## What I learned

- **The 12-tile margin crash was recursion in `MapLoader::FloodZone`.** Marking terrain lines as zone boundaries avoids it, so **the stack size did not need raising**.
- **A "max-size" map is not 341 tiles in the stock engine.** `R_PointOnSide` uses 32-bit deltas, which wrap once a point is more than 32,768 units from a node line. The city group spans about 61,000 units, and 329 of 39,870 test points landed in the wrong sector. A small patch uses 64-bit math, only while a generated town map is loaded.
- A constant `false` in a ZScript `if` condition made the whole function body stop running in my test harness. I did not find the cause in the compiler. The harness now assigns those flags at run time.

## Engine changes

All marked `[DoomDaggerfall]`:

| File | Change |
|---|---|
| `playsim/dd_treadmill.cpp`, `.h` | Blending, handoff, town table support, town billboards |
| `rendering/r_utility.h` | Wide node side test, behind a flag that is true only on `DDTOWN` maps |
| `p_setup.cpp` | One call that sets that flag |
| `hw_dfmesh.cpp`, `.h`, `hw_drawinfo.cpp` | Draw the town mesh from the overworld, and keep it loaded across a handoff |

`tools/dungeon_converter/door_objects.zs` gained a swing direction, which defaults to the old behavior.

## Evidence

Run with `tools/overworld/stitch_test.py`. Logs are in `D:\dev\DoomDaggerfall-build\stitch-tests`.

| Check | Result |
|---|---|
| Height mismatch at the seam, 39,870 points on real town floors | Mean 0.0003, worst 0.0013 Doom units |
| Round trip through the east, west, north, and south gates | 4/4 pass: 0 position jumps, 0 below floor |
| Largest per-tic step across all handoffs, driven at 40 units/tic | 42.0 units |
| Same route at 16 units/tic (normal run speed, east gate) | Pass |
| Closed gate blocks, then opens 90 degrees | Pass on all 4 runs |
| World table after a round trip (corpse, wounded imp, dropped item) | All three correct |
| Save in town, load, leave, check table | Pass |
| Save in the overworld near the city, load, check table | Pass |
| Same round trip with dense placeholder packs requested | Pass. Pack spawn counts were not checked |
| Second location (Gothway Garden and Privateer's Hold) | Pass, seam worst 0.0014 |
| Same view from the same point on both maps, 3 directions | Mean difference 0.01 of 255, 0.01% of pixels visibly different |
| Transition time, 3 runs with the node cache | 0.94 to 1.00 s in, 0.68 to 0.71 s out |
| Overworld with town in view (minimized) | Median 5.5 ms. Shift frames 12 to 18 ms |
| `DOOM.WAD -norun` | Exit 1337 |
| DOOM.WAD E1M1, save, reload | Ran, treadmill off, no treadmill data in the save |
| Privateer's Hold | WAD hash matches the recorded baseline (`6958922D`), door data unchanged, map loads with 58 doors |

The stock check covers E1M1 only. Other WADs and mods were not run. On non-town maps the side test takes one extra flag check, and its math is unchanged.

## Known gaps

- **Heights are matched to each other, not yet to Daggerfall Unity.** Both maps use the same Perlin stand-in, so small bumps still differ from the real game. This can be fixed later in one place per engine.
- **Only one town package can be loaded at a time.** `DFMESH`, `DFFLATS`, and the script classes have fixed names. A world with many towns needs per-map lump names and one shared runtime.
- **Adjacent locations are walkable only near their own walls.** Between them, the player crosses open overworld, so going from the city to Ripwych Commons means two short loads.
- **Town contents do not persist as map state.** Monsters and items parked in the table return, but gates reset to closed on each entry.
- **Closed gate leaves differ slightly from Daggerfall's closed model.** The cross-bars come from the open model, rotated, so their position differs.
- Open ground outside the town mesh uses one grass tile, and water is not represented.
- Fast travel was not built. The handoff takes a world position, so it should be able to use the same path.

## Not verified

- Real keyboard play and real windowed frame rate. All runs were minimized and scripted.
- Sound across the handoff. Tests ran with `-nosound`.
- Whether the screen wipe is suppressed without `+wipetype 0`. The engine requests no wipe, but every test and the demo also set that option.
- Combat during a handoff, projectiles in flight, and monsters standing at the seam.
- Other location types beyond the two tested groups.

## Play-test list

1. Run into the city from each side. Can you see the moment of the handoff, apart from the short hold?
2. Is a 1.0 s hold in and 0.7 s out acceptable?
3. Do the walls, trees, and ground look the same just before and after the load?
4. Open each gate. Do the leaves look right, swing the right way, and feel right to walk through?
5. Fight a pack near the city, enter, leave, and check what is still there.
6. Save in town, reload, and walk out.
7. Walk around Ripwych Commons and Copperfield Manor.

## Questions for the owner

1. Daggerfall opens city gates by day and closes them at night. These gates start closed and open with Use, as the brief asked. Should they follow the time of day later?
2. Should adjacent locations become one continuous walkable map? It would avoid the double load, but it needs far more sectors or a faster map load.
