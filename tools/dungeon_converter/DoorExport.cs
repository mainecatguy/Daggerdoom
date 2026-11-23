// Exports hinged Daggerfall doors as separate objects: <slug>_doors.pk3 holds one OBJ per door model, their textures,
// a DFDOORS placement lump, and the runtime in door_objects.zs. It is derived from game data, so keep it outside the repo.
//
// DFDOORS, one door per line: slot pivotX pivotY pivotZ closedAngle x0 x1 y0 y1 z0 z1
// The pivot is the model origin, which DaggerfallActionDoor rotates about. Bounds are model space at Doom scale.
// OBJ vertices are centered on the door panel, so the drawn actor always stands inside the doorway or room.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    // RDBLayout.IsActionDoor.
    static bool IsActionDoorModel(uint id, string description) =>
        id != RedBrickDoorModel && description is "DOR" or "DDR" or "NEW" or "CAV";

    sealed class DoorModel
    {
        public uint Id;
        public bool Flipped; // model drawn upside down (roll of 180 degrees): the flip is baked into the vertices
        public string Name => $"m{Id}{(Flipped ? "f" : "")}";
        public int Slot;
        public double X0 = 1e9, X1 = -1e9, Y0 = 1e9, Y1 = -1e9, Z0 = 1e9, Z1 = -1e9;
        public string Obj;
        public readonly HashSet<(int archive, int record)> Textures = new HashSet<(int, int)>();
    }

    static DoorModel BuildDoorModel(uint id, int slot, DFMesh mesh, Func<int, TextureFile> archive, int[] table, DFLocation location, bool flipped = false)
    {
        var model = new DoorModel { Id = id, Slot = slot, Flipped = flipped };
        // A roll of 180 degrees maps (x, y, z) to (x, -y, -z) in model space, normals too.
        double flip = flipped ? -1 : 1;
        foreach (var sub in mesh.SubMeshes)
            foreach (var plane in sub.Planes)
                foreach (var p in plane.Points)
                {
                    var l = ToDoom(new V3(p.X, -p.Y * flip, p.Z * flip));
                    model.X0 = Math.Min(model.X0, l.X); model.X1 = Math.Max(model.X1, l.X);
                    model.Y0 = Math.Min(model.Y0, l.Y); model.Y1 = Math.Max(model.Y1, l.Y);
                    model.Z0 = Math.Min(model.Z0, l.Z); model.Z1 = Math.Max(model.Z1, l.Z);
                }
        double cx = (model.X0 + model.X1) / 2, cy = (model.Y0 + model.Y1) / 2;
        var text = new StringBuilder("# Daggerfall door model\n"); // the engine's OBJ parser only recognizes usemtl after a newline
        int next = 1;
        string F(double v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
        foreach (var sub in mesh.SubMeshes)
        {
            var source = archive(sub.TextureArchive);
            double w = source.GetWidth(sub.TextureRecord), h = source.GetHeight(sub.TextureRecord);
            var key = (SwapArchive(sub.TextureArchive, table, location), sub.TextureRecord);
            model.Textures.Add(key);
            text.Append($"usemtl dfmesh/a{key.Item1:D3}r{key.Item2:D2}.png\n");
            foreach (var plane in sub.Planes)
            {
                int first = next;
                foreach (var p in plane.Points)
                {
                    var l = ToDoom(new V3(p.X, -p.Y * flip, p.Z * flip));
                    double nx = p.NX, ny = p.NZ * flip, nz = -p.NY * flip, length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                    if (length < 1e-6) length = 1;
                    // The engine's OBJ loader negates z and flips v.
                    text.Append($"v {F(l.X - cx)} {F(l.Z)} {F(-(l.Y - cy))}\nvt {F(p.U / w)} {F(1 - p.V / h)}\nvn {F(nx / length)} {F(nz / length)} {F(-ny / length)}\n");
                    next++;
                }
                for (int i = 1; i + 1 < plane.Points.Length; i++)
                {
                    int a = first, b = first + i + 1, c = first + i;
                    text.Append($"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n");
                }
            }
        }
        model.Obj = text.ToString();
        return model;
    }

    // Lists every dungeon block that holds a door model with a roll or pitch. Usage: --list-tilted-doors
    static int ListTiltedDoors(string arena2)
    {
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        int doors = 0, tilted = 0;
        var tiltedBlocks = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (int i = 0; i < blocks.Count; i++)
        {
            string name = blocks.GetBlockName(i);
            if (!name.EndsWith(".RDB", StringComparison.OrdinalIgnoreCase)) continue;
            var block = blocks.GetBlock(i);
            if (block.RdbBlock.ObjectRootList == null) continue;
            foreach (var group in block.RdbBlock.ObjectRootList)
                foreach (var obj in group.RdbObjects ?? new DFBlock.RdbObject[0])
                {
                    if (obj.Type != DFBlock.RdbResourceTypes.Model) continue;
                    var reference = block.RdbBlock.ModelReferenceList[obj.Resources.ModelResource.ModelIndex];
                    if (!IsActionDoorModel(reference.ModelIdNum, reference.Description)) continue;
                    doors++;
                    var m = obj.Resources.ModelResource;
                    if (m.XRotation != 0 || m.ZRotation != 0)
                    {
                        tilted++;
                        tiltedBlocks.Add(name);
                        Console.WriteLine($"{name} door {reference.ModelIdNum} rot {m.XRotation / BlocksFile.RotationDivisor:F1},{m.YRotation / BlocksFile.RotationDivisor:F1},{m.ZRotation / BlocksFile.RotationDivisor:F1}");
                    }
                }
            blocks.DiscardBlock(i);
        }
        Console.WriteLine($"{doors} door objects in RDB blocks, {tilted} tilted");
        // Which dungeons use those blocks, so the doors can be checked in a real map.
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                var used = location.Dungeon.Blocks.Select(b => b.BlockName).Where(tiltedBlocks.Contains).Distinct().ToList();
                if (used.Count > 0) Console.WriteLine($"TILTEDIN #{location.MapTableData.MapId} {region.Name}/{region.MapNames[l]} blocks={location.Dungeon.Blocks.Length} {string.Join(",", used)}");
            }
        }
        return 0;
    }

    static string SourceDirectory([CallerFilePath] string file = "") => Path.GetDirectoryName(file);

    static void WriteDoorPackage(string path, List<DoorModel> models, List<string> placements, Func<int, TextureFile> archive, ActionPackage actions)
    {
        if (File.Exists(path)) File.Delete(path);
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        void Text(string name, string body)
        {
            using var s = new StreamWriter(zip.CreateEntry(name, CompressionLevel.Fastest).Open(), new UTF8Encoding(false));
            s.Write(body);
        }
        // One actor class per model: a class with several model slots draws all of them at once.
        var classes = new StringBuilder(runtimeDungeon ? "version \"4.10\"\n" : File.ReadAllText(Path.Combine(SourceDirectory(), "door_objects.zs")));
        if (runtimeDungeon) Text("DDDUNGN", dungeonInfo.ToString());
        var modeldef = new StringBuilder();
        foreach (var m in models)
        {
            classes.Append($"\nclass DFDoorVisual{m.Slot} : DFDoorVisual {{}}\n");
            modeldef.Append($"Model DFDoorVisual{m.Slot}\n{{\n\tPath \"models/dfdoors\"\n\tDONTCULLBACKFACES\n\tModel 0 \"{m.Name}.obj\"\n\tFrameIndex DFDR A 0 0\n}}\n");
        }
        classes.Append(File.ReadAllText(Path.Combine(SourceDirectory(), "action_objects.zs")));
        var actionModels = actions.Models.Values.OrderBy(m => m.Slot).ToList();
        foreach (var m in actionModels)
        {
            classes.Append($"\nclass DFActionVisual{m.Slot} : DFActionVisual {{}}\n");
            modeldef.Append($"Model DFActionVisual{m.Slot}\n{{\n\tPath \"models/dfactions\"\n\tDONTCULLBACKFACES\n\tUSEACTORPITCH\n\tUSEACTORROLL\n\tModel 0 \"m{m.Id}.obj\"\n\tFrameIndex DFAC A 0 0\n}}\n");
            Text($"models/dfactions/m{m.Id}.obj", m.Obj);
        }
        // Action flats name their texture directly, so ANIMDEFS animates them the same way as ordinary billboards.
        var animdefs = new StringBuilder();
        for (int i = 0; i < actions.Flats.Count; i++)
        {
            var (fa, fr) = actions.Flats[i];
            var (sx, sy) = BillboardScale(archive(fa), fr);
            classes.Append(FormattableString.Invariant($"\nclass DFActionFlat{i} : DFActionFlat {{ override void BeginPlay() {{ Super.BeginPlay(); picnum = TexMan.CheckForTexture(\"{FlatTextureName(fa, fr)}\", TexMan.Type_Any); scale = ({sx:F4}, {sy:F4}); }} States {{ Spawn: PLAY A -1 Bright; Stop; }} }}\n"));
        }
        foreach (var (fa, fr) in actions.Flats.Concat(actions.Ordinary.Select(f => (f.archive, f.record))).Distinct())
            WriteFlatTexture(zip, animdefs, archive(fa), fa, fr);
        if (actions.Ordinary.Count > 0) Text("DFDFLATS", DungeonFlatLump(actions, archive));
        Text("DFACTIONS", ActionLump(actions));
        Text("zscript.zs", classes.ToString());
        Text("MAPINFO", "GameInfo\n{\n\tAddEventHandlers = \"DFDoorHandler\", \"DFActionHandler\"\n}\n");
        Text("DFDOORS", string.Join("\n", placements) + "\n");
        Text("MODELDEF", modeldef.ToString());
        foreach (var m in models) Text($"models/dfdoors/{m.Name}.obj", m.Obj);
        foreach (var (a, r) in models.Concat(actionModels).SelectMany(m => m.Textures).Distinct())
        {
            var file = archive(a);
            var image = r < file.RecordCount ? file.GetDFBitmap(r, 0) : null;
            if (image?.Data == null || image.Width == 0) { Console.WriteLine($"missing door texture {a}:{r}"); continue; }
            using (var s = zip.CreateEntry($"dfmesh/a{a:D3}r{r:D2}.png", CompressionLevel.Fastest).Open())
                WriteTexturePng(s, image, file.Palette);
            WriteModelTextureFrames(zip, animdefs, file, a, r);
        }
        if (animdefs.Length > 0) Text("ANIMDEFS", animdefs.ToString());
    }
}
