# Dungeon connectivity fix

**Result:** v14 and v16 are open in the converted Privateer's Hold and reachable from the entrance. The fix creates no verified leak through a real wall or closed door. No human has played either map, and rendering performance of the larger maps was not measured.

**Review images:** `D:\dev\DoomDaggerfall-loop\review\connectivity-fix\index.html` (Daggerfall left, UZDoom right). Generated output, not committed.

## Root causes and changes

1. **Steep surfaces were treated as walls (v16, v12).** Faces with normal Z below 0.5 were walls. The tunnel's A-frame ceiling is 0.25 to 0.49, so the tunnel had a floor but no ceiling and vanished. The wall threshold is now 0.1.
2. **Any wall overlap deleted the whole span (v14).** A lintel above a 90-unit doorway made the doorway solid. A lintel now lowers the ceiling and a sill may raise the floor by one step. A wall rising higher than a step still makes the cell solid.
3. **Stair sampling skipped treads (v14).** Treads about 14 deep on a 16-unit grid produced a false 28-unit step. The upper floor is lowered by at most 8 units, only where a fine walk over the raw faces proves the climb.
4. **Thin beams occupied two cells (v04).** A hanging beam or lintel with faces on both sides of one cell boundary now occupies only the nearer cell.
5. **Bars slipped between sample lines (an older false opening).** Model 41313 is a row of bars about 21 units apart, which the player cannot fit through, but Doom could walk through them. Separate model pieces with a footprint of at most one cell and at least 40 units of height now make their center cell solid, and gap bridging cannot reopen them.

New diagnostics: `--debug-line` and `--audit-points`. Each conversion also writes `<slug>.leaks.txt`.

## Measurements

| | Privateer's Hold before | after | Scourg Barrow before | after |
|---|---:|---:|---:|---:|
| Reachable from entrance | 9,149 of 13,729 (66.6%) | 9,541 of 13,991 (68.2%) | 406 of 51,882 (0.8%) | 406 of 57,040 (0.7%) |
| Connected areas | 24 | 22 | 103 | 59 |
| Largest area, counting one-way drops | 9,398 | 9,773 | 14,079 | 41,003 |
| Engine node / link failures | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Closed-door links blocked | 653 of 816 | 657 of 820 | 2,375 of 2,951 | 2,418 of 3,013 |
| Links crossing a raw wall at body height | 33 | 10 | 23 | 18 |
| Links crossing a door box untagged | 0 | 0 | 0 | 0 |
| Nodes with no raw floor nearby | 0.29% | 0.94% | 0.62% | 3.33% |
| Nodes with no raw ceiling nearby | 1.51% | 2.62% | 2.17% | 5.38% |
| Map lines | 26,704 | 34,819 | 120,742 | 202,890 |

The raw floor and ceiling misses rose. Raised sills and lowered lintels are expected to cause some of this, but I did not separate them.

## Viewpoints (Privateer's Hold)

Final run: fresh Daggerfall and UZDoom captures of all 16 viewpoints. **15 of 16 match.**

- **Fixed:** v04 (up 128 to about 164, Daggerfall 163), v12 and v16 (south 24 to 744, Daggerfall 746), v14 (west 24 to 424, Daggerfall 418).
- **Still mismatched:** v10. Daggerfall has a door-shaped hole into empty space and Doom has a wall.
- **Changed but still matching:** v03, v07, v15.
- **v13 is not fixed.** Its probes agree, but the image still shows a slab wider than the source door with a recessed band above it. The width comes from door cells on the 16-unit grid. This is door appearance, so I left it.

## Daggerfall flood bug

The earlier flood fill stopped early. `DungeonCaptureTest.Key` rounds to even, and starts on cell centers land on .5, so neighboring cells collapsed into one key. `compare.py` now starts 4 units off-center, which avoids this without a Unity build. The earlier note's "90.9%" and its doubts about the flood should be read with this in mind.

## False-opening evidence

**Privateer's Hold:**

- Daggerfall's collision flood from the entrance reaches 97.6% of the map's entrance area and **0% of the top cut-off areas in the report**.
- Only 2 of 35,497 Daggerfall positions have no map node nearby, so no meaningful walkable area is still walled off.
- The remaining 31.8% is separate under static collision. A moving-object route could still connect it, which is the open owner decision.

**Rays along suspect links, both dungeons:**

- All 254 two-way links at the edge of flood coverage are open in Daggerfall (16 and 238).
- Of 28 links flagged by the audit, Daggerfall blocks 9 (2 and 7). All 9 existed before this work and none affects reachability from the entrance.

**Scourg Barrow:**

- 82 of 183,078 Daggerfall positions have no map node nearby.
- The large merged area is mostly separate two-way walk areas joined by **one-way drops** (largest two-way area 14,785 nodes). The flood cannot follow large drops, which is why it looked split.
- I tested one sample from each of the 20 largest drop connections, on the map just before the bar fix. 16 matched. 3 land 37 to 45 units lower than the map says, and 1 lands on top of a closed cave door, which the map also models.
- The entrance crypt is still sealed. Its moving-object route was not worked on.

## Failed approaches

- Keeping the free space above a wall as a span created false ledges and split door 55.
- The first Scourg Barrow floods appeared to prove false connections. That was the rounding bug.

## Remaining defects

- 9 older links pass small obstacles that Daggerfall blocks.
- v10's hole and v13's door shape are unchanged.
- Scourg Barrow has more lines and sectors, and its render cost is unmeasured.

## Owner review list

1. Open the review page and compare v04, v12, v14, and v16.
2. Walk the v14 stairs and the v16 tunnel in UZDoom.
3. Check that the barred cells in Privateer's Hold block you and look acceptable.
4. Decide whether v13's wider door slab is acceptable for now.
