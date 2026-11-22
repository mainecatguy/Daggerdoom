# Stock Doom body at 75% world scale

Map: Privateer's Hold, `--world-scale 0.75`, UZDoom build `uzdoom-mesh`. Output is in `review/stock-demo-75`.

## Changed

- Generated maps now default to Doom height 56, eye 41, step 24, and crouch 28.
- Collision width follows Daggerfall at world scale, by owner decision: radius 10.5 (21 wide) at 75%. The runtime width add-on is separate (`privateershold_width.pk3`).
- `--daggerfall-player` keeps the old scaled body and writes `_player.pk3`. `parity.py` has the same flag.
- Low spaces stay in the map using the old scaled threshold (42 at 75%), so crouch routes are not deleted by the taller standing height.
- Door logic is unchanged.

## Measured

Without the width add-on, the real player on the demo map and on DOOM.WAD E1M1 reports radius 16, height 56, view 41, step 24, crouched 28/20.5.

Parity flood, positions reachable from the entrance (Doom, with Daggerfall in brackets):

| Mode | Scaled Daggerfall body | This build |
|---|---|---|
| Standing, doors closed | 1164 (1188) | 1164 (1188) |
| Standing, doors open | 19534 (19569) | 20189 (19771) |
| Crouching, doors open | 19790 (20091) | 20460 (20333) |

Standing with doors open, false openings rose from 817 to 1067 and false walls fell from 772 to 649.

Door test: real `+use`, then real `TryMove` with a 21-wide, 56-tall test body, all 58 door controls, from both sides of each door's main face.

- Every tested door face is at least 48 wide, so none is too narrow for 21 wide.
- 46 of 58 doors pass in both directions.
- 12 do not pass. Each stops at a solid wall at a block seam: (-1524,480,960) (-1524,1056,384) (-480,12,384) (12,-1056,960) (12,-480,384) (12,2016,960) (12,2592,384) (1056,-1524,384) (2592,12,384) (480,-1524,960) (-1056,12,960) (2016,12,960). For (-1056,12,960), the source geometry has no floor or ceiling behind the door, so it is a dead-end door there. The other 11 were not checked against the source.
- **Use opens each door from only one side.** All 58 opened from the line's front side (+X or +Y) and none from the back. Door lines set `playeruse` but not `playeruseback`. This was not changed, per the scope instruction.

## Not verified

- Passing through doors at the runtime radius 16, or with the width add-on loaded.
- Game feel and a human play-through.
- Scourg Barrow (skipped by instruction).

## Owner decisions

1. Should doors open with Use from both sides? The likely change is adding `playeruseback = true` to door lines.
2. What should the 12 block-seam doors do? At least one is a dead end in the source.
