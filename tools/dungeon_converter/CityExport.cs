// Converts a Daggerfall city (RMB blocks) and its surrounding terrain into a UDMF map plus a mesh package.
// Usage: dotnet run -c Release -- --city "Daggerfall" --region "Daggerfall" --out <dir> [--margin 12] [--visual-pixels 1] [--raster 8]
//
// The player sees real Daggerfall models, ground tiles, billboards, and sky. Collision is separate:
// the flattened city area is rasterized into sectors, and the terrain around it is one sloped sector per triangle.
//
// Coordinates: doomX = S * (worldX - originX), doomY = S * (worldZ - originZ), doomZ = S * (dfHeight - groundHeight),
// where S is the world scale. The DFCITY lump records the origin and ground height so overworld travel can connect later.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;

static partial class Program
{
    static class City
    {
        const int TilesPerPixel = 128, TileDf = 256, TilesPerBlock = 16, RmbDf = 4096;
        const double MaxTerrain = 1539, TerrainScale = 1.5, UnityToDf = 40, HeightToDf = MaxTerrain * TerrainScale * UnityToDf;
        const float Ocean = 3.4f * 8, Beach = 5f * 8;
        const uint GateOpen = 446, GateClosed = 447;
        const int NoSector = -1;

        static double S => PlayerScale.DoomUnitsPerDaggerfallUnit;
        static double DoomTile => TileDf * S;

        static WoodsFile woods;
        static readonly Dictionary<(int, int), float[,]> pixels = new Dictionary<(int, int), float[,]>();
        static int cityX, cityY;
        static float target;
        static int flatX0, flatX1, flatY0, flatY1; // flattened tile rect, in vertices
        static byte[,] locationTiles;

        public static int Run(string[] args)
        {
            string Arg(string name, string fallback) { int at = Array.IndexOf(args, name); return at >= 0 ? args[at + 1] : fallback; }
            string cityName = Arg("--city", null), regionName = Arg("--region", cityName), outDir = Arg("--out", null);
            string arena2 = Arg("--arena2", @"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2");
            // Margin 16 and up crashes the current engine build during map load. The same build with a 64 MB stack loads margin 32, so the default stays below the limit.
            int margin = int.Parse(Arg("--margin", "12")), visualPixels = int.Parse(Arg("--visual-pixels", "1")), rasterCell = int.Parse(Arg("--raster", "8"));
            PlayerScale.DoomUnitsPerDaggerfallUnit = double.Parse(Arg("--world-scale", "0.75"), CultureInfo.InvariantCulture);
            if (cityName == null || outDir == null) { Console.Error.WriteLine("usage: --city <name> [--region <name>] --out <dir>"); return 2; }
            if (Math.Abs(DoomTile / rasterCell - Math.Round(DoomTile / rasterCell)) > 1e-9) { Console.Error.WriteLine("--raster must divide the Doom tile size"); return 2; }
            Directory.CreateDirectory(outDir);
            var clock = System.Diagnostics.Stopwatch.StartNew();

            var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
            if (!FindCity(maps, regionName, cityName, out DFLocation location)) { Console.Error.WriteLine("city not found: " + cityName); return 1; }
            var pixel = MapsFile.LongitudeLatitudeToMapPixel(location.MapTableData.Longitude, location.MapTableData.Latitude);
            cityX = pixel.X; cityY = pixel.Y;
            int blocksWide = location.Exterior.ExteriorData.Width, blocksHigh = location.Exterior.ExteriorData.Height;
            int originTileX = (TilesPerPixel - blocksWide * TilesPerBlock) / 2, originTileY = (TilesPerPixel - blocksHigh * TilesPerBlock) / 2;
            Console.WriteLine($"{location.RegionName}/{location.Name}: map pixel {cityX},{cityY}, {blocksWide}x{blocksHigh} blocks, climate {location.Climate.WorldClimate} base {location.Climate.ClimateType}, ground {location.Climate.GroundArchive}, nature {location.Climate.NatureArchive}, sky {location.Climate.SkyBase}");

            woods = new WoodsFile(Path.Combine(arena2, "WOODS.WLD"), FileUsage.UseMemory, true);
            var blocksFile = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
            var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
            var blocks = new DFBlock[blocksWide * blocksHigh];
            for (int y = 0; y < blocksHigh; y++)
                for (int x = 0; x < blocksWide; x++)
                    blocks[y * blocksWide + x] = blocksFile.GetBlock(maps.GetRmbBlockName(location, x, y));

            PrepareCityTerrain(blocks, blocksWide, blocksHigh, originTileX, originTileY);
            double groundDf = target * HeightToDf;
            double originDfX = TilesPerPixel / 2 * TileDf, originDfZ = originDfX;

            var scene = new Scene(arena2, location, originDfX, originDfZ);
            for (int y = 0; y < blocksHigh; y++)
                for (int x = 0; x < blocksWide; x++)
                    scene.AddBlock(blocks[y * blocksWide + x], arch, originTileX * TileDf + x * RmbDf, originTileY * TileDf + y * RmbDf);
            scene.AddTerrain(-visualPixels * TilesPerPixel, (visualPixels + 1) * TilesPerPixel);
            scene.AddNature(-margin, TilesPerPixel + margin);
            Console.WriteLine($"scene: {scene.Models} models ({scene.Missing} missing), {scene.Gates} gates, {scene.Colliders.Count} collider triangles, {scene.Flats.Count} billboards, {scene.Triangles} mesh triangles [{clock.ElapsedMilliseconds} ms]");

            foreach (var probe in (Arg("--probe", "")).Split(';', StringSplitOptions.RemoveEmptyEntries))
                Collision.Probes.Add((double.Parse(probe.Split(',')[0], CultureInfo.InvariantCulture), double.Parse(probe.Split(',')[1], CultureInfo.InvariantCulture)));
            var collision = new Collision(rasterCell, margin);
            collision.Rasterize(scene.Colliders);
            var map = collision.Build();
            string slug = new string(cityName.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant() + "_city";
            string wad = Path.Combine(outDir, slug + ".wad");
            WriteWad(wad, map.Text, "");
            File.WriteAllText(Path.Combine(outDir, slug + ".routes.txt"), collision.Routes());

            string metadata = FormattableString.Invariant($"scale {S}\nmappixel {cityX} {cityY}\noriginworld {cityX * 32768 + originDfX} {(499 - cityY) * 32768 + originDfZ}\ngroundheight {groundDf}\nflat {flatX0} {flatX1} {flatY0} {flatY1}\nstart {map.StartX} {map.StartY}\n");
            string package = Path.Combine(outDir, slug + "_mesh.pk3");
            scene.WritePackage(package, location, metadata);

            string report = ( // the project sets InvariantGlobalization
                $"city {location.RegionName}/{location.Name}\nmap pixel {cityX},{cityY}\nblocks {blocksWide}x{blocksHigh}\nflat tiles x {flatX0}..{flatX1} y {flatY0}..{flatY1}\nground height {groundDf:F1} df units\n" +
                $"models {scene.Models} missing {scene.Missing} gates {scene.Gates}\nmesh triangles {scene.Triangles} batches {scene.BatchCount} textures unreadable {scene.BadTextures}\nbillboards {scene.Flats.Count}\n" +
                $"raster {collision.W}x{collision.H} at {rasterCell} units\nopen cells {collision.OpenCells} solid cells {collision.SolidCells} removed unreachable {collision.RemovedCells} kept regions {collision.KeptRegions}\nouter edge reachable from start {collision.ReachesEdge}\n" +
                $"sectors {map.Sectors} (city {map.CitySectors}, terrain {map.TerrainSectors}) lines {map.Lines} vertices {map.Vertices}\nstart {map.StartX},{map.StartY}\nwad {new FileInfo(wad).Length / 1024} KiB\nmesh package {new FileInfo(package).Length / 1024} KiB\nconvert time {clock.ElapsedMilliseconds} ms\n");
            File.WriteAllText(Path.Combine(outDir, slug + ".stats.txt"), report);
            Console.WriteLine(report);
            return scene.BadTextures == 0 && scene.Missing == 0 ? 0 : 1;
        }

        static bool FindCity(MapsFile maps, string region, string name, out DFLocation location)
        {
            for (int r = 0; r < maps.RegionCount; r++)
            {
                if (!maps.LoadRegion(r)) continue;
                var data = maps.GetRegion(r);
                if (data.MapNames == null || !string.Equals(data.Name, region, StringComparison.OrdinalIgnoreCase)) continue;
                for (int l = 0; l < data.LocationCount; l++)
                    if (string.Equals(data.MapNames[l], name, StringComparison.OrdinalIgnoreCase)) { location = maps.GetLocation(r, l); return true; }
            }
            location = default;
            return false;
        }

        // ---- Terrain heights: a port of DefaultTerrainSampler and BlendLocationTerrainJob ----

        static float Cubic(float v0, float v1, float v2, float v3, float t)
        {
            float a = (v3 - v2) - (v0 - v1), b = (v0 - v1) - a, c = v2 - v0;
            return a * t * t * t + b * t * t + c * t + v1;
        }

        // Mathf.PerlinNoise is native Unity code. This classic Perlin surrogate has the same frequencies and range, as in the terrain treadmill spike.
        static readonly int[] perm = BuildPermutation();
        static int[] BuildPermutation()
        {
            var random = new Random(417028);
            var p = Enumerable.Range(0, 256).OrderBy(_ => random.Next()).ToArray();
            return p.Concat(p).ToArray();
        }
        static float Perlin(float x, float y)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
            float fx = x - xi, fy = y - yi;
            xi &= 255; yi &= 255;
            float Fade(float t) => t * t * t * (t * (t * 6 - 15) + 10);
            float Grad(int h, float dx, float dy) => ((h & 1) == 0 ? dx : -dx) + ((h & 2) == 0 ? dy : -dy);
            float L(float a, float b, float t) => a + (b - a) * t;
            float u = Fade(fx), v = Fade(fy);
            float n = L(L(Grad(perm[perm[xi] + yi], fx, fy), Grad(perm[perm[xi + 1] + yi], fx - 1, fy), u),
                        L(Grad(perm[perm[xi] + yi + 1], fx, fy - 1), Grad(perm[perm[xi + 1] + yi + 1], fx - 1, fy - 1), u), v);
            return Math.Clamp((n + 1) / 2, 0, 1);
        }

