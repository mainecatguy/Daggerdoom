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
        public bool IsFlat, IsDoor, TrapdoorTile;
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
    static bool IsMovingAction(DFBlock.RdbObject obj, bool isDoor, uint modelId)
    {
        var model = obj.Resources.ModelResource;
        return !isDoor && (model.ActionResource.Flags is >= 1 and <= 8 || IsSpecialDoorFlag(model.ActionResource.Flags)) && model.XRotation == 0 && model.ZRotation == 0;
    }

    // Actions 18 and 20 on a model that is not a real door: RDBLayout gives it DaggerfallActionDoorSpecial, which swings it
    // 90 degrees about its own Y in 1.5 s. Its mesh collider stays solid and turns with it.
    static bool IsSpecialDoorFlag(int flag) => flag is 18 or 20;

    // RDBLayout.AddAction, GetTranslationActionVector, and GetRotationActionVector. Rotation stays in Unity's axes.
    static (V3 move, V3 spin, int tics, bool forwardOnly) ActionMotion(ActionRecord r)
    {
        if (IsSpecialDoorFlag(r.Flag)) return (default, new V3(0, -90, 0), 53, false); // DaggerfallActionDoorSpecial: OpenAngle -90, OpenDuration 1.5 s
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

    // One row along the panel's long side, stacked to its height. Each cell is as wide as the panel is thick.
    static List<V3> ThinPanelCells(DoorModel m)
    {
        bool alongX = m.X1 - m.X0 >= m.Y1 - m.Y0;
        double half = Math.Max(Math.Min(m.X1 - m.X0, m.Y1 - m.Y0) / 2, 1), start = alongX ? m.X0 : m.Y0, end = alongX ? m.X1 : m.Y1;
        double middle = alongX ? (m.Y0 + m.Y1) / 2 : (m.X0 + m.X1) / 2;
        int across = Math.Max(1, (int)Math.Ceiling((end - start) / (half * 2)));
        int up = Math.Max(1, (int)Math.Ceiling((m.Z1 - m.Z0) / ActionCellSize));
        var cells = new List<V3>();
        for (int i = 0; i < across; i++)
        {
            double along = across == 1 ? (start + end) / 2 : start + half + (end - start - 2 * half) * i / (across - 1);
            for (int k = 0; k < up; k++)
            {
                double z = up == 1 ? (m.Z0 + m.Z1) / 2 : m.Z0 + ActionCellSize / 2.0 + (m.Z1 - m.Z0 - ActionCellSize) * k / (up - 1);
                cells.Add(alongX ? new V3(along, middle, z) : new V3(middle, along, z));
            }
        }
        return cells;
    }

    // A trapdoor lies flat, so its thin side is its height.
    static bool IsFloorTile(DoorModel m) => m.Z1 - m.Z0 < Math.Min(m.X1 - m.X0, m.Y1 - m.Y0) / 4;
    // Every flat TRP model that turns on a hinge: action 8, or the special door actions 18 and 20.
    static bool IsTrapdoorTile(ActionRecord r, DoorModel m) => r.Description == "TRP" && r.Flag is 8 or 18 or 20 && IsFloorTile(m);

    // One layer of cells that covers the tile exactly and has its real thickness.
    static List<V3> FloorTileCells(DoorModel m)
    {
        int nx = Math.Max(1, (int)Math.Ceiling((m.X1 - m.X0) / ActionCellSize)), ny = Math.Max(1, (int)Math.Ceiling((m.Y1 - m.Y0) / ActionCellSize));
        var cells = new List<V3>();
        for (int i = 0; i < nx; i++)
            for (int j = 0; j < ny; j++)
                cells.Add(new V3(m.X0 + (m.X1 - m.X0) * (i + 0.5) / nx, m.Y0 + (m.Y1 - m.Y0) * (j + 0.5) / ny, (m.Z0 + m.Z1) / 2));
        return cells;
    }

    static readonly List<(double x0, double x1, double y0, double y1, double bottom)> lidFootprints = new List<(double, double, double, double, double)>();

    // A moving model's world box at rest. Moving models are untilted, so only the yaw turns it.
    static (double x0, double x1, double y0, double y1, double bottom, double top)? RestingBox(Arch3dFile arch, uint id, DFBlock.RdbObject obj, V3 offset)
    {
        int record = arch.GetRecordIndex(id);
        if (record < 0) return null;
        const double toRad = Math.PI / 180;
        double ry = -obj.Resources.ModelResource.YRotation / BlocksFile.RotationDivisor * toRad;
        var position = new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset;
        double x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, bottom = 1e9, top = -1e9;
        foreach (var sub in arch.GetMesh(record).SubMeshes)
            foreach (var plane in sub.Planes)
                foreach (var q in plane.Points)
                {
                    var p = ToDoom(Rotate(new V3(q.X, -q.Y, q.Z), 0, ry, 0) + position);
                    x0 = Math.Min(x0, p.X); x1 = Math.Max(x1, p.X); y0 = Math.Min(y0, p.Y); y1 = Math.Max(y1, p.Y);
                    bottom = Math.Min(bottom, p.Z); top = Math.Max(top, p.Z);
                }
        return (x0, x1, y0, y1, bottom, top);
    }

    static void NoteLidFootprint(Arch3dFile arch, uint id, DFBlock.RdbObject obj, V3 offset)
    {
        if (RestingBox(arch, id, obj, offset) is var (x0, x1, y0, y1, bottom, _)) lidFootprints.Add((x0, x1, y0, y1, bottom));
    }

    // Trapdoor tiles by their closed world box. Some cover a hole with no Daggerfall geometry under it at all.
    static readonly List<(double x0, double x1, double y0, double y1, double top, int block, int next)> trapdoorFootprints = new List<(double, double, double, double, double, int, int)>();
    // How far below the tile an artificial floor goes when Daggerfall has none and no hidden mover marks the shaft's depth.
    // Doom needs a floor; Daggerfall's fall never ends.
    const double BottomlessPitDepth = 1024;
    // Every action object by (block, file position): its chain link, and for a moving model its box at rest.
    static readonly Dictionary<(int block, int position), (int next, int flag, (double x0, double x1, double y0, double y1, double bottom, double top)? box)> actionLinks =
        new Dictionary<(int, int), (int, int, (double, double, double, double, double, double)?)>();

    static void NoteActionLink(int block, DFBlock.RdbObject obj, int next, int flag, (double, double, double, double, double, double)? box) =>
        actionLinks[(block, obj.Position)] = (next, flag, box);

    static void NoteTrapdoorFootprint(Arch3dFile arch, uint id, DFBlock.RdbObject obj, V3 offset, string description, int block)
    {
        var action = obj.Resources.ModelResource.ActionResource;
        var box = RestingBox(arch, id, obj, offset);
        NoteActionLink(block, obj, action.NextObjectOffset, action.Flags, box);
        if (description != "TRP" || action.Flags is not (8 or 18 or 20)) return;
        if (box is not var (x0, x1, y0, y1, bottom, top)) return;
        if (top - bottom >= Math.Min(x1 - x0, y1 - y0) / 4) return; // the IsFloorTile rule
        trapdoorFootprints.Add((x0, x1, y0, y1, top, block, action.NextObjectOffset));
    }

    // The lever trapdoors hide a pillar and a frame in their shaft, later on the tile's own chain. Both are action 1 to 7
    // movers that sit under the closed tile and rise once it flips. The shaft floor goes at the lowest of their bases,
    // so the pillar rises from the floor instead of from mid-air over a deep pit. Null when the chain hides nothing.
    static double? HiddenMoverBase(double x0, double x1, double y0, double y1, double top, int block, int next)
    {
        double? floor = null;
        var seen = new HashSet<int>();
        while (next > 0 && seen.Add(next) && actionLinks.TryGetValue((block, next), out var link))
        {
            if (link.flag is >= 1 and <= 7 && link.box is var (bx0, bx1, by0, by1, bottom, btop)
                && bx0 < x1 && bx1 > x0 && by0 < y1 && by1 > y0 && btop <= top + 1)
                floor = Math.Min(floor ?? double.MaxValue, bottom);
            next = link.next;
        }
        return floor;
    }

    // A cell under a trapdoor with no surface at all below the tile's top gets an artificial floor, so the room's air
    // above the closed tile survives. It goes at the base of the hidden pillar on the tile's chain, or else BottomlessPitDepth down.
    static (int cells, int pillarShafts, int deepShafts) FloorBottomlessPits(List<(double z, bool up)>[] hits)
    {
        int floored = 0, pillarShafts = 0, deepShafts = 0;
        foreach (var (x0, x1, y0, y1, top, block, next) in trapdoorFootprints)
        {
            double? pillarBase = HiddenMoverBase(x0, x1, y0, y1, top, block, next);
            double floor = pillarBase ?? top - BottomlessPitDepth;
            int before = floored;
            for (int j = Math.Max(0, (int)Math.Floor((y0 - minY) / cell)); j <= Math.Min(height - 1, (int)Math.Floor((y1 - minY) / cell)); j++)
                for (int i = Math.Max(0, (int)Math.Floor((x0 - minX) / cell)); i <= Math.Min(width - 1, (int)Math.Floor((x1 - minX) / cell)); i++)
                {
                    double px = minX + (i + 0.5) * cell, py = minY + (j + 0.5) * cell;
                    if (px < x0 || px > x1 || py < y0 || py > y1) continue;
                    var list = hits[Index(i, j)] ??= new List<(double, bool)>();
                    if (list.Any(h => h.z <= top + 1)) continue;
                    list.Add((floor, true));
                    floored++;
                }
            if (floored == before) continue;
            if (pillarBase != null) pillarShafts++; else deepShafts++;
            Console.WriteLine(FormattableString.Invariant($"trapdoor shaft at {(x0 + x1) / 2:F0},{(y0 + y1) / 2:F0}: tile top {top:F1}, floor {floor:F1} ({(pillarBase != null ? "pillar base" : "deep")}), was {top - BottomlessPitDepth:F1}, {floored - before} cells"));
        }
        return (floored, pillarShafts, deepShafts);
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
        public readonly Dictionary<uint, List<V3>> SpecialCells = new Dictionary<uint, List<V3>>(); // models with action 18 or 20
        public readonly Dictionary<uint, double> CellHalf = new Dictionary<uint, double>(); // thin special panels only; others use ActionCellSize / 2
        public readonly Dictionary<uint, double> CellHeight = new Dictionary<uint, double>(); // flat trapdoor tiles only; others use ActionCellSize
        public readonly List<(int archive, int record)> Flats = new List<(int, int)>();
        public readonly List<(int archive, int record, V3 at, ulong npc)> Ordinary = new List<(int, int, V3, ulong)>();
        public readonly List<(V3 at, double range)> Lights = new List<(V3, double)>(); // RDB light records; range in Doom units
    }

    // Fills the placement, bounds, and collision of one model record during --export-mesh.
    static void PrepareActionModel(ActionPackage package, ActionRecord r, DFBlock.RdbObject obj, DFMesh mesh, double yaw, Func<int, TextureFile> archive, int[] table, DFLocation location)
    {
        r.Yaw = yaw;
        bool moving = IsMovingAction(obj, r.IsDoor, r.Model);
        r.Kind = moving ? 1 : 0;
        if (moving)
        {
            if (!package.Models.TryGetValue(r.Model, out var model))
            {
                package.Models[r.Model] = model = BuildDoorModel(r.Model, package.Models.Count, mesh, archive, table, location);
                package.Cells[r.Model] = ActionCells(mesh);
            }
            // The same model can also be an ordinary mover elsewhere in the dungeon, so special doors keep their own cells.
            // A trapdoor tile uses its real shape on either action. The 16-unit grid puts its walking surface 16 units too high.
            r.TrapdoorTile = IsTrapdoorTile(r, model);
            if ((IsSpecialDoorFlag(r.Flag) || r.TrapdoorTile) && !package.SpecialCells.ContainsKey(r.Model))
            {
                if (IsFloorTile(model))
                {
                    package.SpecialCells[r.Model] = FloorTileCells(model);
                    package.CellHalf[r.Model] = ActionCellSize / 2.0;
                    package.CellHeight[r.Model] = Math.Max(model.Z1 - model.Z0, 1);
                }
                else
                {
                    // A 4-unit panel on the 16-unit grid would fill a doorway when open. Use one thin row of real thickness.
                    package.SpecialCells[r.Model] = ThinPanelCells(model);
                    package.CellHalf[r.Model] = Math.Max(Math.Min(model.X1 - model.X0, model.Y1 - model.Y0) / 2, 1);
                }
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

    // Flats have no mesh. Daggerfall Unity draws every action flat except editor markers, which keep working while hidden.
    // Treasure and NPC flats are drawn only when they move or start a chain, so the player can still find a working switch.
    static void PrepareActionFlats(ActionPackage package, Func<int, TextureFile> archive)
    {
        double scale = PlayerScale.DoomUnitsPerDaggerfallUnit;
        foreach (var r in package.Records.Where(x => x.IsFlat))
        {
            r.Kind = 2;
            var file = archive(r.FlatArchive);
            double w = Math.Max(8, file.GetWidth(r.FlatRecord) * scale) / 2, h = Math.Max(8, file.GetHeight(r.FlatRecord) * scale) / 2;
            (r.X0, r.X1, r.Y0, r.Y1, r.Z0, r.Z1) = (-w, w, -w, w, -h, h);
            if (r.FlatArchive == EditorFlatArchive) continue;
            if (!IsOrdinaryFlat(r.FlatArchive) && r.Flag is < 1 or > 8 && r.Next < 0) continue;
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
                $"A {r.Id} {r.Kind} {r.Flag} {trigger} {r.Next} {r.Door} {r.Visual} {r.Position.X:F3} {r.Position.Y:F3} {r.Position.Z:F3} {r.Yaw:F3} {move.X:F3} {move.Y:F3} {move.Z:F3} {spin.X:F3} {spin.Y:F3} {spin.Z:F3} {tics} {(forwardOnly ? 1 : 0)} {cx:F3} {cy:F3} 0 {r.X0:F3} {r.X1:F3} {r.Y0:F3} {r.Y1:F3} {r.Z0:F3} {r.Z1:F3} {r.Sound} {r.Axis} {r.Magnitude} {r.LockValue} {(r.TrapdoorTile ? 1 : 0)}\n"));
            if (r.Kind == 1)
            {
                bool special = package.SpecialCells.ContainsKey(r.Model) && (IsSpecialDoorFlag(r.Flag) || r.TrapdoorTile);
                string half = special && package.CellHalf.TryGetValue(r.Model, out var h) ? FormattableString.Invariant($" {h:F2}") : "";
                if (special && package.CellHeight.TryGetValue(r.Model, out var tall)) half += FormattableString.Invariant($" {tall:F2}");
                foreach (var c in special ? package.SpecialCells[r.Model] : package.Cells[r.Model])
                    text.Append(FormattableString.Invariant($"C {r.Id} {c.X:F2} {c.Y:F2} {c.Z:F2}{half}\n"));
            }
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

    // The record's tilt and its model's size in Doom units, for the census below.
    static string SpecialDoorShape(string arena2, ActionRecord x)
    {
        var block = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true).GetBlock(x.BlockName);
        var obj = block.RdbBlock.ObjectRootList.Where(g => g.RdbObjects != null).SelectMany(g => g.RdbObjects).First(o => o.Position == x.FilePosition);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        var points = arch.GetMesh(arch.GetRecordIndex(x.Model)).SubMeshes.SelectMany(s => s.Planes).SelectMany(p => p.Points).Select(q => ToDoom(new V3(q.X, -q.Y, q.Z))).ToList();
        var m = obj.Resources.ModelResource;
        return FormattableString.Invariant($"tilt={m.XRotation},{m.ZRotation} yaw={m.YRotation / BlocksFile.RotationDivisor:F0} x={points.Min(p => p.X):F0}..{points.Max(p => p.X):F0} y={points.Min(p => p.Y):F0}..{points.Max(p => p.Y):F0} z={points.Min(p => p.Z):F0}..{points.Max(p => p.Z):F0}");
    }

    // --list-door-actions: every model with action 18 or 20 that is not a real door, in every dungeon (DaggerfallActionDoorSpecial).
    static int ListDoorActions(string arena2)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        int dungeons = 0, affected = 0, placed = 0;
        var perBlock = new SortedDictionary<string, string>();
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
                var records = ReadActionRecords(arena2, location);
                var special = records.Where(x => !x.IsFlat && !x.IsDoor && x.Flag is 18 or 20).ToList();
                if (special.Count == 0) continue;
                affected++;
                placed += special.Count;
                bool main = MainStoryIds.Contains(location.MapTableData.MapId);
                Console.WriteLine($"DUNGEON {location.MapTableData.MapId} {region.Name}/{region.MapNames[l]} main={main} objects={special.Count}");
                foreach (var x in special)
                    perBlock[$"{x.BlockName} {x.FilePosition}"] = $"m{x.Model} {x.Description} flag={x.Flag} trig={x.Trigger} at={x.Position.X:F0},{x.Position.Y:F0},{x.Position.Z:F0} {SpecialDoorShape(arena2, x)} next={x.Next} prev={string.Join(",", x.Previous.Select(p => $"{records[p].Description}:{records[p].Flag}:t{records[p].Trigger}"))}";
            }
        }
        foreach (var kv in perBlock) Console.WriteLine($"OBJECT {kv.Key} {kv.Value}");
        // Every action 8 trapdoor tile, so the count of tiles this affects is known.
        var hinged = new SortedDictionary<string, int>();
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r) || maps.GetRegion(r).MapNames == null) continue;
            var region = maps.GetRegion(r);
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                int n = ReadActionRecords(arena2, location).Count(x => !x.IsFlat && x.Description == "TRP" && x.Flag == 8);
                if (n > 0) hinged[$"{location.MapTableData.MapId} {region.Name}/{region.MapNames[l]}"] = n;
            }
        }
        foreach (var kv in hinged) Console.WriteLine($"HINGED {kv.Key} tiles={kv.Value}");
        Console.WriteLine($"HINGEDTOTAL dungeons={hinged.Count} tiles={hinged.Values.Sum()}");
        Console.WriteLine($"TOTAL dungeons={dungeons} affected={affected} placed={placed} distinctBlockObjects={perBlock.Count}");
        return 0;
    }

    // --list-trapdoors: every TRP model record in every dungeon, grouped by what can change how it behaves.
    static int ListTrapdoors(string arena2)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        var shapes = new Dictionary<uint, string>();
        var kinds = new SortedDictionary<string, (int placed, HashSet<int> dungeons, string example)>();
        var pillars = new SortedDictionary<string, (int tiles, int withPillar, string without)>();
        string Shape(uint id)
        {
            if (shapes.TryGetValue(id, out var known)) return known;
            var p = arch.GetMesh(arch.GetRecordIndex(id)).SubMeshes.SelectMany(s => s.Planes).SelectMany(q => q.Points).Select(q => ToDoom(new V3(q.X, -q.Y, q.Z))).ToList();
            double w = p.Max(q => q.X) - p.Min(q => q.X), d = p.Max(q => q.Y) - p.Min(q => q.Y), h = p.Max(q => q.Z) - p.Min(q => q.Z);
            return shapes[id] = FormattableString.Invariant($"{w:F0}x{d:F0}x{h:F0} {(h < Math.Min(w, d) / 4 ? "flat" : "notflat")}");
        }
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r) || maps.GetRegion(r).MapNames == null) continue;
            var region = maps.GetRegion(r);
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                var records = ReadActionRecords(arena2, location);
                foreach (var x in records.Where(x => !x.IsFlat && x.Description == "TRP"))
                {
                    var obj = blocks.GetBlock(x.BlockName).RdbBlock.ObjectRootList.Where(g => g.RdbObjects != null).SelectMany(g => g.RdbObjects).First(o => o.Position == x.FilePosition);
                    var m = obj.Resources.ModelResource;
                    string root = "self";
                    var seen = new HashSet<int> { x.Id };
                    var at = x;
                    while (at.Previous.Count > 0 && seen.Add(at.Previous[0])) at = records[at.Previous[0]];
                    if (at != x) root = $"{(at.IsFlat ? "flat" : at.IsDoor ? "door" : at.Description)}:f{at.Flag}:t{at.Trigger}";
                    string key = $"m{x.Model} {Shape(x.Model)} door={x.IsDoor} flag={x.Flag} trig={x.Trigger} axis={x.Axis} mag={x.Magnitude} dur={x.Duration} tilted={m.XRotation != 0 || m.ZRotation != 0} parents={x.Previous.Count} root={root}";
                    kinds.TryGetValue(key, out var k);
                    k.dungeons ??= new HashSet<int>();
                    k.dungeons.Add(location.MapTableData.MapId);
                    k.example ??= $"{location.MapTableData.MapId} {region.Name}/{region.MapNames[l]} {x.BlockName} record={x.Id}";
                    k.placed++;
                    kinds[key] = k;
                    if (x.Flag is 8 or 18 or 20) CountShaftPillar(location, blocks, arch, records, x, obj, pillars, key);
                }
            }
        }
        foreach (var kv in kinds) Console.WriteLine($"KIND placed={kv.Value.placed} dungeons={kv.Value.dungeons.Count} {kv.Key} eg {kv.Value.example}");
        Console.WriteLine($"TOTAL kinds={kinds.Count} placed={kinds.Values.Sum(k => k.placed)} dungeons={kinds.Values.SelectMany(k => k.dungeons).Distinct().Count()}");
        foreach (var kv in pillars) Console.WriteLine($"SHAFT {kv.Key}: {kv.Value.withPillar} of {kv.Value.tiles} flat hinged tiles hide a mover under them on their chain{(kv.Value.without != null ? " eg without " + kv.Value.without : "")}");
        return 0;
    }

    // Census for HiddenMoverBase: does a flat hinged tile's chain hold an action 1 to 7 model resting under it?
    static void CountShaftPillar(DFLocation location, BlocksFile blocks, Arch3dFile arch, List<ActionRecord> records, ActionRecord x, DFBlock.RdbObject obj,
        SortedDictionary<string, (int tiles, int withPillar, string without)> pillars, string key)
    {
        var dungeonBlock = location.Dungeon.Blocks[x.Block];
        var offset = new V3(dungeonBlock.X * BlockSide, 0, dungeonBlock.Z * BlockSide);
        if (RestingBox(arch, x.Model, obj, offset) is not var (x0, x1, y0, y1, bottom, top) || top - bottom >= Math.Min(x1 - x0, y1 - y0) / 4) return;
        var all = blocks.GetBlock(x.BlockName).RdbBlock.ObjectRootList.Where(g => g.RdbObjects != null).SelectMany(g => g.RdbObjects).ToList();
        bool found = false;
        var seen = new HashSet<int> { x.Id };
        for (var at = x; at.Next >= 0 && seen.Add(at.Next) && !found;)
        {
            at = records[at.Next];
            if (at.IsFlat || at.Flag is < 1 or > 7) continue;
            var o = all.First(q => q.Position == at.FilePosition);
            found = RestingBox(arch, at.Model, o, offset) is var (bx0, bx1, by0, by1, _, btop) && bx0 < x1 && bx1 > x0 && by0 < y1 && by1 > y0 && btop <= top + 1;
        }
        pillars.TryGetValue(key, out var c);
        pillars[key] = (c.tiles + 1, c.withPillar + (found ? 1 : 0), c.without ?? (found ? null : $"{location.MapTableData.MapId} {location.Name} {x.BlockName} record={x.Id}"));
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
