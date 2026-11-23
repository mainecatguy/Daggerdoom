// Building roofs for converted cities. Solid building cells become sectors raised to the real roof surface.
// A building's sides are its near-vertical faces that come down to the ground. Roof overhangs outside them are ignored.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using DaggerfallConnect.Utility;

static partial class Program
{
    static partial class City
    {
        sealed partial class Collision
        {
            const double MinSideHeight = 16;
            const int DoorClosing = 4; // cells; bridges door-sized gaps in a building's sides when finding its inside
            static readonly List<(double a, double b, double c, double d, int z)> roofPlanes = new List<(double, double, double, double, int)>();
            static readonly Dictionary<(long, long, long, long), int> roofPlaneIds = new Dictionary<(long, long, long, long), int>();
            int[] roofPlane;
            readonly List<(int owner, double x, double y, double z)> roofSamples = new List<(int, double, double, double)>();
            public int Buildings, RoofCells, SlopedRoofCells, FilledRoofCells, FallbackRoofCells, OpenFootprintCells, NoRoofCells;

            int Code(int c) => roofPlane[c] >= 0 ? 1000000 + roofPlane[c] : floor[c] == short.MinValue ? int.MinValue : floor[c];

            static (double x, double y, double z) Normal(V3 a, V3 b, V3 c)
            {
                double ux = b.X - a.X, uy = b.Y - a.Y, uz = b.Z - a.Z, vx = c.X - a.X, vy = c.Y - a.Y, vz = c.Z - a.Z;
                return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx);
            }

            static bool IsVertical(V3 a, V3 b, V3 c)
            {
                var (nx, ny, nz) = Normal(a, b, c);
                double length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                return length < 1e-9 || Math.Abs(nz) / length < 0.2;
            }

            static int AddPlane(double a, double b, double c, double d, int z)
            {
                var key = ((long)Math.Round(a * 2000), (long)Math.Round(b * 2000), (long)Math.Round(c * 2000), (long)Math.Round(d * 2));
                if (!roofPlaneIds.TryGetValue(key, out int id))
                {
                    roofPlaneIds[key] = id = roofPlanes.Count;
                    roofPlanes.Add((a, b, c, d, z));
                }
                return id;
            }

            static int FlatPlane(double z) => AddPlane(0, 0, 1, -Math.Round(z), (int)Math.Round(z));

            static int PlaneOf(V3 p, V3 q, V3 r)
            {
                var (nx, ny, nz) = Normal(p, q, r);
                if (nz < 0) { nx = -nx; ny = -ny; nz = -nz; }
                double length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                nx /= length; ny /= length; nz /= length;
                double mid = (p.Z + q.Z + r.Z) / 3;
                if (Math.Abs(nx) < 0.01 && Math.Abs(ny) < 0.01) return FlatPlane(mid);
                return AddPlane(nx, ny, nz, -(nx * p.X + ny * p.Y + nz * p.Z), (int)Math.Round(mid));
            }

            static bool[] Dilate(bool[] grid, int w, int h, int radius)
            {
                var across = new bool[grid.Length];
                for (int j = 0; j < h; j++)
                {
                    int last = -radius - 1;
                    for (int i = 0; i < w; i++) { if (grid[i + j * w]) last = i; if (i - last <= radius) across[i + j * w] = true; }
                    last = w + radius;
                    for (int i = w - 1; i >= 0; i--) { if (grid[i + j * w]) last = i; if (last - i <= radius) across[i + j * w] = true; }
                }
                var result = new bool[grid.Length];
                for (int i = 0; i < w; i++)
                {
                    int last = -radius - 1;
                    for (int j = 0; j < h; j++) { if (across[i + j * w]) last = j; if (j - last <= radius) result[i + j * w] = true; }
                    last = h + radius;
                    for (int j = h - 1; j >= 0; j--) { if (across[i + j * w]) last = j; if (last - j <= radius) result[i + j * w] = true; }
                }
                return result;
            }