        static float[,] SamplePixel(int mx, int my)
        {
            const int dim = TilesPerPixel + 1;
            float div = (dim - 1) / 3f;
            byte[] shm = woods.GetHeightMapValuesRange1Dim(mx - 2, my - 2, 4);
            byte[,] lhm = woods.GetLargeHeightMapValuesRange(mx - 1, my, 3);
            float S4(int r, int c) => shm[r + c * 4];
            var result = new float[dim, dim];
            for (int x = 0; x < dim; x++)
                for (int y = 0; y < dim; y++)
                {
                    float rx = x / div, ry = y / div;
                    int ix = (int)Math.Floor(rx), iy = (int)Math.Floor(ry);
                    float sx = x / (float)(dim - 1), sy = y / (float)(dim - 1), fx = (x - ix * div) / div, fy = (y - iy * div) / div;
                    float a = Cubic(S4(0, 3), S4(1, 3), S4(2, 3), S4(3, 3), sx), b = Cubic(S4(0, 2), S4(1, 2), S4(2, 2), S4(3, 2), sx);
                    float c = Cubic(S4(0, 1), S4(1, 1), S4(2, 1), S4(3, 1), sx), d = Cubic(S4(0, 0), S4(1, 0), S4(2, 0), S4(3, 0), sx);
                    float h = Cubic(a, b, c, d, sy) * 8f;
                    float L(int px, int py) => lhm[Math.Min(px, 8), Math.Min(py, 8)];
                    a = Cubic(L(ix, iy), L(ix + 1, iy), L(ix + 2, iy), L(ix + 3, iy), fx);
                    b = Cubic(L(ix, iy + 1), L(ix + 1, iy + 1), L(ix + 2, iy + 1), L(ix + 3, iy + 1), fx);
                    c = Cubic(L(ix, iy + 2), L(ix + 1, iy + 2), L(ix + 2, iy + 2), L(ix + 3, iy + 2), fx);
                    d = Cubic(L(ix, iy + 3), L(ix + 1, iy + 3), L(ix + 2, iy + 3), L(ix + 3, iy + 3), fx);
                    h += Cubic(a, b, c, d, fy) * 4f;
                    int nx = mx * (dim - 1) + x, ny = (MapsFile.MaxMapPixelY - my) * (dim - 1) + y;
                    h += Math.Clamp(Perlin(nx * 0.3f, ny * 0.3f) * 0.5f, 0, 1) * Math.Clamp(Perlin(nx * 0.9f, ny * 0.9f) * 0.5f, 0, 1) * 10f;
                    if (h < Ocean) h = Ocean;
                    result[x, y] = Math.Clamp(h / (float)MaxTerrain, 0, 1);
                }
            return result;
        }

        static void PrepareCityTerrain(DFBlock[] blocks, int wide, int high, int originX, int originY)
        {
            locationTiles = new byte[TilesPerPixel, TilesPerPixel];
            int xmin = int.MaxValue, ymin = int.MaxValue, xmax = 0, ymax = 0;
            for (int by = 0; by < high; by++)
                for (int bx = 0; bx < wide; bx++)
                {
                    var ground = blocks[by * wide + bx].RmbBlock.FldHeader.GroundData.GroundTiles;
                    for (int ty = 0; ty < TilesPerBlock; ty++)
                        for (int tx = 0; tx < TilesPerBlock; tx++)
                        {
                            var tile = ground[tx, TilesPerBlock - 1 - ty];
                            if (tile.TextureRecord >= 56) continue;
                            int x = originX + bx * TilesPerBlock + tx, y = originY + by * TilesPerBlock + ty;
                            xmin = Math.Min(xmin, x); xmax = Math.Max(xmax, x); ymin = Math.Min(ymin, y); ymax = Math.Max(ymax, y);
                            locationTiles[x, y] = tile.TileBitfield == 0 ? byte.MaxValue : tile.TileBitfield;
                        }
                }
            flatX0 = xmin - 3; flatX1 = xmax + 3; flatY0 = ymin - 3; flatY1 = ymax + 3;

            var h = SamplePixel(cityX, cityY);
            double sum = 0;
            foreach (float v in h) sum += v;
            target = (float)(sum / h.Length);
            float x0 = flatX0 / (float)TilesPerPixel, x1 = flatX1 / (float)TilesPerPixel, y0 = flatY0 / (float)TilesPerPixel, y1 = flatY1 / (float)TilesPerPixel;
            float left = 1 / x0, right = 1 / (1 - x1), top = 1 / y0, bottom = 1 / (1 - y1);
            for (int y = 0; y <= TilesPerPixel; y++)
            {
                float v = y / (float)TilesPerPixel;
                bool insideY = v >= y0 && v <= y1;
                for (int x = 0; x <= TilesPerPixel; x++)
                {
                    float u = x / (float)TilesPerPixel, strength = 0;
                    bool insideX = u >= x0 && u <= x1;
                    if (insideX || insideY)
                    {
                        if (insideY && u <= x0) strength = u * left;
                        else if (insideY && u >= x1) strength = (1 - u) * right;
                        else if (insideX && v <= y0) strength = v * top;
                        else if (insideX && v >= y1) strength = (1 - v) * bottom;
                    }
                    else
                    {
                        float xs = u <= x0 ? u * left : (1 - u) * right, ys = v <= y0 ? v * top : (1 - v) * bottom;
                        strength = xs * ys; // BilinearInterpolator(0, 0, 0, 1, xs, ys)
                    }
                    h[x, y] = insideX && insideY ? target : h[x, y] + (target - h[x, y]) * strength;
                }
            }
            pixels[(cityX, cityY)] = h;
        }

