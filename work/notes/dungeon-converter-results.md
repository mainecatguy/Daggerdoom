# Daggerfall dungeon converter: results

**Result:** the converter works and is repeatable. Both dungeons load and run in unmodified UZDoom with true room-over-room stacking. Privateer's Hold is navigable from its entrance across 66.6% of its test points. Scourg Barrow's geometry converts and passes the engine checks, but the player cannot leave its entrance crypt yet (0.8% reachable), because the way out is not understood.

No human has played either map. The automated check does not judge game feel, visuals, or rendering performance.

## How to run it

```powershell
python tools/dungeon_converter/run.py "Privateer's Hold" --out <dir outside the repo>
python tools/dungeon_converter/run.py "Scourg Barrow" --out <dir outside the repo>
```

Each run writes `<slug>.wad`, `.points.txt`, `.stats.txt`, and `.report.txt`. To play a converted map:

```powershell
D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe -iwad D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD -file <out>\privateershold.wad tools\dungeon_converter\check +map MAP01
```

The `check` folder must be loaded, because Doom spawns players on the lowest floor and its script moves the player to the real entrance. The map check itself only runs with `+set dfcheck 1`.

Diagnostic converter flags: `--open-actions`, `--route-step N`, `--no-walls`, `--debug-row x,y,z`, and `--cell N`. The test-point logic assumes the default 16-unit cell.

## How the converter works

1. **Reads real data.** It compiles Daggerfall Unity's own `MapsFile`, `BlocksFile`, `Arch3dFile`, and related readers unchanged. Unity-only dependencies are stubbed, and mods and "smaller dungeons" are off. Model placement follows `RDBLayout.GetModelMatrix`.
2. **Finds open space.** It casts a vertical ray through each 16-unit map cell and pairs upward faces with the downward faces above them. Each pair is one walkable vertical span.
3. **Applies walls and door gaps.** A wall between two cell centers makes the cell behind it solid at that height. Gaps of up to 3 cells are bridged when no wall lies between the two sides, because room meshes stop short at door frames.
4. **Writes UDMF.** Connected cells with the same vertical layout become one sector. Solid material between stacked spans becomes a solid 3D floor.
5. **Makes doors.** A door is a 3D-floor slab in its opening. Using it runs `Ceiling_LowerToFloor` on the slab's control sector.
6. **Writes test data.** Points and neighbor links go into a `DFPOINTS` lump for the in-engine check.

Scale is 1 Daggerfall unit = 1 Doom unit. Heights are rounded to 4 units, so ramps become small stairs.

## Stacking approach and why

I used **stock UDMF solid 3D floors on a uniform grid**, with no engine changes. They represent any number of levels in one column, including open pits with doors at several heights, without teleporters. Real data reached 6 layers in Privateer's Hold and 7 in Scourg Barrow, and the engine handled both. No tested failure justified an engine extension.

The cost is that diagonal and curved walls become 16-unit stair-steps.

## Measured results

| | Privateer's Hold | Scourg Barrow |
|---|---:|---:|
| Blocks | 5 | 22 |
| Source triangles | 8,329 | 30,945 |
| Open map cells | 33,950 | 151,951 |
| Cells with stacked levels | 38.8% | 28.0% |
| Most levels in one column | 6 | 7 |
| Map sectors + 3D control sectors | 4,490 + 3,533 | 25,758 + 13,326 |
| Lines | 26,704 | 120,742 |
| Crashes, VM or script errors | 0 | 0 |
| Test points failing in engine | 0 of 13,729 | 0 of 51,882 |
| Short moves failing in engine | 0 of 48,767 | 0 of 182,222 |
| Points with no raw floor nearby | 0.29% | 0.62% |
| Points with no raw ceiling nearby | 1.51% | 2.17% |
| **Reachable from entrance** | **66.6%** | **0.8%** |
| Separate walkable areas | 24 | 103 |
| Doors placed / door models | 58 / 58 | 211 / 212 |
| Door controls opened by use, stuck | 58, 0 | 208, 0 |
| Player walk samples passed | 8 of 8 | 8 of 8 |
| Player fall samples passed | 8 of 8 | 8 of 8 |
| Sight blocked through slabs | 8 of 8 | 8 of 8 |
| Sight across ledges | 8 of 8 | 8 of 8 |
| Projectile hits across ledges | 7 of 8 | 8 of 8 |
| Projectiles stopped by slabs | 8 of 8 | 8 of 8 |
| Monster chased across a height change | 8 of 8 | 7 of 8 |

