# Daggerfall player size and collision parity results

**Result: complete except for one measurement.** The player-size layer, scale value, parity test, and bullet check work. The converter fix halves standing false walls with doors open in Privateer's Hold and opens no new collision space in either dungeon.

**Not met:** Daggerfall's crouch height and eye height were not measured at runtime. They come from source constants. Radius, standing height, step, and slope were read from the live controller. Measuring the rest needs one Unity build, and this session could not confirm that Unity is closed.

No human has played these maps. Review images: `D:\dev\DoomDaggerfall-loop\review\collision-parity\worst_privateers\index.html` and `...\worst_scourg\index.html` (Daggerfall left, UZDoom right). Generated output, not committed.

## Measured player values

| | Daggerfall Unity | Source of DFU value | Doom default (runtime) | Doom on Daggerfall map (runtime) |
|---|---:|---|---:|---:|
| Standing height | 72 | live controller | 56 | 72 |
| Eye height | 68.4 | source constant | 41 | 68.4 |
| Crouch height | 36 | source constant | 28 | 36 |
| Crouch eye | 32.4 | source constant | 20.5 | 34.2 |
| Radius | 14, round capsule | live controller | 16, square box | 14, square box |
| Step | 20 | live controller | 24 | 20 |
| Slope limit | 70 degrees | live controller | n/a | n/a |

- Doom's crouched eye is 1.8 units above Daggerfall's, because Doom halves the eye height.
- Doom's body stays a square box. It is wider than Daggerfall's capsule on diagonals.
- Nothing in `Assets/Scripts` outside `PlayerHeightChanger.cs` sets the standing height adjustment, so race and settings do not change these values in the base game. This is a code search, not a runtime test of each race. Mods could still change them.
- `DOOM.WAD` E1M1 keeps 16 / 56 / 41 / 24, with and without the package, through crouch and stand.

## Changing or disabling the scale

- **One value:** `PlayerScale.DoomUnitsPerDaggerfallUnit` in `tools/dungeon_converter/PlayerScale.cs`, default 1.0. Override with `--world-scale <value>`. World size, player size, cell size, and conversion thresholds derive from it.
- **Turn the player size off:** leave `<slug>_player.pk3` out of the load order, or add `+df_playersize 0`.
- **Tested at 0.75:** the player measured 54 tall, 27 crouched, radius 10.5, step 15, eye 51.3. Entrance connectivity stayed at 68.1%. The parity and bullet checks were **not** run at 0.75.

## Parity results

Positions on a 16-unit grid, from the entrance plus 24 seeded random legal positions. Doom walks with its real collision on an 8-unit grid in 4-unit moves. Lower is better.

| Dungeon | Mode | False walls before | after | False openings before | after |
|---|---|---:|---:|---:|---:|
| Privateer's Hold | Standing, doors closed | 3,143 | 2,209 | 230 | 234 |
| | Crouching, doors closed | 2,603 | 2,603 | 262 | 262 |
| | Standing, doors open | 3,871 | 1,947 | 331 | 374 |
| | Crouching, doors open | 2,453 | 2,453 | 386 | 386 |
| Scourg Barrow | Standing, doors closed | 7,642 | 6,080 | 11,380 | 11,380 |
| | Crouching, doors closed | 8,254 | 8,254 | 3,535 | 3,535 |
| | Standing, doors open | 10,816 | 7,307 | 10,828 | 10,838 |
| | Crouching, doors open | 9,741 | 9,741 | 11,343 | 11,343 |

Each run's `parity.csv` splits these by ceiling, doorway, step, and narrow gap. "Narrow gap" is the catch-all, and it holds most mismatches.

**New standing false openings.** I asked UZDoom whether a standing body already fit at each new position on the unfixed map.

- Privateer's Hold: 43 new positions, all 43 already fit. The fix only made them reachable.
- Scourg Barrow: 10 new positions, all 10 already fit. An earlier version of the fix opened 7 real positions with 68 units of clearance. The final rule leaves a cell alone when it is too low by itself.

**Trust in the Daggerfall side.** The offline flood matched the real Unity capture on Privateer's Hold, standing with doors open: 34,601 positions each, with 3 differing. Crouching, closed doors (modeled as the door's bounding box), and Scourg Barrow were not validated against Unity.

## Bullet results

200 seeded shots per dungeon, doors closed, compared with the first visible face on the same ray. "On surface" is within 4 units.

