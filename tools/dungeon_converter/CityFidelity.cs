// Checks and measurements for exterior collision (towns and dungeon exteriors). Converter tooling only.
//
// HeightCheck (always run): no raster cell may be open to the sky, and no cell's collision top may stand more than
// HeightTolerance above the highest model surface in that cell.
//
// Fidelity (--fidelity): an independent sample of Daggerfall's model on a grid twice as fine as the raster, compared with
// the collision Doom gets. For each fine cell the model's true top is
//   - inside a building's sides and not reachable from the street: the highest surface (the roof seen from outside),
//   - where model surfaces block the player's body: the top of that solid stack,
//   - otherwise: the walkable floor.
// The error is collision top minus true top, capped at Cap; a cell with no collision top (open to the sky) counts as Cap.
// Cells within ReachCells raster cells of ground reachable from the start weigh 1, others 0.25.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    static partial class City
    {
        // --find-group <name>: print the runtime group ids whose locations' names contain <name>.
        public static int FindGroups(string query, string arena2)
        {
            var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
            var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
            WorldTerrain.Load(arena2, maps, blocks);
            var groups = WorldTerrain.Groups();
            for (int g = 0; g < groups.Count; g++)
                if (groups[g].Any(p => p.Name.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0))
                    Console.WriteLine($"group {g}: " + string.Join("; ", groups[g].Select(p => $"{p.Region}/{p.Name} ({p.Type}, {p.BlocksWide}x{p.BlocksHigh})")));
            return 0;
        }

        sealed partial class Collision
        {
            const double HeightTolerance = 8, Cap = 512;
            const int ReachCells = 4;

            double CollisionTop(int c, double px, double py)
            {
                if (roofPlane[c] >= 0) { var q = roofPlanes[roofPlane[c]]; return -(q.a * px + q.b * py + q.d) / q.c; }
                return floor[c] == short.MinValue ? double.PositiveInfinity : floor[c];
            }

            public static string HeightCheck(List<Collision> rasters, out bool pass)
            {
                int open = 0, tall = 0, cells = 0;
                double worst = 0;
                var examples = new List<string>();
                foreach (var r in rasters)
                    for (int c = 0; c < r.floor.Length; c++)
                    {
                        cells++;
                        double cx = r.x0 + (c % r.W) * r.cell, cy = r.y0 + (c / r.W) * r.cell, top = double.MinValue;
                        foreach (var (px, py) in new[] { (cx, cy), (cx + r.cell, cy), (cx, cy + r.cell), (cx + r.cell, cy + r.cell), (cx + r.cell / 2.0, cy + r.cell / 2.0) })
                            top = Math.Max(top, r.CollisionTop(c, px, py));
                        double model = r.columnTop[c] == float.MinValue ? r.baseZ : Math.Max(r.columnTop[c], r.baseZ);
                        if (double.IsPositiveInfinity(top)) { open++; if (examples.Count < 8) examples.Add(FormattableString.Invariant($"open to sky at {cx + r.cell / 2.0:F0},{cy + r.cell / 2.0:F0}")); continue; }
                        double over = top - model;
                        if (over <= HeightTolerance) continue;
                        tall++; worst = Math.Max(worst, over);
                        if (examples.Count < 8) examples.Add(FormattableString.Invariant($"{over:F0} above model at {cx + r.cell / 2.0:F0},{cy + r.cell / 2.0:F0}"));
                    }
                pass = open == 0 && tall == 0;
                return FormattableString.Invariant($"finite height check {(pass ? "PASS" : "FAIL")}: {cells} cells, {open} open to the sky, {tall} more than {HeightTolerance} above the model (worst {worst:F0})") +
                    string.Concat(examples.Select(e => "\n  " + e));
            }

            // Evenly spread model-top cells for the flight test: x y top street.
            public static string TopSamples(List<Collision> rasters, int count)
            {
                var all = rasters.SelectMany(r => r.Tops).ToList();
                int every = Math.Max(1, all.Count / count);
                return string.Concat(all.Where((_, n) => n % every == 0).Take(count).Select(t => FormattableString.Invariant($"{t.x:F1} {t.y:F1} {t.top:F0} {t.walk:F0}\n")));
            }

            sealed class Tally
            {
                public double Weight, Error, Excess, Missing;
                public int Cells, OpenSky, TooTall, Phantom, TooLow;
                public readonly List<string> Examples = new List<string>();
            }

            public static string Fidelity(List<Collision> rasters, List<(V3 a, V3 b, V3 c)> triangles, List<int> owners)
            {
                var all = new Tally();
                foreach (var r in rasters) r.Measure(triangles, owners, all);
                return FormattableString.Invariant(
                    $"exterior fidelity: {all.Cells} fine cells, weighted mean |error| {all.Error / all.Weight:F2} units, excess {all.Excess / all.Weight:F2}, missing {all.Missing / all.Weight:F2}\n") + FormattableString.Invariant(
                    $"open to sky {all.OpenSky}, too tall {all.TooTall} (phantom walls {all.Phantom}), too low {all.TooLow}\n") + string.Concat(all.Examples.Select(x => "  " + x + "\n"));
            }

            void Measure(List<(V3 a, V3 b, V3 c)> triangles, List<int> owners, Tally tally)
            {
                const double fine = 4; // fixed, so rasters of any cell size are measured on the same grid
                int fw = (int)(W * cell / fine), fh = (int)(H * cell / fine);
                var spans = new List<(float lo, float hi)>[fw * fh];
                var high = new List<(float lo, float hi)>[fw * fh];
                Span<(double x, double y, double z)> poly = new (double, double, double)[12], next = new (double, double, double)[12];
                for (int t = 0; t < triangles.Count; t++)
                {
                    var (a, b, c) = triangles[t];
                    int owner = owners[t];
                    bool vertical = IsVertical(a, b, c);
                    int i0 = Math.Max(0, (int)Math.Floor((Math.Min(a.X, Math.Min(b.X, c.X)) - x0) / fine)), i1 = Math.Min(fw - 1, (int)Math.Floor((Math.Max(a.X, Math.Max(b.X, c.X)) - x0) / fine));
                    int j0 = Math.Max(0, (int)Math.Floor((Math.Min(a.Y, Math.Min(b.Y, c.Y)) - y0) / fine)), j1 = Math.Min(fh - 1, (int)Math.Floor((Math.Max(a.Y, Math.Max(b.Y, c.Y)) - y0) / fine));
                    for (int j = j0; j <= j1; j++)
                        for (int i = i0; i <= i1; i++)
                        {
                            poly[0] = (a.X, a.Y, a.Z); poly[1] = (b.X, b.Y, b.Z); poly[2] = (c.X, c.Y, c.Z);
                            double cx0 = x0 + i * fine, cy0 = y0 + j * fine;
                            int n = Clip(poly, 3, next, 0, cx0, 1); n = Clip(next, n, poly, 0, cx0 + fine, -1);
                            n = Clip(poly, n, next, 1, cy0, 1); n = Clip(next, n, poly, 1, cy0 + fine, -1);
                            if (n == 0) continue;
                            double lo = double.MaxValue, hi = double.MinValue;
                            for (int k = 0; k < n; k++) { lo = Math.Min(lo, poly[k].z); hi = Math.Max(hi, poly[k].z); }
                            bool overhang = owner >= 0 && owner < ownerGround.Length && !vertical && lo > ownerGround[owner] + Step;
                            ((overhang ? high : spans)[i + j * fw] ??= new List<(float, float)>(4)).Add(((float)lo, (float)hi));
                        }
                }
                var reachable = new bool[W * H];
                for (int q = 0; q < reachable.Length; q++) reachable[q] = component[q] >= 0;
                var near = Dilate(reachable, W, H, ReachCells);
                for (int j = 0; j < fh; j++)
                    for (int i = 0; i < fw; i++)
                    {
                        int f = i + j * fw, c = (int)((i + 0.5) * fine / cell) + (int)((j + 0.5) * fine / cell) * W;
                        double px = x0 + (i + 0.5) * fine, py = y0 + (j + 0.5) * fine;
                        double walk = WalkFloor(spans[f], baseZ);
                        bool blocked = spans[f] != null && spans[f].Any(s => s.lo < walk + Body && s.hi > walk + Clearance);
                        bool enclosed = insideBuilding[c] && component[c] < 0; // an arch or doorway the street reaches is a passage, not a roof
                        double truth = enclosed ?Math.Max(walk, Both(spans[f], high[f]).Select(s => (double)s.hi).DefaultIfEmpty(walk).Max())
                            : blocked ? StackTop(Both(spans[f], high[f]), walk) : walk;
                        double top = CollisionTop(c, px, py), w = near[c] ? 1 : 0.25;
                        double e = double.IsPositiveInfinity(top) ? Cap : Math.Clamp(top - truth, -Cap, Cap);
                        tally.Cells++; tally.Weight += w; tally.Error += w * Math.Abs(e);
                        if (e > 0) tally.Excess += w * e; else tally.Missing -= w * e;
                        if (double.IsPositiveInfinity(top)) tally.OpenSky++;
                        if (e > HeightTolerance) { tally.TooTall++; if (!enclosed && !blocked && top > walk + Step) tally.Phantom++; }
                        if (e < -Step && tally.TooLow++ % 97 == 0 && tally.Examples.Count < 12) tally.Examples.Add(FormattableString.Invariant($"too low at {px:F0},{py:F0}: collision {top:F0}, model {truth:F0}, floor {walk:F0}, enclosed {enclosed}, blocked {blocked}, roof {roofPlane[c] >= 0}"));
                    }
            }
        }
    }
}