The engine check tests the converter's own points, so agreement alone only proves UZDoom matches the converter's grid. The "no raw floor/ceiling" rows are the independent comparison against the original triangles. I did not inspect the individual mismatches.

## What breaks

- **Scourg Barrow's entrance is sealed in the converted map.** The likely route is the central sarcophagus near (896, 1180): the data shows an open shaft from z 1536 to 1843 under a lid-height surface. This is not proven. Removing all moving models reached only 434 points, and also allowing 64-unit steps did not improve that.
- **Moving models are static.** Lifts, lids, and moving walls stay at their start position (5 in Privateer's Hold, 28 in Scourg Barrow). Clearing them changed Privateer's Hold only from 66.6% to 66.8%.
- **A third of Privateer's Hold is cut off.** 94% of its main block is reachable, while its four border blocks are mostly not. No door joins two separate areas, and most large cut-off areas have no same-level neighbor nearby, which suggests they are sealed in the source. I have not confirmed this in Daggerfall itself.
- **Privateer's Hold has a sealed domed room** at the Daggerfall "Enter" marker (510, 1672, 25). The converter starts at the "Start" marker beside the exit door instead.
- **Stacked doors can open together.** A line holds one special, so 3 Scourg Barrow doors share a control with a door in the same column. One door there was not placed, and one line touches two doors.
- **One monster chase failed in Scourg Barrow**, between points 5289 and 5261. I did not diagnose it.
- **163 of 816 door-tagged moves in Privateer's Hold were not blocked by closed doors** (576 of 2,951 in Scourg Barrow). The tag includes moves beside a door, so many are expected, but I did not separate them.

## Outside review claims

| Claim | Finding |
|---|---|
| Sector fragmentation | **Confirmed, not fatal.** Scourg Barrow needs 39,084 sectors and still loads and runs. Real rendering cost is unmeasured. |
| Vertical sound bleed | **Confirmed.** Noise crossed the slab in 8 of 8 samples in both dungeons. |
| Doors cutting through floors | **Mostly rejected.** Slab doors stay at their own level. The exception is stacked doors that share a control. |
| Sloped collision problems | **Not reproduced.** Slopes become small stairs, and all short moves passed. Feel is untested. |
| Automap or lighting problems | **Not tested.** Stacked rooms share a sector, so shared lighting and overlapping automap lines are likely. |

## Failed approaches

- A single ray per cell left door frames disconnected, with only 3.9% reachable. Bridging short wall-free gaps raised this to 66.6%.
- Using the "Enter" marker as the entrance put the player in a sealed room.
- Testing whether lids or jumping open Scourg Barrow's crypt did not connect it (406 to at most 574 points).

## Play-test list for the owner

1. Walk Privateer's Hold from the entrance. Do rooms, stairs, and doors feel right?
2. Do 16-unit stair-stepped diagonal and curved walls look or feel acceptable?
3. Do ramps feel acceptable as 4-unit stairs?
4. Look down an open pit and across levels. Is there any visual bleed or rendering error?
5. Check the automap and lighting in stacked areas.
6. Fire weapons and wake monsters near stacked rooms. Is noise through floors acceptable?
7. In real Daggerfall, confirm how the player leaves Scourg Barrow's entrance crypt.
8. In real Daggerfall, confirm whether Privateer's Hold's border-block rooms are reachable.
