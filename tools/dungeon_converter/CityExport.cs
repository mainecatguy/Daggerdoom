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
    static partial class City
    {
        const int TilesPerPixel = 128, TileDf = 256, TilesPerBlock = 16, RmbDf = 4096;
        const double MaxTerrain = 1539, TerrainScale = 1.5, UnityToDf = 40, HeightToDf = MaxTerrain * TerrainScale * UnityToDf;
        const float Ocean = 3.4f * 8, Beach = 5f * 8;
        const uint GateOpen = 446, GateClosed = 447;
        const int NoSector = -1;

        static double S => PlayerScale.DoomUnitsPerDaggerfallUnit;
        static double DoomTile => TileDf * S;

        // One location on this exterior map. Tile coordinates are relative to the primary location's map pixel, +Y north.
        sealed class Site
        {
            public WorldTerrain.Place Place;
            public DFLocation Location;
            public DFBlock[] Blocks;
            public byte[,] Tiles = new byte[TilesPerPixel, TilesPerPixel];
            public int DX, DY, FlatX0, FlatX1, FlatY0, FlatY1;
            public float Target;
            public bool InFlat(int x, int y) => x >= FlatX0 && x < FlatX1 && y >= FlatY0 && y < FlatY1;
        }

        static readonly List<Site> sites = new List<Site>();
        static WoodsFile woods => WorldTerrain.Woods;
        static int cityX, cityY, originTileX, originTileY, walkMargin;
        static float target;
        static bool Walkable(int x, int y) => sites.Any(s => x >= s.FlatX0 - walkMargin && x < s.FlatX1 + walkMargin && y >= s.FlatY0 - walkMargin && y < s.FlatY1 + walkMargin);

        // --winter: the location as Daggerfall draws it in winter (ClimateSwaps, TerrainMaterialProvider.GetClimateInfo).
        static bool Winter;
        static bool SnowyNature(int archive) => archive is (int)DFLocation.ClimateTextureSet.Nature_TemperateWoodland or (int)DFLocation.ClimateTextureSet.Nature_WoodlandHills
            or (int)DFLocation.ClimateTextureSet.Nature_HauntedWoodlands or (int)DFLocation.ClimateTextureSet.Nature_Mountains;
        static int NatureArchive(DFLocation l) => Winter && SnowyNature(l.Climate.NatureArchive) ? l.Climate.NatureArchive + 1 : l.Climate.NatureArchive;
        static int GroundArchive(DFLocation l) => Winter && l.Climate.ClimateType != DFLocation.ClimateBaseType.Desert ? l.Climate.GroundArchive + 1 : l.Climate.GroundArchive;

        public static int Run(string[] args)
        {
            string Arg(string name, string fallback) { int at = Array.IndexOf(args, name); return at >= 0 ? args[at + 1] : fallback; }
            string cityName = Arg("--city", null), regionName = Arg("--region", cityName), outDir = Arg("--out", null);
            string arena2 = Arg("--arena2", @"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2");
            // Terrain lines carry zone boundaries, which keeps the engine's recursive sound-zone flood shallow at any margin.
            int margin = int.Parse(Arg("--margin", "24")), visualMargin = int.Parse(Arg("--visual-margin", "64")), rasterCell = int.Parse(Arg("--raster", "8"));
            string mapName = Arg("--map-name", "MAP01");
            PlayerScale.DoomUnitsPerDaggerfallUnit = double.Parse(Arg("--world-scale", "0.75"), CultureInfo.InvariantCulture);
            // --group <id> --ddt <file> converts one location group for the running game.
            int groupId = int.Parse(Arg("--group", "-1"));
            Winter = args.Contains("--winter"); // Daggerfall's winter season: ClimateSwaps' winter texture sets
            string ddtPath = Arg("--ddt", null);
            if (args.Contains("--list-buildings")) return ListBuildings(groupId, arena2);
            if (groupId >= SpaceBase) return RunInterior(groupId, ddtPath, outDir, arena2);
            if (groupId >= 0) mapName = RuntimeMapName(groupId);
            if ((cityName == null && groupId < 0) || outDir == null) { Console.Error.WriteLine("usage: --city <name> [--region <name>] --out <dir>, or --group <id> --ddt <file> --out <work dir>"); return 2; }
            if (Math.Abs(DoomTile / rasterCell - Math.Round(DoomTile / rasterCell)) > 1e-9) { Console.Error.WriteLine("--raster must divide the Doom tile size"); return 2; }
            Directory.CreateDirectory(outDir);
            var clock = System.Diagnostics.Stopwatch.StartNew();
            walkMargin = margin;

            var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
            List<WorldTerrain.Place> runtimeGroup = null;
            DFLocation location = default;
            if (groupId < 0 && !FindCity(maps, regionName, cityName, out location)) { Console.Error.WriteLine("city not found: " + cityName); return 1; }
            var blocksFile = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
            var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
            WorldTerrain.Load(arena2, maps, blocksFile);
            if (groupId >= 0)
            {
                var groups = WorldTerrain.Groups();
                if (groupId >= groups.Count) { Console.Error.WriteLine("no such group: " + groupId); return 1; }
                runtimeGroup = groups[groupId];
                var primary = runtimeGroup[0];
                location = maps.GetLocation(primary.RegionIndex, primary.LocationIndex);
                cityName = primary.Name;
                cityX = primary.X; cityY = primary.Y;
            }
            else
            {
                var pixel = MapsFile.LongitudeLatitudeToMapPixel(location.MapTableData.Longitude, location.MapTableData.Latitude);
                cityX = pixel.X; cityY = pixel.Y;
            }
            Console.WriteLine($"{location.RegionName}/{location.Name}: map pixel {cityX},{cityY}, climate {location.Climate.WorldClimate} base {location.Climate.ClimateType}, ground {location.Climate.GroundArchive}, nature {location.Climate.NatureArchive}, sky {location.Climate.SkyBase}");

            // Adjacent locations share this one map.
            foreach (var place in runtimeGroup ?? WorldTerrain.GroupOf(WorldTerrain.Places[(cityX, cityY)]))
            {
                var site = new Site { Place = place, Location = maps.GetLocation(place.RegionIndex, place.LocationIndex), DX = place.X - cityX, DY = cityY - place.Y };
                site.Blocks = new DFBlock[place.BlocksWide * place.BlocksHigh];
                for (int y = 0; y < place.BlocksHigh; y++)
                    for (int x = 0; x < place.BlocksWide; x++)
                        site.Blocks[y * place.BlocksWide + x] = blocksFile.GetBlock(maps.GetRmbBlockName(site.Location, x, y));
                PrepareSite(site);
                sites.Add(site);
                Console.WriteLine($"  site {place.Name} ({place.Type}) pixel {place.X},{place.Y} flat x {site.FlatX0}..{site.FlatX1} y {site.FlatY0}..{site.FlatY1}");
            }
            target = sites[0].Target;
            int bx0 = sites.Min(q => q.FlatX0) - margin, bx1 = sites.Max(q => q.FlatX1) + margin, by0 = sites.Min(q => q.FlatY0) - margin, by1 = sites.Max(q => q.FlatY1) + margin;
            int mapLimit = (int)Math.Floor(65000 / DoomTile);
            if (bx1 - bx0 > mapLimit || by1 - by0 > mapLimit) { Console.Error.WriteLine($"walkable area {bx1 - bx0}x{by1 - by0} tiles exceeds the {mapLimit}-tile map limit"); return 1; }
            originTileX = (bx0 + bx1) / 2; originTileY = (by0 + by1) / 2;
            double groundDf = target * HeightToDf;
            double originDfX = originTileX * TileDf, originDfZ = originTileY * TileDf;

            var scene = new Scene(arena2, location, originDfX, originDfZ) { DoorGroup = groupId };
            foreach (var site in sites)
            {
                scene.Use(site.Location);
                double up = (site.Target - target) * HeightToDf, baseX = (site.DX * TilesPerPixel + site.Place.OriginX) * TileDf, baseZ = (site.DY * TilesPerPixel + site.Place.OriginY) * TileDf;
                for (int y = 0; y < site.Place.BlocksHigh; y++)
                    for (int x = 0; x < site.Place.BlocksWide; x++)
                        scene.AddBlock(site.Blocks[y * site.Place.BlocksWide + x], arch, baseX + x * RmbDf, baseZ + y * RmbDf, up, site.Location.MapTableData.MapId, x, y);
            }
            scene.Use(location);
            scene.AddTerrain(bx0 - visualMargin, bx1 + visualMargin, by0 - visualMargin, by1 + visualMargin);
            scene.AddNature(bx0, bx1, by0, by1);
            Console.WriteLine($"scene: {scene.Models} models ({scene.Missing} missing), {scene.Gates} gates, {scene.Colliders.Count} collider triangles, {scene.Flats.Count} billboards, {scene.Triangles} mesh triangles [{clock.ElapsedMilliseconds} ms]");

            foreach (var probe in (Arg("--probe", "")).Split(';', StringSplitOptions.RemoveEmptyEntries))
                Collision.Probes.Add((double.Parse(probe.Split(',')[0], CultureInfo.InvariantCulture), double.Parse(probe.Split(',')[1], CultureInfo.InvariantCulture)));
            var rasters = sites.Select(q => new Collision(rasterCell, q, q == sites[0])).ToList();
            foreach (var raster in rasters) raster.Rasterize(scene.Colliders, scene.ColliderOwners);
            var collision = rasters[0];
            var map = Collision.Build(rasters, bx0, bx1, by0, by1);
            string slug = new string(cityName.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant() + "_city";
            string wad = Path.Combine(outDir, slug + ".wad");
            WriteWad(wad, map.Text, "", mapName);
            File.WriteAllText(Path.Combine(outDir, slug + ".routes.txt"), collision.Routes());
            File.WriteAllText(Path.Combine(outDir, slug + ".roofs.txt"), string.Concat(rasters.Select(q => q.RoofSamples())));

            int worldTileX = cityX * TilesPerPixel, worldTileY = (WorldTerrain.WorldH - 1 - cityY) * TilesPerPixel;
            var first = sites[0];
            string metadata = FormattableString.Invariant($"scale {S}\nmappixel {cityX} {cityY}\noriginworld {(worldTileX + originTileX) * (double)TileDf} {(worldTileY + originTileY) * (double)TileDf}\ngroundheight {groundDf}\nflat {first.FlatX0} {first.FlatX1} {first.FlatY0} {first.FlatY1}\nstart {map.StartX} {map.StartY}\n");
            // DDTOWN tells the engine where this map sits in the world. Rectangles are global tiles.
            var town = new StringBuilder(FormattableString.Invariant($"map {mapName}\nscale {S}\norigin {(worldTileX + originTileX) * (double)TileDf} {(worldTileY + originTileY) * (double)TileDf}\nground {groundDf:R}\nmargin {margin}\nvisual {worldTileX + bx0 - visualMargin} {worldTileX + bx1 + visualMargin} {worldTileY + by0 - visualMargin} {worldTileY + by1 + visualMargin}\n"));
            foreach (var q in sites) town.Append($"rect {worldTileX + q.FlatX0} {worldTileX + q.FlatX1} {worldTileY + q.FlatY0} {worldTileY + q.FlatY1}\n");
            string package = ddtPath ?? Path.Combine(outDir, slug + "_mesh.pk3");
            if (ddtPath != null)
            {
                scene.WriteRuntimeEntry(ddtPath, wad, town.ToString(), mapName);
                File.Delete(wad);
            }
            else scene.WritePackage(package, location, metadata, town.ToString(), mapName);

            string report = ( // the project sets InvariantGlobalization
                $"city {location.RegionName}/{location.Name}\nmap pixel {cityX},{cityY}\nsites {sites.Count}\nblocks {sites[0].Place.BlocksWide}x{sites[0].Place.BlocksHigh}\nflat tiles x {sites[0].FlatX0}..{sites[0].FlatX1} y {sites[0].FlatY0}..{sites[0].FlatY1}\nground height {groundDf:F1} df units\n" +
                $"models {scene.Models} missing {scene.Missing} gates {scene.Gates}\nmesh triangles {scene.Triangles} batches {scene.BatchCount} textures unreadable {scene.BadTextures}\nbillboards {scene.Flats.Count}\n" +
                $"raster {collision.W}x{collision.H} at {rasterCell} units\nopen cells {collision.OpenCells} solid cells {collision.SolidCells} removed unreachable {collision.RemovedCells} kept regions {collision.KeptRegions}\nouter edge reachable from start {collision.ReachesEdge}\n" +
                $"buildings {rasters.Sum(q => q.Buildings)} roof cells {rasters.Sum(q => q.RoofCells)} sloped {rasters.Sum(q => q.SlopedRoofCells)} filled from a neighbor {rasters.Sum(q => q.FilledRoofCells)} flat fallback {rasters.Sum(q => q.FallbackRoofCells)} open inside footprint {rasters.Sum(q => q.OpenFootprintCells)} no roof inside footprint {rasters.Sum(q => q.NoRoofCells)}\n" +
                $"sectors {map.Sectors} (city {map.CitySectors}, terrain {map.TerrainSectors}) lines {map.Lines} vertices {map.Vertices}\nstart {map.StartX},{map.StartY}\nwad {(File.Exists(wad) ? new FileInfo(wad).Length / 1024 : 0)} KiB\nmesh package {new FileInfo(package).Length / 1024} KiB\nconvert time {clock.ElapsedMilliseconds} ms\n");
            File.WriteAllText(Path.Combine(outDir, slug + ".stats.txt"), report);
            Console.WriteLine(report);
            if (ddtPath != null) return 0; // A missing prop is reported above and does not stop the player from entering.
            return scene.BadTextures == 0 && scene.Missing == 0 ? 0 : 1;
        }

        public static string RuntimeMapName(int group) => "DDT" + group.ToString("D5", CultureInfo.InvariantCulture);

        // The package every runtime location shares: the location index, all textures, the gate models, and the scripts.
        public static int RuntimeAssets(string[] args)
        {
            string Arg(string name, string fallback) { int at = Array.IndexOf(args, name); return at >= 0 ? args[at + 1] : fallback; }
            string outFile = Arg("--out", null), arena2 = Arg("--arena2", @"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2");
            if (outFile == null) { Console.Error.WriteLine("usage: --runtime-assets --out <ddruntime.pk3>"); return 2; }
            PlayerScale.DoomUnitsPerDaggerfallUnit = 0.75;
            var clock = System.Diagnostics.Stopwatch.StartNew();
            var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
            var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
            var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
            WorldTerrain.Load(arena2, maps, blocks);
            var groups = WorldTerrain.Groups();

            // DDGROUPS: where each group is, so the engine can request it before any conversion has run.
            int tooLarge = 0, mapLimit = (int)Math.Floor(65000 / DoomTile);
            var index = new MemoryStream();
            using (var w = new BinaryWriter(index, Encoding.ASCII, true))
            {
                w.Write(Encoding.ASCII.GetBytes("DDG1"));
                w.Write(groups.Count);
                foreach (var group in groups)
                {
                    var rects = group.Select(p => (x0: p.X * TilesPerPixel + p.RectX0, x1: p.X * TilesPerPixel + p.RectX1,
                        y0: (WorldTerrain.WorldH - 1 - p.Y) * TilesPerPixel + p.RectY0, y1: (WorldTerrain.WorldH - 1 - p.Y) * TilesPerPixel + p.RectY1)).ToList();
                    bool large = rects.Max(r => r.x1) - rects.Min(r => r.x0) + 48 > mapLimit || rects.Max(r => r.y1) - rects.Min(r => r.y0) + 48 > mapLimit;
                    tooLarge += large ? 1 : 0;
                    w.Write((short)rects.Count);
                    w.Write((short)(large ? 1 : 0));
                    foreach (var r in rects) { w.Write(r.x0); w.Write(r.x1); w.Write(r.y0); w.Write(r.y1); }
                }
            }

            // Billboards can come from any archive a block names, plus the nature sets.
            var flatArchives = new HashSet<int>(Enumerable.Range((int)DFLocation.ClimateTextureSet.Nature_RainForest, (int)DFLocation.ClimateTextureSet.Nature_Mountains_Snow - (int)DFLocation.ClimateTextureSet.Nature_RainForest + 1));
            var npcArchives = new HashSet<int>();
            for (int b = 0; b < blocks.Count; b++)
            {
                if (!blocks.GetBlockName(b).EndsWith(".RMB", StringComparison.OrdinalIgnoreCase)) continue;
                var data = blocks.GetBlock(b).RmbBlock;
                foreach (var sub in data.SubRecords)
                {
                    foreach (var f in sub.Exterior.BlockFlatObjectRecords) { flatArchives.Add(f.TextureArchive); if (f.FactionID != 0) npcArchives.Add(f.TextureArchive); }
                    foreach (var f in sub.Interior.BlockFlatObjectRecords) flatArchives.Add(f.TextureArchive);
                    foreach (var p in sub.Interior.BlockPeopleRecords) { flatArchives.Add(p.TextureArchive); npcArchives.Add(p.TextureArchive); }
                }
                foreach (var f in data.MiscFlatObjectRecords) { flatArchives.Add(f.TextureArchive); if (f.FactionID != 0) npcArchives.Add(f.TextureArchive); }
            }
            flatArchives.Remove(199);
            npcArchives.Remove(199);
            // Townspeople: MobilePersonBillboard's walking and idle archives, drawn by Doom from Daggerfall's live list.
            var mobileArchives = new HashSet<int>(Enumerable.Range(381, 19).Concat(Enumerable.Range(451, 6)));
            flatArchives.UnionWith(mobileArchives);
            var mobileScales = new StringBuilder();

            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outFile)));
            string temp = outFile + ".tmp";
            if (File.Exists(temp)) File.Delete(temp);
            int meshImages = 0, flatImages = 0, windowMasks = 0;
            var npcAnimation = new StringBuilder();
            using (var zip = ZipFile.Open(temp, ZipArchiveMode.Create))
            {
                void Text(string name, string body) { using var s = new StreamWriter(zip.CreateEntry(name, CompressionLevel.Fastest).Open()); s.Write(body); }
                using (var s = zip.CreateEntry("DDGROUPS", CompressionLevel.Fastest).Open()) { index.Position = 0; index.CopyTo(s); }
                foreach (string path in Directory.GetFiles(arena2, "TEXTURE.*").OrderBy(p => p, StringComparer.OrdinalIgnoreCase))
                {
                    if (!int.TryParse(Path.GetExtension(path).TrimStart('.'), out int archive)) continue;
                    var file = new TextureFile(path, FileUsage.UseMemory, true);
                    for (int record = 0; record < file.RecordCount; record++)
                    {
                        var image = file.GetDFBitmap(record, 0);
                        if (image?.Data == null || image.Width == 0) continue;
                        using (var s = zip.CreateEntry($"dfmesh/a{archive:D3}r{record:D2}.png", CompressionLevel.Fastest).Open()) WriteTexturePng(s, image, file.Palette);
                        meshImages++;
                        if (WriteWindowMask(zip, archive, record, image, file.Palette)) windowMasks++;
                        if (!flatArchives.Contains(archive)) continue;
                        using (var s = zip.CreateEntry($"dfflat/F{archive:D3}R{record:D2}.png", CompressionLevel.Fastest).Open()) WriteFlatPng(s, image, file.Palette);
                        flatImages++;
                        // NPCs idle through their frames in Daggerfall.
                        bool mobile = mobileArchives.Contains(archive);
                        if (mobile) { var (msx, msy) = BillboardScale(file, record); mobileScales.Append(FormattableString.Invariant($"{archive} {record} {msx:F4} {msy:F4}\n")); }
                        int frames = npcArchives.Contains(archive) || mobile ? file.GetFrameCount(record) : 1;
                        if (frames <= 1) continue;
                        for (int frame = 1; frame < frames; frame++)
                            using (var s = zip.CreateEntry($"dfflat/F{archive:D3}R{record:D2}_f{frame}.png", CompressionLevel.Fastest).Open()) WriteFlatPng(s, file.GetDFBitmap(record, frame), file.Palette);
                        int animatedRecord = record, animatedArchive = archive;
                        AppendAnimation(npcAnimation, f => $"dfflat/F{animatedArchive:D3}R{animatedRecord:D2}{(f > 0 ? $"_f{f}" : "")}.png", frames, mobile ? (record == 5 || record == 15 ? 1 : 4) : BillboardFps(archive)); // MobilePersonBillboard's idle and walk speeds
                    }
                }
                if (npcAnimation.Length > 0) Text("ANIMDEFS", npcAnimation.ToString());
                Text("DFMOBILE", mobileScales.ToString());
                var home = maps.GetLocation(WorldTerrain.Places[(207, 213)].RegionIndex, WorldTerrain.Places[(207, 213)].LocationIndex);
                var scene = new Scene(arena2, home, 0, 0);
                scene.WriteSharedSky(zip);
                scene.BuildGateModels(arch);
                string modeldef = "";
                for (int slot = 0; slot < 2; slot++)
                {
                    Text($"models/dfdoors/gate{slot}.obj", scene.GateObj(slot));
                    modeldef += $"Model DFDoorVisual{slot}{(char)10}{{{(char)10}Path \"models/dfdoors\"{(char)10}DONTCULLBACKFACES{(char)10}Model 0 \"gate{slot}.obj\"{(char)10}FrameIndex DFDR A 0 0{(char)10}}}{(char)10}";
                }
                Text("MODELDEF", modeldef);
                // One map entry is the template for every generated location. The engine gives each its own copy.
                Text("MAPINFO", "GameInfo\n{\n\tAddEventHandlers = \"DFRuntimeHandler\"\n}\nmap DDTOWN \"Daggerfall Location\"\n{\n\tpixelratio = 1.0\n\tsky1 = \"DFSKY\"\n\tkeepfullinventory\n}\n");
                string doors = File.ReadAllText(Path.Combine(SourceDirectory(), "door_objects.zs"));
                doors = doors.Substring(doors.IndexOf((char)10) + 1);
                Text("zscript.zs", RuntimeScript + doors + "class DFDoorVisual0 : DFDoorVisual {}" + (char)10 + "class DFDoorVisual1 : DFDoorVisual {}" + (char)10);
            }
            File.Move(temp, outFile, true);
            // A readable list for choosing test locations. It names game content, so it stays beside the package, outside the repository.
            File.WriteAllLines(Path.ChangeExtension(outFile, ".groups.tsv"), groups.Select((g, id) => $"{id}\t{g.Count}\t{g.Max(p => p.BlocksWide * p.BlocksHigh)}\t{string.Join("; ", g.Select(p => $"{p.Region}/{p.Name} {p.Type} {p.BlocksWide}x{p.BlocksHigh}"))}"));
            Console.WriteLine($"runtime assets: {groups.Count} groups ({tooLarge} over the map limit), {meshImages} mesh textures, {windowMasks} window masks, {flatImages} billboards, {new FileInfo(outFile).Length / 1048576} MiB, {clock.ElapsedMilliseconds} ms");
            return 0;
        }

        const string RuntimeScript = @"version ""4.10""

