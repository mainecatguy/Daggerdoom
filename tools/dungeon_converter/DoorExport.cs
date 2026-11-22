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
        public int Slot;
        public double X0 = 1e9, X1 = -1e9, Y0 = 1e9, Y1 = -1e9, Z0 = 1e9, Z1 = -1e9;
        public string Obj;
        public readonly HashSet<(int archive, int record)> Textures = new HashSet<(int, int)>();
    }

    static DoorModel BuildDoorModel(uint id, int slot, DFMesh mesh, Func<int, TextureFile> archive, int[] table, DFLocation location)
    {
        var model = new DoorModel { Id = id, Slot = slot };
        foreach (var sub in mesh.SubMeshes)
            foreach (var plane in sub.Planes)
                foreach (var p in plane.Points)
                {
                    var l = ToDoom(new V3(p.X, -p.Y, p.Z));
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
                    var l = ToDoom(new V3(p.X, -p.Y, p.Z));
                    double nx = p.NX, ny = p.NZ, nz = -p.NY, length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
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

    static string SourceDirectory([CallerFilePath] string file = "") => Path.GetDirectoryName(file);

    static void WriteDoorPackage(string path, List<DoorModel> models, List<string> placements, Func<int, TextureFile> archive)
    {
        if (File.Exists(path)) File.Delete(path);
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        void Text(string name, string body)
        {
            using var s = new StreamWriter(zip.CreateEntry(name, CompressionLevel.Fastest).Open(), new UTF8Encoding(false));
            s.Write(body);
        }
        // One actor class per model: a class with several model slots draws all of them at once.
        var classes = new StringBuilder(File.ReadAllText(Path.Combine(SourceDirectory(), "door_objects.zs")));
        var modeldef = new StringBuilder();
        foreach (var m in models)
        {
            classes.Append($"\nclass DFDoorVisual{m.Slot} : DFDoorVisual {{}}\n");
            modeldef.Append($"Model DFDoorVisual{m.Slot}\n{{\n\tPath \"models/dfdoors\"\n\tDONTCULLBACKFACES\n\tModel 0 \"m{m.Id}.obj\"\n\tFrameIndex DFDR A 0 0\n}}\n");
        }
        Text("zscript.zs", classes.ToString());
        Text("MAPINFO", "GameInfo\n{\n\tAddEventHandlers = \"DFDoorHandler\"\n}\n");
        Text("DFDOORS", string.Join("\n", placements) + "\n");
        Text("MODELDEF", modeldef.ToString());
        foreach (var m in models) Text($"models/dfdoors/m{m.Id}.obj", m.Obj);
        foreach (var (a, r) in models.SelectMany(m => m.Textures).Distinct())
        {
            var file = archive(a);
            var image = r < file.RecordCount ? file.GetDFBitmap(r, 0) : null;
            if (image?.Data == null || image.Width == 0) { Console.WriteLine($"missing door texture {a}:{r}"); continue; }
            using var s = zip.CreateEntry($"dfmesh/a{a:D3}r{r:D2}.png", CompressionLevel.Fastest).Open();
            WriteTexturePng(s, image, file.Palette);
        }
    }
}
