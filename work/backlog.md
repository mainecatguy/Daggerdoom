# Backlog

Work we intend to do later, in priority order. Add items here instead of expanding the current goal.

## Overnight queue rules (approved 2026-11-21)

The supervising Claude session reviews each finished run, then starts the next eligible task:

- Use Opus with a $10 estimated limit and 4-hour limit per run.
- Continue through dungeon conversion, the comparison test, and the terrain treadmill.
- Stop before the city converter, because the building-exterior design question is still open.
- Stop if weekly plan usage reaches 60%, extra usage becomes enabled, a run is blocked on an owner decision, or two runs in a row fail to make verified progress.
- Stop if the next task depends on work that is missing or unverified, or if the right next step is unclear. Stopping is an acceptable result.
- Do not merge to `main`, push, or make owner-level design choices.

## Next: Daggerfall visual layer (owner direction, 2026-11-22)

Aim for visual fidelity. Stairs and right-angle ceilings were an acceptable first pass for navigation, but not the intended final look. An opt-in extension to the map type is allowed if normal WADs stay unaffected.

Target layers for generated maps:

- **Visual:** draw Daggerfall's real meshes, textures, and UVs. Doom sectors are not visible.
- **Weapons:** bullets, rails, and projectiles collide with the Daggerfall mesh, through engine hooks so weapon mods need no changes.
- **Movement:** the player and monsters use invisible Doom sectors, with real slopes for ramps instead of stairs.

Test in this order on Privateer's Hold, stopping if a stage fails:

1. Draw the real mesh over the existing collision. Measure visual match, popping, and frame time.
2. Convert ramps to sloped movement collision.
3. Route hitscan through the mesh, then projectiles. Measure cost with large numbers of shots.
4. Check monster sight, splash damage, bouncing, and impact marks against the mesh.

**Status 2026-11-22:** stage 1 is the current task, with an F1 toggle between Daggerfall mesh view and Doom collider view. Compatibility for now is `DOOM.WAD` E1M1 only. DRLA is not in scope yet. The owner started this run directly, so later stages wait for review.

## Next: Daggerfall player and collision parity (owner direction, 2026-11-22)

Do this before sloped movement collision, so later collision work has a reliable test. The owner's play-test found that the Doom player is much too short, some ceilings block places Daggerfall allows, some doorways become solid, and conversion results feel unpredictable.

**Source values to confirm at runtime** (`PlayerAdvanced.prefab`, `PlayerHeightChanger.cs`, 1 m = 40 Doom units):

| | Daggerfall Unity | Doom default |
|---|---:|---:|
| Standing height | 1.8 m = 72 | 56 |
| Eye height | 1.71 m = about 68 | 41 |
| Crouch height | 0.9 m = 36 | 28 |
| Radius | 0.35 m = 14, round capsule | 16, square box |
| Step height | 0.5 m = 20 | 24 |

1. **Measure both players.** Spawn a real player in DFU and in UZDoom, then record height, eye height, crouch height, radius, step height, and collision shape. Check whether race or settings change the DFU values.
2. **Apply Daggerfall's player size on Daggerfall maps only.** Prefer a lightweight event handler in the generated package that adjusts the current player class, instead of replacing it, so mods keep working. Restore normal values on regular maps. Verify standing, crouching, view height, and `DOOM.WAD` E1M1.
3. **Build a two-way movement parity test.** From seeded random legal positions plus the entrance, flood fill movement with the real DFU capsule and the real Doom player collision on the same grid. Report:
   - **False walls:** Daggerfall can move there and Doom cannot.
   - **False openings:** Doom can move there and Daggerfall cannot.
   - Separate results for standing and crouching, doors open and closed, and ceilings, doorways, steps, and narrow gaps. Save the worst cases with coordinates and side-by-side images.