// [DoomDaggerfall] Shared script for Daggerfall locations converted during play.
class DFCityFlat : Actor
{
	Default { +NOINTERACTION +NOBLOCKMAP +NOGRAVITY +DONTSPLASH +NOTONAUTOMAP Radius 1; Height 1; }
	States { Spawn: PLAY A -1; Stop; }
}

// A Daggerfall NPC. It blocks nothing and takes no damage. args[0] and args[1] hold the low and high halves of its id.
class DFNpc : DFCityFlat {}

// A townsperson Daggerfall generated. The engine moves it from Daggerfall's list; ddRecordId holds its id.
class DFTownsperson : DFCityFlat {}

class DFRuntimeTown
{
	// Called by the engine on a fresh entry. Each line: slot pivotX pivotY pivotZ angle x0 x1 y0 y1 z0 z1 direction.
	play static void SpawnGates(String body)
	{
		Array<String> lines;
		body.Split(lines, ""\n"", TOK_SKIPEMPTY);
		int count = 0;
		for (int n = 0; n < lines.Size(); n++)
		{
			Array<String> f;
			lines[n].Split(f, "" "", TOK_SKIPEMPTY);
			if (f.Size() < 12) continue;
			let door = DFDoor(Actor.Spawn(""DFDoor"", (f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble()), NO_REPLACE));
			door.Setup(f[0].ToInt(), f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble(), f[4].ToDouble(),
				f[5].ToDouble(), f[6].ToDouble(), f[7].ToDouble(), f[8].ToDouble(), f[9].ToDouble(), f[10].ToDouble());
			door.swingDir = f[11].ToDouble();
			door.solidWhenOpen = true;
			count++;
		}
		{ let dbg = CVar.FindCVar(""dd_debugmessages""); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, ""DFGATES spawned %d leaves"", count); } // diagnostics: on screen only with dd_debugmessages
	}
}

