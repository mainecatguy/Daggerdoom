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

## Future: Locked doors with Daggerfall's requirements

Doors that were locked in Daggerfall must have the same requirements in Doom. A door that required lockpicking or a key must still require it.

- Read each door's real lock data and requirements from Daggerfall. Do not infer them from appearance or assign them by hand.
- Daggerfall stays the authority for lock state, skill checks, keys, and whether a door has been unlocked. UZDoom asks it before opening the door.
- Monsters and scripted movement must not bypass a locked door unless Daggerfall's rules allow it.
- Verify with real locked, unlocked, lockpick, and key cases, including saving and reloading after a door is unlocked.
- Depends on the swinging door work and the engine-sync contract. Any other way past a lock, such as bashing or magic, follows Daggerfall's rules unless the owner decides otherwise.

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