4. **Fix the converter using that test.** Make ceiling and doorway handling use Daggerfall's player shape. Raise collision detail only where it measurably helps, such as doorways, lintels, and angled ceilings, because detail everywhere increases map size. Doorways must not become solid unless Daggerfall blocks them.
5. **Run on Privateer's Hold, then Scourg Barrow.** Keep the test as a repeatable check for future converter changes.
6. **Simple bullet check.** Fire a small seeded sample at random walls and measure whether Doom's impact lands on the visible Daggerfall surface. Keep this and the parity test short.

**Status 2026-11-22:** player scale layer, parity test, bullet check, and first ceiling fix are on branch `agent/20261122-070408`, not yet on `integration`. That branch accidentally tracks two `__pycache__` files, which must be removed before merging. Large mismatches remain: Privateer's Hold has 1,947 standing false walls with doors open, and fewer than half of test shots land on the visible surface. The 87.5% demo is at `D:\dev\DoomDaggerfall-loop\review\scale-demo-875`. Its monster route check was inconclusive and should not be treated as proof that large monsters fit.

Any new Unity capture build must restore tracked generated files before work is saved. The size of Doom monsters relative to the taller player remains an owner judgment after play-testing.

## Next after parity: compromise scale demo (owner approved, 2026-11-22)

When the parity run finishes and is reviewed, generate a playable Privateer's Hold demo with Doom monsters at Daggerfall's 42 enemy markers using:

- World scale 87.5%, chosen over 90% because terrain tiles stay exactly 224 units.
- Player height 60, eye height 56, step height 20, on Daggerfall maps only.
- Player collision width must match Daggerfall's measured width at world scale. If the runtime radius is confirmed as 14, use 12.25 at 87.5% (24.5 wide). Doom's collision is a square box and Daggerfall's is a round capsule, so check doorways, corners, and diagonal gaps with the parity test.
- Stock player speed, monsters, and regular Doom maps.

Check that it loads, that the player and monsters fit through the main routes, and that `DOOM.WAD` E1M1 stays normal. This is a feel test for the owner, not a final scale decision.

## Future: Daggerfall traversal limits on steep surfaces

Doom currently lets the player walk up very steep hills and surfaces without limit. The player should be blocked, slide, or need Daggerfall's climbing wherever Daggerfall would require it. The main goal is removing unlimited surface climbing, not only adding a climbing move.

When this task starts, research Daggerfall Unity's real behavior first: which surfaces the player can walk up, when they slide or get blocked, and when climbing starts, continues, or fails, including skill checks. Start with `FrictionMotor.cs`, `ClimbingMotor.cs`, and the player's slope limit. Then design the Doom behavior with the owner. Do not implement it before that research.

## Future: Locked doors with Daggerfall's requirements

Doors that were locked in Daggerfall must have the same requirements in Doom. A door that required lockpicking or a key must still require it.

- Read each door's real lock data and requirements from Daggerfall. Do not infer them from appearance or assign them by hand.
- Daggerfall stays the authority for lock state, skill checks, keys, and whether a door has been unlocked. UZDoom asks it before opening the door.
- Monsters and scripted movement must not bypass a locked door unless Daggerfall's rules allow it.
- Verify with real locked, unlocked, lockpick, and key cases, including saving and reloading after a door is unlocked.
- Depends on the swinging door work and the engine-sync contract. Any other way past a lock, such as bashing or magic, follows Daggerfall's rules unless the owner decides otherwise.

## Future: Experiment with doors that swing in both directions

Generated actor-based swinging doors, like those in Privateer's Hold, currently swing one way. Run an experiment on having them open in both directions. Do not start until the owner asks. The owner will judge the result by play-testing.

## Future: True angled walls in movement collision

The converter builds movement collision on a grid (12-unit cells at 75% scale), so angled Daggerfall walls become small stairsteps in the invisible collision. The owner wants these to be real straight lines at their true angle. Doom sectors support any angle. Check the effect on stacked rooms, sliver sectors, node building, swinging doors, and the player's square collision box against diagonal walls.