class DFRuntimeHandler : EventHandler
{
	static bool IsTown()
	{
		String prefix = level.MapName.Left(3);
		if ((prefix ~== ""DDT"" || prefix ~== ""DDS"") && level.MapName.Length() == 8) return true;
		return level.MapName ~== ""MAP01"" && Wads.CheckNumForName(""DDDUNGN"", Wads.ns_global) >= 0;	// A dungeon entered from a town.
	}
	override void WorldLoaded(WorldEvent e) { if (IsTown()) for (int i = 0; i < MAXPLAYERS; i++) if (playeringame[i]) Fit(players[i].mo); }
	override void PlayerEntered(PlayerEvent e) { if (IsTown()) Fit(players[e.PlayerNumber].mo); }
	static void Fit(PlayerPawn mo) { if (mo) mo.A_SetSize(10.5, mo.height); }
}
";

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

        // ---- Terrain heights come from WorldTerrain, the same function the overworld uses ----

        static float Perlin(float x, float y) => WorldTerrain.Perlin(x, y);

        static void PrepareSite(Site site)
        {
            var place = site.Place;
            for (int by = 0; by < place.BlocksHigh; by++)
                for (int bx = 0; bx < place.BlocksWide; bx++)
                {
                    var ground = site.Blocks[by * place.BlocksWide + bx].RmbBlock.FldHeader.GroundData.GroundTiles;
                    for (int ty = 0; ty < TilesPerBlock; ty++)
                        for (int tx = 0; tx < TilesPerBlock; tx++)
                        {
                            var tile = ground[tx, TilesPerBlock - 1 - ty];
                            if (tile.TextureRecord >= 56) continue;
                            site.Tiles[place.OriginX + bx * TilesPerBlock + tx, place.OriginY + by * TilesPerBlock + ty] = tile.TileBitfield == 0 ? byte.MaxValue : tile.TileBitfield;
                        }
                }
            site.FlatX0 = site.DX * TilesPerPixel + place.RectX0; site.FlatX1 = site.DX * TilesPerPixel + place.RectX1;
            site.FlatY0 = site.DY * TilesPerPixel + place.RectY0; site.FlatY1 = site.DY * TilesPerPixel + place.RectY1;
            site.Target = WorldTerrain.Pixel(place.X, place.Y)[(place.RectX0 + place.RectX1) / 2, (place.RectY0 + place.RectY1) / 2];
        }

        static int FloorDiv(int a, int b) => WorldTerrain.FloorDiv(a, b);

        // Normalized height at a tile vertex relative to the primary location's map pixel. +y is north, toward smaller map pixel Y.
        static float Height(int tx, int ty) => WorldTerrain.Height(cityX * TilesPerPixel + tx, (WorldTerrain.WorldH - 1 - cityY) * TilesPerPixel + ty);

        static double DoomZ(int tx, int ty) => (Height(tx, ty) - target) * HeightToDf * S;
        static double DoomX(int t) => (t - originTileX) * DoomTile;
        static double DoomY(int t) => (t - originTileY) * DoomTile;

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
            uint hash = (uint)((cityX * TilesPerPixel + tx) * 73856093) ^ (uint)(((WorldTerrain.WorldH - 1 - cityY) * TilesPerPixel + ty) * 19349663); // world tiles, so every map agrees
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
            int tilePixelX = FloorDiv(tx, TilesPerPixel), tilePixelY = FloorDiv(ty, TilesPerPixel);
            foreach (var site in sites)
            {
                if (site.DX != tilePixelX || site.DY != tilePixelY) continue;
                byte own = site.Tiles[tx - tilePixelX * TilesPerPixel, ty - tilePixelY * TilesPerPixel];
                if (own != 0) return own == byte.MaxValue ? (byte)0 : own;
            }
            int b0 = TileClass(tx, ty), b1 = TileClass(tx + 1, ty), b2 = TileClass(tx, ty + 1), b3 = TileClass(tx + 1, ty + 1);
            int shape = (b0 & 1) | (b1 & 1) << 1 | (b2 & 1) << 2 | (b3 & 1) << 3;
            return lookup[shape | ((b0 + b1 + b2 + b3) >> 2) << 4];
        }

        // ---- Visual scene ----

        sealed class Scene
        {
            public readonly List<(V3 a, V3 b, V3 c)> Colliders = new List<(V3, V3, V3)>();
            public readonly List<int> ColliderOwners = new List<int>(); // building id per collider triangle, or -1 for walls, gates, and props
            int currentOwner = -1, nextOwner;
            public readonly List<(int archive, int record, double x, double y, double z, double sx, double sy, ulong npc)> Flats = new List<(int, int, double, double, double, double, double, ulong)>();
            public int Models, Missing, Gates, BadTextures, BatchCount;
            public int Triangles => batches.Values.Sum(b => b.Count) / 24;
            public readonly List<V3> ColliderNormals = new List<V3>(); // Doom axes, parallel to Colliders
            public readonly List<(uint id, int instance)> ColliderModels = new List<(uint, int)>();
            public int DoorGroup = -1; // The runtime group, so the town can list its doors.
            public readonly List<string> DoorLines = new List<string>();
            int nextBuilding;

            readonly string arena2;
            DFLocation location;
            readonly double originX, originZ;
            readonly Dictionary<(int archive, int record), List<float>> batches = new Dictionary<(int, int), List<float>>();
            readonly Dictionary<int, TextureFile> files = new Dictionary<int, TextureFile>();
            readonly Dictionary<uint, DFMesh> meshes = new Dictionary<uint, DFMesh>();
            readonly Dictionary<(int, int), (double w, double h, double texW, double texH)> flatSizes = new Dictionary<(int, int), (double, double, double, double)>();

            public Scene(string arena2, DFLocation location, double originX, double originZ)
            {
                this.arena2 = arena2; this.location = location; this.originX = originX; this.originZ = originZ;
            }

            public void Use(DFLocation current) => location = current; // climate swaps follow the location being placed

            TextureFile Archive(int a)
            {
                if (files.TryGetValue(a, out var f)) return f;
                string path = Path.Combine(arena2, TextureFile.IndexToFileName(a));
                f = File.Exists(path) ? new TextureFile(path, FileUsage.UseMemory, true) : null;
                return files[a] = f;
            }

            static readonly HashSet<int> ClimateSets = new HashSet<int> { 2, 7, 9, 10, 12, 13, 14, 15, 17, 18, 26, 27, 29, 30, 35, 36, 38, 39, 42, 43, 58, 59, 61, 62, 64, 65, 69, 70, 79, 80, 82, 83, 74,
                11, 16, 19, 20, 22, 23, 24, 25, 28, 37, 40, 41, 44, 45, 47, 48, 60, 63, 66, 68 };

            // ClimateSwaps.GetClimateTextureInfo's sets with supportsWinter: terrain and the exterior building sets.
            static readonly HashSet<int> WinterSets = new HashSet<int> { 2, 7, 9, 12, 14, 17, 26, 29, 35, 38, 42, 58, 61, 64, 69, 79, 80, 82, 83 };

            // ClimateSwaps.ApplyClimate for summer, or for winter with --winter.
            int Swap(int archive, int record)
            {
                if (archive % 100 == 74 && record == 3) return archive;
                if (archive >= 500) return Winter && SnowyNature(archive) ? archive + 1 : archive;
                int set = archive % 100;
                // Same whitelist as ClimateSwaps.GetClimateTextureInfo; other sets (wagon 88, hedges, planks, furniture) never swap.
                if (!ClimateSets.Contains(set)) return archive;
                string setName = ((DFLocation.ClimateTextureSet)set).ToString();
                if (location.Climate.ClimateType == DFLocation.ClimateBaseType.Swamp && setName == "Interior_MarbleFloors") return archive;
                bool winter = Winter && SupportsWinter(set, setName, archive, record);
                if (archive is 75 or 76 or 77 or 79 or 80 or 82 or 83) return winter ? archive + 1 : archive;
                return (int)location.Climate.ClimateType + set + (winter ? 1 : 0);
            }

            // ClimateSwaps' winter rules: terrain and exterior sets have a winter variant, never in desert climates,
            // and a few archives lack one. The Castle test keeps ClimateSwaps' operator precedence (any climate).
            bool SupportsWinter(int set, string setName, int archive, int record)
            {
                if (location.Climate.ClimateType == DFLocation.ClimateBaseType.Desert) return false;
                if (!WinterSets.Contains(set)) return false;
                if (location.Climate.ClimateType == DFLocation.ClimateBaseType.Swamp && setName == "Exterior_MagesGuild" || setName == "Exterior_Castle" && record > 3) return false;
                if (archive == 82 && record > 1 || archive == 77) return false;
                return true;
            }

            public void AddModel(Arch3dFile arch, uint id, V3 position, double rx, double ry, double rz, V3 scale, V3 parent, double parentYaw)
            {
                // A gate's frame stays in the static mesh. Its two leaves become swinging door objects (AddGate).
                if (id == GateClosed) id = GateOpen;
                bool isGate = id == GateOpen;
                if (isGate) Gates++;
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
                        if (isGate && GateLeaf(sub.TextureArchive, plane) != 0) continue;
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
                            ColliderOwners.Add(isGate ? -1 : currentOwner);
                            ColliderNormals.Add(new V3(n.X / length, n.Z / length, n.Y / length));
                            ColliderModels.Add((id, Models));
                        }
                    }
                }
                if (isGate) AddGate(mesh, Place);
            }

            // Model 446 holds both leaves in their open pose: left beside x = -314, right beside x = 59, both hinged at z = -128.
            const double HingeLeftX = -314, HingeRightX = 59, HingeZ = -128;
            const int GateTextureArchive = 321;
            readonly string[] gateLeafObj = new string[2];
            readonly double[,] gateLeafBounds = new double[2, 6];
            public readonly List<string> GatePlacements = new List<string>();

            static int GateLeaf(int archive, DFMesh.DFPlane plane)
            {
                if (archive != GateTextureArchive) return 0;
                double low = plane.Points.Min(p => (double)p.X), high = plane.Points.Max(p => (double)p.X);
                return high <= -282 ? 1 : low >= 27 && high <= 59 ? -1 : 0;
            }

            // Writes one leaf as an OBJ in its closed pose, relative to the hinge, as door_objects.zs expects.
            void BuildGateLeaf(DFMesh mesh, int leaf)
            {
                int slot = leaf > 0 ? 0 : 1;
                double hx = leaf > 0 ? HingeLeftX : HingeRightX;
                (double x, double y) Close(double ox, double oz) => leaf > 0 ? (oz, -ox) : (-oz, ox);
                double x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, z0 = 1e9, z1 = -1e9;
                foreach (var sub in mesh.SubMeshes)
                    foreach (var plane in sub.Planes)
                    {
                        if (GateLeaf(sub.TextureArchive, plane) != leaf) continue;
                        foreach (var p in plane.Points)
                        {
                            var c = Close(p.X - hx, p.Z - HingeZ);
                            x0 = Math.Min(x0, c.x * S); x1 = Math.Max(x1, c.x * S); y0 = Math.Min(y0, c.y * S); y1 = Math.Max(y1, c.y * S);
                            z0 = Math.Min(z0, -p.Y * S); z1 = Math.Max(z1, -p.Y * S);
                        }
                    }
                double cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
                string F(double v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
                var text = new StringBuilder("# Daggerfall gate leaf" + (char)10);
                int next = 1;
                foreach (var sub in mesh.SubMeshes)
                {
                    var source = Archive(sub.TextureArchive);
                    double w = source.GetWidth(sub.TextureRecord), h = source.GetHeight(sub.TextureRecord);
                    int archive = Swap(sub.TextureArchive, sub.TextureRecord);
                    if (Archive(archive) == null || sub.TextureRecord >= Archive(archive).RecordCount) archive = sub.TextureArchive;
                    bool any = false;
                    foreach (var plane in sub.Planes)
                    {
                        if (GateLeaf(sub.TextureArchive, plane) != leaf) continue;
                        if (!any)
                        {
                            any = true;
                            text.Append($"usemtl dfmesh/a{archive:D3}r{sub.TextureRecord:D2}.png" + (char)10);
                            if (!batches.ContainsKey((archive, sub.TextureRecord))) batches[(archive, sub.TextureRecord)] = new List<float>(); // keeps the texture in the package
                        }
                        int first = next;
                        foreach (var p in plane.Points)
                        {
                            var c = Close(p.X - hx, p.Z - HingeZ);
                            var n = Close(p.NX, p.NZ);
                            double nz = -p.NY, length = Math.Sqrt(n.x * n.x + n.y * n.y + nz * nz);
                            if (length < 1e-6) length = 1;
                            // The engine's OBJ loader negates z and flips v.
                            text.Append($"v {F(c.x * S - cx)} {F(-p.Y * S)} {F(-(c.y * S - cy))}{(char)10}vt {F(p.U / w)} {F(1 - p.V / h)}{(char)10}vn {F(n.x / length)} {F(nz / length)} {F(-n.y / length)}{(char)10}");
                            next++;
                        }
                        for (int i = 1; i + 1 < plane.Points.Length; i++)
                        {
                            int a = first, b = first + i + 1, d = first + i;
                            text.Append($"f {a}/{a}/{a} {b}/{b}/{b} {d}/{d}/{d}" + (char)10);
                        }
                    }
                }
                gateLeafObj[slot] = text.ToString();
                gateLeafBounds[slot, 0] = x0; gateLeafBounds[slot, 1] = x1; gateLeafBounds[slot, 2] = y0;
                gateLeafBounds[slot, 3] = y1; gateLeafBounds[slot, 4] = z0; gateLeafBounds[slot, 5] = z1;
            }

            void AddGate(DFMesh mesh, Func<double, double, double, V3> place)
            {
                if (gateLeafObj[0] == null) { BuildGateLeaf(mesh, 1); BuildGateLeaf(mesh, -1); }
                var origin = place(0, 0, 0);
                var axis = place(1, 0, 0);
                double angle = Math.Atan2(axis.Z - origin.Z, axis.X - origin.X) * 180 / Math.PI;
                for (int slot = 0; slot < 2; slot++)
                {
                    var hinge = place(slot == 0 ? HingeLeftX : HingeRightX, 0, HingeZ);
                    GatePlacements.Add(FormattableString.Invariant($"{slot} {(hinge.X - originX) * S:F3} {(hinge.Z - originZ) * S:F3} {hinge.Y * S:F3} {angle:F3} {gateLeafBounds[slot, 0]:F3} {gateLeafBounds[slot, 1]:F3} {gateLeafBounds[slot, 2]:F3} {gateLeafBounds[slot, 3]:F3} {gateLeafBounds[slot, 4]:F3} {gateLeafBounds[slot, 5]:F3} {(slot == 0 ? 1 : -1)}"));
                }
            }

            // Town billboards stand on their position. Interior ones are centered on it, as in Daggerfall Unity.
            public void AddFlat(int archive, int record, double x, double up, double z, bool centered = false, ulong npc = 0)
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
                if (centered) up -= size.h / 2;
                Flats.Add((archive, record, (x - originX) * S, (z - originZ) * S, up * S, size.w / size.texW * S, size.h / size.texH * S, npc));
            }

            public void AddBlock(DFBlock block, Arch3dFile arch, double blockX, double blockZ, double up, int mapId, int layoutX, int layoutY)
            {
                const double toRad = Math.PI / 180;
                double div = BlocksFile.RotationDivisor;
                var data = block.RmbBlock;
                var origin = new V3(blockX, 2 + up, blockZ);
                bool isWallBlock = (block.Name ?? "").StartsWith("WALL", StringComparison.OrdinalIgnoreCase);
                V3 ScaleOf(DFBlock.RmbBlock3dObjectRecord o) => new V3(o.XScale == 0 ? 1 : o.XScale, o.YScale == 0 ? 1 : o.YScale, o.ZScale == 0 ? 1 : o.ZScale);
                foreach (var sub in data.SubRecords)
                {
                    var parent = origin + new V3(sub.XPos, 0, RmbDf - sub.ZPos);
                    double yaw = -sub.YRotation / div * toRad;
                    // One subrecord is one building. City wall blocks and gates keep their full-height collision.
                    currentOwner = !isWallBlock && !sub.Exterior.Block3dObjectRecords.Any(o => o.ModelIdNum == GateOpen || o.ModelIdNum == GateClosed) ? nextOwner++ : -1;
                    foreach (var o in sub.Exterior.Block3dObjectRecords)
                        AddModel(arch, o.ModelIdNum, new V3(o.XPos, -o.YPos, o.ZPos), -o.XRotation / div * toRad, -o.YRotation / div * toRad, -o.ZRotation / div * toRad, ScaleOf(o), parent, yaw);
                    AddDoors(sub, arch, parent, yaw, nextBuilding++);
                    foreach (var f in sub.Exterior.BlockFlatObjectRecords)
                    {
                        if (f.TextureArchive == 199) continue; // editor markers
                        int archive = f.TextureArchive;
                        double fx = origin.X + sub.XPos + f.XPos, fy = origin.Y - f.YPos - 6, fz = origin.Z - sub.ZPos + f.ZPos + RmbDf;
                        if (archive >= (int)DFLocation.ClimateTextureSet.Nature_RainForest && archive <= (int)DFLocation.ClimateTextureSet.Nature_Mountains_Snow)
                            archive = NatureArchive(location);
                        AddFlat(archive, f.TextureRecord, fx, fy, fz, false, f.FactionID != 0 ? NpcIdentity.Make(mapId, NpcIdentity.Exterior, layoutX, layoutY, 0, f.Position) : 0);
                    }
                }
                currentOwner = -1;
                foreach (var o in data.Misc3dObjectRecords)
                    AddModel(arch, o.ModelIdNum, new V3(o.XPos, -o.YPos - 4, o.ZPos + RmbDf), -o.XRotation / div * toRad, -o.YRotation / div * toRad, -o.ZRotation / div * toRad, ScaleOf(o), origin, 0);
                if (DoorGroup >= 0) AddDoorsFrom(data.Misc3dObjectRecords, arch, origin, 0, new V3(0, -4, RmbDf), MaxBuildings, false);
                foreach (var f in data.MiscFlatObjectRecords)
                    if (f.TextureArchive != 199)
                        AddFlat(f.TextureArchive, f.TextureRecord, origin.X + f.XPos, origin.Y - f.YPos - 6, origin.Z + f.ZPos + RmbDf, false, f.FactionID != 0 ? NpcIdentity.Make(mapId, NpcIdentity.Exterior, layoutX, layoutY, 0, f.Position) : 0);
                var scenery = data.FldHeader.GroundData.GroundScenery;
                for (int y = 0; y < 16; y++)
                    for (int x = 0; x < 16; x++)
                        if (scenery[x, 15 - y].TextureRecord >= 1)
                            AddFlat(NatureArchive(location), scenery[x, 15 - y].TextureRecord, origin.X + x * TileDf, origin.Y - 2, origin.Z + y * TileDf + TileDf);
            }

            // DDDOORS, one per line: kind target index x y z nx ny, in town map units. Kind 0 targets an interior space
            // id, and kind 1 a dungeon's Daggerfall map id. The height is the door's bottom edge.
            void AddDoors(DFBlock.RmbSubRecord sub, Arch3dFile arch, V3 parent, double yaw, int building)
            {
                if (DoorGroup < 0) return;
                bool hasInterior = building < MaxBuildings && sub.Interior.Block3dObjectRecords != null && sub.Interior.Block3dObjectRecords.Length > 0;
                AddDoorsFrom(sub.Exterior.Block3dObjectRecords, arch, parent, yaw, new V3(0, 0, 0), building, hasInterior);
            }

            // Dungeon entrances are often block-level models rather than part of a building record.
            void AddDoorsFrom(DFBlock.RmbBlock3dObjectRecord[] records, Arch3dFile arch, V3 parent, double yaw, V3 shift, int building, bool hasInterior)
            {
                const double toRad = Math.PI / 180;
                double div = BlocksFile.RotationDivisor;
                int index = 0;
                foreach (var o in records)
                {
                    int record = arch.GetRecordIndex(o.ModelIdNum);
                    if (record < 0) continue;
                    var scale = new V3(o.XScale == 0 ? 1 : o.XScale, o.YScale == 0 ? 1 : o.YScale, o.ZScale == 0 ? 1 : o.ZScale);
                    double rx = -o.XRotation / div * toRad, ry = -o.YRotation / div * toRad, rz = -o.ZRotation / div * toRad;
                    foreach (var door in DoorPlanes(arch.GetMesh(record)))
                    {
                        if (door.Type == DoorExit) continue;
                        int doorIndex = door.Type == DoorBuilding ? index++ : 0; // Interior landings count building doors only.
                        if (door.Type == DoorBuilding && !hasInterior) continue;
                        if (door.Type == DoorEntrance && !location.HasDungeon) continue;
                        var local = new V3(door.Centre.X * scale.X, door.Centre.Y * scale.Y, door.Centre.Z * scale.Z);
                        var at = Rotate(Rotate(local, rx, ry, rz) + new V3(o.XPos, -o.YPos, o.ZPos) + shift, 0, yaw, 0) + parent;
                        var n = Rotate(Rotate(door.Normal, rx, ry, rz), 0, yaw, 0);
                        int kind = door.Type == DoorBuilding ? 0 : 1;
                        int target = kind == 0 ? SpaceBase + DoorGroup * SpacePerGroup + building : location.MapTableData.MapId;
                        DoorLines.Add(FormattableString.Invariant($"{kind} {target} {doorIndex} {(at.X - originX) * S:F3} {(at.Z - originZ) * S:F3} {(at.Y - door.HalfHeight * Math.Abs(scale.Y)) * S + 2:F3} {n.X:F4} {n.Z:F4}"));
                    }
                }
            }

            public void AddTerrain(int fromX, int toX, int fromY, int toY)
            {
                int archive = GroundArchive(location);
                for (int ty = fromY; ty < toY; ty++)
                    for (int tx = fromX; tx < toX; tx++)
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
                            v.Add((float)DoomX(x)); v.Add((float)DoomZ(x, y)); v.Add((float)DoomY(y));
                            v.Add(tu); v.Add(1 - tv); // Unity samples tile images bottom-up
                            v.Add(0); v.Add(1); v.Add(0);
                        }
                        Emit(tx, ty); Emit(tx, ty + 1); Emit(tx + 1, ty + 1);
                        Emit(tx, ty); Emit(tx + 1, ty + 1); Emit(tx + 1, ty);
                    }
            }

            // DefaultTerrainNature's rules. Unity's random sequence is not reproduced, so individual trees differ from Daggerfall Unity.
            // Only the walkable area gets trees: a billboard outside every Doom sector would never be drawn.
            public void AddNature(int fromX, int toX, int fromY, int toY)
            {
                const int clearance = 4;
                const double maxSteepness = 50, sinkRatio = 70;
                var random = new Random(TerrainKey(cityX, cityY));
                for (int y = fromY; y < toY; y++)
                    for (int x = fromX; x < toX; x++)
                    {
                        if (!Walkable(x, y) || sites.Any(q => x >= q.FlatX0 - clearance && x < q.FlatX1 + clearance && y >= q.FlatY0 - clearance && y < q.FlatY1 + clearance)) continue;
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
                        AddFlat(NatureArchive(location), record, originX + (x - originTileX) * TileDf, up, originZ + (y - originTileY) * TileDf);
                    }
            }

            static int TerrainKey(int x, int y) => (y << 16) + x;

            public void WritePackage(string path, DFLocation place, string metadata, string townInfo, string mapName)
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
                using (var s = zip.CreateEntry("DFMESH", CompressionLevel.Fastest).Open()) WriteMesh(s, keys, mapName);
                foreach (var k in keys)
                {
                    var file = Archive(k.archive);
                    var image = file != null && k.record < file.RecordCount ? file.GetDFBitmap(k.record, 0) : null;
                    if (image?.Data == null || image.Width == 0) { BadTextures++; Console.WriteLine($"missing texture {k.archive}:{k.record}"); continue; }
                    using (var s = zip.CreateEntry($"dfmesh/a{k.archive:D3}r{k.record:D2}.png", CompressionLevel.Fastest).Open())
                        WriteTexturePng(s, image, file.Palette);
                    WriteWindowMask(zip, k.archive, k.record, image, file.Palette);
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
                Text("DDTOWN", townInfo);
                WriteSky(zip);
                Text("MAPINFO", $"GameInfo\n{{\n\tAddEventHandlers = \"DFCityHandler\"\n}}\nmap {mapName} \"{place.Name}\"\n{{\n\tpixelratio = 1.0\n\tsky1 = \"DFSKY\"\n\tkeepfullinventory\n}}\n");
                // The swinging gates reuse the dungeon door runtime. Its handler is not registered here, so only DFGATES spawns doors.
                string doors = File.ReadAllText(Path.Combine(SourceDirectory(), "door_objects.zs"));
                doors = doors.Substring(doors.IndexOf((char)10) + 1);
                Text("zscript.zs", CityScript.Replace("@MAP@", mapName) + doors + "class DFDoorVisual0 : DFDoorVisual {}" + (char)10 + "class DFDoorVisual1 : DFDoorVisual {}" + (char)10);
                Text("DFGATES", string.Join((char)10, GatePlacements) + (char)10);
                if (gateLeafObj[0] != null)
                {
                    var modeldef = new StringBuilder();
                    for (int slot = 0; slot < 2; slot++)
                    {
                        Text($"models/dfdoors/gate{slot}.obj", gateLeafObj[slot]);
                        modeldef.Append($"Model DFDoorVisual{slot}{(char)10}{{{(char)10}Path \"models/dfdoors\"{(char)10}DONTCULLBACKFACES{(char)10}Model 0 \"gate{slot}.obj\"{(char)10}FrameIndex DFDR A 0 0{(char)10}}}{(char)10}");
                    }
                    Text("MODELDEF", modeldef.ToString());
                }
            }

            void WriteMesh(Stream s, List<(int archive, int record)> keys, string mapName)
            {
                var writer = new BinaryWriter(s);
                writer.Write(Encoding.ASCII.GetBytes("DFM1"));
                writer.Write(Encoding.ASCII.GetBytes(mapName.PadRight(8, '\0')));
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

            // One cache entry: "DDT3", entry count, then name[8], raw size, packed size for each, then the zlib streams.
            // It is written to a temporary file and renamed, so the engine never sees a partial entry.
            public void WriteRuntimeEntry(string path, string wadPath, string townInfo, string mapName)
            {
                var keys = batches.Keys.OrderBy(k => k.archive).ThenBy(k => k.record).ToList();
                BatchCount = keys.Count;
                var mesh = new MemoryStream();
                WriteMesh(mesh, keys, mapName);
                var flatList = new StringBuilder();
                foreach (var f in Flats)
                    flatList.Append(FormattableString.Invariant($"dfflat/F{f.archive:D3}R{f.record:D2}.png {f.x:F2} {f.y:F2} {f.z:F2} {f.sx:F4} {f.sy:F4}{(f.npc != 0 ? $" {f.npc:x16}" : "")}\n"));
                var entries = new (string name, byte[] data)[]
                {
                    ("MAPWAD", File.ReadAllBytes(wadPath)), ("DFMESH", mesh.ToArray()), ("DFFLATS", Encoding.ASCII.GetBytes(flatList.ToString())),
                    ("DFGATES", Encoding.ASCII.GetBytes(string.Join((char)10, GatePlacements) + (char)10)), ("DDTOWN", Encoding.ASCII.GetBytes(townInfo)),
                    ("DDDOORS", Encoding.ASCII.GetBytes(string.Join((char)10, DoorLines) + (char)10)),
                };
                var packed = new byte[entries.Length][];
                System.Threading.Tasks.Parallel.For(0, entries.Length, i =>
                {
                    var body = new MemoryStream();
                    using (var z = new ZLibStream(body, CompressionLevel.Fastest, true)) z.Write(entries[i].data);
                    packed[i] = body.ToArray();
                });
                string temp = path + ".tmp";
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
                using (var w = new BinaryWriter(File.Create(temp)))
                {
                    w.Write(Encoding.ASCII.GetBytes("DDT3"));
                    w.Write(entries.Length);
                    for (int i = 0; i < entries.Length; i++)
                    {
                        w.Write(Encoding.ASCII.GetBytes(entries[i].name.PadRight(8, '\0')));
                        w.Write(entries[i].data.Length);
                        w.Write(packed[i].Length);
                    }
                    foreach (var body in packed) w.Write(body);
                }
                File.Move(temp, path, true);
            }

            public void WriteSharedSky(ZipArchive zip) => WriteSky(zip);

            public void BuildGateModels(Arch3dFile arch)
            {
                var mesh = arch.GetMesh(arch.GetRecordIndex(GateOpen));
                BuildGateLeaf(mesh, 1);
                BuildGateLeaf(mesh, -1);
            }

            public string GateObj(int slot) => gateLeafObj[slot];

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
        // A window mask (dfwin/aNNNrNN.png) for each of Daggerfall's exterior window textures that has emissive pixels.
        static bool WriteWindowMask(ZipArchive zip, int archive, int record, DFBitmap image, DFPalette palette)
        {
            if (!IsExteriorWindow(archive, record) || Array.IndexOf(image.Data, (byte)255) < 0) return false;
            using var s = zip.CreateEntry($"dfwin/a{archive:D3}r{record:D2}.png", CompressionLevel.Fastest).Open();
            WriteFlatPng(s, image, palette, true);
            return true;
        }

        // Daggerfall Unity's ClimateSwaps.IsExteriorWindow, unchanged (that file needs Unity, so it is not compiled here).
        static bool IsExteriorWindow(int archive, int record)
        {
            if (archive >= 375 && archive <= 379 || archive == 210 || archive == 280) return false;
            if (archive == 36 && record == 2 || archive == 151 && record == 3 || archive == 154 && record == 3 || archive == 351 && record == 3 ||
                archive == 171 && record == 2 || archive == 172 && record == 3 || archive == 173 && record == 3)
                return true;
            switch (archive % 100)
            {
                case 9: case 10: case 12: case 13: case 14: case 15: case 26: case 27: case 35: case 36:
                case 38: case 39: case 42: case 43: case 58: case 59: case 61: case 62: case 64: case 65:
                    return record == 3;
                case 75: case 76: case 77: return true;
                case 79: case 80: return record == 0 || record == 2;
                case 82: case 83: return record == 0;
            }
            return false;
        }

        // windowMask: instead, white where the palette index is 255 and clear elsewhere, with no grAb. That is Daggerfall's
        // window emission map (BaseImageFile.GetWindowColors32); Doom tints it with Daggerfall's window colour (hw_dfmesh.cpp).
        static void WriteFlatPng(Stream output, DFBitmap image, DFPalette palette, bool windowMask = false)
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
                    if (windowMask) { raw[at++] = 255; raw[at++] = 255; raw[at++] = 255; raw[at++] = (byte)(index == 255 ? 255 : 0); continue; }
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
            if (!windowMask) Chunk("grAb", Big(w / 2, h));
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
	static bool IsCity() { return level.MapName ~== ""@MAP@"" && Wads.CheckNumForName(""DFCITY"", Wads.ns_global) >= 0; }

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
		{ let dbg = CVar.FindCVar(""dd_debugmessages""); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, ""DFCITY: %d billboards"", rows.Size()); } // diagnostics: on screen only with dd_debugmessages
		SpawnGates();
	}

	// Each gate leaf is a hinged door object: slot pivotX pivotY pivotZ angle x0 x1 y0 y1 z0 z1 direction.
	static void SpawnGates()
	{
		int lump = Wads.CheckNumForName(""DFGATES"", Wads.ns_global);
		if (lump < 0) return;
		Array<String> lines;
		Wads.ReadLump(lump).Split(lines, ""\n"", TOK_SKIPEMPTY);
		int count = 0;
		for (int n = 0; n < lines.Size(); n++)
		{
			Array<String> f;
			lines[n].Split(f, "" "", TOK_SKIPEMPTY);
			if (f.Size() < 12) continue;
			let door = DFDoor(Actor.Spawn(""DFDoor"", (f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble()), NO_REPLACE));
			door.Setup(f[0].ToInt(), f[1].ToDouble(), f[2].ToDouble(), f[3].ToDouble(), f[4].ToDouble(),
				f[5].ToDouble(), f[6].ToDouble(), f[7].ToDouble(), f[8].ToDouble(), f[9].ToDouble(), f[10].ToDouble());
			door.swingDir = f[11].ToDouble();
			door.solidWhenOpen = true;
			count++;
		}
		{ let dbg = CVar.FindCVar(""dd_debugmessages""); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, ""DFGATES spawned %d leaves"", count); } // diagnostics: on screen only with dd_debugmessages
	}

	override void PlayerEntered(PlayerEvent e) { if (IsCity()) Fit(players[e.PlayerNumber].mo); }

	static void Fit(PlayerPawn mo) { if (mo) mo.A_SetSize(10.5, mo.height); }
}
";

        // ---- Collision ----

        sealed partial class Collision
        {
            public static readonly List<(double x, double y)> Probes = new List<(double, double)>(); // --probe x,y;x,y prints what the raster saw
            const double Step = 24, Body = 56, Clearance = 2;
            public int W, H, OpenCells, SolidCells, RemovedCells, KeptRegions;
            public bool ReachesEdge;
            readonly int cell, perTile, flatX0, flatX1, flatY0, flatY1;
            readonly bool primary;
            readonly double x0, y0, baseZ;
            short[] floor; // quantized floor, or short.MinValue when solid
            int[] component;
            int startIndex = -1;

            public Collision(int cell, Site site, bool primary)
            {
                this.cell = cell; this.primary = primary;
                flatX0 = site.FlatX0; flatX1 = site.FlatX1; flatY0 = site.FlatY0; flatY1 = site.FlatY1;
                baseZ = (site.Target - target) * HeightToDf * S;
                perTile = (int)Math.Round(DoomTile / cell);
                W = (flatX1 - flatX0) * perTile; H = (flatY1 - flatY0) * perTile;
                x0 = DoomX(flatX0); y0 = DoomY(flatY0);
            }

            public void Rasterize(List<(V3 a, V3 b, V3 c)> triangles, List<int> owners)
            {
                var hits = new List<(float lo, float hi)>[W * H];
                Span<(double x, double y, double z)> poly = new (double, double, double)[12], next = new (double, double, double)[12];
                // A building's ground is its lowest point, or the street when the model is sunk into it.
                var ground = new double[owners.Count == 0 ? 0 : owners.Max() + 1];
                Array.Fill(ground, double.MaxValue);
                for (int t = 0; t < triangles.Count; t++)
                    if (owners[t] >= 0) ground[owners[t]] = Math.Min(ground[owners[t]], Math.Min(triangles[t].a.Z, Math.Min(triangles[t].b.Z, triangles[t].c.Z)));
                for (int o = 0; o < ground.Length; o++) ground[o] = Math.Max(ground[o], baseZ);
                var sides = new Dictionary<int, HashSet<int>>();
                for (int t = 0; t < triangles.Count; t++)
                {
                    var (a, b, c) = triangles[t];
                    int owner = owners[t];
                    bool vertical = IsVertical(a, b, c);
                    double triLow = Math.Min(a.Z, Math.Min(b.Z, c.Z)), triHigh = Math.Max(a.Z, Math.Max(b.Z, c.Z));
                    bool side = owner >= 0 && vertical && triLow <= ground[owner] + Body && triHigh - triLow >= MinSideHeight;
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
                            if (side)
                            {
                                if (!sides.TryGetValue(owner, out var set)) sides[owner] = set = new HashSet<int>();
                                set.Add(i + j * W);
                            }
                            // A roof overhang above step height must not block the player at the wall below it.
                            if (owner >= 0 && !vertical && lo > ground[owner] + Step) continue;
                            (hits[i + j * W] ??= new List<(float, float)>(4)).Add(((float)lo, (float)hi));
                        }
                }

                floor = new short[W * H];
                for (int c = 0; c < floor.Length; c++)
                {
                    var list = hits[c];
                    if (list == null) { floor[c] = (short)(Math.Round(baseZ / 4) * 4); continue; }
                    list.Sort((p, q) => p.lo.CompareTo(q.lo));
                    double f = baseZ;
                    foreach (var (lo, hi) in list)
                        if (hi > f && hi <= f + Step && lo <= f + Step) f = hi;
                    bool solid = false;
                    foreach (var (lo, hi) in list)
                        if (lo < f + Body && hi > f + Clearance) { solid = true; break; }
                    floor[c] = solid ? short.MinValue : (short)(Math.Round(f / 4) * 4);
                }
                var before = (short[])floor.Clone();
                KeepReachable();
                BuildRoofs(triangles, owners, sides);
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
                if (startIndex < 0 && primary) throw new InvalidDataException("no open start cell");
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

            // One UDMF map: each location's raster, and sloped terrain triangles over the walkable tiles around them.
            public static MapText Build(List<Collision> rasters, int tx0, int tx1, int ty0, int ty1)
            {
                var floors = new List<int>();
                var floorSlopes = new List<string>();
                var stack = new Stack<int>();
                foreach (var r in rasters)
                {
                    r.sectorOf = new int[r.W * r.H];
                    Array.Fill(r.sectorOf, NoSector);
                    for (int s = 0; s < r.sectorOf.Length; s++)
                    {
                        int code = r.Code(s);
                        if (code == int.MinValue || r.sectorOf[s] >= 0) continue;
                        int id = floors.Count;
                        floors.Add(r.roofPlane[s] >= 0 ? roofPlanes[r.roofPlane[s]].z : r.floor[s]);
                        floorSlopes.Add(r.RoofSlope(r.roofPlane[s]));
                        r.sectorOf[s] = id;
                        stack.Push(s);
                        while (stack.Count > 0)
                        {
                            int p = stack.Pop(), i = p % r.W, j = p / r.W;
                            void Try(int ni, int nj)
                            {
                                if (ni < 0 || nj < 0 || ni >= r.W || nj >= r.H) return;
                                int q = ni + nj * r.W;
                                if (r.sectorOf[q] < 0 && r.Code(q) == code) { r.sectorOf[q] = id; stack.Push(q); }
                            }
                            Try(i + 1, j); Try(i - 1, j); Try(i, j + 1); Try(i, j - 1);
                        }
                    }
                }
                int citySectors = floors.Count;

                // Terrain: two sloped sectors per walkable tile outside the flat rectangles.
                int across = tx1 - tx0, tall = ty1 - ty0;
                var lower = new int[across * tall]; // triangle (x,y) (x+1,y+1) (x+1,y): right and bottom edges
                var upper = new int[across * tall]; // triangle (x,y) (x,y+1) (x+1,y+1): left and top edges
                var kind = new byte[across * tall]; // 0 outside, 1 terrain, 2 flat
                int TileIndex(int x, int y) => (x - tx0) + (y - ty0) * across;
                for (int y = ty0; y < ty1; y++)
                    for (int x = tx0; x < tx1; x++)
                        kind[TileIndex(x, y)] = (byte)(sites.Any(q => q.InFlat(x, y)) ? 2 : Walkable(x, y) ? 1 : 0);
                bool InBox(int x, int y) => x >= tx0 && x < tx1 && y >= ty0 && y < ty1;
                bool InFlat(int x, int y) => InBox(x, y) && kind[TileIndex(x, y)] == 2;
                bool InMap(int x, int y) => InBox(x, y) && kind[TileIndex(x, y)] == 1;
                var sectors = new StringBuilder();
                string F(double v) => v.ToString("R", CultureInfo.InvariantCulture);
                double maxZ = Math.Max(floors.Count > 0 ? floors.Max() : 0, rasters.Max(q => q.RoofTop()));
                for (int y = ty0; y <= ty1; y++)
                    for (int x = tx0; x <= tx1; x++)
                        if (InMap(x, y) || InMap(x - 1, y) || InMap(x, y - 1) || InMap(x - 1, y - 1)) maxZ = Math.Max(maxZ, DoomZ(x, y));
                int ceiling = (int)Math.Ceiling(maxZ / 64 + 1) * 64 + 2048;
                for (int n = 0; n < floors.Count; n++)
                    sectors.Append($"sector {{ heightfloor = {floors[n]}; heightceiling = {ceiling}; texturefloor = \"FLOOR0_1\"; textureceiling = \"F_SKY1\"; lightlevel = 192;{floorSlopes[n]} }}\n");
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
                        if (!InMap(x, y)) { lower[t] = upper[t] = NoSector; continue; }
                        double X0 = DoomX(x), X1 = DoomX(x + 1), Y0 = DoomY(y), Y1 = DoomY(y + 1);
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
                void Line(double ax, double ay, double bx, double by, int right, int left, bool zone = false)
                {
                    if (right == left) return;
                    if (right < 0) { (ax, ay, bx, by) = (bx, by, ax, ay); (right, left) = (left, right); }
                    int v1 = Vertex(ax, ay), v2 = Vertex(bx, by), front = Side(right, left >= 0);
                    lines.Append(left >= 0 ? $"linedef {{ v1 = {v1}; v2 = {v2}; sidefront = {front}; sideback = {Side(left, true)}; twosided = true;{(zone ? " zoneboundary = true;" : "")} }}\n" : $"linedef {{ v1 = {v1}; v2 = {v2}; sidefront = {front}; blocking = true; }}\n");
                    lineCount++;
                }

                // Terrain edges. Edges against a flat rectangle are written by the raster pass below.
                for (int y = ty0; y < ty1; y++)
                    for (int x = tx0; x < tx1; x++)
                    {
                        if (!InMap(x, y)) continue;
                        int t = TileIndex(x, y);
                        double X0 = DoomX(x), X1 = DoomX(x + 1), Y0 = DoomY(y), Y1 = DoomY(y + 1);
                        Line(X0, Y0, X1, Y1, lower[t], upper[t]);
                        if (!InFlat(x + 1, y)) Line(X1, Y0, X1, Y1, InMap(x + 1, y) ? upper[TileIndex(x + 1, y)] : NoSector, lower[t], (x + 1) % ZoneTiles == 0);
                        if (!InFlat(x, y + 1)) Line(X0, Y1, X1, Y1, upper[t], InMap(x, y + 1) ? lower[TileIndex(x, y + 1)] : NoSector, (y + 1) % ZoneTiles == 0);
                        if (!InMap(x - 1, y) && !InFlat(x - 1, y)) Line(X0, Y0, X0, Y1, upper[t], NoSector);
                        if (!InMap(x, y - 1) && !InFlat(x, y - 1)) Line(X0, Y0, X1, Y0, NoSector, lower[t]);
                    }

                // Raster cell boundaries, merged along their length. Cells past a rectangle resolve to the adjoining terrain triangle.
                foreach (var r in rasters)
                {
                    int W = r.W, H = r.H, cell = r.cell, perTile = r.perTile;
                    double x0 = r.x0, y0 = r.y0;
                    int Id(int i, int j)
                    {
                        if (i >= 0 && j >= 0 && i < W && j < H) return r.sectorOf[i + j * W];
                        if (i < 0) return lower[TileIndex(r.flatX0 - 1, r.flatY0 + j / perTile)];
                        if (i >= W) return upper[TileIndex(r.flatX1, r.flatY0 + j / perTile)];
                        if (j < 0) return upper[TileIndex(r.flatX0 + i / perTile, r.flatY0 - 1)];
                        return lower[TileIndex(r.flatX0 + i / perTile, r.flatY1)];
                    }
                    bool Zone(int a, int b) => a >= citySectors || b >= citySectors; // keeps each zone to one raster or one terrain patch
                    for (int i = 0; i <= W; i++)
                    {
                        int run = -1, runLeft = 0, runRight = 0;
                        for (int j = 0; j <= H; j++)
                        {
                            int l = j < H ? Id(i - 1, j) : NoSector, q = j < H ? Id(i, j) : NoSector;
                            bool edge = j < H && l != q;
                            if (run >= 0 && (!edge || l != runLeft || q != runRight))
                            {
                                Line(x0 + i * cell, y0 + run * cell, x0 + i * cell, y0 + j * cell, runRight, runLeft, Zone(runLeft, runRight));
                                run = -1;
                            }
                            if (edge && run < 0) { run = j; runLeft = l; runRight = q; }
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
                                Line(x0 + run * cell, y0 + j * cell, x0 + i * cell, y0 + j * cell, runBelow, runAbove, Zone(runBelow, runAbove));
                                run = -1;
                            }
                            if (edge && run < 0) { run = i; runBelow = b; runAbove = a; }
                        }
                    }
                }

                var main = rasters[0];
                double startX = main.x0 + (main.startIndex % main.W + 0.5) * main.cell, startY = main.y0 + (main.startIndex / main.W + 0.5) * main.cell;
                var text = new StringBuilder("namespace = \"zdoom\";\n");
                foreach (var pair in vertices.OrderBy(p => p.Value))
                    text.Append($"vertex {{ x = {(pair.Key.Item1 / 8.0).ToString("0.0##", CultureInfo.InvariantCulture)}; y = {(pair.Key.Item2 / 8.0).ToString("0.0##", CultureInfo.InvariantCulture)}; }}\n");
                text.Append(lines).Append(sides).Append(sectors);
                text.Append(FormattableString.Invariant($"thing {{ x = {startX:F1}; y = {startY:F1}; angle = 90; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }}\n"));
                return new MapText { Text = text.ToString(), Sectors = sectorCount, CitySectors = citySectors, TerrainSectors = sectorCount - citySectors, Lines = lineCount, Vertices = vertices.Count, StartX = startX, StartY = startY };
            }

            const int ZoneTiles = 16;
            int[] sectorOf;
        }

        sealed class MapText
        {
            public string Text;
            public int Sectors, CitySectors, TerrainSectors, Lines, Vertices;
            public double StartX, StartY;
        }
    }
}