        static int FloorDiv(int a, int b) => a >= 0 ? a / b : -((-a + b - 1) / b);

        // Normalized height at a tile vertex relative to the city's map pixel. +y is north, toward smaller map pixel Y.
        static float Height(int tx, int ty)
        {
            int px = FloorDiv(tx, TilesPerPixel), py = FloorDiv(ty, TilesPerPixel);
            var key = (cityX + px, cityY - py);
            if (!pixels.TryGetValue(key, out var h)) pixels[key] = h = SamplePixel(key.Item1, key.Item2);
            return h[tx - px * TilesPerPixel, ty - py * TilesPerPixel];
        }

        static double DoomZ(int tx, int ty) => (Height(tx, ty) - target) * HeightToDf * S;
        static double DoomXY(int t) => (t - TilesPerPixel / 2) * DoomTile;

        // ---- Ground tiles: a port of DefaultTerrainTexturing ----

        static readonly byte[] lookup = BuildLookup();
        static byte Make(int index, bool rotate, bool flip) => (byte)(index + (rotate ? 64 : 0) + (flip ? 128 : 0));
        static byte[] BuildLookup()
        {
            var t = new byte[64];
            void Range(int baseStart, int baseEnd, int shape, int saddle, bool reverse, int o)
            {
                var forward = new (int d, bool r, bool f)[] { (-1, false, false), (0, true, false), (0, false, true), (1, true, false), (0, false, false), (1, false, false), (-2, false, false), (2, true, false), (0, true, true), (-2, true, false), (1, false, true), (2, false, true), (1, true, true), (2, false, false), (2, true, true), (-3, false, false) };
                var backward = new (int d, bool r, bool f)[] { (-1, false, false), (2, true, true), (2, false, false), (1, true, true), (2, false, true), (1, false, true), (-2, true, false), (0, true, true), (2, true, false), (-2, false, false), (1, false, false), (0, false, false), (1, true, false), (0, false, true), (0, true, false), (-3, false, false) };
                var table = reverse ? backward : forward;
                for (int i = 0; i < 16; i++)
                {
                    int index = table[i].d == -1 ? baseStart : table[i].d == -3 ? baseEnd : table[i].d == -2 ? saddle : shape + table[i].d;
                    t[o + i] = Make(index, table[i].r, table[i].f);
                }
            }
            Range(0, 1, 5, 48, false, 0);
            Range(2, 1, 10, 51, true, 16);
            Range(2, 3, 15, 53, false, 32);
            Range(3, 3, 15, 53, true, 48);
            return t;
        }

        static float Noise(float x, float y)
        {
            float total = 0, frequency = 0.05f, amplitude = 0.9f;
            for (int i = 0; i < 3; i++) { total += Perlin(417028 + x * frequency, 417028 + y * frequency) * amplitude; frequency *= 2; amplitude *= 0.4f; }
            return Math.Clamp(total, -1, 1);
        }

        static int TileClass(int tx, int ty)
        {
            float height = Height(tx, ty) * (float)MaxTerrain;
            if (height <= Ocean) return 0;
            uint hash = (uint)(tx * 73856093) ^ (uint)(ty * 19349663);
            hash = (hash ^ (hash >> 13)) * 1274126177u;
            float jitter = ((hash >> 8) & 0xffff) / 65535f * 3f - 1.5f; // Stands in for Unity's Random.CreateFromIndex
            if (height <= Beach + jitter) return 1;
            int px = FloorDiv(tx, TilesPerPixel), py = FloorDiv(ty, TilesPerPixel);
            int lat = (cityX + px) * TilesPerPixel + (tx - px * TilesPerPixel);
            int lon = MapsFile.MaxWorldTileCoordZ - (cityY - py) * TilesPerPixel + (ty - py * TilesPerPixel);
            float weight = Noise(lat, lon);
            return weight < 0.5f ? 1 : weight > 0.95f ? 3 : 2;
        }

        static byte TileAt(int tx, int ty)
        {
            if (tx >= 0 && ty >= 0 && tx < TilesPerPixel && ty < TilesPerPixel && locationTiles[tx, ty] != 0)
                return locationTiles[tx, ty] == byte.MaxValue ? (byte)0 : locationTiles[tx, ty];
            int b0 = TileClass(tx, ty), b1 = TileClass(tx + 1, ty), b2 = TileClass(tx, ty + 1), b3 = TileClass(tx + 1, ty + 1);
            int shape = (b0 & 1) | (b1 & 1) << 1 | (b2 & 1) << 2 | (b3 & 1) << 3;
            return lookup[shape | ((b0 + b1 + b2 + b3) >> 2) << 4];
        }

        // ---- Visual scene ----

        sealed class Scene
        {
            public readonly List<(V3 a, V3 b, V3 c)> Colliders = new List<(V3, V3, V3)>();
            public readonly List<(int archive, int record, double x, double y, double z, double sx, double sy)> Flats = new List<(int, int, double, double, double, double, double)>();
            public int Models, Missing, Gates, BadTextures, BatchCount;
            public int Triangles => batches.Values.Sum(b => b.Count) / 24;

            readonly string arena2;
            readonly DFLocation location;
            readonly double originX, originZ;
            readonly Dictionary<(int archive, int record), List<float>> batches = new Dictionary<(int, int), List<float>>();
            readonly Dictionary<int, TextureFile> files = new Dictionary<int, TextureFile>();
            readonly Dictionary<uint, DFMesh> meshes = new Dictionary<uint, DFMesh>();
            readonly Dictionary<(int, int), (double w, double h, double texW, double texH)> flatSizes = new Dictionary<(int, int), (double, double, double, double)>();

            public Scene(string arena2, DFLocation location, double originX, double originZ)
            {
                this.arena2 = arena2; this.location = location; this.originX = originX; this.originZ = originZ;
            }

            TextureFile Archive(int a)
            {
                if (files.TryGetValue(a, out var f)) return f;
                string path = Path.Combine(arena2, TextureFile.IndexToFileName(a));
                f = File.Exists(path) ? new TextureFile(path, FileUsage.UseMemory, true) : null;
                return files[a] = f;
            }

            static readonly HashSet<int> ClimateSets = new HashSet<int> { 2, 7, 9, 10, 12, 13, 14, 15, 17, 18, 26, 27, 29, 30, 35, 36, 38, 39, 42, 43, 58, 59, 61, 62, 64, 65, 69, 70, 79, 80, 82, 83, 74,
                11, 16, 19, 20, 22, 23, 24, 25, 28, 37, 40, 41, 44, 45, 47, 48, 60, 63, 66, 68 };

            // ClimateSwaps.ApplyClimate for summer.
            int Swap(int archive, int record)
            {
                if (archive % 100 == 74 && record == 3) return archive;
                if (archive >= 500 || archive is 75 or 76 or 77 or 79 or 80 or 82 or 83) return archive;
                int set = archive % 100;
                // Same whitelist as ClimateSwaps.GetClimateTextureInfo; other sets (wagon 88, hedges, planks, furniture) never swap.
                if (!ClimateSets.Contains(set)) return archive;
                string setName = ((DFLocation.ClimateTextureSet)set).ToString();
                if (location.Climate.ClimateType == DFLocation.ClimateBaseType.Swamp && setName == "Interior_MarbleFloors") return archive;
                return (int)location.Climate.ClimateType + set;
            }

