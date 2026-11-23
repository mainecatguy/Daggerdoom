// Reads Daggerfall action records from a dungeon's RDB blocks.
// Links use the record's file position inside its block, as RDBLayout's actionLinkDict does.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    sealed class ActionRecord
    {
        public int Id, Block, FilePosition, NextPosition = -1, Next = -1;
        public string BlockName, Description = "FLT";
        public bool IsFlat, IsDoor;
        public uint Model, Trigger;
        public int Flag, Axis, Duration, Magnitude, Sound;
        public V3 Position;
        public readonly List<int> Previous = new List<int>();
        public int Door = -1, Visual = -1, Kind, FlatArchive, FlatRecord, LockValue;
        public double Yaw, X0, X1, Y0, Y1, Z0, Z1;
    }

    const int ActionCellSize = 16;
    static readonly int[] DoorLockValues = { 0x00, 0x02, 0x04, 0x06, 0x08, 0x0A, 0x0C, 0x0E, 0x10, 0x12, 0x14, 0x19, 0x1E, 0x32, 0x80, 0xFF }; // RDBLayout

    // Moving, untilted, non-door models leave the static mesh and collision. Their real position is decided at runtime.
    static bool IsMovingAction(DFBlock.RdbObject obj, bool isDoor)
    {
        var model = obj.Resources.ModelResource;
        return !isDoor && model.ActionResource.Flags is >= 1 and <= 8 && model.XRotation == 0 && model.ZRotation == 0;
    }

    // RDBLayout.AddAction, GetTranslationActionVector, and GetRotationActionVector. Rotation stays in Unity's axes.
    static (V3 move, V3 spin, int tics, bool forwardOnly) ActionMotion(ActionRecord r)
    {
        int flag = r.Flag, axis = r.Axis, duration = r.Duration;
        double magnitude = r.Magnitude;
        bool forwardOnly = false;
        V3 move = default, spin = default;
        if (flag == 8)
        {
            if (axis == 13 && r.Description == "TRP") { axis = 2; magnitude = 400; }
            if (axis == 12 && r.Description == "C0E") { axis = 3; duration = 0; }
            double turn = magnitude / BlocksFile.RotationDivisor;
            spin = axis switch
            {
                1 => new V3(-turn, 0, 0), 2 => new V3(turn, 0, 0), 3 => new V3(0, -turn, 0),
                4 => new V3(0, turn, 0), 5 => new V3(0, 0, -turn), 6 => new V3(0, 0, turn), _ => default,
            };
        }
        else if (flag is >= 1 and <= 7)
        {
            // Flags 2-7 are +X, -X, +Y, -Y, +Z, -Z. The axis enum is -X, +X, -Y, +Y, -Z, +Z.
            if (flag > 1) { duration = 50; magnitude = axis * 8; axis = flag % 2 == 0 ? flag : flag - 2; }
            if (r.Axis == 11 && r.Description == "C0X") { axis = 3; forwardOnly = true; }
            var unity = axis switch
            {
                1 => new V3(magnitude, 0, 0), 2 => new V3(-magnitude, 0, 0), 3 => new V3(0, -magnitude, 0),
                4 => new V3(0, magnitude, 0), 5 => new V3(0, 0, magnitude), 6 => new V3(0, 0, -magnitude), _ => default,
            };
            move = ToDoom(unity);
        }
        if (r.Description == "LID") spin = new V3(0, 0, -90);
        if (r.Description == "WHE") spin = new V3(0, -360, 0);
        return (move, spin, (int)Math.Round(duration / 20.0 * 35), forwardOnly);
    }

    // Surface cubes in model space at Doom scale. Each is the center of one DFActionCell.
    static List<V3> ActionCells(DFMesh mesh)
    {
        var seen = new HashSet<(int, int, int)>();
        double step = ActionCellSize / 2.0;
        void Mark(V3 p) => seen.Add(((int)Math.Floor(p.X / ActionCellSize), (int)Math.Floor(p.Y / ActionCellSize), (int)Math.Floor(p.Z / ActionCellSize)));
        foreach (var sub in mesh.SubMeshes)
            foreach (var plane in sub.Planes)
            {
                var pts = plane.Points.Select(q => ToDoom(new V3(q.X, -q.Y, q.Z))).ToArray();
                for (int i = 1; i + 1 < pts.Length; i++)
                {
                    V3 a = pts[0], b = pts[i], c = pts[i + 1];
                    double Length(V3 u, V3 v) => Math.Sqrt((u.X - v.X) * (u.X - v.X) + (u.Y - v.Y) * (u.Y - v.Y) + (u.Z - v.Z) * (u.Z - v.Z));
                    int n = Math.Max(1, (int)Math.Ceiling(Math.Max(Length(a, b), Math.Max(Length(b, c), Length(a, c))) / step));
                    for (int u = 0; u <= n; u++)
                        for (int v = 0; v <= n - u; v++)
                        {
                            double s = (double)u / n, t = (double)v / n, w = 1 - s - t;
                            Mark(new V3(a.X * w + b.X * s + c.X * t, a.Y * w + b.Y * s + c.Y * t, a.Z * w + b.Z * s + c.Z * t));
                        }
                }
            }
        return seen.Select(k => new V3((k.Item1 + 0.5) * ActionCellSize, (k.Item2 + 0.5) * ActionCellSize, (k.Item3 + 0.5) * ActionCellSize)).ToList();
    }

    static readonly List<(double x0, double x1, double y0, double y1, double bottom)> lidFootprints = new List<(double, double, double, double, double)>();

    static void NoteLidFootprint(Arch3dFile arch, uint id, DFBlock.RdbObject obj, V3 offset)
    {
        int record = arch.GetRecordIndex(id);
        if (record < 0) return;
        const double toRad = Math.PI / 180;
        double ry = -obj.Resources.ModelResource.YRotation / BlocksFile.RotationDivisor * toRad;
        var position = new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset;
        double x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, bottom = 1e9;
        foreach (var sub in arch.GetMesh(record).SubMeshes)
            foreach (var plane in sub.Planes)
                foreach (var q in plane.Points)
                {
                    var p = ToDoom(Rotate(new V3(q.X, -q.Y, q.Z), 0, ry, 0) + position);
                    x0 = Math.Min(x0, p.X); x1 = Math.Max(x1, p.X); y0 = Math.Min(y0, p.Y); y1 = Math.Max(y1, p.Y); bottom = Math.Min(bottom, p.Z);
                }
        lidFootprints.Add((x0, x1, y0, y1, bottom));
    }

    // A coffin's rim is narrower than a grid cell, so its top can be missed and the air above it lost.
    // The lid rests on the rim, so inside each lid's footprint the space above the lid's underside is open up to the room's ceiling.
    static int OpenLidRims()
    {
        int opened = 0;
        foreach (var (x0, x1, y0, y1, bottom) in lidFootprints)
        {
            int rim = (int)Math.Ceiling(bottom);
            int i0 = Math.Max(0, (int)Math.Floor((x0 - minX) / cell)), i1 = Math.Min(width - 1, (int)Math.Floor((x1 - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((y0 - minY) / cell)), j1 = Math.Min(height - 1, (int)Math.Floor((y1 - minY) / cell));
            int roof = int.MinValue;
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    foreach (var s in grid[Index(i, j)])
                        if (s.C > rim) roof = roof == int.MinValue ? s.C : Math.Min(Math.Max(roof, s.C), rim + 256);
            if (roof == int.MinValue) continue;
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    var spans = grid[Index(i, j)];
                    if (spans.Any(s => s.C > rim)) continue;
                    spans.Add(new Span { F = rim, C = roof });
                    opened++;
                }
        }
        return opened;
    }

    sealed class ActionPackage
    {
        public readonly List<ActionRecord> Records = new List<ActionRecord>();
        public readonly Dictionary<uint, DoorModel> Models = new Dictionary<uint, DoorModel>();
        public readonly Dictionary<uint, List<V3>> Cells = new Dictionary<uint, List<V3>>();
        public readonly List<(int archive, int record)> Flats = new List<(int, int)>();
    }

    // Fills the placement, bounds, and collision of one model record during --export-mesh.
    static void PrepareActionModel(ActionPackage package, ActionRecord r, DFBlock.RdbObject obj, DFMesh mesh, double yaw, Func<int, TextureFile> archive, int[] table, DFLocation location)
    {
        r.Yaw = yaw;
        bool moving = IsMovingAction(obj, r.IsDoor);
        r.Kind = moving ? 1 : 0;
        if (moving)
        {
            if (!package.Models.TryGetValue(r.Model, out var model))
            {
                package.Models[r.Model] = model = BuildDoorModel(r.Model, package.Models.Count, mesh, archive, table, location);
                package.Cells[r.Model] = ActionCells(mesh);
            }
            r.Visual = model.Slot;
            (r.X0, r.X1, r.Y0, r.Y1, r.Z0, r.Z1) = (model.X0, model.X1, model.Y0, model.Y1, model.Z0, model.Z1);
            return;
        }
        // A static record's box is axis-aligned around its full placement, because tilted levers stay in the static mesh.
        const double toRad = Math.PI / 180;
        double rx = -obj.Resources.ModelResource.XRotation / BlocksFile.RotationDivisor * toRad;
        double ry = -obj.Resources.ModelResource.YRotation / BlocksFile.RotationDivisor * toRad;
        double rz = -obj.Resources.ModelResource.ZRotation / BlocksFile.RotationDivisor * toRad;
        r.Yaw = 0;
        r.X0 = r.Y0 = r.Z0 = 1e9; r.X1 = r.Y1 = r.Z1 = -1e9;
        foreach (var sub in mesh.SubMeshes)
            foreach (var plane in sub.Planes)
                foreach (var q in plane.Points)
                {
                    var l = ToDoom(Rotate(new V3(q.X, -q.Y, q.Z), rx, ry, rz));
                    r.X0 = Math.Min(r.X0, l.X); r.X1 = Math.Max(r.X1, l.X);
                    r.Y0 = Math.Min(r.Y0, l.Y); r.Y1 = Math.Max(r.Y1, l.Y);
                    r.Z0 = Math.Min(r.Z0, l.Z); r.Z1 = Math.Max(r.Z1, l.Z);
                }
    }

    // Flats have no mesh. A flat that moves or starts a chain is drawn so the player can find it.
    static void PrepareActionFlats(ActionPackage package, Func<int, TextureFile> archive)
    {
        double scale = PlayerScale.DoomUnitsPerDaggerfallUnit;
        foreach (var r in package.Records.Where(x => x.IsFlat))
        {
            r.Kind = 2;
            var file = archive(r.FlatArchive);
            double w = Math.Max(8, file.GetWidth(r.FlatRecord) * scale) / 2, h = Math.Max(8, file.GetHeight(r.FlatRecord) * scale) / 2;
            (r.X0, r.X1, r.Y0, r.Y1, r.Z0, r.Z1) = (-w, w, -w, w, -h, h);
            if (r.Flag is < 1 or > 8 && r.Next < 0) continue;
            int slot = package.Flats.IndexOf((r.FlatArchive, r.FlatRecord));
            if (slot < 0) { slot = package.Flats.Count; package.Flats.Add((r.FlatArchive, r.FlatRecord)); }
            r.Visual = slot;
        }
    }

    // DFACTIONS: "S <cell size>", then one "A" line per record and one "C <record> x y z" line per collision cube.
    static string ActionLump(ActionPackage package)
    {
        var text = new System.Text.StringBuilder($"S {ActionCellSize}\n");
        foreach (var r in package.Records)
        {
            var (move, spin, tics, forwardOnly) = r.Kind == 1 || (r.IsFlat && r.Flag is >= 1 and <= 8) ? ActionMotion(r) : (default, default, 0, false);
            int trigger = Enum.IsDefined(typeof(DFBlock.RdbTriggerFlags), (DFBlock.RdbTriggerFlags)r.Trigger) ? (int)r.Trigger : 0;
            double cx = (r.X0 + r.X1) / 2, cy = (r.Y0 + r.Y1) / 2;
            text.Append(FormattableString.Invariant(
                $"A {r.Id} {r.Kind} {r.Flag} {trigger} {r.Next} {r.Door} {r.Visual} {r.Position.X:F3} {r.Position.Y:F3} {r.Position.Z:F3} {r.Yaw:F3} {move.X:F3} {move.Y:F3} {move.Z:F3} {spin.X:F3} {spin.Y:F3} {spin.Z:F3} {tics} {(forwardOnly ? 1 : 0)} {cx:F3} {cy:F3} 0 {r.X0:F3} {r.X1:F3} {r.Y0:F3} {r.Y1:F3} {r.Z0:F3} {r.Z1:F3} {r.Sound} {r.Axis} {r.Magnitude} {r.LockValue} 0\n"));
            if (r.Kind == 1)
                foreach (var c in package.Cells[r.Model])
                    text.Append(FormattableString.Invariant($"C {r.Id} {c.X:F2} {c.Y:F2} {c.Z:F2}\n"));
        }
        return text.ToString();
    }

    static List<ActionRecord> ReadActionRecords(string arena2, DFLocation location)
    {
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var records = new List<ActionRecord>();
        int blockIndex = -1;
        foreach (var dungeonBlock in location.Dungeon.Blocks)
        {
            blockIndex++;
            var block = blocks.GetBlock(dungeonBlock.BlockName);
            if (block.RdbBlock.ObjectRootList == null) continue;
            var offset = new V3(dungeonBlock.X * BlockSide, 0, dungeonBlock.Z * BlockSide);
            var inBlock = new Dictionary<int, ActionRecord>();
            var targets = new HashSet<int>();
            foreach (var group in block.RdbBlock.ObjectRootList)
            {
                if (group.RdbObjects == null) continue;
                foreach (var obj in group.RdbObjects)
                {
                    ActionRecord r = null;
                    if (obj.Type == DFBlock.RdbResourceTypes.Model && obj.Resources.ModelResource.ActionResource.Flags != 0)
                    {
                        var model = obj.Resources.ModelResource;
                        var reference = block.RdbBlock.ModelReferenceList[model.ModelIndex];
                        r = new ActionRecord
                        {
                            Description = reference.Description, Model = reference.ModelIdNum,
                            IsDoor = IsActionDoorModel(reference.ModelIdNum, reference.Description),
                            Trigger = model.TriggerFlag_StartingLock, Flag = model.ActionResource.Flags, Axis = model.ActionResource.Axis,
                            Duration = model.ActionResource.Duration, Magnitude = model.ActionResource.Magnitude,
                            Sound = model.SoundIndex, NextPosition = model.ActionResource.NextObjectOffset,
                            LockValue = DoorLockValues[(model.TriggerFlag_StartingLock >> 4) & 15],
                        };
                        if (model.ActionResource.Flags is >= 1 and <= 8 && (model.XRotation != 0 || model.ZRotation != 0))
                            Console.WriteLine($"TILTED {dungeonBlock.BlockName} m{reference.ModelIdNum} {reference.Description} rot {model.XRotation},{model.YRotation},{model.ZRotation} at {obj.XPos},{obj.ZPos},{-obj.YPos}");
                    }
                    else if (obj.Type == DFBlock.RdbResourceTypes.Flat && obj.Resources.FlatResource.Action != 0)
                    {
                        var flat = obj.Resources.FlatResource;
                        r = new ActionRecord
                        {
                            IsFlat = true, Trigger = flat.Flags, Flag = flat.Action, Axis = flat.Magnitude, Magnitude = flat.Magnitude,
                            Sound = flat.SoundIndex, NextPosition = flat.NextObjectOffset,
                            FlatArchive = flat.TextureArchive, FlatRecord = flat.TextureRecord,
                        };
                    }
                    if (r == null) continue;
                    r.Id = records.Count; r.Block = blockIndex; r.BlockName = dungeonBlock.BlockName; r.FilePosition = obj.Position;
                    r.Position = ToDoom(new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset);
                    records.Add(r);
                    inBlock[obj.Position] = r;
                    if (r.NextPosition > 0) targets.Add(r.NextPosition);
                }
            }
            foreach (var r in inBlock.Values)
                if (r.NextPosition > 0 && inBlock.TryGetValue(r.NextPosition, out var next)) { r.Next = next.Id; next.Previous.Add(r.Id); }
        }
        return records;
    }

    static int DumpActions(string arena2, DFLocation location, string outDir)
    {
        var records = ReadActionRecords(arena2, location);
        File.WriteAllLines(Path.Combine(outDir, "actions.txt"), records.Select(r => FormattableString.Invariant(
            $"ACT {r.Id} {r.BlockName} {(r.IsFlat ? "flat" : r.IsDoor ? "door" : "model")} m{r.Model} {r.Description} flag={r.Flag} trig={r.Trigger} axis={r.Axis} dur={r.Duration} mag={r.Magnitude} snd={r.Sound} next={r.Next} rawnext={r.NextPosition} prev={string.Join(",", r.Previous)} at {r.Position.X:F0},{r.Position.Y:F0},{r.Position.Z:F0}")));
        Console.WriteLine($"TOTAL {records.Count} records, {records.Count(r => r.IsDoor)} on doors, {records.Count(r => r.IsFlat)} on flats");
        foreach (var g in records.GroupBy(r => r.Flag).OrderBy(g => g.Key))
            Console.WriteLine($"FLAG {g.Key}: {g.Count()} (models {g.Count(r => !r.IsFlat && !r.IsDoor)}, doors {g.Count(r => r.IsDoor)}, flats {g.Count(r => r.IsFlat)}) triggers {string.Join(",", g.Select(r => r.Trigger).Distinct().OrderBy(t => t))}");
        Console.WriteLine($"UNRESOLVED links: {records.Count(r => r.NextPosition > 0 && r.Next < 0)}");
        return 0;
    }
}
