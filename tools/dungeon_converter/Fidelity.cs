// Collision fidelity metric: how closely the emitted map's collision matches the visible Daggerfall faces.
// Test only and offline: runs only with --fidelity <dir>, never at the dungeon door. See work/notes/20261128-002113.md.
//
// Doom side: the collision solid is rebuilt from the emitted TEXTMAP (lines, sector planes, solid 3D floors), so writing
// bugs count too. Daggerfall side: the static model faces, which are what the player sees and what Daggerfall collides
// with. Doors are runtime objects on both sides (door leaves are not in the face list, and door sight blockers are
// non-solid 3D floors), so doorways are measured open, as in Parity.cs's open mode without the leaves.
//
// Mesh to collision: each face sample's signed distance to the collision surface along the face normal
// (+ collision in front of the face: invisible walls; - behind it: walking into visible walls).
// Collision to mesh: each collision sample's distance to the nearest visible face (+ in front of that face).
// Both are area-sampled at about 2x2 units and weighted by reach tier.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

static partial class Program
{
    static string fidelityDir, fidelityCache;
    const int FidVersion = 3; // the cache key also holds a hash of the code that builds the Daggerfall side (FidCodeHash.cs)
    const double FidCap = 32, FidVoxel = 16, FidLevOffset = 4;
    // Exteriors (CityFidelity.cs) sample on a coarser grid and keep a fixed share of every tier, so a whole town fits in
    // memory; the kept samples stand for more area, so the score stays unbiased. Exteriors have open sky: see Tier.
    static double FidStep = 2, FidKeepScale = 1;
    static bool FidExterior;
    // From DoomerfallClimb.zs: SteepNormalZ (steeper surfaces are climbed) and Touch (reach beyond the body radius).
    // Climbing has no height limit (holding still never slips), so the climb band reaches the ceiling over the floor.
    const double FidSteepZ = 0.34202, FidTouch = 12;
    static readonly double[] TierWeight = { 1.0, 0.3, 0.1, 0.05 };
    static readonly string[] TierName = { "contact", "climb", "levitation", "unreached" };
    static readonly string[] ClassName = { "axis walls", "45-degree walls", "other walls", "flat floors", "slopes", "steep floors", "flat ceilings", "sloped ceilings" };

    struct FSample { public float X, Y, Z, NX, NY, NZ, Area, Error; public byte Tier, Cls; }

    static byte OrientClass(double nx, double ny, double nz)
    {
        if (nz >= WallNormalZ) return (byte)(nz > 0.999 ? 3 : nz >= FidSteepZ ? 4 : 5);
        if (nz <= -WallNormalZ) return (byte)(nz < -0.999 ? 6 : 7);
        double a = Math.Atan2(ny, nx) * 180 / Math.PI, m = ((a % 90) + 90) % 90;
        if (Math.Min(m, 90 - m) <= 1) return 0;
        return (byte)(Math.Abs(m - 45) <= 1 ? 1 : 2);
    }