            void AddModel(Arch3dFile arch, uint id, V3 position, double rx, double ry, double rz, V3 scale, V3 parent, double parentYaw)
            {
                if (id == GateClosed) id = GateOpen; // Gates stand open so the city connects to the terrain.
                if (id == GateOpen) Gates++;
                if (!meshes.TryGetValue(id, out var mesh))
                {
                    int record = arch.GetRecordIndex(id);
                    if (record < 0) { Missing++; return; }
                    meshes[id] = mesh = arch.GetMesh(record);
                }
                Models++;
                V3 Place(double x, double y, double z)
                {
                    var p = Rotate(new V3(x * scale.X, y * scale.Y, z * scale.Z), rx, ry, rz) + position;
                    return Rotate(p, 0, parentYaw, 0) + parent;
                }
                foreach (var sub in mesh.SubMeshes)
                {
                    var source = Archive(sub.TextureArchive);
                    if (source == null || sub.TextureRecord >= source.RecordCount) { BadTextures++; continue; }
                    double w = source.GetWidth(sub.TextureRecord), h = source.GetHeight(sub.TextureRecord);
                    int swapped = Swap(sub.TextureArchive, sub.TextureRecord);
                    var replacement = Archive(swapped);
                    if (replacement == null || sub.TextureRecord >= replacement.RecordCount) swapped = sub.TextureArchive;
                    var key = (swapped, sub.TextureRecord);
                    if (!batches.TryGetValue(key, out var v)) batches[key] = v = new List<float>();
                    foreach (var plane in sub.Planes)
                    {
                        var world = plane.Points.Select(p => Place(p.X, -p.Y, p.Z)).ToArray();
                        var n = Rotate(Rotate(new V3(plane.Points[0].NX, -plane.Points[0].NY, plane.Points[0].NZ), rx, ry, rz), 0, parentYaw, 0);
                        double length = Math.Sqrt(n.X * n.X + n.Y * n.Y + n.Z * n.Z);
                        if (length < 1e-6) length = 1;
                        void Emit(int i)
                        {
                            var at = world[i];
                            v.Add((float)((at.X - originX) * S)); v.Add((float)(at.Y * S)); v.Add((float)((at.Z - originZ) * S));
                            v.Add((float)(plane.Points[i].U / w)); v.Add((float)(plane.Points[i].V / h));
                            v.Add((float)(n.X / length)); v.Add((float)(n.Y / length)); v.Add((float)(n.Z / length));
                        }
                        for (int i = 1; i + 1 < world.Length; i++)
                        {
                            Emit(0); Emit(i + 1); Emit(i);
                            V3 D(V3 p) => new V3((p.X - originX) * S, (p.Z - originZ) * S, p.Y * S);
                            Colliders.Add((D(world[0]), D(world[i]), D(world[i + 1])));
                        }
                    }
                }
            }

            void AddFlat(int archive, int record, double x, double up, double z)
            {
                var file = Archive(archive);
                if (file == null || record >= file.RecordCount) { BadTextures++; return; }
                if (!flatSizes.TryGetValue((archive, record), out var size))
                {
                    var raw = file.GetSize(record);
                    var scale = file.GetScale(record);
                    int xChange = (int)(raw.Width * (scale.Width / (double)BlocksFile.ScaleDivisor)), yChange = (int)(raw.Height * (scale.Height / (double)BlocksFile.ScaleDivisor));
                    flatSizes[(archive, record)] = size = (raw.Width + xChange, raw.Height + yChange, raw.Width, raw.Height);
                }
                Flats.Add((archive, record, (x - originX) * S, (z - originZ) * S, up * S, size.w / size.texW * S, size.h / size.texH * S));
            }

            public void AddBlock(DFBlock block, Arch3dFile arch, double blockX, double blockZ)
            {
                const double toRad = Math.PI / 180;
                double div = BlocksFile.RotationDivisor;
                var data = block.RmbBlock;
                var origin = new V3(blockX, 2, blockZ);
                V3 ScaleOf(DFBlock.RmbBlock3dObjectRecord o) => new V3(o.XScale == 0 ? 1 : o.XScale, o.YScale == 0 ? 1 : o.YScale, o.ZScale == 0 ? 1 : o.ZScale);
                foreach (var sub in data.SubRecords)
                {
                    var parent = origin + new V3(sub.XPos, 0, RmbDf - sub.ZPos);
                    double yaw = -sub.YRotation / div * toRad;
                    foreach (var o in sub.Exterior.Block3dObjectRecords)
                        AddModel(arch, o.ModelIdNum, new V3(o.XPos, -o.YPos, o.ZPos), -o.XRotation / div * toRad, -o.YRotation / div * toRad, -o.ZRotation / div * toRad, ScaleOf(o), parent, yaw);
                    foreach (var f in sub.Exterior.BlockFlatObjectRecords)
                    {
                        if (f.TextureArchive == 199 || f.FactionID != 0) continue; // editor markers and NPCs are out of scope
                        int archive = f.TextureArchive;
                        double fx = origin.X + sub.XPos + f.XPos, fy = origin.Y - f.YPos - 6, fz = origin.Z - sub.ZPos + f.ZPos + RmbDf;
                        if (archive >= (int)DFLocation.ClimateTextureSet.Nature_RainForest && archive <= (int)DFLocation.ClimateTextureSet.Nature_Mountains_Snow)
                            archive = location.Climate.NatureArchive;
                        AddFlat(archive, f.TextureRecord, fx, fy, fz);
                    }
                }
                foreach (var o in data.Misc3dObjectRecords)
                    AddModel(arch, o.ModelIdNum, new V3(o.XPos, -o.YPos - 4, o.ZPos + RmbDf), -o.XRotation / div * toRad, -o.YRotation / div * toRad, -o.ZRotation / div * toRad, ScaleOf(o), origin, 0);
                foreach (var f in data.MiscFlatObjectRecords)
                    if (f.TextureArchive != 199 && f.FactionID == 0)
                        AddFlat(f.TextureArchive, f.TextureRecord, origin.X + f.XPos, origin.Y - f.YPos - 6, origin.Z + f.ZPos + RmbDf);
                var scenery = data.FldHeader.GroundData.GroundScenery;
                for (int y = 0; y < 16; y++)
                    for (int x = 0; x < 16; x++)
                        if (scenery[x, 15 - y].TextureRecord >= 1)
                            AddFlat(location.Climate.NatureArchive, scenery[x, 15 - y].TextureRecord, origin.X + x * TileDf, origin.Y - 2, origin.Z + y * TileDf + TileDf);
            }

            public void AddTerrain(int from, int to)
            {
                int archive = location.Climate.GroundArchive;
                for (int ty = from; ty < to; ty++)
                    for (int tx = from; tx < to; tx++)
                    {
                        byte tile = TileAt(tx, ty);
                        int record = tile & 63;
                        if (!batches.TryGetValue((archive, record), out var v)) batches[(archive, record)] = v = new List<float>();
                        bool rotate = (tile & 64) != 0, flip = (tile & 128) != 0;
                        int transform = (rotate ? 1 : 0) + (flip ? 2 : 0);
                        void Emit(int x, int y)
                        {
                            float u = x - tx, w = y - ty, tu, tv;
                            switch (transform)
                            {
                                case 1: tu = w; tv = 1 - u; break;
                                case 2: tu = 1 - u; tv = 1 - w; break;
                                case 3: tu = 1 - w; tv = u; break;
                                default: tu = u; tv = w; break;
                            }
                            v.Add((float)DoomXY(x)); v.Add((float)DoomZ(x, y)); v.Add((float)DoomXY(y));
                            v.Add(tu); v.Add(1 - tv); // Unity samples tile images bottom-up
                            v.Add(0); v.Add(1); v.Add(0);
                        }
                        Emit(tx, ty); Emit(tx, ty + 1); Emit(tx + 1, ty + 1);
                        Emit(tx, ty); Emit(tx + 1, ty + 1); Emit(tx + 1, ty);
                    }
            }

