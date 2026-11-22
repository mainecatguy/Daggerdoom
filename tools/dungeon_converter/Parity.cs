// Two-way movement parity and bullet check. Daggerfall's side repeats DungeonCaptureTest's flood on the raw faces.
// First run with --parity <dir> writes the DFPARITY lump. After UZDoom writes doom_flood.txt there, a second run compares.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

static partial class Program
{
    const int ParitySeed = 20261122, ParitySeeds = 24, ParityShots = 200, ParityCell = 16;
    const double FloodClearance = 20, FloodKnee = 30, FloodBodyFit = 0.9, ProbeRange = 4096, SurfaceTolerance = 4;
    // A Doom actor stands on the highest floor under its box, up to about 30 units above the center of a 45-degree stair.
    // Stacked walkable levels are at least a crouched body (36) apart, so this cannot match the wrong level.
    const double MatchZ = 34;
    static string parityDir;
    static readonly List<Tri> doorMeshTris = new List<Tri>();
    static List<Tri> pTris;
    static Dictionary<(int, int), List<int>> pIndex;
    const int Bucket = 32;

    static void IndexTris(List<Tri> list)
    {
        pTris = list;
        pIndex = new Dictionary<(int, int), List<int>>();
        for (int n = 0; n < list.Count; n++)
        {
            var t = list[n];
            int i0 = (int)Math.Floor(Math.Min(t.A.X, Math.Min(t.B.X, t.C.X)) / Bucket), i1 = (int)Math.Floor(Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)) / Bucket);
            int j0 = (int)Math.Floor(Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y)) / Bucket), j1 = (int)Math.Floor(Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)) / Bucket);
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    if (!pIndex.TryGetValue((i, j), out var l)) pIndex[(i, j)] = l = new List<int>();
                    l.Add(n);
                }
        }
    }

    static V3 Sub(V3 a, V3 b) => new V3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
    static double Dot(V3 a, V3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;
    static V3 Cross(V3 a, V3 b) => new V3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);
    static V3 Along(V3 p, V3 d, double r) => new V3(p.X + d.X * r, p.Y + d.Y * r, p.Z + d.Z * r);

    // Front-face ray test, matching Unity's raycasts against mesh colliders. Returns the distance or -1.
    static double RayTri(V3 p, V3 d, in Tri t, double max)
    {
        if (Dot(d, t.N) >= 0) return -1;
        V3 e1 = Sub(t.B, t.A), e2 = Sub(t.C, t.A), h = Cross(d, e2);
        double det = Dot(e1, h);
        if (Math.Abs(det) < 1e-9) return -1;
        V3 s = Sub(p, t.A);
        double u = Dot(s, h) / det;
        if (u < -1e-6 || u > 1 + 1e-6) return -1;
        V3 q = Cross(s, e1);
        double v = Dot(d, q) / det;
        if (v < -1e-6 || u + v > 1 + 1e-6) return -1;
        double r = Dot(e2, q) / det;
        return r >= 0 && r <= max ? r : -1;
    }

    // Walks the buckets under a ray and returns the nearest front-face hit.
    static double Cast(V3 p, V3 d, double max)
    {
        double best = -1;
        var seen = new HashSet<int>();
        double length = Math.Sqrt(d.X * d.X + d.Y * d.Y);
        int steps = length < 1e-9 ? 0 : (int)Math.Ceiling(max * length / (Bucket / 2.0));
        for (int k = 0; k <= steps; k++)
        {
            double r = steps == 0 ? 0 : max * k / steps;
            if (best >= 0 && r > best + Bucket) break;
            int ci = (int)Math.Floor((p.X + d.X * r) / Bucket), cj = (int)Math.Floor((p.Y + d.Y * r) / Bucket);
            for (int j = cj - 1; j <= cj + 1; j++)
                for (int i = ci - 1; i <= ci + 1; i++)
                {
                    if (!pIndex.TryGetValue((i, j), out var list)) continue;
                    foreach (int n in list)
                    {
                        if (!seen.Add(n)) continue;
                        var t = pTris[n];
                        double hit = RayTri(p, d, t, max);
                        if (hit >= 0 && (best < 0 || hit < best)) best = hit;
                    }
                }
        }
        return best;
    }

    static double SegPointSq(V3 a, V3 b, V3 p)
    {
        V3 ab = Sub(b, a);
        double l = Dot(ab, ab), f = l < 1e-12 ? 0 : Math.Clamp(Dot(Sub(p, a), ab) / l, 0, 1);
        V3 c = Sub(Along(a, ab, f), p);
        return Dot(c, c);
    }

    static double SegSegSq(V3 p1, V3 q1, V3 p2, V3 q2)
    {
        V3 d1 = Sub(q1, p1), d2 = Sub(q2, p2), r = Sub(p1, p2);
        double a = Dot(d1, d1), e = Dot(d2, d2), f = Dot(d2, r), s, t;
        if (a < 1e-12 && e < 1e-12) return Dot(r, r);
        if (a < 1e-12) { s = 0; t = Math.Clamp(f / e, 0, 1); }
        else
        {
            double c = Dot(d1, r);
            if (e < 1e-12) { t = 0; s = Math.Clamp(-c / a, 0, 1); }
            else
            {
                double b = Dot(d1, d2), den = a * e - b * b;
                s = den > 1e-12 ? Math.Clamp((b * f - c * e) / den, 0, 1) : 0;
                t = (b * s + f) / e;
                if (t < 0) { t = 0; s = Math.Clamp(-c / a, 0, 1); }
                else if (t > 1) { t = 1; s = Math.Clamp((b - c) / a, 0, 1); }
            }
        }
        V3 g = Sub(Along(p1, d1, s), Along(p2, d2, t));
        return Dot(g, g);
    }

    static bool PointOverTri(V3 p, in Tri t, out double distance)
    {
        V3 e0 = Sub(t.B, t.A), e1 = Sub(t.C, t.A), n = Cross(e0, e1);
        double l = Math.Sqrt(Dot(n, n));
        distance = 0;
        if (l < 1e-9) return false;
        n = new V3(n.X / l, n.Y / l, n.Z / l);
        V3 w = Sub(p, t.A);
        distance = Math.Abs(Dot(w, n));
        double d00 = Dot(e0, e0), d01 = Dot(e0, e1), d11 = Dot(e1, e1), d20 = Dot(w, e0), d21 = Dot(w, e1), den = d00 * d11 - d01 * d01;
        if (Math.Abs(den) < 1e-12) return false;
        double v = (d11 * d20 - d01 * d21) / den, u = (d00 * d21 - d01 * d20) / den;
        return v >= 0 && u >= 0 && u + v <= 1;
    }

    static bool CapsuleTouches(V3 a, V3 b, double radius, in Tri t)
    {
        double rr = radius * radius;
        if (SegSegSq(a, b, t.A, t.B) < rr || SegSegSq(a, b, t.B, t.C) < rr || SegSegSq(a, b, t.C, t.A) < rr) return true;
        if (PointOverTri(a, t, out double da) && da < radius) return true;
        if (PointOverTri(b, t, out double db) && db < radius) return true;
        V3 d = Sub(b, a);
        double l = Math.Sqrt(Dot(d, d));
        if (l < 1e-9) return false;
        V3 e1 = Sub(t.B, t.A), e2 = Sub(t.C, t.A), h = Cross(d, e2);
        double det = Dot(e1, h);
        if (Math.Abs(det) < 1e-9) return false;
        V3 s = Sub(a, t.A);
        double u = Dot(s, h) / det;
        if (u < 0 || u > 1) return false;
        V3 q = Cross(s, e1);
        double v = Dot(d, q) / det, r = Dot(e2, q) / det;
        return v >= 0 && u + v <= 1 && r >= 0 && r <= 1;
    }

    static bool BodyBlocked(V3 floor, double radius, double bodyHeight)
    {
        double fit = radius * FloodBodyFit;
        // A crouched body is too short for one capsule above the 20-unit step clearance, so nine thin capsules fill that band.
        if (bodyHeight - FloodClearance < 2 * fit)
        {
            double thin = (bodyHeight - FloodClearance) / 2 - 0.01, ring = Math.Max(0, fit - thin);
            for (int k = 0; k < 9; k++)
            {
                double angle = k * Math.PI / 4, off = k == 8 ? 0 : ring;
                var center = new V3(floor.X + Math.Cos(angle) * off, floor.Y + Math.Sin(angle) * off, floor.Z + FloodClearance + thin);
                if (CapsuleBlocked(center, center, thin)) return true;
            }
            return false;
        }
        // Same body as DungeonCaptureTest.
        V3 a = new V3(floor.X, floor.Y, floor.Z + radius + FloodClearance);
        V3 b = new V3(floor.X, floor.Y, floor.Z + Math.Max(radius + FloodClearance, bodyHeight - radius));
        return CapsuleBlocked(a, b, fit);
    }

    static bool CapsuleBlocked(V3 a, V3 b, double fit)
    {
        V3 floor = a;
        double reach = fit + 1;
        int i0 = (int)Math.Floor((floor.X - reach) / Bucket), i1 = (int)Math.Floor((floor.X + reach) / Bucket);
        int j0 = (int)Math.Floor((floor.Y - reach) / Bucket), j1 = (int)Math.Floor((floor.Y + reach) / Bucket);
        for (int j = j0; j <= j1; j++)
            for (int i = i0; i <= i1; i++)
            {
                if (!pIndex.TryGetValue((i, j), out var list)) continue;
                foreach (int n in list)
                {
                    var t = pTris[n];
                    if (Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z)) < a.Z - fit || Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z)) > b.Z + fit) continue;
                    if (CapsuleTouches(a, b, fit, t)) return true;
                }
            }
        return false;
    }

    static bool FloorBelow(V3 from, out V3 floor)
    {
        double r = Cast(from, new V3(0, 0, -1), ProbeRange);
        floor = r >= 0 ? new V3(from.X, from.Y, from.Z - r) : from;
        return r >= 0;
    }

    static bool LineBlocked(V3 a, V3 b)
    {
        V3 d = Sub(b, a);
        double l = Math.Sqrt(Dot(d, d));
        return l > 1e-6 && Cast(a, new V3(d.X / l, d.Y / l, d.Z / l), l) >= 0;
    }

    static (int, int, int) PKey(V3 p) => ((int)Math.Round(p.X / ParityCell * 2), (int)Math.Round(p.Y / ParityCell * 2), (int)Math.Round(p.Z / 4));

    static Dictionary<(int, int, int), (V3 at, int seed)> FloodDf(List<V3> seeds, double bodyHeight)
    {
        double scale = PlayerScale.DoomUnitsPerDaggerfallUnit, radius = PlayerScale.Radius, maxRise = Math.Max(PlayerScale.Step, ParityCell);
        var seen = new Dictionary<(int, int, int), (V3, int)>();
        var rejected = new HashSet<(int, int, int)>();
        var open = new Queue<(V3 at, int seed)>();
        for (int s = 0; s < seeds.Count; s++)
        {
            if (!FloorBelow(new V3(seeds[s].X, seeds[s].Y, seeds[s].Z + 8), out var first) || seen.ContainsKey(PKey(first))) continue;
            seen[PKey(first)] = (first, s);
            open.Enqueue((first, s));
            while (open.Count > 0)
            {
                var (at, seed) = open.Dequeue();
                foreach (var (dx, dy) in new[] { (1, 0), (0, 1), (-1, 0), (0, -1) })
                {
                    V3 next = new V3(at.X + dx * ParityCell, at.Y + dy * ParityCell, at.Z);
                    double lift = maxRise + 1, roof = Cast(new V3(next.X, next.Y, next.Z + 2), new V3(0, 0, 1), lift);
                    if (roof >= 0) lift = roof + 1.5;
                    if (!FloorBelow(new V3(next.X, next.Y, next.Z + lift), out var floor)) continue;
                    var key = PKey(floor);
                    if (seen.ContainsKey(key)) continue;
                    if (LineBlocked(new V3(at.X, at.Y, at.Z + FloodKnee), new V3(floor.X, floor.Y, floor.Z + FloodKnee)) || BodyBlocked(floor, radius, bodyHeight)) continue;
                    seen[key] = (floor, seed);
                    open.Enqueue((floor, seed));
                }
            }
        }
        return seen;
    }

    // Every standing position Daggerfall's body fits, by column, with doors treated as open.
    static List<(V3 at, double ceiling)> LegalPositions()
    {
        var legal = new List<(V3, double)>();
        double x0 = tris.Min(t => Math.Min(t.A.X, Math.Min(t.B.X, t.C.X))), x1 = tris.Max(t => Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)));
        double y0 = tris.Min(t => Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y))), y1 = tris.Max(t => Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)));
        double top = tris.Max(t => Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z))) + 8;
        const int Pitch = 8;
        for (double y = Math.Floor(y0 / Pitch) * Pitch + 4; y <= y1; y += Pitch)
            for (double x = Math.Floor(x0 / Pitch) * Pitch + 4; x <= x1; x += Pitch)
            {
                double z = top;
                while (FloorBelow(new V3(x, y, z), out var floor))
                {
                    double roof = Cast(new V3(x, y, floor.Z + 2), new V3(0, 0, 1), ProbeRange);
                    if (roof >= PlayerScale.Height - 2 && !BodyBlocked(floor, PlayerScale.Radius, PlayerScale.Height))
                        legal.Add((floor, floor.Z + 2 + roof));
                    z = floor.Z - 1;
                }
            }
        return legal;
    }

    // A square Doom body rests on the highest floor under it and is limited by the lowest ceiling over it. Beside stairs
    // this can leave less clearance than Daggerfall's rounded capsule needs. Where a legal Daggerfall body stands, raises
    // only the too-low collision ceilings, by at most MaxCeilingRelief. Walls and floors do not change.
    // 16 opened a real false opening under a 56-unit ceiling. 4 covers the rounded-capsule cases at the foot of stairs.
    static int MaxCeilingRelief = 4;

    static int RelieveCeilings()
    {
        IndexTris(tris);
        double r = PlayerScale.Radius, h = PlayerScale.Height, step = PlayerScale.Step;
        var needed = new Dictionary<Span, int>();
        foreach (var (at, _) in LegalPositions())
        {
            int i0 = (int)Math.Floor((at.X - r - minX) / cell), i1 = (int)Math.Floor((at.X + r - minX) / cell);
            int j0 = (int)Math.Floor((at.Y - r - minY) / cell), j1 = (int)Math.Floor((at.Y + r - minY) / cell);
            if (i0 < 0 || j0 < 0 || i1 >= width || j1 >= height) continue;
            var under = new List<Span>();
            bool covered = true;
            for (int j = j0; j <= j1 && covered; j++)
                for (int i = i0; i <= i1; i++)
                {
                    var s = grid[Index(i, j)].FirstOrDefault(x => x.F <= at.Z + step && x.C > at.Z + 8);
                    if (s == null) { covered = false; break; }
                    under.Add(s);
                }
            if (!covered) continue;
            int top = under.Max(s => s.F), target = (int)Math.Ceiling((top + h) / ZQuant) * ZQuant;
            if (under.Min(s => s.C) >= target || target - under.Min(s => s.C) > MaxCeilingRelief) continue;
            foreach (var s in under)
                if (s.C < target && (!needed.TryGetValue(s, out int old) || old < target)) needed[s] = target;
        }
        int raised = 0;
        foreach (var list in grid)
            for (int n = 0; n < list.Count; n++)
                if (needed.TryGetValue(list[n], out int target))
                {
                    int limit = n + 1 < list.Count ? list[n + 1].F - ZQuant : int.MaxValue;
                    int value = Math.Min(target, limit);
                    if (value > list[n].C) { list[n].C = value; raised++; }
                }
        Console.WriteLine($"collision ceilings raised for Daggerfall's body: {raised}");
        return raised;
    }

    static List<Tri> WithDoorBoxes()
    {
        var list = new List<Tri>(tris);
        foreach (var d in doors)
        {
            V3 P(int m) => new V3((m & 1) != 0 ? d.MaxX : d.MinX, (m & 2) != 0 ? d.MaxY : d.MinY, (m & 4) != 0 ? d.MaxZ : d.MinZ);
            void Face(int a, int b, int c, int e, V3 n)
            {
                list.Add(new Tri { A = P(a), B = P(b), C = P(c), N = n, Instance = -1 });
                list.Add(new Tri { A = P(a), B = P(c), C = P(e), N = n, Instance = -1 });
            }
            Face(0, 2, 6, 4, new V3(-1, 0, 0)); Face(1, 5, 7, 3, new V3(1, 0, 0));
            Face(0, 4, 5, 1, new V3(0, -1, 0)); Face(2, 3, 7, 6, new V3(0, 1, 0));
            Face(0, 1, 3, 2, new V3(0, 0, -1)); Face(4, 6, 7, 5, new V3(0, 0, 1));
        }
        return list;
    }

    static int RunParity(string dir, V3 entrance)
    {
        Directory.CreateDirectory(dir);
        var clock = System.Diagnostics.Stopwatch.StartNew();
        double Snap(double v) => Math.Floor(v / ParityCell) * ParityCell + 12;
        IndexTris(tris);
        var rng = new Random(ParitySeed);
        var entranceColumn = new V3(Snap(entrance.X), Snap(entrance.Y), entrance.Z + 8);
        var seeds = new List<V3> { FloorBelow(entranceColumn, out var entranceFloor) ? entranceFloor : entranceColumn }; // the marker floats above the floor
        double x0 = tris.Min(t => Math.Min(t.A.X, Math.Min(t.B.X, t.C.X))), x1 = tris.Max(t => Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)));
        double y0 = tris.Min(t => Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y))), y1 = tris.Max(t => Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)));
        double z0 = tris.Min(t => Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z))), z1 = tris.Max(t => Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z)));
        for (int tries = 0; seeds.Count <= ParitySeeds && tries < 200000; tries++)
        {
            var from = new V3(Snap(x0 + rng.NextDouble() * (x1 - x0)), Snap(y0 + rng.NextDouble() * (y1 - y0)), z0 + rng.NextDouble() * (z1 - z0));
            if (!FloorBelow(from, out var floor) || Cast(new V3(floor.X, floor.Y, floor.Z + 2), new V3(0, 0, 1), PlayerScale.Height) >= 0 || BodyBlocked(floor, PlayerScale.Radius, PlayerScale.Height)) continue;
            seeds.Add(floor);
        }
        var modes = new[] { ("stand_closed", PlayerScale.Height, true), ("crouch_closed", PlayerScale.CrouchHeight, true), ("stand_open", PlayerScale.Height, false), ("crouch_open", PlayerScale.CrouchHeight, false) };
        var closedTris = WithDoorBoxes();
        var df = new Dictionary<string, Dictionary<(int, int, int), (V3 at, int seed)>>();
        foreach (var (name, h, closed) in modes)
        {
            IndexTris(closed ? closedTris : tris);
            df[name] = FloodDf(seeds, h);
            Console.WriteLine($"Daggerfall flood {name}: {df[name].Count} positions");
        }
        Console.WriteLine($"Daggerfall floods: {clock.Elapsed.TotalSeconds:F1} s");

        // Check the offline flood against the real Unity flood when that capture is supplied.
        string unity = Path.Combine(dir, "df_flood_walk.txt");
        if (File.Exists(unity))
        {
            IndexTris(tris);
            var offline = FloodDf(seeds.Take(1).ToList(), PlayerScale.Height);
            var real = new HashSet<(int, int, int)>(File.ReadLines(unity).Select(l => l.Split(' ')).Where(p => p.Length == 3)
                .Select(p => PKey(new V3(double.Parse(p[0], CultureInfo.InvariantCulture), double.Parse(p[1], CultureInfo.InvariantCulture), double.Parse(p[2], CultureInfo.InvariantCulture)))));
            bool Near(HashSet<(int, int, int)> set, (int x, int y, int z) k) { for (int dz = -3; dz <= 3; dz++) if (set.Contains((k.x, k.y, k.z + dz))) return true; return false; }
            var mine = new HashSet<(int, int, int)>(offline.Keys);
            int both = mine.Count(k => Near(real, k)), onlyMine = mine.Count - both, onlyReal = real.Count(k => !Near(mine, k));
            string text = $"Offline flood vs real Unity flood (standing, doors open, entrance): offline {mine.Count}, Unity {real.Count}, offline not in Unity {onlyMine} ({100.0 * onlyMine / Math.Max(1, mine.Count):F2}%), Unity not in offline {onlyReal} ({100.0 * onlyReal / Math.Max(1, real.Count):F2}%)";
            Console.WriteLine(text);
            File.WriteAllText(Path.Combine(dir, "unity_validation.txt"), text + "\n");
        }

        var shots = new List<(V3 at, double angle, double pitch)>();
        var legal = df["stand_open"].Values.Select(v => v.at).OrderBy(v => v.X).ThenBy(v => v.Y).ThenBy(v => v.Z).ToList();
        var shotRng = new Random(ParitySeed + 1);
        for (int n = 0; n < ParityShots && legal.Count > 0; n++)
        {
            var p = legal[shotRng.Next(legal.Count)];
            shots.Add((new V3(p.X, p.Y, p.Z + PlayerScale.EyeHeight), shotRng.NextDouble() * 360, -20 + shotRng.NextDouble() * 40));
        }

        string doomFile = Path.Combine(dir, "doom_flood.txt");
        if (!File.Exists(doomFile))
        {
            var lump = new StringBuilder();
            lump.Append(FormattableString.Invariant($"B {PlayerScale.Radius} {PlayerScale.Height} {PlayerScale.CrouchHeight} {PlayerScale.Step} {Math.Floor(x0) - 64} {Math.Floor(y0) - 64} {Math.Floor(z0) - 64}\n"));
            foreach (var s in seeds) lump.Append(FormattableString.Invariant($"P {s.X:F1} {s.Y:F1} {s.Z:F1}\n"));
            foreach (var s in shots) lump.Append(FormattableString.Invariant($"T {s.at.X:F1} {s.at.Y:F1} {s.at.Z:F1} {s.angle:F3} {s.pitch:F3}\n"));
            var controls = doors.Select(d => d.Control).Where(c => c > 0).Distinct();
            foreach (int c in controls) lump.Append($"D {c}\n");
            string query = Path.Combine(dir, "query.txt"); // optional: asks Doom whether a standing body fits at these positions
            if (File.Exists(query)) foreach (var line in File.ReadLines(query)) lump.Append("Q ").Append(line).Append('\n');
            Directory.CreateDirectory(Path.Combine(dir, "lumps"));
            File.WriteAllText(Path.Combine(dir, "lumps", "DFPARITY"), lump.ToString());
            Console.WriteLine($"Wrote test lump: {seeds.Count} seeds, {shots.Count} shots");
            return 0;
        }
        return CompareParity(dir, modes.Select(m => m.Item1).ToArray(), df, shots, closedTris);
    }

    static string Classify(V3 p, double bodyHeight, bool doomSide)
    {
        foreach (var d in doors)
            if (p.X >= d.MinX - 16 && p.X <= d.MaxX + 16 && p.Y >= d.MinY - 16 && p.Y <= d.MaxY + 16 && p.Z + bodyHeight >= d.MinZ && p.Z <= d.MaxZ) return "doorway";
        int i = (int)Math.Floor((p.X - minX) / cell), j = (int)Math.Floor((p.Y - minY) / cell);
        if (i < 0 || j < 0 || i >= width || j >= height) return "narrow gap";
        var spans = grid[Index(i, j)];
        var near = spans.Where(s => s.F <= p.Z + StepHeight && s.C >= p.Z).OrderBy(s => Math.Abs(s.F - p.Z)).FirstOrDefault();
        if (doomSide)
        {
            double up = Cast(new V3(p.X, p.Y, p.Z + 2), new V3(0, 0, 1), bodyHeight);
            if (up >= 0) return "ceiling";
            return FloorBelow(new V3(p.X, p.Y, p.Z + 8), out var f) && Math.Abs(f.Z - p.Z) > MatchZ ? "step" : "narrow gap";
        }
        if (near == null) return "narrow gap";
        if (Math.Abs(near.F - p.Z) > MatchZ) return "step";
        return near.C - near.F < bodyHeight ? "ceiling" : "narrow gap";
    }

    static int CompareParity(string dir, string[] modes, Dictionary<string, Dictionary<(int, int, int), (V3 at, int seed)>> df, List<(V3 at, double angle, double pitch)> shots, List<Tri> closedTris)
    {
        var doom = modes.ToDictionary(m => m, m => new Dictionary<(int, int), List<(double z, int seed)>>());
        var hits = new Dictionary<int, (bool hit, double x, double y, double z)>();
        foreach (var line in File.ReadLines(Path.Combine(dir, "doom_flood.txt")))
        {
            var p = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (p.Length >= 4 && p[0] == "DFF" && doom.TryGetValue(p[1], out var target))
            {
                int seed = int.Parse(p[2]);
                foreach (var entry in p.Skip(3))
                {
                    var v = entry.Split(',');
                    if (v.Length != 3) continue;
                    var key = ((int)Math.Round(double.Parse(v[0], CultureInfo.InvariantCulture)), (int)Math.Round(double.Parse(v[1], CultureInfo.InvariantCulture)));
                    if (!target.TryGetValue(key, out var list)) target[key] = list = new List<(double, int)>();
                    list.Add((double.Parse(v[2], CultureInfo.InvariantCulture), seed));
                }
            }
            else if (p.Length == 6 && p[0] == "DFB")
                hits[int.Parse(p[1])] = (p[2] == "1", double.Parse(p[3], CultureInfo.InvariantCulture), double.Parse(p[4], CultureInfo.InvariantCulture), double.Parse(p[5], CultureInfo.InvariantCulture));
        }

        File.Delete(Path.Combine(dir, "frontier.txt"));
        var report = new StringBuilder("mode,scope,daggerfall,doom,false_walls,false_openings,fw_ceiling,fw_doorway,fw_step,fw_narrow,fo_ceiling,fo_doorway,fo_step,fo_narrow\n");
        var worst = new List<(int size, string kind, string mode, V3 at, string cls)>();
        string[] classes = { "ceiling", "doorway", "step", "narrow gap" };
        foreach (string mode in modes)
        {
            bool closed = mode.EndsWith("closed");
            double body = mode.StartsWith("stand") ? PlayerScale.Height : PlayerScale.CrouchHeight;
            IndexTris(closed ? closedTris : tris);
            foreach (bool entranceOnly in new[] { true, false })
            {
                var dfPoints = df[mode].Values.Where(v => !entranceOnly || v.seed == 0).Select(v => v.at).ToList();
                var doomPoints = doom[mode].SelectMany(c => c.Value.Where(v => !entranceOnly || v.seed == 0).Select(v => new V3(c.Key.Item1, c.Key.Item2, v.z))).ToList();
                var dfByCell = dfPoints.GroupBy(v => ((int)Math.Round(v.X), (int)Math.Round(v.Y))).ToDictionary(g => g.Key, g => g.Select(v => v.Z).ToList());
                var doomByCell = doomPoints.GroupBy(v => ((int)Math.Round(v.X), (int)Math.Round(v.Y))).ToDictionary(g => g.Key, g => g.Select(v => v.Z).ToList());
                bool Has(Dictionary<(int, int), List<double>> set, V3 v) => set.TryGetValue(((int)Math.Round(v.X), (int)Math.Round(v.Y)), out var zs) && zs.Any(z => Math.Abs(z - v.Z) <= MatchZ);
                var falseWalls = dfPoints.Where(v => !Has(doomByCell, v)).ToList();
                var falseOpenings = doomPoints.Where(v => !Has(dfByCell, v)).ToList();
                var fw = classes.ToDictionary(c => c, c => 0);
                var fo = classes.ToDictionary(c => c, c => 0);
                foreach (var v in falseWalls) fw[Classify(v, body, false)]++;
                foreach (var v in falseOpenings) fo[Classify(v, body, true)]++;
                report.Append($"{mode},{(entranceOnly ? "entrance" : "all_seeds")},{dfPoints.Count},{doomPoints.Count},{falseWalls.Count},{falseOpenings.Count},{string.Join(",", classes.Select(c => fw[c]))},{string.Join(",", classes.Select(c => fo[c]))}\n");
                // The frontier is where a false wall actually begins. Cells behind it are only its downstream effect.
                var frontier = falseWalls.Where(v => new[] { (ParityCell, 0), (-ParityCell, 0), (0, ParityCell), (0, -ParityCell) }
                    .Any(o => doomByCell.TryGetValue(((int)Math.Round(v.X) + o.Item1, (int)Math.Round(v.Y) + o.Item2), out var zs) && zs.Any(z => Math.Abs(z - v.Z) <= StepHeight))).ToList();
                var frontierText = new StringBuilder($"{mode} {(entranceOnly ? "entrance" : "all_seeds")}: {frontier.Count} frontier cells\n");
                foreach (var v in frontier.OrderBy(v => v.X).ThenBy(v => v.Y).Take(entranceOnly ? 5000 : 0))
                {
                    int ci = (int)Math.Floor((v.X - minX) / cell), cj = (int)Math.Floor((v.Y - minY) / cell);
                    frontierText.Append(FormattableString.Invariant($"  {v.X:F0},{v.Y:F0},{v.Z:F0} {Classify(v, body, false)} spans {string.Join(" ", grid[Index(ci, cj)].Select(s => $"[{s.F},{s.C}{(s.Door >= 0 ? " door" + s.Door : "")}]"))}\n"));
                }
                File.AppendAllText(Path.Combine(dir, "frontier.txt"), frontierText.ToString());
                if (!entranceOnly) File.WriteAllLines(Path.Combine(dir, "false_openings_" + mode + ".txt"), falseOpenings.Select(v => FormattableString.Invariant($"{v.X:F0} {v.Y:F0} {v.Z:F1}")));
                if (entranceOnly) continue;
                foreach (var (kind, list) in new[] { ("false_wall", falseWalls), ("false_opening", falseOpenings) })
                {
                    var left = new HashSet<(int, int, int)>(list.Select(v => ((int)Math.Round(v.X), (int)Math.Round(v.Y), (int)Math.Round(v.Z / 8))));
                    var byKey = list.GroupBy(v => ((int)Math.Round(v.X), (int)Math.Round(v.Y), (int)Math.Round(v.Z / 8))).ToDictionary(g => g.Key, g => g.First());
                    while (left.Count > 0)
                    {
                        var first = left.First();
                        var stack = new Stack<(int x, int y, int z)>();
                        stack.Push(first);
                        left.Remove(first);
                        int size = 0;
                        while (stack.Count > 0)
                        {
                            var c = stack.Pop();
                            size++;
                            foreach (var (dx, dy) in new[] { (ParityCell, 0), (-ParityCell, 0), (0, ParityCell), (0, -ParityCell) })
                                for (int dz = -2; dz <= 2; dz++)
                                {
                                    var n = (c.x + dx, c.y + dy, c.z + dz);
                                    if (left.Remove(n)) stack.Push(n);
                                }
                        }
                        worst.Add((size, kind, mode, byKey[first], Classify(byKey[first], body, kind == "false_opening")));
                    }
                }
            }
        }
        File.WriteAllText(Path.Combine(dir, "parity.csv"), report.ToString());
        Console.Write(report);

        var views = new StringBuilder("# id | kind | x y floor yaw pitch | note\n");
        var chosen = worst.OrderByDescending(w => w.size).GroupBy(w => (w.kind, w.cls)).SelectMany(g => g.Take(3)).OrderByDescending(w => w.size).Take(16).ToList();
        int index = 0;
        foreach (var w in chosen)
            views.Append(FormattableString.Invariant($"w{++index:D2} | {w.kind} | {Math.Floor(w.at.X / 16) * 16 + 8} {Math.Floor(w.at.Y / 16) * 16 + 8} {w.at.Z:F0} 0 10 | {w.mode}, {w.cls}, {w.size} cells\n"));
        File.WriteAllText(Path.Combine(dir, "worst_views.txt"), views.ToString());
        Console.Write(views);

        // Bullets: compare Doom's impact with the first visible Daggerfall face along the same ray.
        var visible = new List<Tri>(tris);
        visible.AddRange(doorMeshTris);
        IndexTris(visible);
        int on = 0, front = 0, behind = 0, noMesh = 0, noDoom = 0;
        var errors = new List<(double error, int shot, double doomDistance, double meshDistance)>();
        for (int n = 0; n < shots.Count; n++)
        {
            if (!hits.TryGetValue(n, out var h) || !h.hit) { noDoom++; continue; }
            var s = shots[n];
            double ca = Math.Cos(s.angle * Math.PI / 180), sa = Math.Sin(s.angle * Math.PI / 180), cp = Math.Cos(s.pitch * Math.PI / 180), sp = Math.Sin(s.pitch * Math.PI / 180);
            var d = new V3(ca * cp, sa * cp, -sp);
            double doomDistance = Math.Sqrt(Dot(Sub(new V3(h.x, h.y, h.z), s.at), Sub(new V3(h.x, h.y, h.z), s.at)));
            double mesh = Cast(s.at, d, 4096);
            if (mesh < 0) { noMesh++; errors.Add((1e6, n, doomDistance, -1)); continue; }
            double delta = doomDistance - mesh;
            if (Math.Abs(delta) <= SurfaceTolerance) on++;
            else if (delta < 0) front++;
            else behind++;
            errors.Add((Math.Abs(delta), n, doomDistance, mesh));
        }
        var bullet = new StringBuilder($"shots {shots.Count}, on visible surface (within {SurfaceTolerance}) {on}, in front {front}, behind {behind}, no mesh hit {noMesh}, no Doom hit {noDoom}\n");
        foreach (var e in errors.OrderByDescending(e => e.error).Take(8))
        {
            var s = shots[e.shot];
            bullet.Append(FormattableString.Invariant($"shot {e.shot} from {s.at.X:F0},{s.at.Y:F0},{s.at.Z:F0} angle {s.angle:F1} pitch {s.pitch:F1}: Doom {e.doomDistance:F1}, mesh {e.meshDistance:F1}\n"));
        }
        File.WriteAllText(Path.Combine(dir, "bullets.txt"), bullet.ToString());
        Console.Write(bullet);
        return 0;
    }
}
