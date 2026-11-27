# Make the angled refit succeed on 45-degree walls

**Waiting on:** the collision fidelity metric (`collision-fidelity-metric.md`), which must show an overall improvement. Owner approval to move to todo.

The owner reports from play that 45-degree walls are the worst offenders in Privateer's Hold. Two causes found in `AngledCollision.cs` (integration as of 2026-11-27, before `dungeonedges`):

- **The alignment test rejects short staircase pieces.** `FindSupport` requires a chain's chord to be within 30 degrees of the feature (`MinAlignment = 0.866`). A 2-3 point piece of a 45-degree staircase has an axis-aligned chord, 45 degrees off. Chains are short because a diagonal corridor with uneven floors or ceilings becomes many small sectors, and each one cuts the wall boundary into its own chain.
- **The reach is too small for staircase corners.** `SnapRadius = 0.9` cells. Outer staircase corners sit about 0.7 cells from a 45-degree wall, or about 1.06 cells when the solid side is offset by half a cell.

Small fixes to try:

- Measure alignment over a longer window.
- Give 45-degree features a larger reach.
- Fit open-to-solid boundaries as long polylines across sector junctions, then pin the junction vertices onto those lines.

No run-time cost is expected. Check first whether `dungeonedges` already changed any of this.