            // DefaultTerrainNature's rules. Unity's random sequence is not reproduced, so individual trees differ from Daggerfall Unity.
            // Only the walkable area gets trees: a billboard outside every Doom sector would never be drawn.
            public void AddNature(int from, int to)
            {
                const int clearance = 4;
                const double maxSteepness = 50, sinkRatio = 70;
                var random = new Random(TerrainKey(cityX, cityY));
                for (int y = from; y < to; y++)
                    for (int x = from; x < to; x++)
                    {
                        if (x >= flatX0 - clearance && x < flatX1 + clearance && y >= flatY0 - clearance && y < flatY1 + clearance) continue;
                        int px = FloorDiv(x, TilesPerPixel), py = FloorDiv(y, TilesPerPixel);
                        double elevation = Math.Clamp(woods.GetHeightMapValue(cityX + px, cityY - py) / 128.0, 0.4, 1.0);
                        int tile = TileAt(x, y) & 0x3F;
                        double chance = tile == 1 ? 0.2 : tile == 2 ? 0.9 : tile == 3 ? 0.05 : -1;
                        double roll = random.NextDouble();
                        int record = random.Next(1, 32);
                        if (chance < 0 || roll > chance * elevation) continue;
                        if (Height(x, y) * MaxTerrain < Beach) continue;
                        double dx = (Height(x + 1, y) - Height(x, y)) * HeightToDf / TileDf, dy = (Height(x, y + 1) - Height(x, y)) * HeightToDf / TileDf;
                        double steepness = Math.Atan(Math.Sqrt(dx * dx + dy * dy)) * 180 / Math.PI;
                        if (steepness > maxSteepness) continue;
                        double up = (Height(x, y) - target) * HeightToDf - steepness / sinkRatio * UnityToDf;
                        AddFlat(location.Climate.NatureArchive, record, originX + (x - TilesPerPixel / 2) * TileDf, up, originZ + (y - TilesPerPixel / 2) * TileDf);
                    }
            }

            static int TerrainKey(int x, int y) => (y << 16) + x;

            public void WritePackage(string path, DFLocation place, string metadata)
            {
                var keys = batches.Keys.OrderBy(k => k.archive).ThenBy(k => k.record).ToList();
                BatchCount = keys.Count;
                if (File.Exists(path)) File.Delete(path);
                using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
                void Text(string name, string body)
                {
                    using var s = new StreamWriter(zip.CreateEntry(name, CompressionLevel.Fastest).Open());
                    s.Write(body);
                }
                using (var s = zip.CreateEntry("DFMESH", CompressionLevel.Fastest).Open())
                {
                    var writer = new BinaryWriter(s);
                    writer.Write(Encoding.ASCII.GetBytes("DFM1"));
                    writer.Write(Encoding.ASCII.GetBytes("MAP01\0\0\0"));
                    writer.Write(keys.Count); writer.Write(keys.Count); writer.Write(batches.Values.Sum(b => b.Count) / 8);
                    foreach (var k in keys)
                        writer.Write(Encoding.ASCII.GetBytes($"dfmesh/a{k.archive:D3}r{k.record:D2}.png".PadRight(32, '\0')));
                    int first = 0;
                    for (int t = 0; t < keys.Count; t++)
                    {
                        int count = batches[keys[t]].Count / 8;
                        writer.Write(t); writer.Write(first); writer.Write(count);
                        first += count;
                    }
                    var buffer = new byte[1 << 16];
                    foreach (var k in keys)
                    {
                        var list = batches[k];
                        for (int i = 0; i < list.Count;)
                        {
                            int n = Math.Min(list.Count - i, buffer.Length / 4);
                            for (int j = 0; j < n; j++) BitConverter.TryWriteBytes(buffer.AsSpan(j * 4), list[i + j]);
                            writer.Write(buffer, 0, n * 4);
                            i += n;
                        }
                    }
                    writer.Flush();
                }
                foreach (var k in keys)
                {
                    var file = Archive(k.archive);
                    var image = file != null && k.record < file.RecordCount ? file.GetDFBitmap(k.record, 0) : null;
                    if (image?.Data == null || image.Width == 0) { BadTextures++; Console.WriteLine($"missing texture {k.archive}:{k.record}"); continue; }
                    using var s = zip.CreateEntry($"dfmesh/a{k.archive:D3}r{k.record:D2}.png", CompressionLevel.Fastest).Open();
                    WriteTexturePng(s, image, file.Palette);
                }
                var flatList = new StringBuilder();
                foreach (var pair in Flats.Select(f => (f.archive, f.record)).Distinct())
                {
                    var file = Archive(pair.archive);
                    var image = file.GetDFBitmap(pair.record, 0);
                    if (image?.Data == null || image.Width == 0) { BadTextures++; continue; }
                    using var s = zip.CreateEntry($"textures/F{pair.archive:D3}R{pair.record:D2}.png", CompressionLevel.Fastest).Open();
                    WriteFlatPng(s, image, file.Palette);
                }
                foreach (var f in Flats)
                    flatList.Append(FormattableString.Invariant($"F{f.archive:D3}R{f.record:D2} {f.x:F2} {f.y:F2} {f.z:F2} {f.sx:F4} {f.sy:F4}\n"));
                Text("DFFLATS", flatList.ToString());
                Text("DFCITY", metadata);
                WriteSky(zip);
                Text("MAPINFO", $"GameInfo\n{{\n\tAddEventHandlers = \"DFCityHandler\"\n}}\nmap MAP01 \"{place.Name}\"\n{{\n\tpixelratio = 1.0\n\tsky1 = \"DFSKY\"\n}}\n");
                Text("zscript.zs", CityScript);
            }

            void WriteSky(ZipArchive zip)
            {
                string path = Path.Combine(arena2, SkyFile.IndexToFileName(location.Climate.SkyBase));
                if (!File.Exists(path)) { Console.WriteLine("sky file missing: " + path); return; }
                var sky = new SkyFile(path, FileUsage.UseMemory, true);
                const int frame = 31; // DaggerfallSky's midday frame
                var east = sky.GetDFBitmap(0, frame);
                var west = sky.GetDFBitmap(1, frame);
                var palette = sky.GetDFPalette(frame);
                var joined = new DFBitmap { Width = east.Width * 2, Height = east.Height, Data = new byte[east.Width * 2 * east.Height] };
                for (int y = 0; y < east.Height; y++)
                {
                    Array.Copy(east.Data, y * east.Width, joined.Data, y * joined.Width, east.Width);
                    Array.Copy(west.Data, y * west.Width, joined.Data, y * joined.Width + east.Width, west.Width);
                }
                using var s = zip.CreateEntry("textures/DFSKY.png", CompressionLevel.Fastest).Open();
                WriteTexturePng(s, joined, palette);
            }
        }

