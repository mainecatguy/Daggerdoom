# Dungeon connectivity fix

**Result:** v14 and v16 are open in the converted Privateer's Hold and reachable from the entrance. Privateer's Hold is well supported by Daggerfall's own collision. Scourg Barrow is **not fully verified**: its largest area may include false connections through steep regions. The run stopped at a usage limit before this was settled. No human or agent has reviewed the new images.

Review images: `C:\Users\Patrick\AppData\Local\Temp\claude\2627cf03f9216b14\a344155d-8e74-4aae-b246-d786951fa34a\scratchpad\compare5\index.html` (a scratchpad, so it can be erased; `compare.py` regenerates it).

## Root causes

1. **Steep surfaces were treated as walls (v16, v12).** Faces with normal Z below 0.5 were walls. The tunnel's A-frame ceiling is 0.25 to 0.49, so the tunnel had a floor but no ceiling and vanished. The wall threshold is now 0.1.
2. **Any wall overlap deleted the whole span (v14).** A lintel above a 90-unit doorway made the doorway solid. A lintel now lowers the ceiling and a sill may raise the floor by one step. A wall rising higher than a step still makes the cell solid.
3. **Stair sampling skipped treads (v14).** Treads about 14 deep on a 16-unit grid produced a false 28-unit step. The upper floor is lowered by at most 8 units, only where a fine walk over the raw faces proves the climb.
4. **Thin beams occupied two cells (v04).** A hanging beam or lintel with faces on both sides of one cell boundary now occupies only the nearer cell.

New diagnostics: `--debug-line` and `--audit-points`. Each conversion also writes `<slug>.leaks.txt`.

## Measurements

| | Privateer's Hold before | after | Scourg Barrow before | after |
|---|---:|---:|---:|---:|
| Reachable from entrance | 9,149 of 13,729 (66.6%) | 9,589 of 14,026 (68.4%) | 406 of 51,882 (0.8%) | 406 of 57,080 (0.7%) |
| Connected areas | 24 | 19 | 103 | 54 |
| Largest area | 9,398 | 9,821 | 14,079 | 42,414 |
| Engine node / link failures | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Closed-door links blocked | 653 of 816 | 657 of 820 | 2,375 of 2,951 | 2,418 of 3,013 |
| Links crossing a raw wall at body height | 33 | 40 | 23 | 35 |
| Links crossing a door box untagged | 0 | 0 | 0 | 0 |
| Nodes with no raw floor nearby | 0.29% | 1.34% | 0.62% | 3.93% |
| Nodes with no raw ceiling nearby | 1.51% | 2.78% | 2.17% | 5.43% |
| Map lines | 26,704 | 34,712 | 120,742 | 202,427 |

The raw floor and ceiling misses rose. Raised sills and lowered lintels are expected to cause some of this, but I did not separate them. Rendering cost of the larger maps is unmeasured.

## Viewpoints (Privateer's Hold)

Daggerfall captures were reused from the saved evidence. UZDoom was recaptured.

- **Fixed:** v04 (up 128 to 164, Daggerfall 163), v12 and v16 (south 24 to 744, Daggerfall 746), v14 (west 24 to 424, Daggerfall 418).
- **Still mismatched:** v10 only. Daggerfall has a door-shaped hole into empty space and Doom has a wall.
- **Changed but still matching:** v03, v07, v15.
- **v13:** probes agree, but I did not check whether the gap above the door is gone.

## Daggerfall flood bug

The earlier flood fill was wrong. `DungeonCaptureTest.Key` uses round-to-even, and starts on cell centers land on .5, so neighboring cells collapse into one key. Starting 4 units off-center avoids this with no rebuild. The code is **not fixed**, and `compare.py` still starts on a cell center, so its `flood_report` numbers remain understated.

## False-opening evidence

**Privateer's Hold, corrected flood from the entrance:**

- Daggerfall reaches 98.1% of the map's entrance area and **0% of every other area**.
- Only 2 of 35,497 Daggerfall positions have no map node nearby.
- So the remaining 31.6% is separate under static collision. A moving-object route could still connect it.
- Removing all flagged links costs 8 nodes and does not change which areas connect.

**Scourg Barrow, 13 floods:**

- 84 of 183,082 Daggerfall positions have no map node nearby.
- The 42,414-node area spans several separate flood groups. They are joined by 5 uncovered regions plus a few direct links, including drops of 96 and 512 units.
- Floods started inside four of these regions stopped after 1 position, so those joins are **unproven**. They may be real steep ramps or false connections through the newly accepted steep faces.
- The entrance crypt is still sealed. Its moving-object route was not worked on.

## Next steps

1. Determine whether Scourg Barrow's connecting regions are real, using views or a player-capsule test. Limit steep faces to Daggerfall's 70-degree slope limit if they are not.
2. Inspect the new flagged links. Of the 7 new ones in Privateer's Hold, the two groups I checked were the toe of a sloped wall and a small prop. Scourg Barrow's new ones were not inspected.
3. Fix the flood key at the next justified Unity build.

## Owner review list

1. Open the review page and compare v04, v12, v14, and v16.
2. Walk the v14 stairs and the v16 tunnel in UZDoom.
3. Check whether the door gap at v13 is still visible.
