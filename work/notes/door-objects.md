# Daggerfall door objects

Map: Privateer's Hold at 75% scale, player 21 wide and 56 tall. Demo: `D:\dev\DoomDaggerfall-loop\review\door-demo\play.bat`.

## What changed

- All 58 doors are now separate objects. They left the static mesh and keep their real model, position, rotation, and size.
- The old door path is removed from the converter: no door line specials, no solid door slabs, no shared door controls.
- `--export-mesh` also writes `<slug>_doors.pk3`: one OBJ per door model, textures, placements, and the runtime (`tools/dungeon_converter/door_objects.zs`).
- No engine change.

## Behavior

- Doors rotate 90 degrees on the model origin in 1.5 s, in Daggerfall Unity's direction, and stay open until used again (`DaggerfallActionDoor`).
- Use works from both sides. Use is ignored while a door moves, as in Daggerfall Unity.
- A door that meets a player or monster waits, then continues when clear. Use reverses a waiting door. This is an engineering choice to meet the "never stuck" test.
- Stock Doom door sounds are used as placeholders. They were not heard in testing (`-nosound`).

## Collision choice

Each door has a row of 8 to 9 small invisible solid actors along the model, moved with it every tic. This was the preferred approach and passed, so polyobjects and an engine collider were not tried. Actors have real height, so other floors are unaffected, and they stop hitscans and projectiles. No slab-that-clears is used for collision.

Each doorway also has a non-solid, invisible 3D floor that blocks only sight while the door is closed, so monsters do not see through closed doors.

Daggerfall Unity makes an open door non-solid. This build keeps it solid, as the brief requires.

## Per-door results

From `tools/dungeon_converter/door_check`, in the running game, using the real use path, `TryMove`, line traces, and projectiles.

| Test | Result |
|---|---|
| Swings fully open and closed | 58/58 |
| Use from each side | 46/46 two-sided doors; 12/12 dead ends from their only side |
| Closed door blocks player, hitscan, projectile | 58/58 from every side with standing room |
| Open door blocks player, hitscan, projectile at the model | 46/46 on every face with standing room (30 have one face against a wall) |
| 21-wide, 56-tall player walks through | 46/46 two-sided doors |
| Closed blocks sight, open clears it | 46/46 |
| Swing into a body waits, then resumes | 46/46; the 12 dead ends swing into solid rock |
| Real player and real Imp in the swing | Doors 0, 1, 2: held and resumed |
| Other floors not blocked | 546 positions, 0 failures |
| Save and load with a door open | Door state and collision preserved (door 0) |
| DOOM.WAD E1M1 with the door package | Loads without errors |

**New-system failures: none.**

**Dead ends in the source (12):** doors 21, 23, 24, 25, 27, 28, 31, 34, 37, 41, 49, 53, at (-1056,2) (-1534,480) (-480,2) (-1534,1056) (480,-1534) (2,-1056) (1056,-1534) (2,-480) (2016,2) (2592,2) (2,2016) (2,2592). Their outer side has no dungeon block and no source faces. They open onto black and were not forced through.

## Not verified

- A human play-through with real keyboard input.
- Appearance of all doors. Before/after screenshots cover 4 doors (`review/door-demo/screenshots`).
- Real weapons. Hitscans used line traces and projectiles used a test projectile.
- Door 15 (diagonal) passes only when the player is up to 6 units off center, away from the hinge, because Doom's square body is wider across a diagonal.
- Locked doors. Locks are out of scope, so every door opens.
- `check_map.py` and the parity tool still have closed-door stages written for the old slabs. They do not load door objects, so their door results no longer mean anything.

## Monsters

Monsters do not open doors. Closed doors block their movement and sight. Most stock Doom monsters have radius 20 or more (40 wide), and the door opening is about 36 wide, so they should not fit even when a door is open. That is from the sizes and was not run as a test.

## Play-test list

- Does the swing speed and direction feel right?
- Does the door look right against its frame while moving and when open?
- Does brushing an open door or a moving door feel acceptable?
- Is the diagonal door near (785,765,1152) easy to get through?
- How do the 12 dead-end doors look when opened onto black?

## Questions for the owner

1. What should the 12 dead-end doors do: stay as they are, stay shut, or be hidden?
2. Should monsters open doors, and how should monsters too wide for a doorway behave?