        // RGBA PNG with palette index 0 transparent and a grAb offset at the bottom center, as Daggerfall billboards stand on their base.
        static void WriteFlatPng(Stream output, DFBitmap image, DFPalette palette)
        {
            byte[] buffer = palette.PaletteBuffer;
            int head = palette.HeaderLength, w = image.Width, h = image.Height;
            var raw = new byte[(w * 4 + 1) * h];
            for (int y = 0, at = 0; y < h; y++)
            {
                raw[at++] = 0;
                for (int x = 0; x < w; x++)
                {
                    int index = image.Data[y * w + x], c = index * 3 + head;
                    raw[at++] = buffer[c]; raw[at++] = buffer[c + 1]; raw[at++] = buffer[c + 2]; raw[at++] = (byte)(index == 0 ? 0 : 255);
                }
            }
            var packed = new MemoryStream();
            using (var z = new ZLibStream(packed, CompressionLevel.Fastest, true)) z.Write(raw, 0, raw.Length);
            void Chunk(string kind, byte[] data)
            {
                var name = Encoding.ASCII.GetBytes(kind);
                WriteBig(output, (uint)data.Length);
                output.Write(name); output.Write(data);
                WriteBig(output, Crc(name, data));
            }
            byte[] Big(params int[] values) => values.SelectMany(v => new[] { (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v }).ToArray();
            output.Write(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A });
            Chunk("IHDR", Big(w, h).Concat(new byte[] { 8, 6, 0, 0, 0 }).ToArray());
            Chunk("grAb", Big(w / 2, h));
            Chunk("IDAT", packed.ToArray());
            Chunk("IEND", new byte[0]);
        }

        const string CityScript = @"version ""4.10""

// [DoomDaggerfall] Billboards and player width for a converted Daggerfall city. Loaded only with the city package.
class DFCityFlat : Actor
{
	Default { +NOINTERACTION +NOBLOCKMAP +NOGRAVITY +DONTSPLASH +NOTONAUTOMAP Radius 1; Height 1; }
	States { Spawn: PLAY A -1; Stop; }
}

class DFCityHandler : EventHandler
{
	static bool IsCity() { return level.MapName ~== ""MAP01"" && Wads.CheckNumForName(""DFCITY"", Wads.ns_global) >= 0; }

	override void WorldLoaded(WorldEvent e)
	{
		if (!IsCity()) return;
		for (int i = 0; i < MAXPLAYERS; i++) if (playeringame[i]) Fit(players[i].mo);
		if (e.IsSaveGame || e.IsReopen) return;
		int lump = Wads.CheckNumForName(""DFFLATS"", Wads.ns_global);
		if (lump < 0) return;
		String body = Wads.ReadLump(lump);
		Array<String> rows;
		body.Split(rows, ""\n"", TOK_SKIPEMPTY);
		Array<String> f;
		for (int r = 0; r < rows.Size(); r++)
		{
			f.Clear();
			rows[r].Split(f, "" "");
			if (f.Size() < 6) continue;
			Actor a = Actor.Spawn(""DFCityFlat"", (f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble()));
			a.picnum = TexMan.CheckForTexture(f[0], TexMan.Type_Any);
			a.scale = (f[4].ToDouble(), f[5].ToDouble());
		}
		Console.Printf(""DFCITY: %d billboards"", rows.Size());
	}

	override void PlayerEntered(PlayerEvent e) { if (IsCity()) Fit(players[e.PlayerNumber].mo); }

	static void Fit(PlayerPawn mo) { if (mo) mo.A_SetSize(10.5, mo.height); }
}
";

        // ---- Collision ----

        sealed class Collision
        {
            public static readonly List<(double x, double y)> Probes = new List<(double, double)>(); // --probe x,y;x,y prints what the raster saw
            const double Step = 24, Body = 56, Clearance = 2;
            public int W, H, OpenCells, SolidCells, RemovedCells, KeptRegions;
            public bool ReachesEdge;
            readonly int cell, margin, perTile;
            readonly double x0, y0;
            short[] floor; // quantized floor, or short.MinValue when solid
            int[] component;
            int startIndex = -1;

            public Collision(int cell, int margin)
            {
                this.cell = cell; this.margin = margin;
                perTile = (int)Math.Round(DoomTile / cell);
                W = (flatX1 - flatX0) * perTile; H = (flatY1 - flatY0) * perTile;
                x0 = DoomXY(flatX0); y0 = DoomXY(flatY0);
            }

            public void Rasterize(List<(V3 a, V3 b, V3 c)> triangles)
            {
                var hits = new List<(float lo, float hi)>[W * H];
                Span<(double x, double y, double z)> poly = new (double, double, double)[12], next = new (double, double, double)[12];
                foreach (var (a, b, c) in triangles)
                {
                    int i0 = Math.Max(0, (int)Math.Floor((Math.Min(a.X, Math.Min(b.X, c.X)) - x0) / cell)), i1 = Math.Min(W - 1, (int)Math.Floor((Math.Max(a.X, Math.Max(b.X, c.X)) - x0) / cell));
                    int j0 = Math.Max(0, (int)Math.Floor((Math.Min(a.Y, Math.Min(b.Y, c.Y)) - y0) / cell)), j1 = Math.Min(H - 1, (int)Math.Floor((Math.Max(a.Y, Math.Max(b.Y, c.Y)) - y0) / cell));
                    for (int j = j0; j <= j1; j++)
                        for (int i = i0; i <= i1; i++)
                        {
                            poly[0] = (a.X, a.Y, a.Z); poly[1] = (b.X, b.Y, b.Z); poly[2] = (c.X, c.Y, c.Z);
                            int n = 3;
                            double cx0 = x0 + i * cell, cy0 = y0 + j * cell;
                            n = Clip(poly, n, next, 0, cx0, 1); n = Clip(next, n, poly, 0, cx0 + cell, -1);
                            n = Clip(poly, n, next, 1, cy0, 1); n = Clip(next, n, poly, 1, cy0 + cell, -1);
                            if (n == 0) continue;
                            double lo = double.MaxValue, hi = double.MinValue;
                            for (int k = 0; k < n; k++) { lo = Math.Min(lo, poly[k].z); hi = Math.Max(hi, poly[k].z); }
                            (hits[i + j * W] ??= new List<(float, float)>(4)).Add(((float)lo, (float)hi));
                        }
                }

                floor = new short[W * H];
                for (int c = 0; c < floor.Length; c++)
                {
                    var list = hits[c];
                    if (list == null) continue;
                    list.Sort((p, q) => p.lo.CompareTo(q.lo));
                    double f = 0;
                    foreach (var (lo, hi) in list)
                        if (hi > f && hi <= f + Step && lo <= f + Step) f = hi;
                    bool solid = false;
                    foreach (var (lo, hi) in list)
                        if (lo < f + Body && hi > f + Clearance) { solid = true; break; }
                    floor[c] = solid ? short.MinValue : (short)(Math.Round(f / 4) * 4);
                }
                var before = (short[])floor.Clone();
                KeepReachable();
                foreach (var (px, py) in Probes)
                {
                    int i = (int)Math.Floor((px - x0) / cell), j = (int)Math.Floor((py - y0) / cell), c = i + j * W;
                    string spans = hits[c] == null ? "none" : string.Join(" ", hits[c].Select(h => FormattableString.Invariant($"{h.lo:F0}..{h.hi:F0}")));
                    Console.WriteLine($"PROBE {px},{py} cell {i},{j}: raster {(before[c] == short.MinValue ? "solid" : "open floor " + before[c])}, final {(floor[c] == short.MinValue ? "void" : "open")}, surfaces {spans}");
                }
            }

            static int Clip(Span<(double x, double y, double z)> input, int count, Span<(double x, double y, double z)> output, int axis, double limit, int sign)
            {
                int n = 0;
                double D((double x, double y, double z) p) => ((axis == 0 ? p.x : p.y) - limit) * sign;
                for (int i = 0; i < count; i++)
                {
                    var p = input[i]; var q = input[(i + 1) % count];
                    double dp = D(p), dq = D(q);
                    if (dp >= 0) output[n++] = p;
                    if ((dp > 0 && dq < 0) || (dp < 0 && dq > 0))
                    {
                        double t = dp / (dp - dq);
                        output[n++] = (p.x + (q.x - p.x) * t, p.y + (q.y - p.y) * t, p.z + (q.z - p.z) * t);
                    }
                }
                return n;
            }

