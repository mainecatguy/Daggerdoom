// Checks and measurements for exterior collision (towns and dungeon exteriors). Converter tooling only.
//
// HeightCheck (always run): no raster cell may be open to the sky, and no cell's collision top may stand more than
// HeightTolerance above the highest model surface in that cell.
//
// Fidelity (--fidelity): the collision fidelity metric of Fidelity.cs on the emitted map (ExteriorMetric below), the same
// metric the dungeons use. It replaced exterior collision 01's raster heightfield measure, which read the converter's own
// arrays and reused its stack rule.
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

        // --fidelity: the collision fidelity metric (Fidelity.cs) on the emitted exterior map. Daggerfall's faces are the
        // model colliders (what Daggerfall Unity collides with and draws) and the terrain over the walkable area.
        // Nature billboards and gate leaves have no collider in either game and are left out.
        static int ExteriorMetric(string wad, string slug, string outDir, string cache, Scene scene, int bx0, int bx1, int by0, int by1, double startX, double startY)
        {
            tris.Clear();
            for (int n = 0; n < scene.Colliders.Count; n++)
            {
                var (a, b, c) = scene.Colliders[n];
                tris.Add(new Tri { A = a, B = b, C = c, N = scene.ColliderNormals[n], Instance = -1 });
            }
            void Ground(V3 a, V3 b, V3 c)
            {
                var n = Cross(Sub(b, a), Sub(c, a));
                double len = Math.Sqrt(Dot(n, n));
                if (len < 1e-9) return;
                if (n.Z < 0) { (b, c) = (c, b); len = -len; }
                tris.Add(new Tri { A = a, B = b, C = c, N = new V3(n.X / len, n.Y / len, n.Z / len), Instance = -1 });
            }
            V3 P(int tx, int ty) => new V3(DoomX(tx), DoomY(ty), DoomZ(tx, ty));
            for (int ty = by0; ty < by1; ty++)
                for (int tx = bx0; tx < bx1; tx++)
                {
                    if (!Walkable(tx, ty)) continue; // the map holds terrain only within the walking margin of each site
                    Ground(P(tx, ty), P(tx, ty + 1), P(tx + 1, ty + 1));
                    Ground(P(tx, ty), P(tx + 1, ty + 1), P(tx + 1, ty));
                }
            fidelityDir = outDir; fidelityCache = cache;
            FidExterior = true; FidStep = 4; FidKeepScale = 0.1;
            return RunFidelity(wad, slug, new V3(startX, startY, double.NaN));
        }

        sealed partial class Collision
        {
            const double HeightTolerance = 8;

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
        }
    }
}