    static int RunFidelity(string wadPath, string slug, V3 entrance)
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        Directory.CreateDirectory(fidelityDir);
        var meshGrid = new FidMeshGrid(tris, FidExterior ? 16 : 8); // the cell size changes only the speed; outdoors the terrain is large
        Console.WriteLine(FormattableString.Invariant($"fidelity: face grid {clock.Elapsed.TotalSeconds:F1} s"));
        var df = LoadOrBuildDfSide(slug, meshGrid, entrance, out bool cached);
        double dfSeconds = clock.Elapsed.TotalSeconds;
        if (double.IsNaN(entrance.Z) && df.Legal.Length > 0) entrance = new V3(df.Legal[0].x, df.Legal[0].y, df.Legal[0].z); // the flood's seed comes first
        var map = FidMap.Read(wadPath);
        if (FidExterior)
        {
            double zTop = tris.Max(t => Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z))) + 8, zBottom = tris.Min(t => Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z))) - 8;
            map.Beyond = (x, y) => meshGrid.VerticalHit(new V3(x, y, zTop), -1, zTop - zBottom) != 0; // any face below: inside Daggerfall's world
        }
        // Samples are kept in proportion to their tier's weight, each then standing for more area, so the score stays
        // unbiased. Selection hashes the lattice index (faces) or the position (collision), so variants compare alike.
        var coll = map.Samples(FidStep, (ref FSample s) =>
        {
            s.Tier = df.Tier(s.X, s.Y, s.Z, s.NX, s.NY, s.NZ);
            double keep = TierKeep[s.Tier] * FidKeepScale;
            if (keep < 1 && Hash01(((ulong)BitConverter.SingleToUInt32Bits(s.X) << 32) ^ BitConverter.SingleToUInt32Bits(s.Y) ^ ((ulong)BitConverter.SingleToUInt32Bits(s.Z) << 16)) >= keep) return false;
            s.Area = (float)(s.Area / keep);
            return true;
        });
        var mesh = Thin(df.Samples);
        double sampleSeconds = clock.Elapsed.TotalSeconds - dfSeconds;

        // Mesh to collision, along each face normal.
        Parallel.For(0, mesh.Length, n =>
        {
            ref var s = ref mesh[n];
            s.Error = (float)map.NormalDistance(s.X, s.Y, s.Z, s.NX, s.NY, s.NZ, FidCap);
        });
        // Collision to mesh: the nearest visible face.
        Parallel.For(0, coll.Length, n =>
        {
            ref var s = ref coll[n];
            var p = new V3(s.X, s.Y, s.Z);
            double d = meshGrid.Nearest(p, FidCap, out V3 q, out int t);
            s.Error = (float)(t < 0 ? FidCap : Dot(Sub(p, q), meshGrid.T[t].N) >= 0 ? d : -d);
        });
        double total = clock.Elapsed.TotalSeconds;

        var report = new StringBuilder();
        var csv = new StringBuilder("map,direction,tier,area,samples,mean,p95,in1,in2,in4,front1,front2,front4,behind1,behind2,behind4\n");
        double headline = Headline(mesh, coll);
        report.Append(FormattableString.Invariant($"Collision fidelity: {slug}\nheadline (tier-weighted mean error, both directions, units; lower is better): {headline:F3}\n"));
        report.Append(FormattableString.Invariant($"samples: mesh {mesh.Length}, collision {coll.Length}; reachable legal positions {df.Legal.Length} of {df.AllLegal}, air voxels {df.AirCount}; Daggerfall side {(cached ? "cached" : "built")} {dfSeconds:F1} s, collision sampling {sampleSeconds:F1} s, total {total:F1} s\n"));
        report.Append("errors are in map units, capped at " + FidCap + "; front = collision in front of the visible face, behind = behind it\n\n");
        foreach (var (dir, set) in new[] { ("mesh_to_collision", mesh), ("collision_to_mesh", coll) })
        {
            report.Append(dir == "mesh_to_collision" ? "Mesh to collision (along the face normal)\n" : "Collision to mesh (nearest visible face)\n");
            report.Append("  tier         area      mean    p95   in1   in2   in4 | front>1 >2   >4  | behind>1 >2  >4\n");
            for (int tier = 0; tier < 4; tier++)
            {
                var st = Stats(set.Where(s => s.Tier == tier));
                report.Append(FormattableString.Invariant($"  {TierName[tier],-11}{st.area,9:F0} {st.mean,8:F2} {st.p95,6:F1} {st.in1,5:P0} {st.in2,5:P0} {st.in4,5:P0} | {st.f1,5:P0} {st.f2,5:P0} {st.f4,5:P0} | {st.b1,5:P0} {st.b2,5:P0} {st.b4,5:P0}\n"));
                csv.Append(FormattableString.Invariant($"{slug},{dir},{TierName[tier]},{st.area:F1},{st.count},{st.mean:F4},{st.p95:F3},{st.in1:F4},{st.in2:F4},{st.in4:F4},{st.f1:F4},{st.f2:F4},{st.f4:F4},{st.b1:F4},{st.b2:F4},{st.b4:F4}\n"));
            }
            report.Append("  by orientation, all tiers weighted:\n");
            for (int c = 0; c < ClassName.Length; c++)
            {
                var st = Stats(set.Where(s => s.Cls == c), weighted: true);
                if (st.count == 0) continue;
                report.Append(FormattableString.Invariant($"    {ClassName[c],-16}{st.area,9:F0} {st.mean,8:F2} {st.p95,6:F1} {st.in1,5:P0} {st.in2,5:P0} {st.in4,5:P0} | {st.f1,5:P0} {st.f2,5:P0} {st.f4,5:P0} | {st.b1,5:P0} {st.b2,5:P0} {st.b4,5:P0}\n"));
                csv.Append(FormattableString.Invariant($"{slug},{dir},{ClassName[c]},{st.area:F1},{st.count},{st.mean:F4},{st.p95:F3},{st.in1:F4},{st.in2:F4},{st.in4:F4},{st.f1:F4},{st.f2:F4},{st.f4:F4},{st.b1:F4},{st.b2:F4},{st.b4:F4}\n"));
            }
            report.Append('\n');
        }
        csv.Append(FormattableString.Invariant($"{slug},headline,all,0,{mesh.Length + coll.Length},{headline:F4},0,0,0,0,0,0,0,0,0,0\n"));
        report.Append(Cases(mesh, coll, csv, slug));
        report.Append(WorstPlaces(mesh, coll, df, meshGrid, entrance, slug));
        File.WriteAllText(Path.Combine(fidelityDir, slug + ".fidelity.txt"), report.ToString());
        File.WriteAllText(Path.Combine(fidelityDir, slug + ".fidelity.csv"), csv.ToString());
        Console.WriteLine(FormattableString.Invariant($"FIDELITY {slug} headline {headline:F4} seconds {total:F2} mesh {mesh.Length} collision {coll.Length} df {(cached ? "cached" : "built")}"));
        return 0;
    }

    static readonly double[] TierKeep = { 1.0, 0.3, 0.1, 0.1 };

    // The failure kinds the exterior card names, by tier, from the same samples as the headline:
    //  walkable top missing: a visible floor (up to 70 degrees) whose collision is more than a step below it, so the
    //    player sinks into it or falls through (a roofless wall walk with no collision top, for example);
    //  phantom wall: collision wall more than 4 units in front of every visible face (an invisible wall);
    //  invisible ledge: collision floor more than a step above every visible face.
    static string Cases(FSample[] mesh, FSample[] coll, StringBuilder csv, string slug)
    {
        double step = PlayerScale.Step;
        var text = new StringBuilder("Failure cases: bad area / tier area, map units^2 (contact | climb | levitation | unreached)\n");
        var places = new StringBuilder();
        void Row(string name, FSample[] set, Func<FSample, bool> kind, Func<FSample, bool> bad)
        {
            var area = new double[4]; var all = new double[4];
            var where = new Dictionary<(int, int, int), double>(); // reached-tier bad area by 64-unit cell
            foreach (var x in set)
                if (kind(x))
                {
                    all[x.Tier] += x.Area;
                    if (!bad(x)) continue;
                    area[x.Tier] += x.Area;
                    if (x.Tier < 3) { var key = ((int)Math.Floor(x.X / 64), (int)Math.Floor(x.Y / 64), (int)Math.Floor(x.Z / 64)); where[key] = where.GetValueOrDefault(key) + x.Area; }
                }
            places.Append($"  {name}:").Append(string.Concat(where.OrderByDescending(kv => kv.Value).Take(6)
                .Select(kv => FormattableString.Invariant($" {kv.Key.Item1 * 64 + 32},{kv.Key.Item2 * 64 + 32},{kv.Key.Item3 * 64 + 32} ({kv.Value:F0})")))).Append('\n');
            text.Append($"  {name,-22}");
            for (int t = 0; t < 4; t++)
            {
                text.Append(FormattableString.Invariant($" {area[t],10:F0} / {all[t],-10:F0}{(t < 3 ? " |" : "")}"));
                csv.Append(FormattableString.Invariant($"{slug},case {name},{TierName[t]},{area[t]:F1},0,{(all[t] > 0 ? area[t] / all[t] : 0):F6},0,0,0,0,0,0,0,0,0,0\n"));
            }
            text.Append('\n');
        }
        Row("walkable top missing", mesh, x => x.NZ >= FidSteepZ, x => x.Error < -step);
        Row("phantom wall", coll, x => Math.Abs(x.NZ) < WallNormalZ, x => x.Error > 4);
        Row("invisible ledge", coll, x => x.NZ >= FidSteepZ, x => x.Error > step);
        return text.Append("Largest places per case (64-unit cells, centre x,y,z and bad area; contact, climb and levitation tiers):\n").Append(places).Append('\n').ToString();
    }

    delegate bool FidAdmit(ref FSample s);

    static double Hash01(ulong z)
    {
        z += 0x9E3779B97F4A7C15UL;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL; z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL; z ^= z >> 31;
        return (z >> 11) * (1.0 / (1UL << 53));
    }

    static FSample[] Thin(FSample[] all)
    {
        var kept = new List<FSample>(all.Length / 2);
        for (int n = 0; n < all.Length; n++)
        {
            double keep = TierKeep[all[n].Tier];
            if (keep < 1 && Hash01((ulong)n) >= keep) continue;
            var s = all[n];
            s.Area = (float)(s.Area / keep);
            kept.Add(s);
        }
        return kept.ToArray();
    }

    static double Headline(FSample[] mesh, FSample[] coll)
    {
        double sum = 0, weight = 0;
        foreach (var set in new[] { mesh, coll })
            foreach (var s in set) { double w = TierWeight[s.Tier] * s.Area; sum += w * Math.Abs(s.Error); weight += w; }
        return weight > 0 ? sum / weight : 0;
    }

    static (double area, int count, double mean, double p95, double in1, double in2, double in4, double f1, double f2, double f4, double b1, double b2, double b4)
        Stats(IEnumerable<FSample> samples, bool weighted = false)
    {
        var list = samples.Select(s => (e: (double)s.Error, w: s.Area * (weighted ? TierWeight[s.Tier] : 1.0), a: (double)s.Area)).ToList();
        double total = list.Sum(v => v.w);
        if (list.Count == 0 || total <= 0) return (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
        double Share(Func<double, bool> f) => list.Where(v => f(v.e)).Sum(v => v.w) / total;
        double mean = list.Sum(v => v.w * Math.Abs(v.e)) / total, run = 0, p95 = 0;
        foreach (var v in list.OrderBy(v => Math.Abs(v.e))) { run += v.w; if (run >= 0.95 * total) { p95 = Math.Abs(v.e); break; } }
        return (list.Sum(v => v.a), list.Count, mean, p95, Share(e => Math.Abs(e) <= 1), Share(e => Math.Abs(e) <= 2), Share(e => Math.Abs(e) <= 4),
            Share(e => e > 1), Share(e => e > 2), Share(e => e > 4), Share(e => e < -1), Share(e => e < -2), Share(e => e < -4));
    }

    // Clusters the worst weighted error into 64-unit cells and writes views the compare and screenshot tools can render.
    static string WorstPlaces(FSample[] mesh, FSample[] coll, FidDfSide df, FidMeshGrid grid, V3 entrance, string slug)
    {
        const double Cell = 64;
        var cells = new Dictionary<(int, int, int), (double sum, double x, double y, double z, double[] kinds, double[] classes)>();
        string[] kinds = { "collision in front of visible face", "visible face with collision behind it", "phantom collision in front of faces", "collision buried behind faces" };
        foreach (var (set, isMesh) in new[] { (mesh, true), (coll, false) })
            foreach (var s in set)
            {
                double c = TierWeight[s.Tier] * s.Area * Math.Max(0, Math.Abs(s.Error) - 1);
                if (c <= 0) continue;
                var key = ((int)Math.Floor(s.X / Cell), (int)Math.Floor(s.Y / Cell), (int)Math.Floor(s.Z / Cell));
                if (!cells.TryGetValue(key, out var v)) v = (0, 0, 0, 0, new double[4], new double[ClassName.Length]);
                v.kinds[(isMesh ? 0 : 2) + (s.Error > 0 ? 0 : 1)] += c;
                v.classes[s.Cls] += c;
                cells[key] = (v.sum + c, v.x + c * s.X, v.y + c * s.Y, v.z + c * s.Z, v.kinds, v.classes);
            }
        var chosen = new List<((int, int, int) key, (double sum, double x, double y, double z, double[] kinds, double[] classes) v)>();
        foreach (var kv in cells.OrderByDescending(kv => kv.Value.sum))
        {
            if (chosen.Count >= 16) break;
            if (chosen.Any(c => Math.Abs(c.key.Item1 - kv.Key.Item1) <= 1 && Math.Abs(c.key.Item2 - kv.Key.Item2) <= 1 && Math.Abs(c.key.Item3 - kv.Key.Item3) <= 1)) continue;
            chosen.Add((kv.Key, kv.Value));
        }
        double scale = PlayerScale.DoomUnitsPerDaggerfallUnit, eye = PlayerScale.EyeHeight;
        var text = new StringBuilder("Worst places (tier-weighted error area beyond 1 unit, 64-unit cells), map units:\n");
        // View files are in Daggerfall units; the first view is the entrance, which compare.py's Daggerfall flood starts from.
        var views = new StringBuilder("# Collision fidelity worst places. id | kind | x y floor yaw pitch | note (Daggerfall units)\n");
        views.Append(FormattableString.Invariant($"w00 | entrance | {entrance.X / scale:F0} {entrance.Y / scale:F0} {entrance.Z / scale:F0} 0 0 | entrance\n"));
        int index = 0;
        foreach (var (key, v) in chosen)
        {
            var target = new V3(v.x / v.sum, v.y / v.sum, v.z / v.sum);
            int kind = Array.IndexOf(v.kinds, v.kinds.Max()), cls = Array.IndexOf(v.classes, v.classes.Max());
            var from = df.Viewpoint(target, grid, eye);
            double dx = target.X - from.X, dy = target.Y - from.Y, dz = target.Z - (from.Z + eye);
            double yaw = Math.Atan2(dy, dx) * 180 / Math.PI, pitch = -Math.Atan2(dz, Math.Max(1, Math.Sqrt(dx * dx + dy * dy))) * 180 / Math.PI;
            index++;
            text.Append(FormattableString.Invariant($"  w{index:D2} at {target.X:F0},{target.Y:F0},{target.Z:F0}: weighted area {v.sum:F0}, mostly {kinds[kind]}, {ClassName[cls]}; view from {from.X:F0},{from.Y:F0},{from.Z:F0}\n"));
            views.Append(FormattableString.Invariant($"w{index:D2} | {kinds[kind]} | {from.X / scale:F0} {from.Y / scale:F0} {from.Z / scale:F0} {yaw:F0} {pitch:F0} | {ClassName[cls]}, weighted area {v.sum:F0}, target {target.X:F0},{target.Y:F0},{target.Z:F0} (map units)\n"));
        }
        File.WriteAllText(Path.Combine(fidelityDir, slug + ".worst_views.txt"), views.ToString());
        return text.ToString();
    }

    static FidDfSide LoadOrBuildDfSide(string slug, FidMeshGrid grid, V3 entrance, out bool cached)
    {
        double hash = 0;
        foreach (var t in tris) hash += t.A.X * 1.000001 + t.B.Y * 3.000003 + t.C.Z * 7.000007 + t.N.Z;
        string key = FormattableString.Invariant($"{FidVersion}|{FidCodeHash()}|{slug}|{PlayerScale.DoomUnitsPerDaggerfallUnit}|{PlayerScale.DaggerfallBody}|{FidExterior}|{FidStep}|{FidKeepScale}|{tris.Count}|{hash:R}");
        string path = fidelityCache == null ? null : Path.Combine(fidelityCache, slug + ".dfside.bin");
        cached = false;
        if (path != null && File.Exists(path))
        {
            var loaded = FidDfSide.Load(path, key, tris, grid);
            if (loaded != null) { cached = true; return loaded; }
        }
        var watch = System.Diagnostics.Stopwatch.StartNew();
        var legal = FidLegal(entrance, out int allLegal);
        double legalSeconds = watch.Elapsed.TotalSeconds;
        var df = FidDfSide.Build(legal, tris, grid);
        df.AllLegal = allLegal;
        Console.WriteLine(FormattableString.Invariant($"fidelity: Daggerfall side legal positions {legalSeconds:F1} s, air and tiers {watch.Elapsed.TotalSeconds - legalSeconds:F1} s"));
        if (path != null) { Directory.CreateDirectory(fidelityCache); df.Save(path, key); }
        return df;
    }

    // Every standing position Daggerfall's body fits (LegalPositions' rule in Parity.cs, rows in parallel; outdoors a
    // column with no ceiling is open sky), and of those the ones the player walks to from the entrance: 8-unit moves onto
    // the highest floor in the next column at most a rise above (Parity.cs's FloodDf rise), dropping any height, where
    // the body fits. Doors open. Teleports, lifts, jumps, climbing and levitation are not followed: surfaces only those
    // reach fall to the levitation or unreached tiers. Returns the reachable positions with the ceiling over each.
    static List<(V3 at, double ceiling)> FidLegal(V3 entrance, out int allLegal)
    {
        IndexTris(tris);
        const int Pitch = 8;
        double x0 = tris.Min(t => Math.Min(t.A.X, Math.Min(t.B.X, t.C.X))), x1 = tris.Max(t => Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)));
        double y0 = tris.Min(t => Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y))), y1 = tris.Max(t => Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)));
        double top = tris.Max(t => Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z))) + 8, height = PlayerScale.Height;
        double bottom = tris.Min(t => Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z))) - 1;
        double gx = Math.Floor(x0 / Pitch) * Pitch + 4, gy = Math.Floor(y0 / Pitch) * Pitch + 4;
        int w = Math.Max(0, (int)Math.Floor((x1 - gx) / Pitch) + 1), h = Math.Max(0, (int)Math.Floor((y1 - gy) / Pitch) + 1);
        var rows = new List<(float z, float ceiling, bool legal)>[h];
        var rowStart = new int[h][];
        Parallel.For(0, h, j =>
        {
            var list = new List<(float, float, bool)>();
            var starts = new int[w + 1];
            for (int i = 0; i < w; i++)
            {
                starts[i] = list.Count;
                double x = gx + i * Pitch, y = gy + j * Pitch, z = top;
                while (z > bottom)
                {
                    // A cast reaches ProbeRange: below a tall map's top (a mountain in an exterior margin) keep going down.
                    if (!FloorBelow(new V3(x, y, z), out var floor)) { z -= ProbeRange - 8; continue; }
                    double roof = Cast(new V3(x, y, floor.Z + 2), new V3(0, 0, 1), ProbeRange);
                    bool sky = roof < 0 && FidExterior;
                    bool legal = (sky || roof >= height - 2) && !BodyBlocked(floor, PlayerScale.Radius, height);
                    list.Add(((float)floor.Z, (float)(sky ? top + ProbeRange : floor.Z + 2 + roof), legal));
                    z = floor.Z - 1;
                }
            }
            starts[w] = list.Count;
            rows[j] = list; rowStart[j] = starts;
        });
        var colStart = new int[w * h + 1];
        int total = 0;
        for (int j = 0; j < h; j++) for (int i = 0; i < w; i++) { colStart[i + j * w] = total; total += rowStart[j][i + 1] - rowStart[j][i]; }
        colStart[w * h] = total;
        var fz = new float[total]; var fc = new float[total]; var fl = new bool[total];
        for (int j = 0; j < h; j++)
            for (int n = 0; n < rows[j].Count; n++) { int at = colStart[j * w] + n; (fz[at], fc[at], fl[at]) = rows[j][n]; }
        allLegal = fl.Count(b => b);

        // Seed: the legal position nearest the entrance, at or below it.
        int seed = -1, sc = 0;
        double best = double.MaxValue;
        for (int radius = 16; seed < 0 && radius <= 256; radius *= 2)
            for (int j = Math.Max(0, (int)Math.Floor((entrance.Y - radius - gy) / Pitch)); j <= Math.Min(h - 1, (int)Math.Ceiling((entrance.Y + radius - gy) / Pitch)); j++)
                for (int i = Math.Max(0, (int)Math.Floor((entrance.X - radius - gx) / Pitch)); i <= Math.Min(w - 1, (int)Math.Ceiling((entrance.X + radius - gx) / Pitch)); i++)
                    for (int n = colStart[i + j * w]; n < colStart[i + j * w + 1]; n++)
                    {
                        // An exterior start has no height (NaN): the street is the lowest legal floor in the nearest column.
                        bool street = double.IsNaN(entrance.Z);
                        if (!fl[n] || (!street && fz[n] > entrance.Z + PlayerScale.Step + 8)) continue;
                        double dx = gx + i * Pitch - entrance.X, dy = gy + j * Pitch - entrance.Y, dz = street ? 0 : fz[n] - entrance.Z, d = dx * dx + dy * dy + dz * dz;
                        if (d < best || (street && d == best && fz[n] < fz[seed])) { best = d; seed = n; sc = i + j * w; }
                    }
        var reached = new bool[total];
        var result = new List<(V3 at, double ceiling)>();
        if (seed < 0) { Console.WriteLine(FormattableString.Invariant($"fidelity: no legal position near the entrance {entrance.X:F0},{entrance.Y:F0},{entrance.Z:F0} (grid {gx:F0}..{gx + w * Pitch:F0}, {gy:F0}..{gy + h * Pitch:F0}); nothing is reachable")); return result; }
        double rise = Math.Max(PlayerScale.Step, ParityCell);
        var open = new Queue<(int i, int j, int n)>();
        reached[seed] = true;
        open.Enqueue((sc % w, sc / w, seed));
        // Outdoors Daggerfall's world goes on past the converted area, so the player can also walk in from the
        // wilderness: the ground (lowest legal floor) of every column beside one with no floor at all, the map's edge.
        if (FidExterior)
            for (int j = 0; j < h; j++)
                for (int i = 0; i < w; i++)
                {
                    int c = i + j * w, last = colStart[c + 1] - 1;
                    if (last < colStart[c] || !fl[last] || reached[last]) continue;
                    bool edge = i == 0 || j == 0 || i == w - 1 || j == h - 1 || colStart[c - 1] == colStart[c] || colStart[c + 2] == colStart[c + 1]
                        || colStart[c - w] == colStart[c - w + 1] || colStart[c + w] == colStart[c + w + 1];
                    if (edge) { reached[last] = true; open.Enqueue((i, j, last)); }
                }
        while (open.Count > 0)
        {
            var (i, j, n) = open.Dequeue();
            result.Add((new V3(gx + i * Pitch, gy + j * Pitch, fz[n]), fc[n]));
            foreach (var (di, dj) in new[] { (1, 0), (-1, 0), (0, 1), (0, -1) })
            {
                int ni = i + di, nj = j + dj;
                if (ni < 0 || nj < 0 || ni >= w || nj >= h) continue;
                int c = ni + nj * w;
                for (int m = colStart[c]; m < colStart[c + 1]; m++)
                {
                    if (fz[m] > fz[n] + rise) continue;
                    if (fl[m] && !reached[m]) { reached[m] = true; open.Enqueue((ni, nj, m)); }
                    break; // the highest floor within a rise is where the body lands
                }
            }
        }
        Console.WriteLine($"fidelity: {result.Count} of {allLegal} legal positions reachable from the entrance");        return result;
    }

    static long FidKey(int i, int j, int k) => ((long)(i + (1 << 20)) << 42) | ((long)(j + (1 << 20)) << 21) | (long)(k + (1 << 20));

    // The Daggerfall side: face samples with their tiers, legal positions, and the open air connected to them.
    // None of it depends on the converter's choices, so it is cached per dungeon.
    sealed class FidDfSide
    {
        public FSample[] Samples;
        // Legal positions the player can walk to from the entrance (FidLegal); AllLegal counts every legal position.
        public (float x, float y, float z, float ceiling)[] Legal;
        public int AllLegal;
        FidMeshGrid grid;
        // Air as a dense bit set over the faces' voxel box (origin ai, aj, ak; size aw, ah, ad).
        public ulong[] AirBits;
        public int ai, aj, ak, aw, ah, ad, AirCount;
        // Legal positions by 16-unit column, as start offsets into one index array.
        int[] cellStart, cellItems;
        int li, lj, lw, lh;
        const double LegalCell = 16;

        void IndexLegal()
        {
            if (Legal.Length == 0) { li = lj = 0; lw = lh = 1; cellStart = new int[2]; cellItems = Array.Empty<int>(); return; }
            li = (int)Math.Floor(Legal.Min(l => l.x) / LegalCell) - 1; lj = (int)Math.Floor(Legal.Min(l => l.y) / LegalCell) - 1;
            lw = (int)Math.Floor(Legal.Max(l => l.x) / LegalCell) - li + 2; lh = (int)Math.Floor(Legal.Max(l => l.y) / LegalCell) - lj + 2;
            var cellOf = new int[Legal.Length];
            cellStart = new int[lw * lh + 1];
            for (int n = 0; n < Legal.Length; n++)
            {
                cellOf[n] = ((int)Math.Floor(Legal[n].x / LegalCell) - li) + ((int)Math.Floor(Legal[n].y / LegalCell) - lj) * lw;
                cellStart[cellOf[n] + 1]++;
            }
            for (int c = 0; c < lw * lh; c++) cellStart[c + 1] += cellStart[c];
            cellItems = new int[Legal.Length];
            var fill = (int[])cellStart.Clone();
            for (int n = 0; n < Legal.Length; n++) cellItems[fill[cellOf[n]]++] = n;
        }

        bool AirAt(int i, int j, int k)
        {
            i -= ai; j -= aj; k -= ak;
            if (i < 0 || j < 0 || k < 0 || i >= aw || j >= ah || k >= ad) return false;
            long bit = i + (long)aw * (j + (long)ah * k);
            return (AirBits[bit >> 6] & (1UL << (int)(bit & 63))) != 0;
        }

        bool SetAir(int i, int j, int k)
        {
            if (AirAt(i, j, k)) return false;
            long bit = (i - ai) + (long)aw * ((j - aj) + (long)ah * (k - ak));
            AirBits[bit >> 6] |= 1UL << (int)(bit & 63);
            AirCount++;
            return true;
        }

        // Contact: floors under a legal position (within the body radius, a step up or down) and walls within reach of
        // one from foot to head. Climb: walls above head height up to the ceiling over that position. Levitation: faces
        // whose open side is air connected to legal positions. Everything else is unreached.
        public byte Tier(double x, double y, double z, double nx, double ny, double nz)
        {
            double radius = PlayerScale.Radius, reach = radius + FidTouch, height = PlayerScale.Height, step = PlayerScale.Step;
            bool floor = nz >= FidSteepZ, wall = !floor && nz > -FidSteepZ, climb = false;
            if (floor || wall)
            {
                double r = floor ? radius : reach;
                int i0 = Math.Max(0, (int)Math.Floor((x - r) / LegalCell) - li), i1 = Math.Min(lw - 1, (int)Math.Floor((x + r) / LegalCell) - li);
                int j0 = Math.Max(0, (int)Math.Floor((y - r) / LegalCell) - lj), j1 = Math.Min(lh - 1, (int)Math.Floor((y + r) / LegalCell) - lj);
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        int c = i + j * lw;
                        for (int m = cellStart[c]; m < cellStart[c + 1]; m++)
                        {
                            int n = cellItems[m];
                            var l = Legal[n];
                            double dx = l.x - x, dy = l.y - y;
                            if (dx * dx + dy * dy > r * r) continue;
                            if (floor) { if (Math.Abs(l.z - z) <= step) return 0; continue; }
                            if (dx * nx + dy * ny < -1) continue; // the position must be on the face's open side
                            if (z >= l.z - 1 && z <= l.z + height) return 0;
                            if (z > l.z + height && z <= l.ceiling + 1) climb = true;
                        }
                    }
            }
            if (climb) return 1;
            double ox = x + nx * FidLevOffset, oy = y + ny * FidLevOffset, oz = z + nz * FidLevOffset;
            if (AirAt((int)Math.Floor(ox / FidVoxel), (int)Math.Floor(oy / FidVoxel), (int)Math.Floor(oz / FidVoxel))) return 2;
            // Outdoors a levitating player comes down from the open sky: any face whose open side has no face above it
            // and ground below it is in reach.
            if (FidExterior && grid.SkyOpen(new V3(ox, oy, oz))) return 2;
            return 3;
        }

        public static FidDfSide Build(List<(V3 at, double ceiling)> legal, List<Tri> faces, FidMeshGrid grid)
        {
            var df = new FidDfSide { Legal = legal.Select(l => ((float)l.at.X, (float)l.at.Y, (float)l.at.Z, (float)l.ceiling)).ToArray(), grid = grid };
            df.IndexLegal();
            if (FidExterior)
            {
                // Outdoors the open air is the sky (Tier's SkyOpen test), so the room flood is not run.
                df.ai = df.aj = df.ak = 0; df.aw = df.ah = df.ad = 1; df.AirBits = new ulong[1];
                df.Samples = Lattice(faces);
                var outdoor = df.Samples;
                Parallel.For(0, outdoor.Length, n => outdoor[n].Tier = df.Tier(outdoor[n].X, outdoor[n].Y, outdoor[n].Z, outdoor[n].NX, outdoor[n].NY, outdoor[n].NZ));
                return df;
            }
            // Air connected to legal positions: 16-unit voxels, stepping between centers wherever no face is crossed.
            double x0 = faces.Min(t => Math.Min(t.A.X, Math.Min(t.B.X, t.C.X))), x1 = faces.Max(t => Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)));
            double y0 = faces.Min(t => Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y))), y1 = faces.Max(t => Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)));
            double z0 = faces.Min(t => Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z))), z1 = faces.Max(t => Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z)));
            int ia = (int)Math.Floor(x0 / FidVoxel), ib = (int)Math.Floor(x1 / FidVoxel), ja = (int)Math.Floor(y0 / FidVoxel), jb = (int)Math.Floor(y1 / FidVoxel);
            int ka = (int)Math.Floor(z0 / FidVoxel), kb = (int)Math.Floor(z1 / FidVoxel);
            df.ai = ia - 1; df.aj = ja - 1; df.ak = ka - 1; df.aw = ib - ia + 3; df.ah = jb - ja + 3; df.ad = kb - ka + 3;
            df.AirBits = new ulong[((long)df.aw * df.ah * df.ad + 63) / 64];
            var open = new Queue<(int i, int j, int k)>();
            foreach (var l in df.Legal)
            {
                var v = ((int)Math.Floor(l.x / FidVoxel), (int)Math.Floor(l.y / FidVoxel), (int)Math.Floor((l.z + PlayerScale.Height / 2) / FidVoxel));
                if (df.SetAir(v.Item1, v.Item2, v.Item3)) open.Enqueue(v);
            }
            V3 Center((int i, int j, int k) c) => new V3((c.i + 0.5) * FidVoxel, (c.j + 0.5) * FidVoxel, (c.k + 0.5) * FidVoxel);
            while (open.Count > 0)
            {
                var c = open.Dequeue();
                foreach (var (di, dj, dk) in new[] { (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1) })
                {
                    var n = (c.i + di, c.j + dj, c.k + dk);
                    if (n.Item1 < ia - 1 || n.Item1 > ib + 1 || n.Item2 < ja - 1 || n.Item2 > jb + 1 || n.Item3 < ka - 1 || n.Item3 > kb + 1) continue;
                    if (df.AirAt(n.Item1, n.Item2, n.Item3) || grid.SegmentBlocked(Center(c), Center(n))) continue;
                    // Inside a room: the nearest face above faces down and the nearest below faces up. This keeps the
                    // flood out of the void around the models when it slips through an opening (the exit door has no model).
                    var at = Center(n);
                    if (grid.VerticalHit(at, 1, 4096) >= 0 || grid.VerticalHit(at, -1, 4096) <= 0) continue;
                    df.SetAir(n.Item1, n.Item2, n.Item3);
                    open.Enqueue(n);
                }
            }
            df.Samples = Lattice(faces);
            var arr = df.Samples;
            Parallel.For(0, arr.Length, n => arr[n].Tier = df.Tier(arr[n].X, arr[n].Y, arr[n].Z, arr[n].NX, arr[n].NY, arr[n].NZ));
            return df;
        }

        // Face samples on a barycentric lattice, about one per 2x2 units, each carrying its share of the face's area.
        static FSample[] Lattice(List<Tri> faces)
        {
            // k*k samples per face; counted first so the faces can be filled in parallel in a fixed order.
            var ks = new int[faces.Count];
            var start = new long[faces.Count + 1];
            for (int n = 0; n < faces.Count; n++)
            {
                var t = faces[n];
                V3 e1 = Sub(t.B, t.A), e2 = Sub(t.C, t.A), cr = Cross(e1, e2);
                double area = 0.5 * Math.Sqrt(Dot(cr, cr));
                double longest = Math.Sqrt(Math.Max(Dot(e1, e1), Math.Max(Dot(e2, e2), Dot(Sub(t.C, t.B), Sub(t.C, t.B)))));
                ks[n] = area < 1e-6 ? 0 : Math.Max(1, Math.Max((int)Math.Ceiling(Math.Sqrt(area / (FidStep * FidStep))), (int)Math.Ceiling(longest / 8)));
                start[n + 1] = start[n] + (long)ks[n] * ks[n];
            }
            // With FidKeepScale < 1 (exteriors) a fixed hashed share of the lattice is kept, chosen by lattice index.
            bool thin = FidKeepScale < 1;
            var samples = thin ? null : new FSample[start[faces.Count]];
            var parts = thin ? new FSample[faces.Count][] : null;
            Parallel.For(0, faces.Count, n =>
            {
                int k = ks[n];
                if (k == 0) return;
                var t = faces[n];
                V3 e1 = Sub(t.B, t.A), e2 = Sub(t.C, t.A), cr = Cross(e1, e2);
                float each = (float)(0.5 * Math.Sqrt(Dot(cr, cr)) / (k * k) / (thin ? FidKeepScale : 1));
                byte cls = OrientClass(t.N.X, t.N.Y, t.N.Z);
                long at = start[n];
                var local = thin ? new List<FSample>() : null;
                void Add(double u, double v)
                {
                    var s = new FSample
                    {
                        X = (float)(t.A.X + e1.X * u + e2.X * v), Y = (float)(t.A.Y + e1.Y * u + e2.Y * v), Z = (float)(t.A.Z + e1.Z * u + e2.Z * v),
                        NX = (float)t.N.X, NY = (float)t.N.Y, NZ = (float)t.N.Z, Area = each, Cls = cls,
                    };
                    if (!thin) samples[at] = s;
                    else if (Hash01((ulong)at ^ 0xA5A5A5A500000000UL) < FidKeepScale) local.Add(s);
                    at++;
                }
                for (int i = 0; i < k; i++)
                    for (int j = 0; i + j < k; j++)
                    {
                        Add((i + 1.0 / 3) / k, (j + 1.0 / 3) / k);
                        if (i + j < k - 1) Add((i + 2.0 / 3) / k, (j + 2.0 / 3) / k);
                    }
                if (thin) parts[n] = local.ToArray();
            });
            return thin ? parts.Where(q => q != null).SelectMany(q => q).ToArray() : samples;
        }

        // A standing spot that sees the target: the nearest legal position 48 to 384 units away with a clear line.
        public V3 Viewpoint(V3 target, FidMeshGrid grid, double eye)
        {
            var near = Legal.Select(l => (l, d: Math.Sqrt((l.x - target.X) * (l.x - target.X) + (l.y - target.Y) * (l.y - target.Y))))
                .Where(c => c.d >= 48 && c.d <= 384 && Math.Abs(c.l.z - target.Z) < 192).OrderBy(c => c.d).Take(400);
            foreach (var (l, d) in near)
            {
                var from = new V3(l.x, l.y, l.z + eye);
                var dir = Sub(target, from);
                double len = Math.Sqrt(Dot(dir, dir));
                if (len < 8 || !grid.SegmentBlocked(from, Along(from, dir, (len - 6) / len))) return new V3(l.x, l.y, l.z);
            }
            var any = Legal.OrderBy(l => Math.Abs(l.x - target.X) + Math.Abs(l.y - target.Y) + Math.Abs(l.z - target.Z)).FirstOrDefault();
            return Legal.Length > 0 ? new V3(any.x, any.y, any.z) : target;
        }

        public void Save(string path, string key)
        {
            using var w = new BinaryWriter(File.Create(path));
            w.Write(key);
            w.Write(Samples.Length);
            w.Write(Samples.Select(s => s.Tier).ToArray()); // the lattice itself is rebuilt from the faces
            w.Write(AllLegal);
            w.Write(Legal.Length);
            foreach (var l in Legal) { w.Write(l.x); w.Write(l.y); w.Write(l.z); w.Write(l.ceiling); }
            foreach (int v in new[] { ai, aj, ak, aw, ah, ad, AirCount, AirBits.Length }) w.Write(v);
            var bytes = new byte[AirBits.Length * 8];
            Buffer.BlockCopy(AirBits, 0, bytes, 0, bytes.Length);
            w.Write(bytes);
        }

        public static FidDfSide Load(string path, string key, List<Tri> faces, FidMeshGrid grid)
        {
            using var r = new BinaryReader(File.OpenRead(path));
            if (r.ReadString() != key) return null;
            var df = new FidDfSide { Samples = Lattice(faces), grid = grid };
            if (r.ReadInt32() != df.Samples.Length) return null;
            var tiers = r.ReadBytes(df.Samples.Length);
            for (int n = 0; n < df.Samples.Length; n++) df.Samples[n].Tier = tiers[n];
            df.AllLegal = r.ReadInt32();
            df.Legal = new (float, float, float, float)[r.ReadInt32()];
            for (int n = 0; n < df.Legal.Length; n++) df.Legal[n] = (r.ReadSingle(), r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
            df.ai = r.ReadInt32(); df.aj = r.ReadInt32(); df.ak = r.ReadInt32(); df.aw = r.ReadInt32(); df.ah = r.ReadInt32(); df.ad = r.ReadInt32();
            df.AirCount = r.ReadInt32();
            df.AirBits = new ulong[r.ReadInt32()];
            Buffer.BlockCopy(r.ReadBytes(df.AirBits.Length * 8), 0, df.AirBits, 0, df.AirBits.Length * 8);
            df.IndexLegal();
            return df;
        }
    }

    // The visible faces in a uniform 3D grid, for nearest-face distances and two-sided segment tests.
    sealed class FidMeshGrid
    {
        public readonly List<Tri> T;
        readonly double g;
        readonly Dictionary<long, int[]> cells;

        readonly Dictionary<long, int> columnTop = new Dictionary<long, int>(); // highest cell layer with a face, by column

        public FidMeshGrid(List<Tri> faces, double cellSize)
        {
            T = faces; g = cellSize;
            var build = new Dictionary<long, List<int>>();
            for (int n = 0; n < faces.Count; n++)
            {
                var t = faces[n];
                int i0 = C(Math.Min(t.A.X, Math.Min(t.B.X, t.C.X))), i1 = C(Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)));
                int j0 = C(Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y))), j1 = C(Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)));
                int k0 = C(Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z))), k1 = C(Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z)));
                // A plane test keeps big sloped or diagonal faces out of the cells they only pass near.
                double d = Dot(t.N, t.A), half = g * 0.5 * (Math.Abs(t.N.X) + Math.Abs(t.N.Y) + Math.Abs(t.N.Z)) + 1e-6;
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        // Only the layers the plane test can pass (big terrain and floor faces span many cells); the test
                        // below still decides, so the cells are the same as testing every layer.
                        int ka = k0, kb = k1;
                        if (Math.Abs(t.N.Z) > 1e-3)
                        {
                            double rest = d - t.N.X * (i + 0.5) * g - t.N.Y * (j + 0.5) * g;
                            double za = (rest - half) / (t.N.Z * g) - 0.5, zb = (rest + half) / (t.N.Z * g) - 0.5;
                            ka = Math.Max(k0, (int)Math.Floor(Math.Min(za, zb)) - 1); kb = Math.Min(k1, (int)Math.Ceiling(Math.Max(za, zb)) + 1);
                        }
                        for (int k = ka; k <= kb; k++)
                        {
                            var c = new V3((i + 0.5) * g, (j + 0.5) * g, (k + 0.5) * g);
                            if (Math.Abs(Dot(t.N, c) - d) > half) continue;
                            long key = FidKey(i, j, k);
                            if (!build.TryGetValue(key, out var l)) build[key] = l = new List<int>();
                            l.Add(n);
                            long column = ((long)i << 32) | (uint)j;
                            if (!columnTop.TryGetValue(column, out int top) || top < k) columnTop[column] = k;
                        }
                    }
            }
            cells = build.ToDictionary(kv => kv.Key, kv => kv.Value.ToArray());
        }

        // Open to the sky: no face straight above p, and an upward-facing face (ground or a roof) below it.
        public bool SkyOpen(V3 p)
        {
            if (!columnTop.TryGetValue(((long)C(p.X) << 32) | (uint)C(p.Y), out int top)) return false;
            double above = (top + 1) * g - p.Z;
            if (above > 0 && VerticalHit(p, 1, above + 1) != 0) return false;
            return VerticalHit(p, -1, 4096) > 0;
        }

        int C(double v) => (int)Math.Floor(v / g);

        public double Nearest(V3 p, double cap, out V3 best, out int bestTri)
        {
            int ci = C(p.X), cj = C(p.Y), ck = C(p.Z);
            double bestSq = cap * cap;
            best = p; bestTri = -1;
            int rings = (int)Math.Ceiling(cap / g) + 1;
            for (int r = 0; r <= rings; r++)
            {
                for (int k = ck - r; k <= ck + r; k++)
                    for (int j = cj - r; j <= cj + r; j++)
                        for (int i = ci - r; i <= ci + r; i++)
                        {
                            if (Math.Max(Math.Abs(i - ci), Math.Max(Math.Abs(j - cj), Math.Abs(k - ck))) != r) continue;
                            if (!cells.TryGetValue(FidKey(i, j, k), out var list)) continue;
                            foreach (int n in list)
                            {
                                var q = ClosestOnTri(p, T[n]);
                                var dv = Sub(p, q);
                                double dd = Dot(dv, dv);
                                if (dd < bestSq) { bestSq = dd; best = q; bestTri = n; }
                            }
                        }
                // Every face not yet seen is at least r cells away in some axis.
                if (bestTri >= 0 && Math.Sqrt(bestSq) <= r * g) break;
            }
            return bestTri >= 0 ? Math.Sqrt(bestSq) : cap;
        }

        // The nearest face straight up (dir 1) or down (-1), either side: its normal z, or 0 when nothing is within max.
        public double VerticalHit(V3 p, int dir, double max)
        {
            int ci = C(p.X), cj = C(p.Y), ck = C(p.Z), last = C(p.Z + dir * max);
            double best = max, normal = 0;
            for (int k = ck; dir > 0 ? k <= last : k >= last; k += dir)
            {
                if (cells.TryGetValue(FidKey(ci, cj, k), out var list))
                    foreach (int n in list)
                    {
                        var t = T[n];
                        if (Math.Abs(t.N.Z) < 1e-9) continue;
                        // Barycentric test in the xy projection, then the plane height there.
                        double d = (t.B.Y - t.C.Y) * (t.A.X - t.C.X) + (t.C.X - t.B.X) * (t.A.Y - t.C.Y);
                        if (Math.Abs(d) < 1e-12) continue;
                        double u = ((t.B.Y - t.C.Y) * (p.X - t.C.X) + (t.C.X - t.B.X) * (p.Y - t.C.Y)) / d;
                        double v = ((t.C.Y - t.A.Y) * (p.X - t.C.X) + (t.A.X - t.C.X) * (p.Y - t.C.Y)) / d;
                        if (u < 0 || v < 0 || u + v > 1) continue;
                        double z = u * t.A.Z + v * t.B.Z + (1 - u - v) * t.C.Z, r = (z - p.Z) * dir;
                        if (r >= 0 && r < best) { best = r; normal = t.N.Z; }
                    }
                double layerEnd = dir > 0 ? (k + 1) * g - p.Z : p.Z - k * g;
                if (normal != 0 && best <= layerEnd) break;
            }
            return normal;
        }

        public bool SegmentBlocked(V3 a, V3 b)
        {
            V3 d = Sub(b, a);
            int i0 = C(Math.Min(a.X, b.X)), i1 = C(Math.Max(a.X, b.X)), j0 = C(Math.Min(a.Y, b.Y)), j1 = C(Math.Max(a.Y, b.Y)), k0 = C(Math.Min(a.Z, b.Z)), k1 = C(Math.Max(a.Z, b.Z));
            // Long sight lines walk the grid in steps instead of testing their whole box.
            double length = Math.Sqrt(Dot(d, d));
            if (length > 4 * g)
            {
                int steps = (int)Math.Ceiling(length / g);
                for (int s = 0; s < steps; s++)
                    if (SegmentBlocked(Along(a, d, (double)s / steps), Along(a, d, (double)(s + 1) / steps))) return true;
                return false;
            }
            for (int k = k0; k <= k1; k++)
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        if (!cells.TryGetValue(FidKey(i, j, k), out var list)) continue;
                        foreach (int n in list)
                        {
                            var t = T[n];
                            V3 e1 = Sub(t.B, t.A), e2 = Sub(t.C, t.A), h = Cross(d, e2);
                            double det = Dot(e1, h);
                            if (Math.Abs(det) < 1e-12) continue;
                            V3 s = Sub(a, t.A);
                            double u = Dot(s, h) / det;
                            if (u < 0 || u > 1) continue;
                            V3 q = Cross(s, e1);
                            double v = Dot(d, q) / det;
                            if (v < 0 || u + v > 1) continue;
                            double r = Dot(e2, q) / det;
                            if (r >= 0 && r <= 1) return true;
                        }
                    }
            return false;
        }

        // Ericson, Real-Time Collision Detection 5.1.5.
        static V3 ClosestOnTri(V3 p, in Tri t)
        {
            V3 a = t.A, b = t.B, c = t.C, ab = Sub(b, a), ac = Sub(c, a), ap = Sub(p, a);
            double d1 = Dot(ab, ap), d2 = Dot(ac, ap);
            if (d1 <= 0 && d2 <= 0) return a;
            V3 bp = Sub(p, b);
            double d3 = Dot(ab, bp), d4 = Dot(ac, bp);
            if (d3 >= 0 && d4 <= d3) return b;
            double vc = d1 * d4 - d3 * d2;
            if (vc <= 0 && d1 >= 0 && d3 <= 0) return Along(a, ab, d1 / (d1 - d3));
            V3 cp = Sub(p, c);
            double d5 = Dot(ab, cp), d6 = Dot(ac, cp);
            if (d6 >= 0 && d5 <= d6) return c;
            double vb = d5 * d2 - d1 * d6;
            if (vb <= 0 && d2 >= 0 && d6 <= 0) return Along(a, ac, d2 / (d2 - d6));
            double va = d3 * d6 - d5 * d4;
            if (va <= 0 && d4 - d3 >= 0 && d5 - d6 >= 0) return Along(b, Sub(c, b), (d4 - d3) / ((d4 - d3) + (d5 - d6)));
            double den = 1 / (va + vb + vc), v = vb * den, w = vc * den;
            return new V3(a.X + ab.X * v + ac.X * w, a.Y + ab.Y * v + ac.Y * w, a.Z + ab.Z * v + ac.Z * w);
        }
    }

    // The collision solid as the emitted TEXTMAP defines it: sectors bounded by lines, sloped floor and ceiling planes,
    // and solid 3D floors (Sector_Set3DFloor type 1). Non-solid 3D floors (door sight blockers, water) are not collision.
    sealed class FidMap
    {
        struct Plane { public double A, B, C; public double Z(double x, double y) => A + B * x + C * y; } // z = A + Bx + Cy
        sealed class Line { public double AX, AY, BX, BY; public int Front = -1, Back = -1, Special, Arg0, Arg1; }
        sealed class Sector { public int Floor, Ceiling, Id; public bool Control, Sky; public List<(int bottom, int top)> Slabs = new List<(int, int)>(); }
        readonly List<Plane> planes = new List<Plane>();
        readonly List<Line> lines = new List<Line>();
        readonly List<Sector> sectors = new List<Sector>();
        Dictionary<long, int[]> rowCells;
        double ox, oy;
        const double BandH = 8, BandW = 64;
        int maxXb;

        public Func<double, double, bool> Beyond; // exteriors: true where Daggerfall has a face at (x, y)

        public static FidMap Read(string wadPath)
        {
            var bytes = File.ReadAllBytes(wadPath);
            int count = BitConverter.ToInt32(bytes, 4), dir = BitConverter.ToInt32(bytes, 8);
            string text = null;
            for (int n = 0; n < count; n++)
            {
                int at = dir + n * 16;
                if (Encoding.ASCII.GetString(bytes, at + 8, 8).TrimEnd('\0') == "TEXTMAP")
                    text = Encoding.ASCII.GetString(bytes, BitConverter.ToInt32(bytes, at), BitConverter.ToInt32(bytes, at + 4));
            }
            if (text == null) throw new InvalidDataException("no TEXTMAP in " + wadPath);
            var map = new FidMap();
            map.Parse(text);
            return map;
        }

        void Parse(string text)
        {
            var verts = new List<(double x, double y)>();
            var sideSector = new List<int>();
            var lineSides = new List<(int v1, int v2, int f, int b, int special, int arg0, int arg1)>();
            int p = 0;
            while (true)
            {
                while (p < text.Length && !char.IsLetter(text[p])) p++;
                if (p >= text.Length) break;
                int s = p;
                while (p < text.Length && (char.IsLetterOrDigit(text[p]) || text[p] == '_')) p++;
                string block = text.Substring(s, p - s);
                while (p < text.Length && char.IsWhiteSpace(text[p])) p++;
                if (p >= text.Length || text[p] != '{') { p = text.IndexOf(';', p) + 1; if (p <= 0) break; continue; } // namespace = "zdoom";
                int end = text.IndexOf('}', p);
                var f = new Dictionary<string, string>();
                foreach (var part in text.Substring(p + 1, end - p - 1).Split(';'))
                {
                    int eq = part.IndexOf('=');
                    if (eq > 0) f[part.Substring(0, eq).Trim()] = part.Substring(eq + 1).Trim().Trim('"');
                }
                p = end + 1;
                double D(string k, double def = 0) => f.TryGetValue(k, out var v) ? double.Parse(v, CultureInfo.InvariantCulture) : def;
                int I(string k, int def = 0) => f.TryGetValue(k, out var v) ? int.Parse(v, CultureInfo.InvariantCulture) : def;
                switch (block)
                {
                    case "vertex": verts.Add((D("x"), D("y"))); break;
                    case "sidedef": sideSector.Add(I("sector")); break;
                    case "linedef": lineSides.Add((I("v1"), I("v2"), I("sidefront", -1), I("sideback", -1), I("special"), I("arg0"), I("arg1"))); break;
                    case "sector":
                        int PlaneOf(string name, double height)
                        {
                            double c = D(name + "_c");
                            planes.Add(Math.Abs(c) > 1e-12 ? new Plane { A = -D(name + "_d") / c, B = -D(name + "_a") / c, C = -D(name + "_b") / c } : new Plane { A = height });
                            return planes.Count - 1;
                        }
                        sectors.Add(new Sector { Floor = PlaneOf("floorplane", D("heightfloor")), Ceiling = PlaneOf("ceilingplane", D("heightceiling")), Id = I("id"), Sky = f.TryGetValue("textureceiling", out var ct) && ct == "F_SKY1" });
                        break;
                }
            }
            foreach (var l in lineSides)
                lines.Add(new Line { AX = verts[l.v1].x, AY = verts[l.v1].y, BX = verts[l.v2].x, BY = verts[l.v2].y, Front = l.f >= 0 ? sideSector[l.f] : -1, Back = l.b >= 0 ? sideSector[l.b] : -1, Special = l.special, Arg0 = l.arg0, Arg1 = l.arg1 });
            var byTag = new Dictionary<int, List<int>>();
            for (int n = 0; n < sectors.Count; n++) if (sectors[n].Id > 0) { if (!byTag.TryGetValue(sectors[n].Id, out var l)) byTag[sectors[n].Id] = l = new List<int>(); l.Add(n); }
            foreach (var l in lines.Where(l => l.Special == 160 && l.Front >= 0)) sectors[l.Front].Control = true;
            foreach (var l in lines.Where(l => l.Special == 160 && l.Front >= 0 && (l.Arg1 & 3) == 1))
                if (byTag.TryGetValue(l.Arg0, out var targets))
                    foreach (int t in targets)
                        if (!sectors[t].Control) sectors[t].Slabs.Add((sectors[l.Front].Floor, sectors[l.Front].Ceiling));
            lines.RemoveAll(l => (l.Front < 0 || sectors[l.Front].Control) && (l.Back < 0 || sectors[l.Back].Control));
            // Row bands for point-in-sector: lines by 8-unit y band and 64-unit x bucket.
            ox = lines.Min(l => Math.Min(l.AX, l.BX)) - 1; oy = lines.Min(l => Math.Min(l.AY, l.BY)) - 1;
            var build = new Dictionary<long, List<int>>();
            for (int n = 0; n < lines.Count; n++)
            {
                var l = lines[n];
                if (l.AY == l.BY) continue;
                int b0 = (int)Math.Floor((Math.Min(l.AY, l.BY) - oy) / BandH), b1 = (int)Math.Floor((Math.Max(l.AY, l.BY) - oy) / BandH);
                int x0 = (int)Math.Floor((Math.Min(l.AX, l.BX) - ox) / BandW), x1 = (int)Math.Floor((Math.Max(l.AX, l.BX) - ox) / BandW);
                maxXb = Math.Max(maxXb, x1);
                for (int b = b0; b <= b1; b++)
                    for (int x = x0; x <= x1; x++)
                    {
                        long key = ((long)b << 32) | (uint)x;
                        if (!build.TryGetValue(key, out var list)) build[key] = list = new List<int>();
                        list.Add(n);
                    }
            }
            rowCells = build.ToDictionary(kv => kv.Key, kv => kv.Value.ToArray());
        }

        // The sector on the +x side of a line crossing a row: the front sector lies right of v1 to v2.
        int RightOf(Line l) => l.BY < l.AY ? l.Back : l.Front;
        int LeftOf(Line l) => l.BY < l.AY ? l.Front : l.Back;

        int SectorAt(double x, double y)
        {
            int band = (int)Math.Floor((y - oy) / BandH);
            double best = double.MaxValue;
            Line hit = null;
            for (int xb = Math.Max(0, (int)Math.Floor((x - ox) / BandW)); xb <= maxXb; xb++)
            {
                if (rowCells.TryGetValue(((long)band << 32) | (uint)xb, out var list))
                    foreach (int n in list)
                    {
                        var l = lines[n];
                        if (!(y >= Math.Min(l.AY, l.BY) && y < Math.Max(l.AY, l.BY))) continue;
                        double xc = l.AX + (y - l.AY) * (l.BX - l.AX) / (l.BY - l.AY);
                        if (xc >= x && xc < best) { best = xc; hit = l; }
                    }
                if (hit != null && best <= ox + (xb + 1) * BandW) break;
            }
            if (hit == null) return -1;
            int s = LeftOf(hit);
            return s >= 0 && !sectors[s].Control ? s : -1;
        }

        // Open intervals of a sector column at (x, y), with the plane bounding each end. Returns the count.
        int Free(int s, double x, double y, Span<double> lo, Span<double> hi, Span<int> loPlane, Span<int> hiPlane)
        {
            if (s < 0) return 0;
            var sec = sectors[s];
            double floor = planes[sec.Floor].Z(x, y), ceiling = planes[sec.Ceiling].Z(x, y), cur = floor;
            int curPlane = sec.Floor, n = 0;
            if (sec.Slabs.Count > 0)
            {
                Span<double> sb = stackalloc double[sec.Slabs.Count], st = stackalloc double[sec.Slabs.Count];
                Span<int> order = stackalloc int[sec.Slabs.Count];
                for (int k = 0; k < sb.Length; k++) { sb[k] = planes[sec.Slabs[k].bottom].Z(x, y); st[k] = planes[sec.Slabs[k].top].Z(x, y); order[k] = k; }
                for (int a = 1; a < order.Length; a++) for (int b = a; b > 0 && sb[order[b]] < sb[order[b - 1]]; b--) (order[b], order[b - 1]) = (order[b - 1], order[b]);
                foreach (int k in order)
                {
                    if (st[k] <= sb[k]) continue;
                    if (sb[k] > cur && n < lo.Length)
                    {
                        double top = Math.Min(sb[k], ceiling);
                        if (top > cur) { lo[n] = cur; loPlane[n] = curPlane; hi[n] = top; hiPlane[n] = sb[k] < ceiling ? sec.Slabs[k].bottom : sec.Ceiling; n++; }
                    }
                    if (st[k] > cur) { cur = st[k]; curPlane = sec.Slabs[k].top; }
                }
            }
            if (ceiling > cur && n < lo.Length) { lo[n] = cur; loPlane[n] = curPlane; hi[n] = ceiling; hiPlane[n] = sec.Ceiling; n++; }
            return n;
        }

        bool Solid(double x, double y, double z)
        {
            int s = SectorAt(x, y);
            if (s < 0) return true;
            Span<double> lo = stackalloc double[16], hi = stackalloc double[16];
            Span<int> lp = stackalloc int[16], hp = stackalloc int[16];
            int n = Free(s, x, y, lo, hi, lp, hp);
            for (int k = 0; k < n; k++) if (z > lo[k] && z < hi[k]) return false;
            return true;
        }

        // Signed distance along the normal to the collision surface: + when the face point is inside collision (the surface
        // is in front of the face), - when it is in the open (the surface is behind). Capped at cap.
        public double NormalDistance(double x, double y, double z, double nx, double ny, double nz, double cap)
        {
            bool start = Solid(x, y, z);
            double sign = start ? 1 : -1, prev = 0;
            for (double t = 0.5; t <= cap + 1e-9; t += t < 8 ? 0.5 : 1)
            {
                if (Solid(x + nx * t * sign, y + ny * t * sign, z + nz * t * sign) == start) { prev = t; continue; }
                double a = prev, b = t;
                for (int k = 0; k < 5; k++)
                {
                    double m = (a + b) / 2;
                    if (Solid(x + nx * m * sign, y + ny * m * sign, z + nz * m * sign) == start) a = m; else b = m;
                }
                return sign * (a + b) / 2;
            }
            return sign * cap;
        }

        // Area samples of the collision surface: floors, ceilings and 3D floor faces by 2-unit rows, walls along each line.
        public FSample[] Samples(double step, FidAdmit admit)
        {
            var result = new List<FSample>();
            var gate = new object();
            double y0 = Math.Floor(oy / step) * step, y1 = lines.Max(l => Math.Max(l.AY, l.BY));
            int rows = (int)Math.Ceiling((y1 - y0) / step);
            Parallel.For(0, rows, () => new List<FSample>(), (r, _, local) =>
            {
                double y = y0 + (r + 0.5) * step;
                int band = (int)Math.Floor((y - oy) / BandH);
                var crossings = new List<(double x, int right)>();
                var seen = new HashSet<int>();
                for (int xb = 0; xb <= maxXb; xb++)
                    if (rowCells.TryGetValue(((long)band << 32) | (uint)xb, out var list))
                        foreach (int n in list)
                        {
                            var l = lines[n];
                            if (!seen.Add(n) || !(y >= Math.Min(l.AY, l.BY) && y < Math.Max(l.AY, l.BY))) continue;
                            crossings.Add((l.AX + (y - l.AY) * (l.BX - l.AX) / (l.BY - l.AY), RightOf(l)));
                        }
                crossings.Sort((a, b) => a.x.CompareTo(b.x));
                double[] lo = new double[16], hi = new double[16];
                int[] lp = new int[16], hp = new int[16];
                for (int c = 0; c + 1 < crossings.Count; c++)
                {
                    int s = crossings[c].right;
                    double xa = crossings[c].x, xb = crossings[c + 1].x;
                    if (s < 0 || sectors[s].Control || xb - xa < 1e-6) continue;
                    double first = Math.Floor(xa / step) * step + step / 2;
                    if (first < xa) first += step;
                    void At(double x, double w)
                    {
                        int n = Free(s, x, y, lo, hi, lp, hp);
                        for (int k = 0; k < n; k++)
                        {
                            AddFlat(local, admit, x, y, lo[k], planes[lp[k]], true, w * step);
                            // A sky ceiling is the map's height limit, not a surface: Daggerfall's sky is open.
                            if (!(sectors[s].Sky && hp[k] == sectors[s].Ceiling)) AddFlat(local, admit, x, y, hi[k], planes[hp[k]], false, w * step);
                        }
                    }
                    if (first >= xb) { At((xa + xb) / 2, xb - xa); continue; }
                    for (double x = first; x < xb; x += step) At(x, Math.Min(x + step / 2, xb) - Math.Max(x - step / 2, xa));
                }
                return local;
            }, local => { lock (gate) result.AddRange(local); });
            Parallel.For(0, lines.Count, () => new List<FSample>(), (n, _, local) => { WallSamples(lines[n], step, admit, local); return local; },
                local => { lock (gate) result.AddRange(local); });
            return result.ToArray();
        }

        static void AddFlat(List<FSample> into, FidAdmit admit, double x, double y, double z, Plane p, bool up, double projected)
        {
            double len = Math.Sqrt(p.B * p.B + p.C * p.C + 1), nx = -p.B / len, ny = -p.C / len, nz = 1 / len;
            if (!up) { nx = -nx; ny = -ny; nz = -nz; }
            var s = new FSample { X = (float)x, Y = (float)y, Z = (float)z, NX = (float)nx, NY = (float)ny, NZ = (float)nz, Area = (float)(projected * len), Cls = OrientClass(nx, ny, nz) };
            if (admit(ref s)) into.Add(s);
        }

        void WallSamples(Line l, double step, FidAdmit admit, List<FSample> into)
        {
            double dx = l.BX - l.AX, dy = l.BY - l.AY, len = Math.Sqrt(dx * dx + dy * dy);
            if (len < 1e-6) return;
            double rx = dy / len, ry = -dx / len; // toward the front sector
            byte clsFront = OrientClass(rx, ry, 0), clsBack = OrientClass(-rx, -ry, 0);
            int pieces = Math.Max(1, (int)Math.Ceiling(len / step));
            double piece = len / pieces;
            Span<double> flo = stackalloc double[16], fhi = stackalloc double[16], blo = stackalloc double[16], bhi = stackalloc double[16];
            Span<int> p1 = stackalloc int[16], p2 = stackalloc int[16];
            int front = l.Front >= 0 && !sectors[l.Front].Control ? l.Front : -1, back = l.Back >= 0 && !sectors[l.Back].Control ? l.Back : -1;
            // Outdoors a one-sided line with no Daggerfall face beyond it is the converted map's outer edge (past the
            // walkable terrain), not an object. A one-sided line with ground or a model beyond it is measured.
            bool edgeCandidate = FidExterior && Beyond != null && (front < 0) != (back < 0);
            double outX = front < 0 ? rx : -rx, outY = front < 0 ? ry : -ry;
            for (int k = 0; k < pieces; k++)
            {
                double f = (k + 0.5) / pieces, x = l.AX + dx * f, y = l.AY + dy * f;
                if (edgeCandidate && !Beyond(x + outX * 12, y + outY * 12)) continue;
                int nf = Free(front, x, y, flo, fhi, p1, p2), nb = Free(back, x, y, blo, bhi, p1, p2);
                // Wall where one side is open and the other solid.
                Emit(flo, fhi, nf, blo, bhi, nb, x, y, rx, ry, clsFront, piece, step, admit, into);
                Emit(blo, bhi, nb, flo, fhi, nf, x, y, -rx, -ry, clsBack, piece, step, admit, into);
            }
        }

        // Samples the parts of the open intervals (lo, hi) not open in (olo, ohi), as a wall facing (nx, ny).
        static void Emit(Span<double> lo, Span<double> hi, int n, Span<double> olo, Span<double> ohi, int on, double x, double y, double nx, double ny, byte cls, double width, double step, FidAdmit admit, List<FSample> into)
        {
            for (int a = 0; a < n; a++)
            {
                double cur = lo[a];
                while (cur < hi[a])
                {
                    // The next part of [cur, hi) not covered by the other side's open intervals.
                    double next = hi[a];
                    bool covered = false;
                    for (int b = 0; b < on; b++)
                    {
                        if (olo[b] <= cur && ohi[b] > cur) { covered = true; next = Math.Min(hi[a], ohi[b]); break; }
                        if (olo[b] > cur && olo[b] < next) next = olo[b];
                    }
                    if (!covered && next - cur > 1e-6)
                    {
                        int count = Math.Max(1, (int)Math.Ceiling((next - cur) / step));
                        double dz = (next - cur) / count;
                        for (int c = 0; c < count; c++)
                        {
                            var s = new FSample { X = (float)x, Y = (float)y, Z = (float)(cur + (c + 0.5) * dz), NX = (float)nx, NY = (float)ny, NZ = 0, Area = (float)(width * dz), Cls = cls };
                            if (admit(ref s)) into.Add(s);
                        }
                    }
                    if (next <= cur) break;
                    cur = next;
                }
            }
        }
    }
}