            void KeepReachable()
            {
                component = new int[W * H];
                Array.Fill(component, -1);
                var sizes = new List<int>();
                var touchesEdge = new List<bool>();
                var stack = new Stack<int>();
                for (int s = 0; s < component.Length; s++)
                {
                    if (floor[s] == short.MinValue || component[s] >= 0) continue;
                    int id = sizes.Count, size = 0;
                    bool edge = false;
                    component[s] = id;
                    stack.Push(s);
                    while (stack.Count > 0)
                    {
                        int p = stack.Pop(), i = p % W, j = p / W;
                        size++;
                        if (i == 0 || j == 0 || i == W - 1 || j == H - 1) edge = true;
                        void Try(int ni, int nj)
                        {
                            if (ni < 0 || nj < 0 || ni >= W || nj >= H) return;
                            int q = ni + nj * W;
                            if (component[q] >= 0 || floor[q] == short.MinValue || Math.Abs(floor[q] - floor[p]) > Step) return;
                            component[q] = id;
                            stack.Push(q);
                        }
                        Try(i + 1, j); Try(i - 1, j); Try(i, j + 1); Try(i, j - 1);
                    }
                    sizes.Add(size);
                    touchesEdge.Add(edge);
                }
                // The start is the open cell nearest the city's center that has room around it, inside the largest region not on the outer ring when one exists.
                int main = Enumerable.Range(0, sizes.Count).OrderByDescending(r => sizes[r]).First();
                var keep = new bool[sizes.Count];
                keep[main] = true;
                for (int r = 0; r < sizes.Count; r++) if (touchesEdge[r]) keep[r] = true;
                KeptRegions = keep.Count(k => k);
                ReachesEdge = touchesEdge[main];
                for (int c = 0; c < floor.Length; c++)
                {
                    if (floor[c] == short.MinValue) { SolidCells++; continue; }
                    if (!keep[component[c]]) { floor[c] = short.MinValue; component[c] = -1; RemovedCells++; SolidCells++; continue; }
                    OpenCells++;
                }
                const int room = 4;
                double best = double.MaxValue;
                for (int j = room; j < H - room; j++)
                    for (int i = room; i < W - room; i++)
                    {
                        int c = i + j * W;
                        if (component[c] != main) continue;
                        double d = (i - W / 2.0) * (i - W / 2.0) + (j - H / 2.0) * (j - H / 2.0);
                        if (d >= best) continue;
                        bool clear = true;
                        for (int b = -room; b <= room && clear; b++)
                            for (int a = -room; a <= room; a++)
                                if (floor[c + a + b * W] != floor[c]) { clear = false; break; }
                        if (clear) { best = d; startIndex = c; }
                    }
                if (startIndex < 0) throw new InvalidDataException("no open start cell");
            }

            // Test routes from the start out through the walls toward each side, over cells wide enough for the player's box.
            public string Routes()
            {
                const int reach = 2; // cells on each side: 8-unit cells cover the 10.5-unit player radius
                var wide = new bool[W * H];
                for (int j = reach; j < H - reach; j++)
                    for (int i = reach; i < W - reach; i++)
                    {
                        int c = i + j * W;
                        if (floor[c] == short.MinValue) continue;
                        bool ok = true;
                        for (int b = -reach; b <= reach && ok; b++)
                            for (int a = -reach; a <= reach; a++)
                            {
                                int q = c + a + b * W;
                                if (floor[q] == short.MinValue || Math.Abs(floor[q] - floor[c]) > Step) { ok = false; break; }
                            }
                        wide[c] = ok;
                    }
                var parent = new int[W * H];
                Array.Fill(parent, -1);
                var queue = new Queue<int>();
                parent[startIndex] = startIndex;
                queue.Enqueue(startIndex);
                int[] best = { startIndex, startIndex, startIndex, startIndex };
                double Score(int side, int i, int j) => side switch { 0 => j, 1 => i, 2 => -j, _ => -i } * 1000.0 - Math.Abs(side % 2 == 0 ? i - W / 2.0 : j - H / 2.0);
                while (queue.Count > 0)
                {
                    int p = queue.Dequeue(), i = p % W, j = p / W;
                    for (int side = 0; side < 4; side++)
                        if (Score(side, i, j) > Score(side, best[side] % W, best[side] / W)) best[side] = p;
                    foreach (var (ni, nj) in new[] { (i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1) })
                    {
                        if (ni < 0 || nj < 0 || ni >= W || nj >= H) continue;
                        int q = ni + nj * W;
                        if (parent[q] >= 0 || !wide[q] || Math.Abs(floor[q] - floor[p]) > Step) continue;
                        parent[q] = p;
                        queue.Enqueue(q);
                    }
                }
                var text = new StringBuilder();
                string[] names = { "north", "east", "south", "west" };
                (int x, int y)[] outward = { (0, 1), (1, 0), (0, -1), (-1, 0) };
                for (int side = 0; side < 4; side++)
                {
                    var path = new List<int>();
                    for (int p = best[side]; ; p = parent[p]) { path.Add(p); if (p == startIndex) break; }
                    path.Reverse();
                    text.Append(FormattableString.Invariant($"route {names[side]} {path.Count * cell}\n"));
                    for (int n = 0; n < path.Count; n += 6)
                        text.Append(FormattableString.Invariant($"{x0 + (path[n] % W + 0.5) * cell:F1} {y0 + (path[n] / W + 0.5) * cell:F1}\n"));
                    double ex = x0 + (best[side] % W + 0.5) * cell, ey = y0 + (best[side] / W + 0.5) * cell;
                    text.Append(FormattableString.Invariant($"{ex:F1} {ey:F1}\n{ex + outward[side].x * 700:F1} {ey + outward[side].y * 700:F1}\n"));
                }
                return text.ToString();
            }

