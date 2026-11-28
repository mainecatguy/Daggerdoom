// Finite tops for exterior collision. Every raster cell the street raster could not walk into becomes a sector whose
// floor is the top of the model there, so nothing in a town or dungeon exterior reaches the sky: the player can
// levitate, climb, or jump onto it, and shots pass above it. Before this, such cells had no sector at all and their
// edges were one-sided lines, which Doom treats as walls of unlimited height.
using System;
using System.Collections.Generic;
using System.Linq;

static partial class Program
{
    static partial class City
    {
        sealed partial class Collision
        {
            public static bool LegacyVoid; // --legacy-void: the old open-topped cells, kept only to measure the baseline
            public int TopCells, RestoredCells, ClampedRoofCells;
            const double RoofSlack = 4; // a sloped roof may overshoot its cell's model top by this much at a corner
            double[] ownerGround;
            float[] columnTop; // highest model surface touching each cell, roof overhangs included
            bool[] insideBuilding; // cells inside a building's sides, from BuildRoofs

            // The floor the street raster reaches in a column: start at the ground and climb any surface within a step.
            static double WalkFloor(List<(float lo, float hi)> spans, double ground)
            {
                double f = ground;
                if (spans == null) return f;
                foreach (var (lo, hi) in spans.OrderBy(s => s.lo))
                    if (hi > f && hi <= f + Step && lo <= f + Step) f = hi;
                return f;
            }

            // The top of the solid stack above a floor: surfaces closer together than the player's height merge,
            // because the player cannot stand in the gap between them. A high overhang with room below is left out.
            static double StackTop(IEnumerable<(float lo, float hi)> spans, double f)
            {
                double t = f;
                foreach (var (lo, hi) in spans.OrderBy(s => s.lo))
                {
                    if (lo >= t + Body) break;
                    if (hi > t) t = hi;
                }
                return t;
            }

            static IEnumerable<(float lo, float hi)> Both(List<(float lo, float hi)> a, List<(float lo, float hi)> b) =>
                (a ?? Enumerable.Empty<(float, float)>()).Concat(b ?? Enumerable.Empty<(float, float)>());

            void FillVoid(List<(float lo, float hi)>[] hits, List<(float lo, float hi)>[] overhangs, short[] raster)
            {
                for (int c = 0; c < floor.Length; c++)
                {
                    if (roofPlane[c] >= 0)
                    {
                        // A roof plane carried past its own triangle (a wall cell filled from a neighbor, a flat fallback at
                        // the building's highest point, or a slope's far corner) can stand above everything in the cell.
                        // Such a cell takes a flat top at the highest model surface it actually holds.
                        double model = Math.Max(columnTop[c], baseZ), cx = x0 + (c % W) * cell, cy = y0 + (c / W) * cell, high = double.MinValue;
                        foreach (var (px, py) in new[] { (cx, cy), (cx + cell, cy), (cx, cy + cell), (cx + cell, cy + cell) }) high = Math.Max(high, CollisionTop(c, px, py));
                        if (high > model + RoofSlack) { roofPlane[c] = FlatPlane(Math.Floor(model)); ClampedRoofCells++; }
                        continue;
                    }
                    if (floor[c] != short.MinValue) continue;
                    // Open ground the walk from the start cannot reach (a walled yard, a wall walk) keeps its own floor.
                    if (raster[c] != short.MinValue) { floor[c] = raster[c]; RestoredCells++; continue; }
                    double top = StackTop(Both(hits[c], overhangs[c]), WalkFloor(hits[c], baseZ));
                    floor[c] = (short)(Math.Round(top / 4) * 4);
                    TopCells++;
                }
            }
        }
    }
}
