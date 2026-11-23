# Overworld travel on the terrain treadmill

## Result

The player can cross real Daggerfall terrain in all eight compass directions without a map load. Killed monsters, wounded monsters, drops, and picked-up items are correct after leaving and returning, including through a save and load.

**One goal is only partly met.** A terrain shift fits in one 60 FPS frame with no monsters, but not with large packs. It costs about 19 ms with 2,000 monsters in the window and about 30 ms with 5,000. That is one or two missed frames, about every 10.5 s at normal running speed.

Demo: `D:\dev\DoomDaggerfall-loop\review\overworld-demo\play.bat`. It uses the engine in `D:\dev\DoomDaggerfall-build\uzdoom-overworld\Release`.

## What was built

- **Terrain.** The engine samples heights at runtime with a port of `DefaultTerrainSampler`, reading a 5 MB `DDWORLD` lump built from `WOODS.WLD`. The whole world is reachable. Nothing is pre-generated per tile.
- **Scale.** One tile is 192 Doom units (256 Daggerfall units at 75%). Transform for the city work:
  - `doomXY = daggerfallWorldXY * 0.75`, before subtracting the window origin
  - `doomZ = daggerfallHeight * 0.75 - 35240`
  - `daggerfallHeight = sampled height * 60`
- **Window.** 128 x 128 tiles, 32,768 sectors. It moves by one 32-tile chunk when the player goes 3,072 units from center.
- **World table.** Rows are stored in Daggerfall world units as doubles, so Daggerfall can become the authority later. Each row holds id, class, position, angle, health, kind (monster, corpse, item, gone), item amount, and corpse frame. It is saved inside the UZDoom save file.
- **Activation.** Only map `DDOVER01` with a `DDWORLD` lump, in single player. The old `-ddtreadmill` switch is gone, so the `work/spikes/treadmill_*.py` scripts no longer run against this engine.
- **Engine patch.** `dd_treadmill.cpp` and `.h`, plus one marked line each in `actor.h`, `p_mobj.cpp`, and a two-line hook in `p_saveg.cpp`. The new actor field is saved only when nonzero.

## Behavior chosen

The owner deferred off-window simulation, so this is the simplest behavior that fits the table. These are easy to change.

| Thing leaving the window | What happens |
|---|---|
| Untouched monster | Removed. Rebuilt identically from its chunk's seed on return |
| Hurt, awake, or moved monster | Frozen in the table. Returns at that spot and health, idle |
| Corpse | Stored in its final frame |
| Dropped item | Stored with class and amount |
| Picked-up item or destroyed actor | Marked gone, never returns |
| Projectiles, puffs, effects, decorations | Removed |

Monster packs are a **placeholder**: a seeded roll per chunk from settings in the `DDWLDCFG` lump. Encounter design is still the owner's.

## Evidence

Commands are in `tools/overworld`. Logs are in `D:\dev\DoomDaggerfall-build\overworld-tests`.

| Check | Command | Result |
|---|---|---|
| All directions | `run_test.py compass compass --timeout 75 --packchance 0.3 --packsize 8` | 8 legs, 24 shifts (6 each in +X, -X, +Y, -Y), 0 position jumps, 0 below floor, 0 blocked legs |
| Terrain after shifts | same run | Worst plane error 0.0003 units |
| Terrain vs. source | 49 points against a separate Python port without the noise term | Difference 5.6 to 70.3 units, inside the noise term's 0 to 112.5 range |
| Leave and return | `run_test.py persist persist --timeout 60 --packsize 64` | PASS: 30/30 corpses, 3/3 hurt, 28/28 untouched, 30/30 drops, picked-up item stayed gone |
| Same, through save and load | `persistsave` mode in two launches | PASS on the last 4 consecutive runs, same counts |
| Stock game | `DOOM.WAD -norun` | Exit code 1337 |
| Stock E1M1 | `check_stock.py` | Ran 15 s, treadmill off, save has no treadmill data, save reloads |
| Dungeon | `check_stock.py` with the door demo | Entered and ran 15 s, treadmill off |

### Shift cost with large packs

All monsters in the starting window were awake. 1280x720 was requested, but the game ran at 3044 x 1649. Runs were **minimized, and another agent's UZDoom was running**, so treat these as rough.

| Monsters in window | Normal frame, median | Shift frame, median | Shift frame, worst | Shift simulation, median |
|---:|---:|---:|---:|---:|
| 0 | 5.4 ms | 15.2 ms | 15.7 ms | 2.1 ms |
| 2,000 | 7.1 ms | 19.2 ms | 20.7 ms | 4.3 ms |
| 5,000 | 12.6 ms | 29.6 ms | 31.8 ms | 8.7 ms |

- Most of the shift frame is not simulation. With no monsters, about 13 ms of it is outside the simulation step, probably re-uploading floors. This was not confirmed.
- Skipping the per-actor floor lookup saved only about 0.5 ms at 5,000 monsters, so I removed that optimization.
- **Unexplained:** two 5,000-monster runs each had one much slower frame (290 ms and 238 ms). In the run I inspected, it came 6 tics after the first shift. The 2,000-monster runs did not show it.

## Bugs found by testing

- Actors within 64 units of the window edge were stored even though their chunk stayed loaded, so they vanished until the chunk reloaded. Fixed, with a regression check.
- Seeded monsters spawned half a window off-center, partly outside the map. Fixed. The height comparison above now guards the coordinate transform.
- Two save-test failures were traced to the test. In one, the scripted player collected a drop on its path. In the other, a drop was about 15 units from its recorded spot. Drops were later measured sliding up to about 1 unit per tic on slopes, which is the likely cause, but I did not prove it for that specific failure.

## Not verified or known gaps

- **Town terrain will not match yet.** Daggerfall Unity flattens terrain around locations and smooths steep location pixels. Neither is ported, so this must be solved before connecting the city.
- **The table resets when the map restarts.** Going to a town map and back would lose it until that transition is built.
- **Fine terrain bumps differ.** Unity's Perlin noise is native code, so a surrogate is used. It affects up to 112.5 Doom units.
- **The highest peaks were not visited.** Terrain can reach about 34,015 Doom units, past the map format's 32,768 limit. The engine accepts this at runtime on the routes tested, but no run went to the extreme peaks.
- **Not tested:** positioned sounds and particles across shifts (code exists, tests ran with `-nosound`), wall decals (removed at each shift), world edges, multiplayer (treadmill stays off), and real keyboard play. Test movement was scripted at 60 units per tic.
- The floor is still one texture. Daggerfall ground textures and scenery are not included.

## Owner play-test list

1. Run in every direction. Is the stutter at each shift noticeable with no monsters nearby?
2. Fight a pack near a shift. Do monsters and projectiles look continuous?
3. Kill monsters, grab some drops, run about 40,000 units away, and come back.
4. Save far from a fight, load, and return.
5. Check whether drops sliding down slopes looks acceptable.

## Questions for the owner

1. With very large packs, a shift can miss one or two frames every 10.5 s. Is that acceptable for now, or should reducing it come before further overworld work?
2. Frozen monsters currently return idle at the spot where they left the window. Should they stay that way, or return already hunting the player?
