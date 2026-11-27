// Dungeons converted while the game runs, into the same disk cache as towns and interiors (dd_towncache.cpp).
//
// --group <DungeonGroupBase + location id> --ddt <file> --out <work dir> converts one dungeon. The location id is the
// low 20 bits of Daggerfall's map id, as dd_treadmill.cpp DungeonSlot uses it. The map is named like an interior space
// (DDS + base 36 of group - SpaceBase), so the engine's runtime map hooks accept it unchanged.
//
// Everything the engine reads only at startup (scripts, MODELDEF, textures, ANIMDEFS) cannot come from a cache file.
// WriteDungeonCatalog puts it in ddruntime.pk3 for every dungeon at once: door and moving action models as classes
// named by model and texture swap (DoorModel.CatalogName), action billboard classes named by texture, every dungeon
// billboard texture, and animated frames of dungeon model textures. --catalog-names makes a conversion use those names.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    public const int DungeonGroupBase = 30000000; // dd_treadmill.cpp DUNGEON_GROUP

    static bool IsRuntimeDungeonGroup(string[] args)
    {
        int at = Array.IndexOf(args, "--group");
        return at >= 0 && at + 1 < args.Length && int.TryParse(args[at + 1], out int group) && group >= DungeonGroupBase;
    }

    static int RunRuntimeDungeon(string[] args)
    {
        string Arg(string name, string fallback) { int at = Array.IndexOf(args, name); return at >= 0 && at + 1 < args.Length ? args[at + 1] : fallback; }
        int group = int.Parse(Arg("--group", "-1"));
        string ddt = Arg("--ddt", null), work = Arg("--out", null), arena2 = Arg("--arena2", @"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2");
        if (ddt == null || work == null) { Console.Error.WriteLine("usage: --group <id> --ddt <file> --out <work dir> [--arena2 <dir>]"); return 2; }
        var clock = Stopwatch.StartNew();
        int locationId = group - DungeonGroupBase;
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var matches = new List<(int mapId, string name)>();
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var candidate = maps.GetLocation(r, l);
                if (candidate.HasDungeon && (candidate.MapTableData.MapId & 0xFFFFF) == locationId) matches.Add((candidate.MapTableData.MapId, region.Name + "/" + region.MapNames[l]));
            }
        }
        if (matches.Count != 1) { Console.Error.WriteLine($"location id {locationId}: {matches.Count} dungeons match"); return 1; }
        var (mapId, place) = matches[0];
        string mapName = City.SpaceMapName(group);

        // Each step runs in its own process: the converter keeps its state in statics that one conversion leaves behind.
        Directory.CreateDirectory(work);
        string self = Environment.ProcessPath;
        var common = new[] { "#" + mapId, "--out", work, "--arena2", arena2, "--map-name", mapName };
        int Step(params string[] extra)
        {
            var info = new ProcessStartInfo(self) { UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true };
            foreach (string a in common.Concat(extra)) info.ArgumentList.Add(a);
            using var p = Process.Start(info);
            string output = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
            p.WaitForExit();
            File.AppendAllText(Path.Combine(work, "convert.log"), output);
            return p.ExitCode;
        }
        int mapCode = Step();
        if (mapCode != 0) { Console.Error.WriteLine($"map conversion failed ({mapCode}), see {work}\\convert.log"); return 1; }
        int meshCode = Step("--export-mesh", "--runtime-dungeon", "--catalog-names");
        string slug = new string(("#" + mapId).Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant();
        string wad = Path.Combine(work, slug + ".wad"), meshPk3 = Path.Combine(work, slug + "_mesh.pk3"), doorsPk3 = Path.Combine(work, slug + "_doors.pk3");
        // A mesh step that names a missing model or texture still writes its packages and exits 1, as for prebuilt dungeons.
        if (!File.Exists(meshPk3) || !File.Exists(doorsPk3)) { Console.Error.WriteLine($"mesh export failed ({meshCode}), see {work}\\convert.log"); return 1; }

        var entries = new List<(string name, byte[] data)> { ("MAPWAD", File.ReadAllBytes(wad)) };
        using (var mesh = ZipFile.OpenRead(meshPk3)) entries.Add(("DFMESH", ReadEntry(mesh, "DFMESH")));
        using (var doors = ZipFile.OpenRead(doorsPk3))
            foreach (string lump in new[] { "DDDUNGN", "DFDOORS", "DFACTIONS", "DFDFLATS", "DFDLIGHTS" })
                if (doors.GetEntry(lump) != null) entries.Add((lump.Length > 8 ? lump.Substring(0, 8) : lump, ReadEntry(doors, lump))); // cache names hold 8 characters
        City.Scene.WriteDdt(ddt, entries);
        Console.WriteLine($"dungeon {mapName} map {mapId} {place}: {new FileInfo(ddt).Length / 1024} KiB, {clock.ElapsedMilliseconds} ms (mesh step exit {meshCode})");
        return 0;
    }

    // Every dungeon with its type, for choosing test samples (runtime_dungeon_check.py). Usage: --list-dungeon-types
    static int ListDungeonTypes(string arena2)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (location.HasDungeon)
                    Console.WriteLine($"DUNGEON\t{location.MapTableData.MapId}\t{location.MapTableData.DungeonType}\t{region.Name}/{region.MapNames[l]}\t{location.Dungeon.Blocks.Length}");
            }
        }
        return 0;
    }

    static byte[] ReadEntry(ZipArchive zip, string name)
    {
        using var s = zip.GetEntry(name).Open();
        var m = new MemoryStream();
        s.CopyTo(m);
        return m.ToArray();
    }

    // Adds what every runtime dungeon needs at engine startup to ddruntime.pk3. Returns script classes for zscript.zs.
    static string WriteDungeonCatalog(ZipArchive zip, string arena2, MapsFile maps, BlocksFile blocks, Arch3dFile arch, StringBuilder animdefs, StringBuilder modeldef)
    {
        var files = new Dictionary<int, TextureFile>();
        TextureFile Archive(int a)
        {
            if (!files.TryGetValue(a, out var f))
                files[a] = f = new TextureFile(Path.Combine(arena2, TextureFile.IndexToFileName(a)), FileUsage.UseMemory, true);
            return f;
        }
        var doorModels = new Dictionary<string, DoorModel>();
        var actionModels = new Dictionary<string, DoorModel>();
        var flats = new HashSet<(int archive, int record)>();
        var actionFlats = new HashSet<(int archive, int record)>();
        var modelTextures = new HashSet<(int archive, int record)>();
        var meshes = new Dictionary<uint, DFMesh?>();
        DFMesh? Mesh(uint id)
        {
            if (!meshes.TryGetValue(id, out var m))
            {
                int index = arch.GetRecordIndex(id);
                meshes[id] = m = index < 0 ? (DFMesh?)null : arch.GetMesh(index);
            }
            return m;
        }
        const double toRad = Math.PI / 180;
        int dungeons = 0;
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                dungeons++;
                int[] table = ClassicTextureTable(location);
                foreach (var dungeonBlock in location.Dungeon.Blocks)
                {
                    var block = blocks.GetBlock(dungeonBlock.BlockName);
                    if (block.RdbBlock.ObjectRootList == null) continue;
                    foreach (var rootGroup in block.RdbBlock.ObjectRootList)
                        foreach (var obj in rootGroup.RdbObjects ?? new DFBlock.RdbObject[0])
                        {
                            if (obj.Type == DFBlock.RdbResourceTypes.Flat)
                            {
                                var flat = obj.Resources.FlatResource;
                                flats.Add((flat.TextureArchive, flat.TextureRecord));
                                if (flat.Action != 0) actionFlats.Add((flat.TextureArchive, flat.TextureRecord));
                                continue;
                            }
                            if (obj.Type != DFBlock.RdbResourceTypes.Model) continue;
                            var reference = block.RdbBlock.ModelReferenceList[obj.Resources.ModelResource.ModelIndex];
                            uint id = reference.ModelIdNum;
                            var mesh = Mesh(id);
                            if (mesh == null) continue;
                            foreach (var sub in mesh.Value.SubMeshes) modelTextures.Add((SwapArchive(sub.TextureArchive, table, location), sub.TextureRecord));
                            var m = obj.Resources.ModelResource;
                            bool door = IsActionDoorModel(id, reference.Description);
                            if (door)
                            {
                                // As ExportMesh: the flip is a 180 degree roll baked into the model.
                                double rx = -m.XRotation / BlocksFile.RotationDivisor * toRad, ry = -m.YRotation / BlocksFile.RotationDivisor * toRad, rz = -m.ZRotation / BlocksFile.RotationDivisor * toRad;
                                var up = Rotate(new V3(0, 1, 0), rx, ry, rz);
                                if (Math.Abs(up.Y) < 0.999) continue; // ExportMesh refuses such a dungeon
                                var model = BuildDoorModel(id, 0, mesh.Value, Archive, table, location, up.Y < 0);
                                doorModels.TryAdd(model.CatalogName, model);
                            }
                            else if (m.ActionResource.Flags != 0 && IsMovingAction(obj, false, id))
                            {
                                var model = BuildDoorModel(id, 0, mesh.Value, Archive, table, location);
                                actionModels.TryAdd(model.CatalogName, model);
                            }
                        }
                }
            }
        }

        var classes = new StringBuilder("\n// [Doomerfall] Door and action visuals of every dungeon, named by model (RuntimeDungeon.cs).\n");
        void Text(string name, string body) { using var s = new StreamWriter(zip.CreateEntry(name, CompressionLevel.Fastest).Open(), new UTF8Encoding(false)); s.Write(body); }
        foreach (var m in doorModels.Values.OrderBy(m => m.CatalogName, StringComparer.Ordinal))
        {
            classes.Append($"class DFDoorVisual_{m.CatalogName} : DFDoorVisual {{}}\n");
            modeldef.Append($"Model DFDoorVisual_{m.CatalogName}\n{{\n\tPath \"models/dfdoors\"\n\tDONTCULLBACKFACES\n\tModel 0 \"{m.CatalogName}.obj\"\n\tFrameIndex DFDR A 0 0\n}}\n");
            Text($"models/dfdoors/{m.CatalogName}.obj", m.Obj);
        }
        foreach (var m in actionModels.Values.OrderBy(m => m.CatalogName, StringComparer.Ordinal))
        {
            classes.Append($"class DFActionVisual_{m.CatalogName} : DFActionVisual {{}}\n");
            modeldef.Append($"Model DFActionVisual_{m.CatalogName}\n{{\n\tPath \"models/dfactions\"\n\tDONTCULLBACKFACES\n\tUSEACTORPITCH\n\tUSEACTORROLL\n\tModel 0 \"{m.CatalogName}.obj\"\n\tFrameIndex DFAC A 0 0\n}}\n");
            Text($"models/dfactions/{m.CatalogName}.obj", m.Obj);
        }
        int flatImages = 0;
        foreach (var (fa, fr) in flats.OrderBy(f => f))
        {
            var file = Archive(fa);
            if (fr >= file.RecordCount) continue;
            var image = file.GetDFBitmap(fr, 0);
            if (image?.Data == null || image.Width == 0) continue;
            WriteFlatTexture(zip, animdefs, file, fa, fr);
            flatImages++;
            if (!actionFlats.Contains((fa, fr))) continue;
            var (sx, sy) = BillboardScale(file, fr);
            classes.Append(FormattableString.Invariant($"class DFActionFlat_a{fa:D3}r{fr:D2} : DFActionFlat {{ override void BeginPlay() {{ Super.BeginPlay(); picnum = TexMan.CheckForTexture(\"{FlatTextureName(fa, fr)}\", TexMan.Type_Any); scale = ({sx:F4}, {sy:F4}); }} States {{ Spawn: PLAY A -1 Bright; Stop; }} }}\n"));
        }
        // ddruntime.pk3 already holds frame 0 of every model texture. Dungeons also animate theirs (MeshExport.cs).
        int animated = 0;
        foreach (var (a, rec) in modelTextures.OrderBy(t => t))
        {
            var file = Archive(a);
            if (rec >= file.RecordCount || file.GetFrameCount(rec) <= 1) continue;
            WriteModelTextureFrames(zip, animdefs, file, a, rec);
            animated++;
        }
        Console.WriteLine($"dungeon catalog: {dungeons} dungeons, {doorModels.Count} door models, {actionModels.Count} action models, {flatImages} billboards ({actionFlats.Count} with actions), {animated} animated model textures");
        return classes.ToString();
    }
}
