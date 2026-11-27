// Fits the grid's collision sectors to the real Daggerfall mesh. The grid still decides which spaces exist and how they
// connect. This pass moves sector boundaries onto real wall and slope edges and gives sectors the real sloped planes.
// Any boundary that cannot be moved safely stays on the grid. --grid-collision turns the whole pass off.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

sealed class SurfacePlane { public double Gx, Gy, H; public double At(double x, double y) => Gx * x + Gy * y + H; }
sealed class Feature { public double X0, Y0, X1, Y1, Lo, Hi; public bool Wall; }
sealed class BoundaryChain
{
    public List<(int x, int y)> Points = new List<(int, int)>();
    public int Front, Back;
    public bool Frozen, Reverted, Gridded; // Reverted: off the real edges, on the smoothed staircase. Gridded: on the grid.
    public List<(double lo, double hi)> Heights;
    public List<(int id, double x, double y)> Fitted;
}

static partial class Program
{
    // Doom stops walkers on floors whose normal z is below STEEPSLOPE (0.70712, just under 45 degrees). Planes are written
    // no steeper than MinPlaneNormal (44.3 degrees). Faces from there down to RampNormal (45.6 degrees) are flattened to it.
    const double STEEPSLOPE = 46342 / 65536.0;
    const double FlatNormal = 0.9995, MinPlaneNormal = 0.715, RampNormal = 0.70, CeilingNormal = 0.2, PlaneMatch = 2.5;
    const double SnapRadius = 0.9, MinAlignment = 0.866, MaxMove = 1.3, MaxDeviation = 1.35, UnsnappedTolerance = 0.72, SnappedTolerance = 1.25, PinnedTolerance = 0.25;
    const int MaxStrikes = 12;
    const int FeatureBucket = 24;

    static bool gridCollision;
    static string debugChains;
    static bool plainAngled; // --plain-angled: the first angled pass only, without ramp planes, sliver merging, or smoothing, for comparison
    static readonly List<SurfacePlane> surfacePlanes = new List<SurfacePlane>();
    static readonly List<Feature> features = new List<Feature>();
    static Dictionary<(int, int), List<Feature>> featureIndex;
    static int floorPlaneSpans, ceilingPlaneSpans, chainCount, chainsFitted, chainsReverted, chainsSmoothed, chainsFrozen, refitPasses, stairCorners;
    const double StairStep = 2.01; // longest staircase step, in cells, that SmoothStairs straightens
    // AbsorbSlivers: largest sliver, in cells, and the largest floor and ceiling changes. Floors barely move, so stairs keep their treads.
    const int SliverCells = 2, SliverFloor = 4, SliverStep = 24;
    static int slivers;
    static string fitReport = "";
    static readonly int[] steepFloorSpans = new int[10];

    static bool PlaneOf(in Tri t, out SurfacePlane plane, out double normalZ)
    {
        plane = null;
        double ux = t.B.X - t.A.X, uy = t.B.Y - t.A.Y, uz = t.B.Z - t.A.Z, vx = t.C.X - t.A.X, vy = t.C.Y - t.A.Y, vz = t.C.Z - t.A.Z;
        double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
        normalZ = length < 1e-9 ? 0 : Math.Abs(nz) / length;
        if (length < 1e-9 || Math.Abs(nz) < 1e-9) return false;
        double gx = -nx / nz, gy = -ny / nz;
        plane = new SurfacePlane { Gx = gx, Gy = gy, H = t.A.Z - gx * t.A.X - gy * t.A.Y };
        return true;
    }