| Dungeon | On surface before | after | In front before | after | Behind before | after |
|---|---:|---:|---:|---:|---:|---:|
| Privateer's Hold | 81 | 82 | 41 | 40 | 78 | 78 |
| Scourg Barrow | 92 | 92 | 36 | 36 | 72 | 72 |

Fewer than half of Doom's impacts land on the visible surface. The worst shots are in each `parity\bullets.txt`. An early 8-unit collision trial scored 164 of 200, but it predates the door-state correction and was not re-measured.

## Converter changes

- **Ceiling relief.** Doom's square body rests on the highest floor under it and is limited by the lowest ceiling over it. At the foot of stairs this left 68 units for a 72-unit body. Where a legal Daggerfall body stands, and every cell under it is tall enough by itself, the collision ceiling rises by at most 4 units. `--ceiling-relief <n>` changes the limit, and `--no-ceiling-relief` disables it.
- **Scale.** Geometry, block rectangles, mesh export, cell size, and thresholds derive from the one scale value.
- Weapons, doors, slopes, monsters, and engine source were not changed.

## Failed approaches

- **Opening every cell a legal body overlaps.** False openings rose from 419 to 5,965 and bullets passed through walls.
- **Opening cells in door throats.** Added 20 false openings at doorways for almost no gain. The door it targeted was only blocked by a flaw in my first test, which moved along axes only.
- **Global 8-unit cells.** Did not improve movement parity.
- **A 16-unit ceiling raise.** Created a real false opening under a 56-unit ceiling.

## Remaining mismatches

1. Scourg Barrow's largest false opening covers 8,077 positions with doors closed (`w01`, near 1448, -4712, floor 512). It predates this work and I did not find its cause.
2. Most remaining false walls are "narrow gap" cases along walls, where the 16-unit staircase and Doom's square body lose space.
3. A 685-position false wall in Privateer's Hold near 1176, 3896, floor 512.
4. Crouching did not improve. The ceiling fix only affects standing clearance.

## Launch safety

An earlier version of `parity.py` could open UZDoom full screen and interrupted the owner. `parity.py` and `player_check.py` now write a windowed private config and pass `+vid_fullscreen 0`.

## Run times

| Dungeon | Full parity and bullet run, including two conversions |
|---|---:|
| Privateer's Hold | 28 to 32 s |
| Scourg Barrow | 88 to 104 s |

Bullets run inside the same UZDoom session and were not timed separately.

## Commands

```powershell
$out = "D:\dev\DoomDaggerfall-loop\review\collision-parity"
python tools/dungeon_compare/parity.py "Privateer's Hold" --baseline --out $out\before --unity-flood D:\dev\DoomDaggerfall-loop\review\connectivity-fix\df_flood_walk.txt --timeout 150
python tools/dungeon_compare/parity.py "Privateer's Hold" --out $out\after --unity-flood D:\dev\DoomDaggerfall-loop\review\connectivity-fix\df_flood_walk.txt --timeout 150
python tools/dungeon_compare/parity.py "Scourg Barrow" --baseline --out $out\scourg_before --timeout 280
python tools/dungeon_compare/parity.py "Scourg Barrow" --out $out\scourg_after --timeout 280
python tools/dungeon_compare/player_check.py --map $out\after\privateershold.wad --player $out\after\privateershold_player.pk3 --out $out\player
python tools/dungeon_compare/compare.py --views $out\after\parity\worst_views.txt --map $out\after\privateershold.wad --out $out\worst_privateers --eye 68 --no-flood --uzdoom D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe
python tools/dungeon_compare/compare.py --dungeon "Scourg Barrow" --views $out\scourg_after\parity\worst_views.txt --map $out\scourg_after\scourgbarrow.wad --out $out\worst_scourg --eye 68 --no-flood --uzdoom D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe
```

To play the result:

```powershell
D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe -iwad D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD -file D:\dev\DoomDaggerfall-loop\review\collision-parity\after\privateershold.wad D:\dev\DoomDaggerfall-loop\review\collision-parity\after\privateershold_player.pk3 +map MAP01
```

## Owner play-test list

1. Walk Privateer's Hold at the new height. Judge the view height and whether doorways and stairs feel right.
2. Walk down the stairs near 950, 640 and through the low doorway at their foot. This is the main fixed route.
3. Crouch under a low opening and stand back up.
4. Run `+df_playersize 0` and compare the feel.
5. Fire at walls and judge whether the impact mismatch is noticeable.