            void BuildRoofs(List<(V3 a, V3 b, V3 c)> triangles, List<int> owners, Dictionary<int, HashSet<int>> sides)
            {
                roofPlane = new int[W * H];
                Array.Fill(roofPlane, -1);
                var bestZ = new double[W * H];
                Array.Fill(bestZ, double.MinValue);
                var byOwner = new Dictionary<int, List<int>>();
                for (int t = 0; t < triangles.Count; t++)
                    if (owners[t] >= 0 && sides.ContainsKey(owners[t]))
                    {
                        if (!byOwner.TryGetValue(owners[t], out var list)) byOwner[owners[t]] = list = new List<int>();
                        list.Add(t);
                    }
                foreach (int owner in sides.Keys.OrderBy(k => k))
                {
                    Buildings++;
                    var cells = sides[owner];
                    int pad = DoorClosing + 1;
                    int li0 = cells.Min(c => c % W) - pad, li1 = cells.Max(c => c % W) + pad, lj0 = cells.Min(c => c / W) - pad, lj1 = cells.Max(c => c / W) + pad;
                    int lw = li1 - li0 + 1, lh = lj1 - lj0 + 1;
                    var wall = new bool[lw * lh];
                    foreach (int c in cells) wall[c % W - li0 + (c / W - lj0) * lw] = true;

                    // Close door-sized gaps, flood in from outside, then give back the closing distance.
                    var closed = Dilate(wall, lw, lh, DoorClosing);
                    var outside = new bool[lw * lh];
                    var stack = new Stack<int>();
                    void Seed(int q) { if (!closed[q] && !outside[q]) { outside[q] = true; stack.Push(q); } }
                    for (int i = 0; i < lw; i++) { Seed(i); Seed(i + (lh - 1) * lw); }
                    for (int j = 0; j < lh; j++) { Seed(j * lw); Seed(lw - 1 + j * lw); }
                    while (stack.Count > 0)
                    {
                        int p = stack.Pop(), i = p % lw, j = p / lw;
                        if (i > 0) Seed(p - 1);
                        if (i < lw - 1) Seed(p + 1);
                        if (j > 0) Seed(p - lw);
                        if (j < lh - 1) Seed(p + lw);
                    }
                    var grown = Dilate(outside, lw, lh, DoorClosing);
                    var inside = new bool[lw * lh];
                    for (int q = 0; q < inside.Length; q++) inside[q] = !grown[q] || wall[q];

                    // The roof at a cell is the highest non-vertical surface of this building over the cell's center.
                    var z = new double[lw * lh];
                    var plane = new int[lw * lh];
                    Array.Fill(z, double.MinValue);
                    Array.Fill(plane, -1);
                    foreach (int t in byOwner[owner])
                    {
                        var (a, b, c) = triangles[t];
                        if (IsVertical(a, b, c)) continue;
                        int i0 = Math.Max(li0, (int)Math.Floor((Math.Min(a.X, Math.Min(b.X, c.X)) - x0) / cell)), i1 = Math.Min(li1, (int)Math.Floor((Math.Max(a.X, Math.Max(b.X, c.X)) - x0) / cell));
                        int j0 = Math.Max(lj0, (int)Math.Floor((Math.Min(a.Y, Math.Min(b.Y, c.Y)) - y0) / cell)), j1 = Math.Min(lj1, (int)Math.Floor((Math.Max(a.Y, Math.Max(b.Y, c.Y)) - y0) / cell));
                        double det = (b.Y - c.Y) * (a.X - c.X) + (c.X - b.X) * (a.Y - c.Y);
                        if (Math.Abs(det) < 1e-9) continue;
                        int id = -1;
                        for (int j = j0; j <= j1; j++)
                            for (int i = i0; i <= i1; i++)
                            {
                                double px = x0 + (i + 0.5) * cell, py = y0 + (j + 0.5) * cell;
                                double u = ((b.Y - c.Y) * (px - c.X) + (c.X - b.X) * (py - c.Y)) / det, v = ((c.Y - a.Y) * (px - c.X) + (a.X - c.X) * (py - c.Y)) / det, w = 1 - u - v;
                                if (u < -1e-6 || v < -1e-6 || w < -1e-6) continue;
                                double height = u * a.Z + v * b.Z + w * c.Z;
                                int q = i - li0 + (j - lj0) * lw;
                                if (!inside[q] || height <= z[q]) continue;
                                if (id < 0) id = PlaneOf(a, b, c);
                                z[q] = height; plane[q] = id;
                            }
                    }

                    // Wall cells can miss the roof's edge by part of a cell. They take the nearest roof.
                    for (int pass = 0; pass < 3; pass++)
                    {
                        var fill = new List<(int q, int from)>();
                        for (int q = 0; q < inside.Length; q++)
                        {
                            if (!inside[q] || !wall[q] || plane[q] >= 0) continue;
                            int i = q % lw, j = q / lw, from = -1;
                            foreach (int n in new[] { i > 0 ? q - 1 : -1, i < lw - 1 ? q + 1 : -1, j > 0 ? q - lw : -1, j < lh - 1 ? q + lw : -1 })
                                if (n >= 0 && plane[n] >= 0 && (from < 0 || z[n] > z[from])) from = n;
                            if (from >= 0) fill.Add((q, from));
                        }
                        foreach (var (q, from) in fill) { z[q] = z[from]; plane[q] = plane[from]; FilledRoofCells++; }
                    }
                    double top = z.Max();
                    if (top == double.MinValue)
                        foreach (int t in byOwner[owner]) top = Math.Max(top, Math.Max(triangles[t].a.Z, Math.Max(triangles[t].b.Z, triangles[t].c.Z)));

                    int sampled = 0, every = Math.Max(1, inside.Count(q => q) / 24);
                    for (int q = 0; q < inside.Length; q++)
                    {
                        if (!inside[q]) continue;
                        int gi = q % lw + li0, gj = q / lw + lj0;
                        if (gi < 0 || gj < 0 || gi >= W || gj >= H) continue;
                        int g = gi + gj * W;
                        if (floor[g] != short.MinValue) { OpenFootprintCells++; continue; } // streets, doorways, and arches stay open
                        if (plane[q] < 0)
                        {
                            if (!wall[q]) { NoRoofCells++; continue; }
                            z[q] = top; plane[q] = FlatPlane(top); FallbackRoofCells++;
                        }
                        if (z[q] <= bestZ[g]) continue;
                        if (roofPlane[g] < 0) RoofCells++;
                        bestZ[g] = z[q]; roofPlane[g] = plane[q];
                        if (!wall[q] && sampled++ % every == 0) roofSamples.Add((owner, x0 + (gi + 0.5) * cell, y0 + (gj + 0.5) * cell, z[q]));
                    }
                }
                for (int c = 0; c < roofPlane.Length; c++)
                    if (roofPlane[c] >= 0 && (roofPlanes[roofPlane[c]].a != 0 || roofPlanes[roofPlane[c]].b != 0)) SlopedRoofCells++;
            }

            // Highest roof surface in this raster, for the shared sky ceiling.
            double RoofTop()
            {
                double top = double.MinValue;
                for (int c = 0; c < roofPlane.Length; c++)
                {
                    if (roofPlane[c] < 0) continue;
                    var q = roofPlanes[roofPlane[c]];
                    double px = x0 + (c % W + 0.5) * cell, py = y0 + (c / W + 0.5) * cell;
                    top = Math.Max(top, -(q.a * px + q.b * py + q.d) / q.c + cell);
                }
                return top;
            }

            string RoofSlope(int planeId)
            {
                if (planeId < 0) return "";
                var q = roofPlanes[planeId];
                if (q.a == 0 && q.b == 0) return "";
                string F(double v) => v.ToString("R", CultureInfo.InvariantCulture);
                return $" floorplane_a = {F(q.a)}; floorplane_b = {F(q.b)}; floorplane_c = {F(q.c)}; floorplane_d = {F(q.d)};";
            }

            public string RoofSamples() => string.Concat(roofSamples.Select(q => FormattableString.Invariant($"{q.owner} {q.x:F1} {q.y:F1} {q.z:F2}\n")));
        }
    }
}