## 1. Dungeon conversion

The engineering approach is open, including UZDoom's 3D floors and other multi-level features, portals, multiple levels, or a map extension. The owner expects teleporters not to work as the general solution, because a converter cannot reliably place them for cases like an open pit with doors on several levels.

Reasonable geometry approximations are allowed and expected, such as replacing a ramp with stairs, simplifying small details, or snapping awkward shapes. Preserve the dungeon's layout, connectivity, and sense of its spaces, and record each kind of approximation. If the current run was limited by exact geometry, the next dungeon run should apply this guidance before moving on.

1. **Real dungeon converter, first on Privateer's Hold.** Build the real converter, developing block by block on the real dungeon. Skip a separate synthetic proof map. Make small reproductions from real dungeon pieces only when something breaks.
2. **Automated run-through test.** Move through the converted map and detect obvious failures such as crashes, script errors, falling through floors, getting stuck, unreachable areas, and bad heights. This supplements the owner's eventual play-test.
3. **Stress test on Scourg Barrow.** Run the same converter on Scourg Barrow, chosen as a likely hard case. Report what works, what breaks, and how much the dungeon overlaps vertically.
4. **Mass-scale stacking audit.** Check whether large-scale 3D floor stacking causes real problems or glitches. Treat the suspected problems below as unverified claims from an outside review, and confirm or reject each with tests on the real dungeons:
   - **2D sector fragmentation:** walls, ramps, and doors from every floor project onto one 2D plane, possibly creating sliver sectors, high sector counts, slow BSP builds, and nodebuilder precision glitches.
   - **Vertical sound bleed:** gunfire on one floor may alert monsters through solid rock on other floors.
   - **Doors and moving geometry:** standard doors and polyobjects may span the full sector height and cut through other floors.
   - **Sloped 3D floor collision:** intersecting or tightly stacked slopes may snag actors or produce rendering seams.
   - **Automap and lighting:** stacked floors may make the automap unreadable, and lighting or underwater fog may bleed between floors.
   - **Anything else** that appears at scale.
5. **Fix confirmed problems** in the converter, in order of how badly they affect play.

**Status 2026-11-22:** the converter, automated check, Scourg Barrow attempt, and first stacking audit are verified on `integration`. Results are in `work/notes/dungeon-converter-results.md`. The comparison test is also verified, and it confirmed false walls in the converter. The connectivity fix is also verified: Privateer's Hold now matches at 15 of 16 viewpoints and reaches 68.2% from the entrance under static collision (`work/notes/dungeon-connectivity-fix.md`). Scourg Barrow's route and any remaining moving-object connections wait for the owner's decision on moving dungeon objects. The terrain treadmill kill test also passed for feasibility (`work/notes/terrain-treadmill-results.md`). The overnight queue stops here because the city converter needs the owner's building-exterior decision.

## 2. Side-by-side world comparison test

Start Daggerfall Unity, place the player at a chosen world position and angle, and take a screenshot. Do the same at the matching place in UZDoom, then compare the two. Build this as soon as the first real dungeon conversion exists, so it can verify the converters.

## 3. Terrain treadmill test (Proposal B)

Rewrite real sloped Daggerfall terrain in place while running across it. Measure whether each rewrite fits in about one frame and whether the player or monsters glitch.

**Status 2026-11-22:** passed on one straight route with few actors. All 32 shifts fit in one 60 FPS frame. Slaughter-sized packs, saves, decals, sounds, and north-south shifts remain untested.

## 4. City converter

Reuse the dungeon converter's model conversion. Convert one real city block, then the full City of Daggerfall, and measure conversion time, sector count, load time, and frame time.

## 5. Distant town view

Show a real town from outside its playable area and capture screenshots for the owner to judge. Needs the city converter.

## 6. Wilderness-to-town handoff

Walk from treadmill terrain into a loaded town map. Measure the hitch and any visible pop. Needs the treadmill and city converter.
