# Angled collision

Map: Privateer's Hold at 75% scale, with the stock 56-tall player and 21-wide box. Demo: `D:\dev\DoomDaggerfall-loop\review\angled-demo\play.bat`. Before/after images are in its `screenshots` folder (grid on the left, angled on the right).

## What changed

- **Sector boundaries now follow the real mesh.** Each stretch of boundary picks one real wall or slope edge. Corners become the intersection of those lines, so a diagonal wall becomes one angled line instead of a staircase.
- **Sectors use the real sloped planes.** Floors up to about 41 degrees and ceilings use the source face's plane, including 3D floors between stacked rooms. Steeper floors stay stepped so routes remain climbable.
- **The grid still decides what exists and what connects.** This keeps stacked rooms, doors, and routes on the tested path. Only the boundary shape and surface planes change.
- **Unsafe fits fall back to the grid.** A boundary that would cross, pinch, or invert a sector returns to its grid position, first vertex by vertex and then as a whole chain.
- **`--grid-collision` restores the old output.** It reproduces the door demo's WAD byte for byte.
- **The converter now defaults to 0.75 world scale** (owner request). `--world-scale` still overrides it. `parity.py`, `compare.py`, and `mesh_compare.py` default to 0.75 too. View files stay in Daggerfall units, and `worst_views.txt` now writes them that way. The default produces a WAD identical to the door demo's.
- No engine change. The code is in `tools/dungeon_converter/AngledCollision.cs`, with small hooks in `Program.cs`.

## Why this approach

Converting faces directly to sectors looked hard exactly where this map is hardest: stacked rooms, overlapping models, and seams between two methods. Refitting the grid's boundaries gets the shape benefit without a second topology to reconcile, and has no seam because every boundary comes from one partition.

## Results

Same parity tool and seeds, real UZDoom collision, doors open. Lower is better for false walls and openings.

| Measure | Grid | Angled |
|---|---|---|
| Bullets landing on the visible surface (of 200) | 106 | 142 |
| Bullets stopping in front of it / passing behind it | 30 / 64 | 17 / 41 |
| Standing false walls / false openings (of 23,454) | 820 / 1405 | 803 / 1282 |
| Crouching false walls / false openings (of 23,906) | 1172 / 1576 | 817 / 1106 |
| Real wall samples within 1 unit of a boundary | 37.3% | 62.2% |
| Real wall to boundary, mean / 95th percentile | 2.86 / 7.50 | 1.66 / 6.55 |
| Sectors / lines | 4975 / 30190 | 3036 / 22997 |
| Angled boundary lines | 0 | 2219 |

Of 7,357 boundary chains, 6,625 were fitted and 732 stayed on the grid.

**Doors** (`door_check`, same run on both maps): every test result that ran is unchanged, with no new failures. The 12 known dead-end doors still report as before. All 58 doors spawn, and real player and Imp stall tests still hold and resume. Coverage shrank slightly: doors 26, 36, 46, and 51 no longer have standing room on their open face, so those three open-face checks did not run for them, and the other-floor check covers 514 positions instead of 546 (all pass).

**Stock Doom:** DOOM.WAD E1M1 loads with the door, mesh, and width packages and no script errors.

## What I learned

- Snapping each vertex separately skewed straight walls. Line-first fitting fixed this.
- Door boundaries must be fitted too. Left on the grid, a door lintel sat up to a cell out from its frame and cut off an 826-position area at the foot of a stair.
- Most rejected fits come from stacked levels: one 2D partition has to serve walls on different floors that nearly line up.

## Known flaws

- Some straight walls have small bends where a vertex had to stay on the grid. One is visible in `stair_lintel_grid_left_angled_right.png`, in the Doom sector view.
- 732 chains keep grid edges.
- Steep floors are still stepped.

## Not verified

- A human play-through with real keyboard input. Movement evidence is the engine's collision flood, not a walking player.
- How real sloped floors feel, including sliding and speed on ramps.
- `check_map.py` was not run. Its door stages are obsolete, and its 2-unit height check does not suit sloped floors.
- Closed-door parity stages are still meaningless, as noted in `door-objects.md`, and are left out of the table.
- `compare.py` was run on its Doom side only (camera placement at 0.75 confirmed). `mesh_compare.py`'s scale change was compiled but not run.
- Only Privateer's Hold was converted. Other dungeons may have different fallback rates.
- Monster pathing on the new geometry, beyond the door test's Imp.

## Play-test list

- Does sliding along diagonal walls feel smooth compared with the old stairsteps?
- Do roofs and sloped ceilings match the mesh when you jump or shoot at them?
- Do bullets and projectiles hit where the wall appears?
- Do ramps and stairs feel right, with no sticking or launching?
- Press F1 in a few rooms. Are any bent walls or odd sectors bad enough to matter?
- Do doors still feel the same, especially the diagonal door near (785,765,1152)?