    // Gives a span the real plane of the sloped face at its cell center, when the span's height came from that face.
    static void AssignPlanes()
    {
        var index = new List<int>[width * height];
        for (int n = 0; n < tris.Count; n++)
        {
            var t = tris[n];
            if (Math.Abs(t.N.Z) < WallNormalZ) continue;
            int i0 = Math.Max(0, (int)Math.Floor((Math.Min(t.A.X, Math.Min(t.B.X, t.C.X)) - minX) / cell));
            int i1 = Math.Min(width - 1, (int)Math.Floor((Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)) - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y)) - minY) / cell));
            int j1 = Math.Min(height - 1, (int)Math.Floor((Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)) - minY) / cell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    (index[Index(i, j)] ??= new List<int>()).Add(n);
        }
        // Daggerfall's 45-degree ramps sit just past Doom's walking limit. Each such ramp face gets one slightly
        // shallower plane, turned about the face's middle so both ends stay within a few units of the visible ramp.
        var rampSums = new Dictionary<(long, long, long), (double x, double y, double w)>();
        foreach (var t in tris)
        {
            if (t.N.Z <= 0 || !PlaneOf(t, out var plane, out double normal) || normal >= MinPlaneNormal || normal < RampNormal) continue;
            var key = ((long)Math.Round(plane.Gx * 2000), (long)Math.Round(plane.Gy * 2000), (long)Math.Round(plane.H * 2));
            double area = Math.Abs((t.B.X - t.A.X) * (t.C.Y - t.A.Y) - (t.C.X - t.A.X) * (t.B.Y - t.A.Y)) / 2 + 1e-6;
            rampSums.TryGetValue(key, out var s);
            rampSums[key] = (s.x + area * (t.A.X + t.B.X + t.C.X) / 3, s.y + area * (t.A.Y + t.B.Y + t.C.Y) / 3, s.w + area);
        }
        var rampCenters = rampSums.ToDictionary(p => p.Key, p => (p.Value.x / p.Value.w, p.Value.y / p.Value.w));
        var ids = new Dictionary<(long, long, long), int>();
        int Find(double px, double py, int z, bool up, List<int> list)
        {
            int best = -1;
            double bestError = PlaneMatch;
            SurfacePlane bestPlane = null;
            double bestNormal = 1;
            foreach (int n in list)
            {
                var t = tris[n];
                if (t.N.Z > 0 != up) continue;
                double d = (t.B.Y - t.C.Y) * (t.A.X - t.C.X) + (t.C.X - t.B.X) * (t.A.Y - t.C.Y);
                if (Math.Abs(d) < 1e-9) continue;
                double u = ((t.B.Y - t.C.Y) * (px - t.C.X) + (t.C.X - t.B.X) * (py - t.C.Y)) / d;
                double v = ((t.C.Y - t.A.Y) * (px - t.C.X) + (t.A.X - t.C.X) * (py - t.C.Y)) / d;
                if (u < -1e-6 || v < -1e-6 || u + v > 1 + 1e-6) continue;
                double error = Math.Abs(u * t.A.Z + v * t.B.Z + (1 - u - v) * t.C.Z - z);
                if (error > bestError || !PlaneOf(t, out var plane, out double normal)) continue;
                bestError = error; bestPlane = plane; bestNormal = normal; best = n;
            }
            if (up && best >= 0 && bestNormal < RampNormal) steepFloorSpans[Math.Min(9, (int)(bestNormal * 10))]++;
            if (best < 0 || bestNormal >= FlatNormal || bestNormal < (up ? (plainAngled ? 0.75 : RampNormal) : CeilingNormal)) return -1;
            var key = ((long)Math.Round(bestPlane.Gx * 2000), (long)Math.Round(bestPlane.Gy * 2000), (long)Math.Round(bestPlane.H * 2));
            if (up && bestNormal < MinPlaneNormal) bestPlane = Flatten(bestPlane, rampCenters[key]);
            if (!ids.TryGetValue(key, out int id)) { ids[key] = id = surfacePlanes.Count; surfacePlanes.Add(bestPlane); }
            return id;
        }
        for (int j = 0; j < height; j++)
            for (int i = 0; i < width; i++)
            {
                var list = index[Index(i, j)];
                if (list == null) continue;
                double px = minX + (i + 0.5) * cell, py = minY + (j + 0.5) * cell;
                foreach (var span in grid[Index(i, j)])
                {
                    if (span.Door >= 0) continue; // door sight blockers rely on flat control sectors
                    span.FP = Find(px, py, span.F, true, list);
                    span.CP = Find(px, py, span.C, false, list);
                    if (span.FP >= 0) floorPlaneSpans++;
                    if (span.CP >= 0) ceilingPlaneSpans++;
                }
            }
    }

    // A diagonal wall or slope edge that cuts through grid cells leaves one- and two-cell sectors along it, each with
    // slightly different heights. Their boundaries zigzag and cannot be fitted to the real edge. Such a sliver takes the
    // layout of the neighbour it shares most boundary with, if its floors match and its ceilings are within a step, so the
    // merged boundary can follow the real edge. Only slivers crossed by a diagonal real edge are touched: a small
    // sector elsewhere (a post, a narrow stair) stays.
    static void AbsorbSlivers()
    {
        if (featureIndex == null) BuildFeatures();
        // A diagonal real edge through the cell at the heights where the two layouts differ.
        bool Diagonal(int i, int j, List<(double lo, double hi)> heights)
        {
            double px = minX + (i + 0.5) * cell, py = minY + (j + 0.5) * cell;
            if (!featureIndex.TryGetValue(((int)Math.Floor(px / FeatureBucket), (int)Math.Floor(py / FeatureBucket)), out var list)) return false;
            foreach (var f in list)
            {
                double dx = Math.Abs(f.X1 - f.X0), dy = Math.Abs(f.Y1 - f.Y0), l = Math.Sqrt(dx * dx + dy * dy);
                if (dx > 0.2 * l && dy > 0.2 * l && Overlaps(f, heights) && ClosestOn(f, px, py).d <= 0.75 * cell) return true;
            }
            return false;
        }
        var floors = new Dictionary<int, List<Tri>>();
        foreach (var t in tris)
        {
            if (t.N.Z < WallNormalZ || t.N.Z >= STEEPSLOPE) continue;
            int i0 = Math.Max(0, (int)Math.Floor((Math.Min(t.A.X, Math.Min(t.B.X, t.C.X)) - minX) / cell));
            int i1 = Math.Min(width - 1, (int)Math.Floor((Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)) - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y)) - minY) / cell));
            int j1 = Math.Min(height - 1, (int)Math.Floor((Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)) - minY) / cell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    (floors.TryGetValue(Index(i, j), out var l) ? l : floors[Index(i, j)] = new List<Tri>()).Add(t);
        }
        // The span's floor is a face too steep to walk, such as a wall's sloped foot.
        bool Steep(int c, Span s)
        {
            if (!floors.TryGetValue(c, out var list)) return false;
            double px = minX + (c % width + 0.5) * cell, py = minY + (c / width + 0.5) * cell;
            foreach (var t in list)
            {
                double d = (t.B.Y - t.C.Y) * (t.A.X - t.C.X) + (t.C.X - t.B.X) * (t.A.Y - t.C.Y);
                if (Math.Abs(d) < 1e-9) continue;
                double u = ((t.B.Y - t.C.Y) * (px - t.C.X) + (t.C.X - t.B.X) * (py - t.C.Y)) / d, v = ((t.C.Y - t.A.Y) * (px - t.C.X) + (t.A.X - t.C.X) * (py - t.C.Y)) / d;
                if (u >= -0.05 && v >= -0.05 && u + v <= 1.05 && Math.Abs(u * t.A.Z + v * t.B.Z + (1 - u - v) * t.C.Z - s.F) <= 4) return true;
            }
            return false;
        }
        // A sliver's gap may close if no crouching body fits, or if it is lower than a standing body and its floor is
        // too steep to walk, such as the space over a diagonal wall's sloped foot. Crawl spaces stay.
        bool Close(int c, List<Span> b)
        {
            var a = grid[c];
            if (a.Count != b.Count) a = a.Where(s => s.Door >= 0 || s.Water != NoWater || s.C - s.F >= PlayerScale.Height
                || (s.C - s.F >= PlayerScale.CrouchHeight && !Steep(c, s))).ToList();
            if (a.Count != b.Count) return false;
            for (int n = 0; n < a.Count; n++)
                if (a[n].Door != b[n].Door || a[n].Water != b[n].Water || Math.Abs(a[n].F - b[n].F) > SliverFloor || Math.Abs(a[n].C - b[n].C) > SliverStep) return false;
            return true;
        }
        for (int pass = 0; pass < 3; pass++)
        {
            var component = new int[width * height];
            Array.Fill(component, -1);
            var members = new List<List<int>>();
            var stack = new Stack<int>();
            for (int c = 0; c < component.Length; c++)
            {
                if (grid[c].Count == 0 || component[c] >= 0) continue;
                string signature = Signature(grid[c]);
                var cells = new List<int> { c };
                component[c] = members.Count;
                stack.Push(c);
                while (stack.Count > 0)
                {
                    int p = stack.Pop(), i = p % width, j = p / width;
                    foreach (var (ni, nj) in new[] { (i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1) })
                    {
                        if (ni < 0 || nj < 0 || ni >= width || nj >= height) continue;
                        int q = Index(ni, nj);
                        if (component[q] < 0 && grid[q].Count > 0 && Signature(grid[q]) == signature) { component[q] = members.Count; cells.Add(q); stack.Push(q); }
                    }
                }
                members.Add(cells);
            }
            int merged = 0;
            foreach (var cells in members)
            {
                if (cells.Count > SliverCells) continue;
                var shared = new Dictionary<int, int>();
                foreach (int c in cells)
                {
                    int i = c % width, j = c / width;
                    foreach (var (ni, nj) in new[] { (i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1) })
                    {
                        if (ni < 0 || nj < 0 || ni >= width || nj >= height) continue;
                        int q = Index(ni, nj);
                        if (component[q] >= 0 && component[q] != component[c] && Close(c, grid[q])
                            && cells.Any(s => Diagonal(s % width, s / width, DifferingHeights(grid[s], grid[q])))) shared[q] = shared.TryGetValue(q, out int n) ? n + 1 : 1;
                    }
                }
                if (shared.Count == 0) continue;
                // The neighbouring sector with the most shared cell edges; ties go to the larger sector, so slivers join rooms.
                var best = shared.GroupBy(p => component[p.Key]).OrderByDescending(g => g.Sum(p => p.Value)).ThenByDescending(g => members[g.Key].Count).First();
                var source = grid[best.First().Key];
                foreach (int c in cells)
                    grid[c] = source.Select(s => new Span { F = s.F, C = s.C, Door = s.Door, FP = s.FP, CP = s.CP, Water = s.Water }).ToList();
                merged++;
            }
            slivers += merged;
            if (merged == 0) break;
        }
    }

    // The same plane through the same middle point, with its normal raised to MinPlaneNormal.
    static SurfacePlane Flatten(SurfacePlane p, (double x, double y) center)
    {
        double g = Math.Sqrt(p.Gx * p.Gx + p.Gy * p.Gy), limit = Math.Sqrt(1 - MinPlaneNormal * MinPlaneNormal) / MinPlaneNormal;
        if (g <= limit) return p;
        double k = limit / g, z = p.At(center.x, center.y);
        return new SurfacePlane { Gx = p.Gx * k, Gy = p.Gy * k, H = z - k * (p.Gx * center.x + p.Gy * center.y) };
    }

    static string PlaneText(int plane, bool ceiling)
    {
        if (plane < 0) return "";
        var p = surfacePlanes[plane];
        double length = Math.Sqrt(p.Gx * p.Gx + p.Gy * p.Gy + 1), sign = ceiling ? 1 : -1;
        string name = ceiling ? "ceilingplane" : "floorplane";
        string F(double v) => v.ToString("R", CultureInfo.InvariantCulture);
        return $" {name}_a = {F(sign * p.Gx / length)}; {name}_b = {F(sign * p.Gy / length)}; {name}_c = {F(-sign / length)}; {name}_d = {F(sign * p.H / length)};";
    }

    static void BuildFeatures()
    {
        var walls = new HashSet<(long, long, long, long, long, long)>();
        long R(double v) => (long)Math.Round(v * 8);
        var edges = new Dictionary<(long, long, long, long, long, long), (V3 a, V3 b, HashSet<(long, long, long)> planes)>();
        foreach (var t in tris)
        {
            var p = new[] { t.A, t.B, t.C };
            if (Math.Abs(t.N.Z) < WallNormalZ)
            {
                V3 a = p[0], b = p[1];
                double longest = -1;
                for (int e = 0; e < 3; e++)
                {
                    V3 q = p[e], r = p[(e + 1) % 3];
                    double d = (q.X - r.X) * (q.X - r.X) + (q.Y - r.Y) * (q.Y - r.Y);
                    if (d > longest) { longest = d; a = q; b = r; }
                }
                if (longest < 1) continue;
                if (R(a.X) > R(b.X) || (R(a.X) == R(b.X) && R(a.Y) > R(b.Y))) (a, b) = (b, a);
                double lo = p.Min(v => v.Z), hi = p.Max(v => v.Z);
                if (walls.Add((R(a.X), R(a.Y), R(b.X), R(b.Y), R(lo), R(hi))))
                    features.Add(new Feature { X0 = a.X, Y0 = a.Y, X1 = b.X, Y1 = b.Y, Lo = lo, Hi = hi, Wall = true });
                continue;
            }
            if (!PlaneOf(t, out var plane, out double normal) || normal >= FlatNormal) continue;
            var planeKey = ((long)Math.Round(plane.Gx * 2000), (long)Math.Round(plane.Gy * 2000), (long)Math.Round(plane.H * 2));
            for (int e = 0; e < 3; e++)
            {
                V3 a = p[e], b = p[(e + 1) % 3];
                if ((R(a.X), R(a.Y), R(a.Z)).CompareTo((R(b.X), R(b.Y), R(b.Z))) > 0) (a, b) = (b, a);
                var key = (R(a.X), R(a.Y), R(a.Z), R(b.X), R(b.Y), R(b.Z));
                if (!edges.TryGetValue(key, out var entry)) edges[key] = entry = (a, b, new HashSet<(long, long, long)>());
                entry.planes.Add(planeKey);
            }
        }
        // An edge inside one flat polygon of a slope is only triangulation. A real crease joins two planes or ends the face.
        var uses = new Dictionary<(long, long, long, long, long, long), int>();
        foreach (var t in tris)
        {
            if (Math.Abs(t.N.Z) < WallNormalZ) continue;
            var p = new[] { t.A, t.B, t.C };
            for (int e = 0; e < 3; e++)
            {
                V3 a = p[e], b = p[(e + 1) % 3];
                if ((R(a.X), R(a.Y), R(a.Z)).CompareTo((R(b.X), R(b.Y), R(b.Z))) > 0) (a, b) = (b, a);
                var key = (R(a.X), R(a.Y), R(a.Z), R(b.X), R(b.Y), R(b.Z));
                uses[key] = uses.TryGetValue(key, out int c) ? c + 1 : 1;
            }
        }
        foreach (var pair in edges)
        {
            if (pair.Value.planes.Count < 2 && uses[pair.Key] > 1) continue;
            V3 a = pair.Value.a, b = pair.Value.b;
            if ((a.X - b.X) * (a.X - b.X) + (a.Y - b.Y) * (a.Y - b.Y) < 1) continue;
            features.Add(new Feature { X0 = a.X, Y0 = a.Y, X1 = b.X, Y1 = b.Y, Lo = Math.Min(a.Z, b.Z), Hi = Math.Max(a.Z, b.Z) });
        }
        featureIndex = new Dictionary<(int, int), List<Feature>>();
        foreach (var f in features)
        {
            int i0 = (int)Math.Floor((Math.Min(f.X0, f.X1) - cell) / FeatureBucket), i1 = (int)Math.Floor((Math.Max(f.X0, f.X1) + cell) / FeatureBucket);
            int j0 = (int)Math.Floor((Math.Min(f.Y0, f.Y1) - cell) / FeatureBucket), j1 = (int)Math.Floor((Math.Max(f.Y0, f.Y1) + cell) / FeatureBucket);
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    if (!featureIndex.TryGetValue((i, j), out var list)) featureIndex[(i, j)] = list = new List<Feature>();
                    list.Add(f);
                }
        }
    }

    static (double x, double y, double d) ClosestOn(Feature f, double x, double y)
    {
        double dx = f.X1 - f.X0, dy = f.Y1 - f.Y0, r = Math.Clamp(((x - f.X0) * dx + (y - f.Y0) * dy) / (dx * dx + dy * dy), 0, 1);
        double px = f.X0 + r * dx, py = f.Y0 + r * dy;
        return (px, py, Math.Sqrt((px - x) * (px - x) + (py - y) * (py - y)));
    }

    static bool Overlaps(Feature f, List<(double lo, double hi)> heights) => heights.Any(h => f.Lo - 6 < h.hi && f.Hi + 6 > h.lo);

    // Covers each chain with stretches that each follow one real edge, longest first from each point.
    static Dictionary<(int, int), HashSet<Feature>> FindSupport(List<BoundaryChain> chains)
    {
        var support = new Dictionary<(int, int), HashSet<Feature>>();
        double reach = SnapRadius * cell;
        foreach (var c in chains)
        {
            var p = c.Points;
            for (int i = 0; i + 1 < p.Count;)
            {
                Feature best = null;
                int bestEnd = i;
                double bestError = double.MaxValue;
                if (featureIndex.TryGetValue(((int)Math.Floor((double)p[i].x / FeatureBucket), (int)Math.Floor((double)p[i].y / FeatureBucket)), out var list))
                    foreach (var f in list)
                    {
                        if (!Overlaps(f, c.Heights) || ClosestOn(f, p[i].x, p[i].y).d > reach) continue;
                        int e = i;
                        double total = ClosestOn(f, p[i].x, p[i].y).d;
                        while (e + 1 < p.Count)
                        {
                            double d = ClosestOn(f, p[e + 1].x, p[e + 1].y).d;
                            if (d > reach) break;
                            total += d;
                            e++;
                        }
                        if (e == i) continue;
                        // A short run beside a corner is also near the crossing wall, so the direction must agree.
                        double cx = p[e].x - p[i].x, cy = p[e].y - p[i].y, fx = f.X1 - f.X0, fy = f.Y1 - f.Y0;
                        double chord = Math.Sqrt(cx * cx + cy * cy), along = Math.Sqrt(fx * fx + fy * fy);
                        if (chord < 1e-6 || Math.Abs(cx * fx + cy * fy) / (chord * along) < MinAlignment) continue;
                        double error = total / (e - i + 1);
                        if (e > bestEnd || (e == bestEnd && error < bestError)) { best = f; bestEnd = e; bestError = error; }
                    }
                if (best == null) { i++; continue; }
                for (int n = i; n <= bestEnd; n++)
                {
                    if (!support.TryGetValue(p[n], out var set)) support[p[n]] = set = new HashSet<Feature>();
                    set.Add(best);
                }
                i = bestEnd;
            }
        }
        return support;
    }

    // Places a vertex on its supporting lines: their intersection at a corner, or the nearest point along a straight wall.
    static bool SolveVertex((int x, int y) v, HashSet<Feature> lines, out double sx, out double sy)
    {
        sx = v.x; sy = v.y;
        double a = 0, b = 0, d = 0, e = 0, g = 0, mx = 0, my = 0;
        foreach (var f in lines)
        {
            double dx = f.X1 - f.X0, dy = f.Y1 - f.Y0, l = Math.Sqrt(dx * dx + dy * dy), nx = -dy / l, ny = dx / l, c = nx * f.X0 + ny * f.Y0;
            a += nx * nx; b += nx * ny; d += ny * ny; e += nx * c; g += ny * c;
            double off = c - nx * v.x - ny * v.y;
            mx += off * nx; my += off * ny;
        }
        double det = a * d - b * b, limit = MaxMove * cell;
        if (det > 0.03 * lines.Count * lines.Count) { sx = (e * d - g * b) / det; sy = (a * g - b * e) / det; }
        else { sx = v.x + mx / lines.Count; sy = v.y + my / lines.Count; }
        if (Math.Sqrt((sx - v.x) * (sx - v.x) + (sy - v.y) * (sy - v.y)) > limit)
        {
            // Nearly parallel lines can intersect far away. Use the closest single line instead.
            double best = limit;
            bool found = false;
            foreach (var f in lines)
            {
                double dx = f.X1 - f.X0, dy = f.Y1 - f.Y0, r = ((v.x - f.X0) * dx + (v.y - f.Y0) * dy) / (dx * dx + dy * dy);
                double px = f.X0 + r * dx, py = f.Y0 + r * dy, m = Math.Sqrt((px - v.x) * (px - v.x) + (py - v.y) * (py - v.y));
                if (m <= best) { best = m; sx = px; sy = py; found = true; }
            }
            if (!found) { sx = v.x; sy = v.y; return false; }
        }
        sx = Math.Round(sx * 8) / 8; sy = Math.Round(sy * 8) / 8;
        return true;
    }

    // Height ranges where one side of a boundary is open and the other is not.
    static List<(double lo, double hi)> DifferingHeights(List<Span> a, List<Span> b)
    {
        var cuts = new SortedSet<int>();
        foreach (var s in (a ?? new List<Span>()).Concat(b ?? new List<Span>())) { cuts.Add(s.F); cuts.Add(s.C); }
        var result = new List<(double, double)>();
        var points = cuts.ToList();
        for (int n = 0; n + 1 < points.Count; n++)
        {
            double m = (points[n] + points[n + 1]) / 2.0;
            bool inA = a != null && a.Any(s => s.F < m && s.C > m), inB = b != null && b.Any(s => s.F < m && s.C > m);
            if (inA != inB) result.Add((points[n], points[n + 1]));
        }
        // Boundaries between different slopes can have no open/solid difference at the sampled heights.
        if (result.Count == 0 && points.Count > 0) result.Add((points[0], points[^1]));
        return result;
    }

    static double PointSegment(double px, double py, double ax, double ay, double bx, double by)
    {
        double dx = bx - ax, dy = by - ay, l = dx * dx + dy * dy;
        double r = l < 1e-12 ? 0 : Math.Clamp(((px - ax) * dx + (py - ay) * dy) / l, 0, 1);
        double qx = ax + r * dx - px, qy = ay + r * dy - py;
        return Math.Sqrt(qx * qx + qy * qy);
    }

    static List<BoundaryChain> BuildChains(List<(int x0, int y0, int x1, int y1, int front, int back)> runs, List<List<Span>> sectorSpans)
    {
        var at = new Dictionary<(int, int), List<int>>();
        void Add((int, int) v, int r) { if (!at.TryGetValue(v, out var l)) at[v] = l = new List<int>(2); l.Add(r); }
        for (int r = 0; r < runs.Count; r++) { Add((runs[r].x0, runs[r].y0), r); Add((runs[r].x1, runs[r].y1), r); }
        (int f, int b) Leaving(int r, (int x, int y) v) => (runs[r].x0, runs[r].y0) == v ? (runs[r].front, runs[r].back) : (runs[r].back, runs[r].front);
        bool Junction((int x, int y) v)
        {
            var l = at[v];
            if (l.Count != 2) return true;
            var p = Leaving(l[0], v); var q = Leaving(l[1], v);
            return p.f != q.b || p.b != q.f;
        }
        (int, int) Other(int r, (int x, int y) v) => (runs[r].x0, runs[r].y0) == v ? (runs[r].x1, runs[r].y1) : (runs[r].x0, runs[r].y0);
        var visited = new bool[runs.Count];
        var chains = new List<BoundaryChain>();
        void Walk((int x, int y) start, int first)
        {
            var side = Leaving(first, start);
            var chain = new BoundaryChain { Front = side.f, Back = side.b };
            chain.Points.Add(start);
            var current = start;
            int r = first;
            while (true)
            {
                visited[r] = true;
                current = Other(r, current);
                chain.Points.Add(current);
                if (current == start || Junction(current)) break;
                var l = at[current];
                r = l[0] == r ? l[1] : l[0];
            }
            var a = chain.Front >= 0 ? sectorSpans[chain.Front] : null;
            var b = chain.Back >= 0 ? sectorSpans[chain.Back] : null;
            // Door boundaries are fitted too. Left on the grid, a door lintel sits up to a cell out from its frame and blocks the stairs beside it.
            chain.Heights = DifferingHeights(a, b);
            chains.Add(chain);
        }
        foreach (var v in at.Keys.Where(Junction).ToList())
            foreach (int r in at[v])
                if (!visited[r]) Walk(v, r);
        for (int r = 0; r < runs.Count; r++)
            if (!visited[r]) Walk((runs[r].x0, runs[r].y0), r);
        return chains;
    }

    static void Simplify(List<(int id, double x, double y, double tolerance)> p, int a, int b, bool[] keep)
    {
        if (b <= a + 1) return;
        int worst = -1;
        double worstExcess = 0;
        for (int n = a + 1; n < b; n++)
        {
            double excess = PointSegment(p[n].x, p[n].y, p[a].x, p[a].y, p[b].x, p[b].y) - p[n].tolerance;
            if (excess > worstExcess) { worstExcess = excess; worst = n; }
        }
        if (worst < 0) return;
        keep[worst] = true;
        Simplify(p, a, worst, keep);
        Simplify(p, worst, b, keep);
    }

    static double Cross(double ax, double ay, double bx, double by, double cx, double cy) => (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);

    static bool SegmentsConflict((int a, int b, double ax, double ay, double bx, double by) s, (int a, int b, double ax, double ay, double bx, double by) t)
    {
        const double E = 1e-7;
        bool sharedA = s.a == t.a || s.a == t.b, sharedB = s.b == t.a || s.b == t.b;
        if (sharedA && sharedB) return true;
        if (sharedA || sharedB)
        {
            // Two segments from one vertex conflict only if they fold back along each other.
            double ox = sharedA ? s.ax : s.bx, oy = sharedA ? s.ay : s.by;
            double px = sharedA ? s.bx : s.ax, py = sharedA ? s.by : s.ay;
            int shared = sharedA ? s.a : s.b;
            double qx = t.a == shared ? t.bx : t.ax, qy = t.a == shared ? t.by : t.ay;
            return Math.Abs(Cross(ox, oy, px, py, qx, qy)) < 1e-4 && (px - ox) * (qx - ox) + (py - oy) * (qy - oy) > 0;
        }
        if (Math.Max(s.ax, s.bx) < Math.Min(t.ax, t.bx) - E || Math.Max(t.ax, t.bx) < Math.Min(s.ax, s.bx) - E
            || Math.Max(s.ay, s.by) < Math.Min(t.ay, t.by) - E || Math.Max(t.ay, t.by) < Math.Min(s.ay, s.by) - E) return false;
        double d1 = Cross(s.ax, s.ay, s.bx, s.by, t.ax, t.ay), d2 = Cross(s.ax, s.ay, s.bx, s.by, t.bx, t.by);
        double d3 = Cross(t.ax, t.ay, t.bx, t.by, s.ax, s.ay), d4 = Cross(t.ax, t.ay, t.bx, t.by, s.bx, s.by);
        return (d1 <= E && d2 >= -E || d1 >= -E && d2 <= E) && (d3 <= E && d4 >= -E || d3 >= -E && d4 <= E);
    }

    // Returns the boundary polylines. A chain that would cross, pinch, or invert a sector goes back to its grid path.
    static List<BoundaryChain> RefitBoundaries(List<(int x0, int y0, int x1, int y1, int front, int back)> runs, List<List<Span>> sectorSpans, int[] cellCounts)
    {
        if (featureIndex == null) BuildFeatures();
        var chains = BuildChains(runs, sectorSpans);
        chainCount = chains.Count;
        chainsFrozen = chains.Count(c => c.Frozen);
        var ids = new Dictionary<(int, int), int>();
        var heights = new Dictionary<(int, int), List<(double lo, double hi)>>();
        // pinned: not snapped to a real edge, so placed on the smoothed staircase. gridded: placed on the grid corner itself.
        var pinned = new HashSet<(int, int)>();
        var gridded = new HashSet<(int, int)>();
        foreach (var c in chains)
            foreach (var v in c.Points)
            {
                if (!ids.ContainsKey(v)) ids[v] = ids.Count;
                if (!heights.TryGetValue(v, out var list)) heights[v] = list = new List<(double, double)>();
                list.AddRange(c.Heights);
                if (c.Frozen) { pinned.Add(v); gridded.Add(v); }
            }
        var smooth = SmoothStairs(chains);
        var keyOf = ids.ToDictionary(p => p.Value, p => p.Key);
        var strikes = new Dictionary<BoundaryChain, int>();
        var snapped = new Dictionary<(int, int), (bool ok, double x, double y)>();
        var support = FindSupport(chains);
        foreach (var v in ids.Keys)
        {
            double sx = v.Item1, sy = v.Item2;
            bool ok = support.TryGetValue(v, out var lines) && SolveVertex(v, lines, out sx, out sy);
            snapped[v] = (ok, ok ? sx : v.Item1, ok ? sy : v.Item2);
        }
        for (refitPasses = 1; refitPasses <= 60; refitPasses++)
        {
            var bad = new HashSet<BoundaryChain>();
            var newPins = new HashSet<(int, int)>();
            var newGrid = new HashSet<(int, int)>();
            // A conflict first moves only the vertices involved: off the real edge onto the smoothed staircase, then onto
            // the grid. A chain that keeps conflicting is smoothed whole, then returned to the grid whole.
            void Strike(BoundaryChain chain, int id)
            {
                var key = keyOf[id];
                if (!pinned.Contains(key)) newPins.Add(key);
                else if (!gridded.Contains(key)) newGrid.Add(key);
                strikes[chain] = strikes.TryGetValue(chain, out int n) ? n + 1 : 1;
                if (strikes[chain] > MaxStrikes) bad.Add(chain);
            }
            foreach (var c in chains) FitChain(c, ids, snapped, smooth, pinned, gridded, bad);
            var segments = new List<(int a, int b, double ax, double ay, double bx, double by, BoundaryChain chain)>();
            var owner = new Dictionary<(long, long), (int id, BoundaryChain chain)>();
            foreach (var c in chains)
            {
                foreach (var p in c.Fitted)
                {
                    var key = ((long)Math.Round(p.x * 8), (long)Math.Round(p.y * 8));
                    if (owner.TryGetValue(key, out var seen) && seen.id != p.id) { Strike(c, p.id); Strike(seen.chain, seen.id); }
                    else owner[key] = (p.id, c);
                }
                for (int n = 0; n + 1 < c.Fitted.Count; n++)
                    segments.Add((c.Fitted[n].id, c.Fitted[n + 1].id, c.Fitted[n].x, c.Fitted[n].y, c.Fitted[n + 1].x, c.Fitted[n + 1].y, c));
            }
            var buckets = new Dictionary<(int, int), List<int>>();
            for (int n = 0; n < segments.Count; n++)
            {
                var s = segments[n];
                int i0 = (int)Math.Floor(Math.Min(s.ax, s.bx) / 32), i1 = (int)Math.Floor(Math.Max(s.ax, s.bx) / 32);
                int j0 = (int)Math.Floor(Math.Min(s.ay, s.by) / 32), j1 = (int)Math.Floor(Math.Max(s.ay, s.by) / 32);
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        if (!buckets.TryGetValue((i, j), out var l)) buckets[(i, j)] = l = new List<int>();
                        foreach (int m in l)
                        {
                            var t = segments[m];
                            if (SegmentsConflict((s.a, s.b, s.ax, s.ay, s.bx, s.by), (t.a, t.b, t.ax, t.ay, t.bx, t.by))) { Strike(s.chain, s.a); Strike(s.chain, s.b); Strike(t.chain, t.a); Strike(t.chain, t.b); }
                        }
                        l.Add(n);
                    }
            }
            // A sector must keep a positive area close to what the grid gave it.
            var area = new double[sectorSpans.Count];
            foreach (var c in chains)
                for (int n = 0; n + 1 < c.Fitted.Count; n++)
                {
                    double twice = c.Fitted[n + 1].x * c.Fitted[n].y - c.Fitted[n].x * c.Fitted[n + 1].y;
                    if (c.Front >= 0) area[c.Front] += twice / 2;
                    if (c.Back >= 0) area[c.Back] -= twice / 2;
                }
            var badSectors = new HashSet<int>();
            for (int s = 0; s < area.Length; s++)
                if (area[s] < 0.25 * cellCounts[s] * cell * cell) badSectors.Add(s);
            if (badSectors.Count > 0)
                foreach (var c in chains)
                    if (!c.Gridded && (badSectors.Contains(c.Front) || badSectors.Contains(c.Back))) bad.Add(c);
            bad.RemoveWhere(c => c.Gridded && c.Points.All(gridded.Contains));
            if (bad.Count == 0 && newPins.Count == 0 && newGrid.Count == 0) break;
            pinned.UnionWith(newPins);
            gridded.UnionWith(newGrid);
            foreach (var c in bad)
            {
                if (c.Reverted) { c.Gridded = true; gridded.UnionWith(c.Points); }
                c.Reverted = true;
                pinned.UnionWith(c.Points);
                strikes[c] = 0;
            }
            if (refitPasses == 60)
            {
                foreach (var c in chains) { c.Reverted = c.Gridded = true; pinned.UnionWith(c.Points); gridded.UnionWith(c.Points); }
                var none = new HashSet<BoundaryChain>();
                foreach (var c in chains) FitChain(c, ids, snapped, smooth, pinned, gridded, none);
                Console.WriteLine("angled collision: did not settle, using the grid boundary everywhere");
            }
        }
        var dbg = debugChains?.Split(',').Select(double.Parse).ToArray();
        if (dbg != null)
            foreach (var c in chains.Where(c => c.Points.Any(p => p.x >= dbg[0] && p.x <= dbg[2] && p.y >= dbg[1] && p.y <= dbg[3])))
            {
                Console.WriteLine($"CHAIN f{c.Front} b{c.Back} rev{c.Reverted} grid{c.Gridded} h[{string.Join(" ", c.Heights.Select(h => $"{h.lo}-{h.hi}"))}]");
                foreach (var p in c.Points)
                {
                    var s = snapped[p];
                    string lines = support.TryGetValue(p, out var l) ? string.Join(";", l.Select(f => $"{(f.Wall ? "W" : "S")}({f.X0:F0},{f.Y0:F0})-({f.X1:F0},{f.Y1:F0})z{f.Lo:F0}-{f.Hi:F0}")) : "";
                    Console.WriteLine($"  P {p.x},{p.y} ok{s.ok} -> {s.x},{s.y} pin{pinned.Contains(p)} grid{gridded.Contains(p)} {lines}");
                }
                Console.WriteLine("  FIT " + string.Join(" ", c.Fitted.Select(f => $"{f.x},{f.y}")));
            }
        // Staircase corners left in the output: a turn between two short axis-aligned segments.
        stairCorners = 0;
        var stairExamples = new List<string>();
        foreach (var c in chains)
        {
            var f = c.Fitted;
            int here = 0;
            for (int n = 1; n + 1 < f.Count; n++)
            {
                bool ax = f[n - 1].x == f[n].x, ay = f[n - 1].y == f[n].y, bx = f[n + 1].x == f[n].x, by = f[n + 1].y == f[n].y;
                double la = Math.Abs(f[n - 1].x - f[n].x) + Math.Abs(f[n - 1].y - f[n].y), lb = Math.Abs(f[n + 1].x - f[n].x) + Math.Abs(f[n + 1].y - f[n].y);
                if ((ax || ay) && (bx || by) && ax != bx && la <= 2 * cell && lb <= 2 * cell) here++;
            }
            stairCorners += here;
            if (here >= 3 && stairExamples.Count < 25)
                stairExamples.Add($"{here} at {c.Points[0].x},{c.Points[0].y} heights {string.Join(" ", c.Heights.Select(h => $"{h.lo}-{h.hi}"))} {(c.Gridded ? "grid" : c.Reverted ? "smoothed" : "fitted")}");
        }
        if (dbg != null) foreach (var s in stairExamples) Console.WriteLine("STAIRS " + s);
        chainsReverted = chains.Count(c => c.Gridded && !c.Frozen);
        chainsSmoothed = chains.Count(c => c.Reverted && !c.Gridded);
        chainsFitted = chains.Count(c => !c.Reverted && !c.Frozen);
        return chains;
    }

    // Where each interior staircase corner would sit on a straight diagonal: (previous + 2 * corner + next) / 4. Applied only
    // where both neighbouring steps are short, so real room corners stay put. Junctions and chain ends never move.
    static Dictionary<(int, int), (double x, double y)> SmoothStairs(List<BoundaryChain> chains)
    {
        var smooth = new Dictionary<(int, int), (double x, double y)>();
        foreach (var c in chains)
        {
            var p = c.Points;
            for (int n = 1; n + 1 < p.Count; n++)
            {
                var (a, v, b) = (p[n - 1], p[n], p[n + 1]);
                int la = Math.Abs(a.x - v.x) + Math.Abs(a.y - v.y), lb = Math.Abs(b.x - v.x) + Math.Abs(b.y - v.y);
                bool turn = (a.x == v.x) != (b.x == v.x);
                if (!turn || la > StairStep * cell || lb > StairStep * cell) continue;
                smooth[v] = (Math.Round((a.x + 2 * v.x + b.x) / 4.0 * 8) / 8, Math.Round((a.y + 2 * v.y + b.y) / 4.0 * 8) / 8);
            }
        }
        return smooth;
    }

    static void FitChain(BoundaryChain c, Dictionary<(int, int), int> ids, Dictionary<(int, int), (bool ok, double x, double y)> snapped,
        Dictionary<(int, int), (double x, double y)> smooth, HashSet<(int, int)> pinned, HashSet<(int, int)> gridded, HashSet<BoundaryChain> bad)
    {
        if (c.Frozen || c.Gridded)
        {
            c.Fitted = c.Points.Select(v => (ids[v], (double)v.x, (double)v.y)).ToList();
            return;
        }
        var points = c.Points.Select(v =>
        {
            var s = snapped[v];
            if (gridded.Contains(v)) return (id: ids[v], x: (double)v.x, y: (double)v.y, tolerance: PinnedTolerance);
            if (pinned.Contains(v))
            {
                var m = !plainAngled && smooth.TryGetValue(v, out var q) ? q : (v.x, v.y);
                return (id: ids[v], x: m.Item1, y: m.Item2, tolerance: PinnedTolerance);
            }
            return s.ok ? (id: ids[v], x: s.x, y: s.y, tolerance: SnappedTolerance) : (id: ids[v], x: (double)v.x, y: (double)v.y, tolerance: UnsnappedTolerance * cell);
        }).ToList();
        var keep = new bool[points.Count];
        keep[0] = keep[^1] = true;
        bool closed = c.Points[0] == c.Points[^1];
        if (closed && points.Count > 3)
        {
            int far = 1;
            double farthest = -1;
            for (int n = 1; n < points.Count - 1; n++)
            {
                double d = Math.Abs(points[n].x - points[0].x) + Math.Abs(points[n].y - points[0].y);
                if (d > farthest) { farthest = d; far = n; }
            }
            keep[far] = true;
            Simplify(points, 0, far, keep);
            Simplify(points, far, points.Count - 1, keep);
        }
        else Simplify(points, 0, points.Count - 1, keep);
        var fitted = new List<(int id, double x, double y)>();
        for (int n = 0; n < points.Count; n++)
        {
            if (!keep[n]) continue;
            // Interior points that landed on the previous point add nothing.
            if (n != points.Count - 1 && fitted.Count > 0 && fitted[^1].x == points[n].x && fitted[^1].y == points[n].y) continue;
            if (n == points.Count - 1 && fitted.Count > 1 && fitted[^1].x == points[n].x && fitted[^1].y == points[n].y) fitted.RemoveAt(fitted.Count - 1);
            fitted.Add((points[n].id, points[n].x, points[n].y));
        }
        c.Fitted = fitted;
        bool degenerate = fitted.Count < 2 || (fitted.Count == 2 && fitted[0].x == fitted[1].x && fitted[0].y == fitted[1].y) || (closed && fitted.Count < 4);
        bool strayed = c.Points.Any(v => Enumerable.Range(0, fitted.Count - 1).Min(n =>
            PointSegment(v.x, v.y, fitted[n].x, fitted[n].y, fitted[n + 1].x, fitted[n + 1].y)) > MaxDeviation * cell);
        if (degenerate || strayed)
        {
            bad.Add(c);
            c.Fitted = c.Points.Select(v => (ids[v], (double)v.x, (double)v.y)).ToList();
        }
    }

    // How closely the emitted boundaries follow the real walls, in map units, in both directions.
    static void MeasureFit(List<(double x0, double y0, double x1, double y1, List<(double lo, double hi)> heights)> lines)
    {
        if (featureIndex == null) BuildFeatures();
        var toWall = new List<double>();
        foreach (var l in lines)
        {
            double length = Math.Sqrt((l.x1 - l.x0) * (l.x1 - l.x0) + (l.y1 - l.y0) * (l.y1 - l.y0));
            int samples = Math.Max(1, (int)(length / 4));
            for (int k = 0; k < samples; k++)
            {
                double r = (k + 0.5) / samples, x = l.x0 + r * (l.x1 - l.x0), y = l.y0 + r * (l.y1 - l.y0), best = 24;
                if (featureIndex.TryGetValue(((int)Math.Floor(x / FeatureBucket), (int)Math.Floor(y / FeatureBucket)), out var list))
                    foreach (var f in list)
                        if (f.Wall && l.heights.Any(h => f.Lo - 6 < h.hi && f.Hi + 6 > h.lo)) best = Math.Min(best, ClosestOn(f, x, y).d);
                toWall.Add(best);
            }
        }
        var lineIndex = new Dictionary<(int, int), List<int>>();
        for (int n = 0; n < lines.Count; n++)
        {
            var l = lines[n];
            int i0 = (int)Math.Floor((Math.Min(l.x0, l.x1) - 24) / 32), i1 = (int)Math.Floor((Math.Max(l.x0, l.x1) + 24) / 32);
            int j0 = (int)Math.Floor((Math.Min(l.y0, l.y1) - 24) / 32), j1 = (int)Math.Floor((Math.Max(l.y0, l.y1) + 24) / 32);
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    if (!lineIndex.TryGetValue((i, j), out var c)) lineIndex[(i, j)] = c = new List<int>();
                    c.Add(n);
                }
        }
        var toLine = new List<double>();
        foreach (var f in features.Where(f => f.Wall && f.Hi - f.Lo >= 16))
        {
            double length = Math.Sqrt((f.X1 - f.X0) * (f.X1 - f.X0) + (f.Y1 - f.Y0) * (f.Y1 - f.Y0));
            int samples = Math.Max(1, (int)(length / 4));
            for (int k = 0; k < samples; k++)
            {
                double r = (k + 0.5) / samples, x = f.X0 + r * (f.X1 - f.X0), y = f.Y0 + r * (f.Y1 - f.Y0), best = 24;
                if (lineIndex.TryGetValue(((int)Math.Floor(x / 32), (int)Math.Floor(y / 32)), out var list))
                    foreach (int n in list)
                    {
                        var l = lines[n];
                        if (l.heights.Any(h => f.Lo - 6 < h.hi && f.Hi + 6 > h.lo))
                            best = Math.Min(best, PointSegment(x, y, l.x0, l.y0, l.x1, l.y1));
                    }
                toLine.Add(best);
            }
        }
        string Row(List<double> v)
        {
            v.Sort();
            return FormattableString.Invariant($"samples {v.Count}, mean {v.Average():F2}, median {v[v.Count / 2]:F2}, p95 {v[(int)(v.Count * 0.95)]:F2}, within 1 unit {100.0 * v.Count(d => d <= 1) / v.Count:F1}%, within 3 units {100.0 * v.Count(d => d <= 3) / v.Count:F1}%");
        }
        int angled = lines.Count(l => Math.Abs(l.x0 - l.x1) > 0.01 && Math.Abs(l.y0 - l.y1) > 0.01);
        var text = new StringBuilder();
        text.AppendLine($"boundary lines: {lines.Count}, not axis-aligned: {angled}");
        text.AppendLine("boundary to nearest real wall: " + Row(toWall));
        text.AppendLine("real wall to nearest boundary: " + Row(toLine));
        text.AppendLine($"sloped spans: floors {floorPlaneSpans}, ceilings {ceilingPlaneSpans}; planes {surfacePlanes.Count}");
        text.AppendLine($"diagonal slivers merged into a neighbour: {slivers}");
        text.AppendLine("floor spans too steep for a plane, by normal z tenths: " + string.Join(" ", steepFloorSpans.Select((n, k) => $"0.{k}:{n}")));
        text.AppendLine($"chains: {chainCount}, fitted {chainsFitted}, smoothed staircase {chainsSmoothed}, returned to grid {chainsReverted}, door chains left on grid {chainsFrozen}, passes {refitPasses}, staircase corners left {stairCorners}");
        fitReport = text.ToString();
    }
}
