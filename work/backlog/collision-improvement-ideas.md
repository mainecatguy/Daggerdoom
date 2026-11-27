# Other collision improvement ideas

**Waiting on:** the collision fidelity metric (`collision-fidelity-metric.md`). Owner picks which, if any, become their own items. Each one must prove an overall improvement on the metric.

From the owner brainstorm of 2026-11-27, roughly best value first:

- **Dual contouring vertex placement.** `WallAxis` already knows exactly where each wall crosses each center-to-center line, and the wall's normal. Place each boundary vertex at the least-squares point of the wall planes crossing its four lines (the math `SolveVertex` already does), instead of searching for a nearby feature. This removes the reach and alignment heuristics. Keep the feature search as a fallback for boundaries with no wall crossing (slope creases, closed gaps, posts, doors).
- **Split instead of revert at stacked-level conflicts.** In the angled-collision run, 732 of 7,357 chains went back to the grid, mostly where one 2D boundary had to serve walls on two floors that nearly line up. Adding a cut line so each level's wall gets its own boundary may keep more fits, at the cost of more sectors. Watch for slivers.
- **Adaptive cell size.** Fine cells near walls and coarse cells in open rooms: better fit without the run-time cost of a uniformly small cell. Pairs naturally with the grid-shape refactor (`work/queue/collisionshape/01.opus.grid-shape-refactor.md`).
- **Exact footprints for posts, pillars and bars.** Today a thin piece makes its whole cell solid (`ApplyPosts`). Emit the real footprint as a small closed sector instead.
- **Steep floors as real slopes.** Floors steeper than about 41 degrees stay stepped so routes stay climbable. With climbing and slide rules (`climbing-levitation-and-steep-surfaces.md`) they could become real slopes.
- **Leaning walls.** Doom walls are vertical. A leaning wall could be approximated with stacked 3D floor bands where the climb band or contact tier needs it.
- **Town collision.** The town raster in `CityExport.cs` has no angled refit. Bring the refit or the shared grid shape to it, and extend the metric to towns.
- **Weapons hit the real mesh.** Already a backlog item (`weapon-collision-with-the-daggerfall-mesh.md`). Better sector fit reduces how much it is needed.
- **Last resort: slice the mesh into polygons.** Cut the walls at waist height for each level and clip sectors against the exact outlines. This is the most accurate, but it brings back the stacked-room problem (one 2D partition for several levels, slivers, overlapping models) and means rebuilding the grid-based door, stair and connectivity stages.