            public MapText Build()
            {
                // City sectors: connected cells with the same floor.
                var sectorOf = new int[W * H];
                Array.Fill(sectorOf, NoSector);
                var floors = new List<int>();
                var stack = new Stack<int>();
                for (int s = 0; s < sectorOf.Length; s++)
                {
                    if (floor[s] == short.MinValue || sectorOf[s] >= 0) continue;
                    int id = floors.Count;
                    floors.Add(floor[s]);
                    sectorOf[s] = id;
                    stack.Push(s);
                    while (stack.Count > 0)
                    {
                        int p = stack.Pop(), i = p % W, j = p / W;
                        void Try(int ni, int nj)
                        {
                            if (ni < 0 || nj < 0 || ni >= W || nj >= H) return;
                            int q = ni + nj * W;
                            if (sectorOf[q] < 0 && floor[q] == floor[s]) { sectorOf[q] = id; stack.Push(q); }
                        }
                        Try(i + 1, j); Try(i - 1, j); Try(i, j + 1); Try(i, j - 1);
                    }
                }
                int citySectors = floors.Count;

                // Terrain: two sloped sectors per tile outside the flat rectangle.
                int tx0 = -margin, tx1 = TilesPerPixel + margin, ty0 = -margin, ty1 = TilesPerPixel + margin, across = tx1 - tx0;
                var lower = new int[across * across]; // triangle (x,y) (x+1,y+1) (x+1,y): right and bottom edges
                var upper = new int[across * across]; // triangle (x,y) (x,y+1) (x+1,y+1): left and top edges
                bool InFlat(int x, int y) => x >= flatX0 && x < flatX1 && y >= flatY0 && y < flatY1;
                int TileIndex(int x, int y) => (x - tx0) + (y - ty0) * across;
                bool InMap(int x, int y) => x >= tx0 && x < tx1 && y >= ty0 && y < ty1;
                var sectors = new StringBuilder();
                string F(double v) => v.ToString("R", CultureInfo.InvariantCulture);
                double maxZ = 0;
                for (int y = ty0; y <= ty1; y++)
                    for (int x = tx0; x <= tx1; x++)
                        maxZ = Math.Max(maxZ, DoomZ(x, y));
                int ceiling = (int)Math.Ceiling(maxZ / 64 + 1) * 64 + 2048;
                foreach (int f in floors)
                    sectors.Append($"sector {{ heightfloor = {f}; heightceiling = {ceiling}; texturefloor = \"FLOOR0_1\"; textureceiling = \"F_SKY1\"; lightlevel = 192; }}\n");
                int sectorCount = citySectors;
                void Slope(double ax, double ay, double az, double bx, double by, double bz, double cx, double cy, double cz)
                {
                    double ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
                    double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
                    if (nz < 0) { nx = -nx; ny = -ny; nz = -nz; }
                    double length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                    nx /= length; ny /= length; nz /= length;
                    double d = -(nx * ax + ny * ay + nz * az);
                    sectors.Append($"sector {{ heightfloor = {(int)Math.Round((az + bz + cz) / 3)}; heightceiling = {ceiling}; texturefloor = \"GRASS1\"; textureceiling = \"F_SKY1\"; lightlevel = 192; floorplane_a = {F(nx)}; floorplane_b = {F(ny)}; floorplane_c = {F(nz)}; floorplane_d = {F(d)}; }}\n");
                }
                for (int y = ty0; y < ty1; y++)
                    for (int x = tx0; x < tx1; x++)
                    {
                        int t = TileIndex(x, y);
                        if (InFlat(x, y)) { lower[t] = upper[t] = NoSector; continue; }
                        double X0 = DoomXY(x), X1 = DoomXY(x + 1), Y0 = DoomXY(y), Y1 = DoomXY(y + 1);
                        double z00 = DoomZ(x, y), z10 = DoomZ(x + 1, y), z01 = DoomZ(x, y + 1), z11 = DoomZ(x + 1, y + 1);
                        lower[t] = sectorCount++; Slope(X0, Y0, z00, X1, Y1, z11, X1, Y0, z10);
                        upper[t] = sectorCount++; Slope(X0, Y0, z00, X0, Y1, z01, X1, Y1, z11);
                    }

                var vertices = new Dictionary<(long, long), int>();
                int Vertex(double x, double y)
                {
                    var key = ((long)Math.Round(x * 8), (long)Math.Round(y * 8));
                    if (!vertices.TryGetValue(key, out int v)) vertices[key] = v = vertices.Count;
                    return v;
                }
                var lines = new StringBuilder();
                var sides = new StringBuilder();
                int lineCount = 0, sideCount = 0;
                int Side(int sector, bool two)
                {
                    sides.Append(two ? $"sidedef {{ sector = {sector}; texturetop = \"STONE2\"; texturebottom = \"STONE2\"; }}\n" : $"sidedef {{ sector = {sector}; texturemiddle = \"STONE2\"; }}\n");
                    return sideCount++;
                }
                void Line(double ax, double ay, double bx, double by, int right, int left)
                {
                    if (right == left) return;
                    if (right < 0) { (ax, ay, bx, by) = (bx, by, ax, ay); (right, left) = (left, right); }
                    int v1 = Vertex(ax, ay), v2 = Vertex(bx, by), front = Side(right, left >= 0);
                    lines.Append(left >= 0 ? $"linedef {{ v1 = {v1}; v2 = {v2}; sidefront = {front}; sideback = {Side(left, true)}; twosided = true; }}\n" : $"linedef {{ v1 = {v1}; v2 = {v2}; sidefront = {front}; blocking = true; }}\n");
                    lineCount++;
                }

                // Terrain edges. Edges against the flat rectangle are written by the raster pass below.
                for (int y = ty0; y < ty1; y++)
                    for (int x = tx0; x < tx1; x++)
                    {
                        if (InFlat(x, y)) continue;
                        int t = TileIndex(x, y);
                        double X0 = DoomXY(x), X1 = DoomXY(x + 1), Y0 = DoomXY(y), Y1 = DoomXY(y + 1);
                        Line(X0, Y0, X1, Y1, lower[t], upper[t]);
                        if (!InFlat(x + 1, y)) Line(X1, Y0, X1, Y1, InMap(x + 1, y) ? upper[TileIndex(x + 1, y)] : NoSector, lower[t]);
                        if (!InFlat(x, y + 1)) Line(X0, Y1, X1, Y1, upper[t], InMap(x, y + 1) ? lower[TileIndex(x, y + 1)] : NoSector);
                        if (x == tx0) Line(X0, Y0, X0, Y1, upper[t], NoSector);
                        if (y == ty0) Line(X0, Y0, X1, Y0, NoSector, lower[t]);
                    }

                // City cell boundaries, merged along their length. Cells past the rectangle resolve to the adjoining terrain triangle.
                int Id(int i, int j)
                {
                    if (i >= 0 && j >= 0 && i < W && j < H) return sectorOf[i + j * W];
                    if (i < 0) return lower[TileIndex(flatX0 - 1, flatY0 + j / perTile)];
                    if (i >= W) return upper[TileIndex(flatX1, flatY0 + j / perTile)];
                    if (j < 0) return upper[TileIndex(flatX0 + i / perTile, flatY0 - 1)];
                    return lower[TileIndex(flatX0 + i / perTile, flatY1)];
                }
                for (int i = 0; i <= W; i++)
                {
                    int run = -1, runLeft = 0, runRight = 0;
                    for (int j = 0; j <= H; j++)
                    {
                        int l = j < H ? Id(i - 1, j) : NoSector, r = j < H ? Id(i, j) : NoSector;
                        bool edge = j < H && l != r;
                        if (run >= 0 && (!edge || l != runLeft || r != runRight))
                        {
                            Line(x0 + i * cell, y0 + run * cell, x0 + i * cell, y0 + j * cell, runRight, runLeft);
                            run = -1;
                        }
                        if (edge && run < 0) { run = j; runLeft = l; runRight = r; }
                    }
                }
                for (int j = 0; j <= H; j++)
                {
                    int run = -1, runBelow = 0, runAbove = 0;
                    for (int i = 0; i <= W; i++)
                    {
                        int b = i < W ? Id(i, j - 1) : NoSector, a = i < W ? Id(i, j) : NoSector;
                        bool edge = i < W && a != b;
                        if (run >= 0 && (!edge || b != runBelow || a != runAbove))
                        {
                            Line(x0 + run * cell, y0 + j * cell, x0 + i * cell, y0 + j * cell, runBelow, runAbove);
                            run = -1;
                        }
                        if (edge && run < 0) { run = i; runBelow = b; runAbove = a; }
                    }
                }

                double startX = x0 + (startIndex % W + 0.5) * cell, startY = y0 + (startIndex / W + 0.5) * cell;
                var text = new StringBuilder("namespace = \"zdoom\";\n");
                foreach (var pair in vertices.OrderBy(p => p.Value))
                    text.Append($"vertex {{ x = {(pair.Key.Item1 / 8.0).ToString("0.0##", CultureInfo.InvariantCulture)}; y = {(pair.Key.Item2 / 8.0).ToString("0.0##", CultureInfo.InvariantCulture)}; }}\n");
                text.Append(lines).Append(sides).Append(sectors);
                text.Append(FormattableString.Invariant($"thing {{ x = {startX:F1}; y = {startY:F1}; angle = 90; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }}\n"));
                return new MapText { Text = text.ToString(), Sectors = sectorCount, CitySectors = citySectors, TerrainSectors = sectorCount - citySectors, Lines = lineCount, Vertices = vertices.Count, StartX = startX, StartY = startY };
            }
        }

        sealed class MapText
        {
            public string Text;
            public int Sectors, CitySectors, TerrainSectors, Lines, Vertices;
            public double StartX, StartY;
        }
    }
}
