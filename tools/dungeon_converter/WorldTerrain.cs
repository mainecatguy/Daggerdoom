// The one Daggerfall height function for converted exteriors, and the world data the engine's overworld reads.
// It ports DefaultTerrainSampler, SetLocationTiles, BlendLocationTerrainJob, and SmoothLocationNeighbourhood.
// UZDoom/src/playsim/dd_treadmill.cpp holds the same math. Change both together: the town seam depends on it.
//
// Usage: dotnet run -c Release -- --world --out <dir outside the repo>
// Writes DDWORLD (smoothed heights) and DDLOCS (every location's blend rectangle). Both derive from game data.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static class WorldTerrain
{
    public const int TilesPerPixel = 128, WorldW = 1000, WorldH = 500;
    public const float MaxTerrain = 1539, Ocean = 3.4f * 8;

    public sealed class Place
    {
        public string Name, Region;
        public int RegionIndex, LocationIndex, X, Y, BlocksWide, BlocksHigh, OriginX, OriginY;
        public DFRegion.LocationTypes Type;
        public int RectX0, RectX1, RectY0, RectY1; // blend rectangle in tiles inside the map pixel, with Daggerfall Unity's clearance
        public bool HasRect;
    }

    public static WoodsFile Woods;
    public static readonly Dictionary<(int x, int y), Place> Places = new Dictionary<(int, int), Place>();
    static readonly Dictionary<(int, int), float[,]> cache = new Dictionary<(int, int), float[,]>();

    public static void Load(string arena2, MapsFile maps, BlocksFile blocks)
    {
        Woods = new WoodsFile(Path.Combine(arena2, "WOODS.WLD"), FileUsage.UseMemory, true);
        Places.Clear();
        cache.Clear();
        var bounds = new Dictionary<string, (int x0, int x1, int y0, int y1)?>();
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                int id = region.MapTable[l].MapId & 0x000fffff;
                var place = new Place
                {
                    Name = region.MapNames[l], Region = region.Name, RegionIndex = r, LocationIndex = l,
                    X = id % WorldW, Y = id / WorldW, Type = region.MapTable[l].LocationType,
                    BlocksWide = location.Exterior.ExteriorData.Width, BlocksHigh = location.Exterior.ExteriorData.Height,
                };
                // TerrainHelper.GetLocationTerrainTileOrigin
                place.OriginX = (TilesPerPixel - place.BlocksWide * 16) / 2;
                place.OriginY = (TilesPerPixel - place.BlocksHigh * 16) / 2;
                if (location.HasCustomLocationPosition()) { place.OriginX = 72; place.OriginY = 55; }
                int xmin = int.MaxValue, ymin = int.MaxValue, xmax = 0, ymax = 0;
                for (int by = 0; by < place.BlocksHigh; by++)
                    for (int bx = 0; bx < place.BlocksWide; bx++)
                    {
                        string name = maps.GetRmbBlockName(location, bx, by);
                        if (!bounds.TryGetValue(name, out var b)) bounds[name] = b = BlockBounds(blocks, name);
                        if (b == null) continue;
                        xmin = Math.Min(xmin, place.OriginX + bx * 16 + b.Value.x0); xmax = Math.Max(xmax, place.OriginX + bx * 16 + b.Value.x1);
                        ymin = Math.Min(ymin, place.OriginY + by * 16 + b.Value.y0); ymax = Math.Max(ymax, place.OriginY + by * 16 + b.Value.y1);
                    }
                if (xmin != int.MaxValue)
                {
                    int clearance = place.Type == DFRegion.LocationTypes.TownCity ? 3 : 2;
                    place.RectX0 = xmin - clearance; place.RectX1 = xmax + clearance;
                    place.RectY0 = ymin - clearance; place.RectY1 = ymax + clearance;
                    place.HasRect = true;
                }
                Places[(place.X, place.Y)] = place;
            }
        }
        SmoothLocationNeighbourhood();
    }

    static (int, int, int, int)? BlockBounds(BlocksFile blocks, string name)
    {
        DFBlock block;
        try { block = blocks.GetBlock(name); } catch (Exception) { return null; }
        if (block.RmbBlock.FldHeader.GroundData.GroundTiles == null) return null;
        var ground = block.RmbBlock.FldHeader.GroundData.GroundTiles;
        int x0 = int.MaxValue, y0 = int.MaxValue, x1 = -1, y1 = -1;
        for (int y = 0; y < 16; y++)
            for (int x = 0; x < 16; x++)
                if (ground[x, 15 - y].TextureRecord < 56)
                {
                    x0 = Math.Min(x0, x); x1 = Math.Max(x1, x);
                    y0 = Math.Min(y0, y); y1 = Math.Max(y1, y);
                }
        return x1 < 0 ? ((int, int, int, int)?)null : (x0, x1, y0, y1);
    }

    // TerrainHelper.SmoothLocationNeighbourhood with its default threshold.
    static void SmoothLocationNeighbourhood()
    {
        byte[] h = Woods.Buffer;
        for (int y = 1; y < WorldH - 1; y++)
            for (int x = 1; x < WorldW - 1; x++)
            {
                if (!Places.ContainsKey((x, y))) continue;
                float here = h[y * WorldW + x], gradient = Math.Abs(h[y * WorldW + x + 1] - here) + Math.Abs(h[(y + 1) * WorldW + x] - here);
                if (gradient <= 20) continue;
                float sum = 0;
                for (int b = y - 1; b < y + 2; b++)
                    for (int a = x - 1; a < x + 2; a++)
                        sum += h[b * WorldW + a];
                byte average = (byte)(sum / 9f);
                for (int b = y - 1; b < y + 2; b++)
                    for (int a = x - 1; a < x + 2; a++)
                        h[b * WorldW + a] = average;
            }
    }

    static float Cubic(float v0, float v1, float v2, float v3, float t)
    {
        float a = (v3 - v2) - (v0 - v1), b = (v0 - v1) - a, c = v2 - v0;
        return a * t * t * t + b * t * t + c * t + v1;
    }

    // Mathf.PerlinNoise is native Unity code. This surrogate is the same one the engine uses, so both maps agree.
    static readonly byte[] perm = BuildPermutation();
    static byte[] BuildPermutation()
    {
        var table = new byte[512];
        for (int i = 0; i < 256; i++) table[i] = (byte)i;
        uint seed = 0x5DEECE6u;
        for (int i = 255; i > 0; i--)
        {
            seed = unchecked(seed * 1664525u + 1013904223u);
            int j = (int)((seed >> 8) % (uint)(i + 1));
            (table[i], table[j]) = (table[j], table[i]);
        }
        Array.Copy(table, 0, table, 256, 256);
        return table;
    }

    public static float Perlin(float x, float y)
    {
        float fx = MathF.Floor(x), fy = MathF.Floor(y);
        int xi = (int)fx & 255, yi = (int)fy & 255;
        float xf = x - fx, yf = y - fy;
        float u = xf * xf * xf * (xf * (xf * 6 - 15) + 10), v = yf * yf * yf * (yf * (yf * 6 - 15) + 10);
        static float Grad(int h, float dx, float dy) => ((h & 1) != 0 ? -dx : dx) + ((h & 2) != 0 ? -dy : dy);
        float n00 = Grad(perm[perm[xi] + yi], xf, yf), n10 = Grad(perm[perm[xi + 1] + yi], xf - 1, yf);
        float n01 = Grad(perm[perm[xi] + yi + 1], xf, yf - 1), n11 = Grad(perm[perm[xi + 1] + yi + 1], xf - 1, yf - 1);
        float a = n00 + u * (n10 - n00), b = n01 + u * (n11 - n01);
        return Math.Clamp((a + v * (b - a)) * 0.5f + 0.5f, 0f, 1f);
    }

    static float[,] SampleRaw(int mx, int my)
    {
        const int dim = TilesPerPixel + 1;
        float div = (dim - 1) / 3f;
        byte[] shm = Woods.GetHeightMapValuesRange1Dim(mx - 2, my - 2, 4);
        byte[,] lhm = Woods.GetLargeHeightMapValuesRange(mx - 1, my, 3);
        float S4(int r, int c) => shm[r + c * 4];
        float L(int px, int py) => lhm[Math.Min(px, 8), Math.Min(py, 8)];
        var result = new float[dim, dim];
        for (int x = 0; x < dim; x++)
            for (int y = 0; y < dim; y++)
            {
                float rx = x / div, ry = y / div;
                int ix = (int)MathF.Floor(rx), iy = (int)MathF.Floor(ry);
                float sx = x / (float)(dim - 1), sy = y / (float)(dim - 1), fx = (x - ix * div) / div, fy = (y - iy * div) / div;
                float a = Cubic(S4(0, 3), S4(1, 3), S4(2, 3), S4(3, 3), sx), b = Cubic(S4(0, 2), S4(1, 2), S4(2, 2), S4(3, 2), sx);
                float c = Cubic(S4(0, 1), S4(1, 1), S4(2, 1), S4(3, 1), sx), d = Cubic(S4(0, 0), S4(1, 0), S4(2, 0), S4(3, 0), sx);
                float h = Cubic(a, b, c, d, sy) * 8f;
                a = Cubic(L(ix, iy), L(ix + 1, iy), L(ix + 2, iy), L(ix + 3, iy), fx);
                b = Cubic(L(ix, iy + 1), L(ix + 1, iy + 1), L(ix + 2, iy + 1), L(ix + 3, iy + 1), fx);
                c = Cubic(L(ix, iy + 2), L(ix + 1, iy + 2), L(ix + 2, iy + 2), L(ix + 3, iy + 2), fx);
                d = Cubic(L(ix, iy + 3), L(ix + 1, iy + 3), L(ix + 2, iy + 3), L(ix + 3, iy + 3), fx);
                h += Cubic(a, b, c, d, fy) * 4f;
                int nx = mx * (dim - 1) + x, ny = (MapsFile.MaxMapPixelY - my) * (dim - 1) + y;
                h += Math.Clamp(Perlin(nx * 0.3f, ny * 0.3f) * 0.5f, 0, 1) * Math.Clamp(Perlin(nx * 0.9f, ny * 0.9f) * 0.5f, 0, 1) * 10f;
                if (h < Ocean) h = Ocean;
                result[x, y] = Math.Clamp(h / MaxTerrain, 0, 1);
            }
        return result;
    }

    // BlendLocationTerrainJob. The average is summed in Daggerfall Unity's index order, in single precision.
    static void Blend(float[,] h, Place p)
    {
        const int dim = TilesPerPixel + 1;
        float sum = 0;
        for (int x = 0; x < dim; x++)
            for (int y = 0; y < dim; y++)
                sum += h[x, y];
        float target = sum / (dim * dim);
        float x0 = p.RectX0 / (float)TilesPerPixel, x1 = p.RectX1 / (float)TilesPerPixel, y0 = p.RectY0 / (float)TilesPerPixel, y1 = p.RectY1 / (float)TilesPerPixel;
        float left = 1 / x0, right = 1 / (1 - x1), top = 1 / y0, bottom = 1 / (1 - y1);
        for (int y = 0; y < dim; y++)
        {
            float v = y / (float)(dim - 1);
            bool insideY = v >= y0 && v <= y1;
            for (int x = 0; x < dim; x++)
            {
                float u = x / (float)(dim - 1), strength = 0;
                bool insideX = u >= x0 && u <= x1;
                if (insideX && insideY) { h[x, y] = target; continue; }
                if (insideY) strength = u <= x0 ? u * left : (1 - u) * right;
                else if (insideX) strength = v <= y0 ? v * top : (1 - v) * bottom;
                else strength = (u <= x0 ? u * left : (1 - u) * right) * (v <= y0 ? v * top : (1 - v) * bottom);
                h[x, y] += (target - h[x, y]) * Math.Clamp(strength, 0, 1);
            }
        }
    }

    public static float[,] Pixel(int mx, int my)
    {
        if (cache.TryGetValue((mx, my), out var h)) return h;
        h = SampleRaw(mx, my);
        if (Places.TryGetValue((mx, my), out var place) && place.HasRect) Blend(h, place);
        return cache[(mx, my)] = h;
    }

    // Normalized height at a global tile vertex. Global Y runs north, as in the engine: gy = (499 - my) * 128 + y.
    public static float Height(int gx, int gy)
    {
        int px = Math.Clamp(FloorDiv(gx, TilesPerPixel), 0, WorldW - 1), north = Math.Clamp(FloorDiv(gy, TilesPerPixel), 0, WorldH - 1);
        return Pixel(px, WorldH - 1 - north)[Math.Clamp(gx - px * TilesPerPixel, 0, TilesPerPixel), Math.Clamp(gy - north * TilesPerPixel, 0, TilesPerPixel)];
    }

    public static int FloorDiv(int a, int b) => a >= 0 ? a / b : -((-a + b - 1) / b);

    // Adjacent locations (8-neighbour) that must share one exterior map.
    public static List<Place> GroupOf(Place start)
    {
        var group = new List<Place> { start };
        var seen = new HashSet<(int, int)> { (start.X, start.Y) };
        for (int n = 0; n < group.Count; n++)
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++)
                {
                    var key = (group[n].X + dx, group[n].Y + dy);
                    if (seen.Contains(key) || !Places.TryGetValue(key, out var other)) continue;
                    seen.Add(key);
                    group.Add(other);
                }
        return group;
    }

    // Every location group in a fixed order. The list index is the group's id, and its first place is the map's primary location.
    public static List<List<Place>> Groups()
    {
        var groups = new List<List<Place>>();
        var seen = new HashSet<(int, int)>();
        foreach (var place in Places.Values.OrderBy(p => p.Y).ThenBy(p => p.X))
        {
            if (seen.Contains((place.X, place.Y))) continue;
            var group = GroupOf(place);
            foreach (var member in group) seen.Add((member.X, member.Y));
            groups.Add(group);
        }
        return groups;
    }

    public static int RunExport(string[] args)
    {
        string Arg(string name, string fallback) { int at = Array.IndexOf(args, name); return at >= 0 ? args[at + 1] : fallback; }
        string outDir = Arg("--out", null), arena2 = Arg("--arena2", @"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2");
        if (outDir == null) { Console.Error.WriteLine("usage: --world --out <dir>"); return 2; }
        Directory.CreateDirectory(outDir);
        var clock = System.Diagnostics.Stopwatch.StartNew();
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        byte[] before = File.ReadAllBytes(Path.Combine(arena2, "WOODS.WLD"));
        Load(arena2, maps, blocks);

        // DDWORLD: the smoothed small map, then each pixel's inner 3x3 of the large map, as GetLargeHeightMapValuesRange reads it.
        int heightOffset = BitConverter.ToInt32(before, 28), changed = 0;
        for (int i = 0; i < WorldW * WorldH; i++) if (before[heightOffset + i] != Woods.Buffer[i]) changed++;
        using (var w = new BinaryWriter(File.Create(Path.Combine(outDir, "DDWORLD"))))
        {
            w.Write(Encoding.ASCII.GetBytes("DDW1"));
            w.Write((ushort)WorldW); w.Write((ushort)WorldH);
            w.Write(Woods.Buffer, 0, WorldW * WorldH);
            var large = new byte[9];
            for (int i = 0; i < WorldW * WorldH; i++)
            {
                int o = BitConverter.ToInt32(before, 144 + i * 4) + 22;
                for (int b = 0; b < 3; b++)
                    Array.Copy(before, o + (3 - b) * 5 + 1, large, b * 3, 3);
                w.Write(large);
            }
        }
        int noRect = 0;
        using (var w = new BinaryWriter(File.Create(Path.Combine(outDir, "DDLOCS"))))
        {
            var withRect = Places.Values.Where(p => { if (!p.HasRect) noRect++; return p.HasRect; }).OrderBy(p => p.Y).ThenBy(p => p.X).ToList();
            w.Write(Encoding.ASCII.GetBytes("DDL1"));
            w.Write(withRect.Count);
            foreach (var p in withRect)
            {
                w.Write((short)p.X); w.Write((short)p.Y);
                w.Write((short)p.RectX0); w.Write((short)p.RectX1); w.Write((short)p.RectY0); w.Write((short)p.RectY1);
            }
        }
        var seen = new HashSet<(int, int)>();
        var report = new StringBuilder($"locations {Places.Count}\nwithout a ground rectangle {noRect}\nsmall-map bytes changed by smoothing {changed}\n");
        int groups = 0;
        foreach (var p in Places.Values.OrderBy(p => p.Y).ThenBy(p => p.X))
        {
            if (seen.Contains((p.X, p.Y))) continue;
            var group = GroupOf(p);
            foreach (var g in group) seen.Add((g.X, g.Y));
            if (group.Count < 2) continue;
            groups++;
            report.Append("group: " + string.Join("; ", group.Select(g => $"{g.Region}/{g.Name} {g.Type} px {g.X},{g.Y} {g.BlocksWide}x{g.BlocksHigh} rect {g.RectX0}..{g.RectX1},{g.RectY0}..{g.RectY1}")) + "\n");
        }
        report.Append($"groups {groups}\nexport {clock.ElapsedMilliseconds} ms\n");
        File.WriteAllText(Path.Combine(outDir, "world.report.txt"), report.ToString());
        Console.Write(report);
        return 0;
    }
}
