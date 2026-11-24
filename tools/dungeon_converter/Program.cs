// Converts a real Daggerfall dungeon into a UDMF map for UZDoom.
// Usage: dotnet run -c Release -- "<dungeon name>" --out <dir> [--arena2 <dir>] [--cell 16]
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

struct V3
{
    public double X, Y, Z;
    public V3(double x, double y, double z) { X = x; Y = y; Z = z; }
    public static V3 operator +(V3 a, V3 b) => new V3(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
}

struct Tri { public V3 A, B, C, N; public uint Model; public int Instance; }
class Span { public int F, C, Door = -1, FP = -1, CP = -1, Water = Program.NoWater; } // FP, CP: real sloped plane, or -1 for flat
class DoorInfo
{
    public int Id, Block; public double MinX, MaxX, MinY, MaxY, MinZ, MaxZ; public int Control, Height;
    // Real placement. The pivot is the model origin, which is the hinge DaggerfallActionDoor rotates about.
    public uint Model; public double PivotX, PivotY, PivotZ, RxDeg, RyDeg, RzDeg;
    public double LocalMinX = 1e9, LocalMaxX = -1e9, LocalMinY = 1e9, LocalMaxY = -1e9, LocalMinZ = 1e9, LocalMaxZ = -1e9;
}
class Node { public int Id, I, J, F, C, Block; public bool Door; }
class HangingCut { public bool AlongX; public int A, B, Behind; public double Position, Lo, Hi; public (int cell, int span) Key; }

static partial class Program
{
    const int ExitDoorModel = 70300, RedBrickDoorModel = 72100, MinTapestry = 42500, MaxTapestry = 42571;
    const int EditorArchive = 199, EnterRecord = 8, StartRecord = 10, BlockSide = 2048;
    const int ZQuant = 4;
    // Conversion thresholds, in Daggerfall units at scale 1. ApplyWorldScale derives them from PlayerScale.
    // KeepHeight keeps low spaces in the map (crouch routes); ActorHeight is what a standing body needs.
    static int ActorRadius = 16, ActorHeight = 56, KeepHeight = 56, StepHeight = 24, MinSpan = 24, MaxStairRelax = 8;

    static void ApplyWorldScale(bool cellWasSet)
    {
        double s = PlayerScale.DoomUnitsPerDaggerfallUnit;
        int Scaled(int value) => Math.Max(1, (int)Math.Round(value * s));
        KeepHeight = Scaled(KeepHeight); ActorRadius = Scaled(ActorRadius);
        // Stock Doom height and step do not shrink with the world.
        if (PlayerScale.DaggerfallBody) { ActorHeight = Scaled(ActorHeight); StepHeight = Scaled(StepHeight); }
        MinSpan = Scaled(MinSpan); MaxStairRelax = Scaled(MaxStairRelax);
        if (routeStep == 24) routeStep = StepHeight;
        if (!cellWasSet) cell = Scaled(cell);
    }
    const double WallNormalZ = 0.1;

    static int cell = 16, minX, minY, width, height;
    static string debugRow, debugLine;
    static List<(double z, bool up)>[] rawHits;
    static V3 entranceMarker;
    static int gapCells, skippedActions, relaxedStairs, postCount, nextInstance;
    static readonly Dictionary<int, List<(double lo, double hi)>> postCells = new Dictionary<int, List<(double lo, double hi)>>();
    static bool openActions;
    static int routeStep = 24;
    static List<Span>[] grid;
    static readonly List<Tri> tris = new List<Tri>();
    static readonly List<HangingCut> hanging = new List<HangingCut>();
    static readonly List<DoorInfo> doors = new List<DoorInfo>();
    static readonly List<EnemyPlacement> enemyPlacements = new List<EnemyPlacement>();
    static readonly StringBuilder monsterIds = new StringBuilder(); // DDMONST: map id, monster id, and the thing's position.
    static int enemiesSkipped, currentMapId;
    const int RandomEnemyRecord = 15, FixedEnemyRecord = 16;
    static readonly List<(string name, int x, int y)> blockRects = new List<(string, int, int)>();

    static int Main(string[] args)
    {
        CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
        if (args.Contains("--world")) return WorldTerrain.RunExport(args); // shared height data for the overworld and town maps
        if (args.Contains("--runtime-assets")) return City.RuntimeAssets(args); // the shared package for locations converted during play
        if (args.Contains("--city") || args.Contains("--group")) return City.Run(args); // cities have their own pipeline in CityExport.cs
        string name = null, outDir = null, arena2 = @"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2";
        if (args.Contains("--list-water")) return ListWater(arena2);
        if (args.Contains("--list-tilted-doors")) return ListTiltedDoors(arena2);
        if (args.Contains("--list-main")) return ListMain(arena2, args.Contains("--list-all"));
        if (args.Contains("--list-flats")) return ListFlats(arena2);
        if (args.Contains("--list-door-actions")) return ListDoorActions(arena2);
        if (args.Contains("--list-trapdoors")) return ListTrapdoors(arena2);
        for (int a = 0; a < args.Length; a++)
        {
            if (args[a] == "--out") outDir = args[++a];
            else if (args[a] == "--arena2") arena2 = args[++a];
            else if (args[a] == "--cell") cell = int.Parse(args[++a]);
            else if (args[a] == "--ceiling-relief") MaxCeilingRelief = int.Parse(args[++a]);
            else if (args[a] == "--world-scale") PlayerScale.DoomUnitsPerDaggerfallUnit = double.Parse(args[++a], CultureInfo.InvariantCulture);
            else if (args[a] == "--daggerfall-player") PlayerScale.DaggerfallBody = true; // opt-in: scaled Daggerfall body and <slug>_player.pk3
            else if (args[a] == "--parity") parityDir = args[++a]; // writes the Doom test lump, or compares if doom_flood.txt exists there
            else if (args[a] == "--debug-row") debugRow = args[++a];
            else if (args[a] == "--debug-line") debugLine = args[++a]; // x0,y0,x1,y1,z0,z1: raw hits, spans, and faces along a line
            else if (args[a] == "--audit-points") a += 2;
            else if (args[a] == "--no-walls" || args[a] == "--export-mesh" || args[a] == "--no-ceiling-relief" || args[a] == "--door-dump" || args[a] == "--action-dump" || args[a] == "--runtime-dungeon") { }
            else if (args[a] == "--texture-table") a++; // used by --export-mesh: six archives, comma separated
            else if (args[a] == "--grid-collision") gridCollision = true; // old axis-aligned boundaries and flat planes
            else if (args[a] == "--open-actions") openActions = true;            else if (args[a] == "--route-step") routeStep = int.Parse(args[++a]); // diagnostic: models jumping or climbing
            else name = args[a];
        }
        if (name == null || outDir == null)
        {
            Console.Error.WriteLine("usage: DungeonConverter \"<dungeon name>\" --out <dir> [--arena2 <dir>] [--cell 16]");
            return 2;
        }
        ApplyWorldScale(args.Contains("--cell"));
        Directory.CreateDirectory(outDir);
        if (!FindDungeon(arena2, name, out DFLocation location)) { Console.Error.WriteLine("dungeon not found: " + name); return 1; }
        if (args.Contains("--action-dump")) return DumpActions(arena2, location, outDir);
        int meshAt = Array.IndexOf(args, "--export-mesh"); // writes <slug>_mesh.pk3 (real models, textures, UVs) and exits
        if (meshAt >= 0) return ExportMesh(arena2, location, outDir, new string(name.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant(), args);

        currentMapId = location.MapTableData.MapId;
        V3 entrance = entranceMarker = LoadGeometry(arena2, location);
        BuildGrid();
        DumpLine("grid");
        int walled = args.Contains("--no-walls") ? 0 : ApplyWalls();
        if (!args.Contains("--no-walls")) ApplyPosts();
        DumpLine("walls");
        relaxedStairs = RelaxStairs();
        gapCells = CloseGaps();
        if (!args.Contains("--no-ceiling-relief")) RelieveCeilings();
        int lidCells = OpenLidRims();
        if (lidFootprints.Count > 0) Console.WriteLine($"coffin rims: {lidCells} cells regained the air above the rim, {lidFootprints.Count} lids");
        ApplyDoors(); // these spans become sight blockers only
        if (!gridCollision) AssignPlanes();
        AssignWater();
        if (args.Contains("--door-dump"))
        {
            foreach (var d in doors)
                Console.WriteLine(FormattableString.Invariant($"DOORDUMP {d.Id} m{d.Model} b{d.Block} pivot {d.PivotX:F2},{d.PivotY:F2},{d.PivotZ:F2} rot {d.RxDeg:F4},{d.RyDeg:F4},{d.RzDeg:F4} local x {d.LocalMinX:F2}..{d.LocalMaxX:F2} y {d.LocalMinY:F2}..{d.LocalMaxY:F2} z {d.LocalMinZ:F2}..{d.LocalMaxZ:F2} world x {d.MinX:F1}..{d.MaxX:F1} y {d.MinY:F1}..{d.MaxY:F1} z {d.MinZ:F1}..{d.MaxZ:F1}"));
            // Whether each side of a door has a dungeon block and source faces 24 units out from the panel.
            double blockSide = BlockSide * PlayerScale.DoomUnitsPerDaggerfallUnit;
            foreach (var d in doors)
            {
                double a = -d.RyDeg * Math.PI / 180, nx = -Math.Sin(a), ny = Math.Cos(a);
                double cx = (d.MinX + d.MaxX) / 2, cy = (d.MinY + d.MaxY) / 2;
                var sides = new[] { 1, -1 }.Select(s =>
                {
                    double x = cx + nx * s * 24, y = cy + ny * s * 24;
                    bool inBlock = blockRects.Any(b => x >= b.Item2 && x < b.Item2 + blockSide && y >= b.Item3 && y < b.Item3 + blockSide);
                    int faces = tris.Count(t => Math.Min(t.A.X, Math.Min(t.B.X, t.C.X)) <= x && Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)) >= x
                        && Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y)) <= y && Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)) >= y
                        && Math.Max(t.A.Z, Math.Max(t.B.Z, t.C.Z)) >= d.MinZ - 8 && Math.Min(t.A.Z, Math.Min(t.B.Z, t.C.Z)) <= d.MaxZ + 8);
                    return $"block={(inBlock ? 1 : 0)},faces={faces}";
                });
                Console.WriteLine($"DOORSIDE {d.Id} {string.Join(" ", sides)}");
            }
            return 0;
        }
        DumpLine("final");
        int auditAt = Array.IndexOf(args, "--audit-points"); // <old points file> <leak output>: audit another version's links, then exit
        if (auditAt >= 0) { AuditPointsFile(args[auditAt + 1], args[auditAt + 2]); return 0; }
        if (debugRow != null)
        {
            var near = doors.OrderBy(d => Math.Abs(d.MinX - entrance.X) + Math.Abs(d.MinY - entrance.Y) + Math.Abs(d.MinZ - entrance.Z)).First();
            Console.WriteLine($"DOOR box x {near.MinX:F0}..{near.MaxX:F0} y {near.MinY:F0}..{near.MaxY:F0} z {near.MinZ:F0}..{near.MaxZ:F0}");
            var parts = debugRow.Split(',');
            DumpAround(parts.Length == 3 ? new V3(double.Parse(parts[0]), double.Parse(parts[1]), double.Parse(parts[2])) : entrance);
        }
        var nodes = BuildNodes(out var edges);
        int start = FindStart(nodes, entrance);
        string slug = new string(name.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant();
        var points = WritePoints(nodes, edges, start);
        var mapStats = WriteMap(Path.Combine(outDir, slug + ".wad"), nodes[start], points);
        File.WriteAllText(Path.Combine(outDir, slug + ".points.txt"), points);
        WriteWaterProbes(outDir, slug, nodes[start]);
        if (PlayerScale.DaggerfallBody) PlayerScale.WritePackage(outDir, slug);
        if (parityDir != null) return RunParity(parityDir, entrance);
        WriteStats(Path.Combine(outDir, slug + ".stats.txt"), name, location, nodes, edges, start, walled, mapStats);
        File.AppendAllText(Path.Combine(outDir, slug + ".stats.txt"), fitReport);
        Console.WriteLine(File.ReadAllText(Path.Combine(outDir, slug + ".stats.txt")));
        return 0;
    }

    // The ids in DaggerfallDungeon.IsMainStoryDungeon, copied because that class needs Unity.
    static readonly int[] MainStoryIds = { 187853213, 630439035, 1291010263, 6634853, 19021260, 728811286, 701948302, 83032363, 1001, 207828842, 9570447, 2352284, 336619236, 43196334 };

    static int ListMain(string arena2, bool all)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var loc = maps.GetLocation(r, l);
                if (!MainStoryIds.Contains(loc.MapTableData.MapId) && !all) continue; // --list-all lists every location with a dungeon
                Console.WriteLine($"MAIN {loc.MapTableData.MapId} {region.Name}/{region.MapNames[l]} hasDungeon={loc.HasDungeon} blocks={(loc.HasDungeon ? loc.Dungeon.Blocks.Length : 0)}");
            }
        }
        return 0;
    }

    static bool FindDungeon(string arena2, string name, out DFLocation location)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                bool byId = name.StartsWith("#"); // "#<map id>" picks the exact location, because names repeat across regions
                if (!byId && !string.Equals(region.MapNames[l], name, StringComparison.OrdinalIgnoreCase)) continue;
                var candidate = maps.GetLocation(r, l);
                if (byId && candidate.MapTableData.MapId.ToString() != name.Substring(1)) continue;
                if (candidate.HasDungeon) { location = candidate; return true; }
            }
        }
        location = default;
        return false;
    }

    // Matches RDBLayout.GetModelMatrix: T * Rz * Rx * Ry, in Unity's axes, before GlobalScale.
    static V3 Rotate(V3 p, double rx, double ry, double rz)
    {
        double c = Math.Cos(ry), s = Math.Sin(ry);
        p = new V3(p.X * c + p.Z * s, p.Y, -p.X * s + p.Z * c);
        c = Math.Cos(rx); s = Math.Sin(rx);
        p = new V3(p.X, p.Y * c - p.Z * s, p.Y * s + p.Z * c);
        c = Math.Cos(rz); s = Math.Sin(rz);
        return new V3(p.X * c - p.Y * s, p.X * s + p.Y * c, p.Z);
    }

    static V3 ToDoom(V3 unity)
    {
        double s = PlayerScale.DoomUnitsPerDaggerfallUnit;
        return new V3(unity.X * s, unity.Z * s, unity.Y * s);
    }

    static V3 LoadGeometry(string arena2, DFLocation location)
    {
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        V3? enter = null, startMark = null;
        int blockIndex = -1;
        foreach (var dungeonBlock in location.Dungeon.Blocks)
        {
            blockIndex++;
            var block = blocks.GetBlock(dungeonBlock.BlockName);
            var offset = new V3(dungeonBlock.X * BlockSide, 0, dungeonBlock.Z * BlockSide);
            blockRects.Add((dungeonBlock.BlockName, (int)Math.Round(dungeonBlock.X * BlockSide * PlayerScale.DoomUnitsPerDaggerfallUnit), (int)Math.Round(dungeonBlock.Z * BlockSide * PlayerScale.DoomUnitsPerDaggerfallUnit)));
            blockWater.Add(BlockWaterHeight(block));
            if (block.RdbBlock.ObjectRootList == null) continue;
            foreach (var group in block.RdbBlock.ObjectRootList)
            {
                if (group.RdbObjects == null) continue;
                foreach (var obj in group.RdbObjects)
                {
                    if (obj.Type == DFBlock.RdbResourceTypes.Flat && dungeonBlock.IsStartingBlock
                        && obj.Resources.FlatResource.TextureArchive == EditorArchive)
                    {
                        var marker = ToDoom(new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset);
                        if (debugRow != null && (obj.Resources.FlatResource.TextureRecord is EnterRecord or StartRecord))
                            Console.WriteLine($"MARKER record={obj.Resources.FlatResource.TextureRecord} at {marker.X:F0},{marker.Y:F0},{marker.Z:F0}");
                        if (obj.Resources.FlatResource.TextureRecord == EnterRecord) enter ??= marker;
                        if (obj.Resources.FlatResource.TextureRecord == StartRecord) startMark ??= marker;
                    }
                    if (obj.Type == DFBlock.RdbResourceTypes.Flat && obj.Resources.FlatResource.TextureArchive == EditorArchive
                        && (obj.Resources.FlatResource.TextureRecord == RandomEnemyRecord || obj.Resources.FlatResource.TextureRecord == FixedEnemyRecord))
                    {
                        var f = obj.Resources.FlatResource;
                        var at = ToDoom(new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset);
                        ulong placement = EnemyRoster.Hash(currentMapId, dungeonBlock.BlockName, dungeonBlock.X, dungeonBlock.Z,
                            obj.XPos, obj.YPos, obj.ZPos, f.TextureRecord, f.FactionOrMobileId);
                        enemyPlacements.Add(new EnemyPlacement(at.X, at.Y, at.Z, EnemyRoster.Pick(placement), EnemyRoster.MonsterId(placement)));
                    }
                    if (obj.Type != DFBlock.RdbResourceTypes.Model) continue;
                    var reference = block.RdbBlock.ModelReferenceList[obj.Resources.ModelResource.ModelIndex];
                    uint id = reference.ModelIdNum;
                    if (debugRow != null && id == ExitDoorModel)
                        Console.WriteLine($"MARKER exit door in {dungeonBlock.BlockName} start={dungeonBlock.IsStartingBlock} at {obj.XPos + offset.X:F0},{obj.ZPos + offset.Z:F0},{-obj.YPos}");
                    // These models have no collider in Daggerfall Unity.
                    if (id == ExitDoorModel || (id >= MinTapestry && id <= MaxTapestry)) continue;
                    bool isDoor = id != RedBrickDoorModel && reference.Description is "DOR" or "DDR" or "NEW" or "CAV";
                    var action = obj.Resources.ModelResource.ActionResource;
                    if (debugRow != null && (action.Flags != 0 || isDoor))
                        Console.WriteLine($"ACTION block={dungeonBlock.BlockName} model={id} desc={reference.Description} door={isDoor} flags={action.Flags} axis={action.Axis} dur={action.Duration} mag={action.Magnitude} next={action.NextObjectOffset} pos={obj.XPos + offset.X:F0},{obj.ZPos + offset.Z:F0},{-obj.YPos}");
                    // Moving models are runtime objects (action_objects.zs), so they are not static collision.
                    if (IsMovingAction(obj, isDoor, id))
                    {
                        skippedActions++;
                        if (reference.Description == "LID") NoteLidFootprint(arch, id, obj, offset);
                        NoteTrapdoorFootprint(arch, id, obj, offset, reference.Description);
                        continue;
                    }
                    // Diagnostic: also treat every other action model as out of the way.
                    if (openActions && !isDoor && action.Flags != 0) { skippedActions++; continue; }
                    AddModel(arch, id, obj, offset, isDoor, blockIndex);
                }
            }
        }
        // Record 10 sits beside the exit door. Record 8 can be a sealed room (Privateer's Hold).
        return startMark ?? enter ?? throw new InvalidDataException("no entrance marker in starting block");
    }

    static void AddModel(Arch3dFile arch, uint id, DFBlock.RdbObject obj, V3 offset, bool isDoor, int block)
    {
        int record = arch.GetRecordIndex(id);
        if (record < 0) return;
        var mesh = arch.GetMesh(record);
        int instance = nextInstance++;
        const double toRad = Math.PI / 180;
        double rx = -obj.Resources.ModelResource.XRotation / BlocksFile.RotationDivisor * toRad;
        double ry = -obj.Resources.ModelResource.YRotation / BlocksFile.RotationDivisor * toRad;
        double rz = -obj.Resources.ModelResource.ZRotation / BlocksFile.RotationDivisor * toRad;
        var position = new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset;
        DoorInfo door = null;
        if (isDoor)
        {
            var pivot = ToDoom(position);
            door = new DoorInfo
            {
                Id = doors.Count, Block = block, MinX = 1e9, MinY = 1e9, MinZ = 1e9, MaxX = -1e9, MaxY = -1e9, MaxZ = -1e9,
                Model = id, PivotX = pivot.X, PivotY = pivot.Y, PivotZ = pivot.Z, RxDeg = rx / toRad, RyDeg = ry / toRad, RzDeg = rz / toRad,
            };
        }
        foreach (var sub in mesh.SubMeshes)
            foreach (var plane in sub.Planes)
            {
                var pts = plane.Points.Select(p => ToDoom(Rotate(new V3(p.X, -p.Y, p.Z), rx, ry, rz) + position)).ToArray();
                if (door != null)
                {
                    foreach (var q in plane.Points)
                    {
                        // Model space at Doom scale, before placement: x, Unity z (Doom y), height.
                        var l = ToDoom(new V3(q.X, -q.Y, q.Z));
                        door.LocalMinX = Math.Min(door.LocalMinX, l.X); door.LocalMaxX = Math.Max(door.LocalMaxX, l.X);
                        door.LocalMinY = Math.Min(door.LocalMinY, l.Y); door.LocalMaxY = Math.Max(door.LocalMaxY, l.Y);
                        door.LocalMinZ = Math.Min(door.LocalMinZ, l.Z); door.LocalMaxZ = Math.Max(door.LocalMaxZ, l.Z);
                    }
                    foreach (var p in pts)
                    {
                        door.MinX = Math.Min(door.MinX, p.X); door.MaxX = Math.Max(door.MaxX, p.X);
                        door.MinY = Math.Min(door.MinY, p.Y); door.MaxY = Math.Max(door.MaxY, p.Y);
                        door.MinZ = Math.Min(door.MinZ, p.Z); door.MaxZ = Math.Max(door.MaxZ, p.Z);
                    }
                    var doorFirst = plane.Points[0];
                    var doorNormal = ToDoom(Rotate(new V3(doorFirst.NX, -doorFirst.NY, doorFirst.NZ), rx, ry, rz));
                    double doorLength = Math.Sqrt(doorNormal.X * doorNormal.X + doorNormal.Y * doorNormal.Y + doorNormal.Z * doorNormal.Z);
                    if (doorLength > 1e-6)
                        for (int i = 1; i + 1 < pts.Length; i++)
                            doorMeshTris.Add(new Tri { A = pts[0], B = pts[i], C = pts[i + 1], N = new V3(doorNormal.X / doorLength, doorNormal.Y / doorLength, doorNormal.Z / doorLength), Model = id, Instance = instance });
                    continue;
                }
                var first = plane.Points[0];
                var normal = ToDoom(Rotate(new V3(first.NX, -first.NY, first.NZ), rx, ry, rz));
                double length = Math.Sqrt(normal.X * normal.X + normal.Y * normal.Y + normal.Z * normal.Z);
                if (length < 1e-6) continue;
                normal = new V3(normal.X / length, normal.Y / length, normal.Z / length);
                for (int i = 1; i + 1 < pts.Length; i++)
                    tris.Add(new Tri { A = pts[0], B = pts[i], C = pts[i + 1], N = normal, Model = id, Instance = instance });
            }
        if (door != null) doors.Add(door);
    }

    static int Quant(double z) => (int)Math.Round(z / ZQuant) * ZQuant;
    static int Index(int i, int j) => i + j * width;

    // Casts one vertical ray through each cell and pairs floors with the ceilings above them.
    static void BuildGrid()
    {
        double x0 = tris.Min(t => Math.Min(t.A.X, Math.Min(t.B.X, t.C.X)));
        double y0 = tris.Min(t => Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y)));
        double x1 = tris.Max(t => Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)));
        double y1 = tris.Max(t => Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)));
        minX = (int)Math.Floor(x0 / cell) * cell - cell;
        minY = (int)Math.Floor(y0 / cell) * cell - cell;
        width = (int)Math.Ceiling((x1 - minX) / cell) + 2;
        height = (int)Math.Ceiling((y1 - minY) / cell) + 2;
        var hits = new List<(double z, bool up)>[width * height];
        foreach (var t in tris)
        {
            // Steep cave ceilings and floors are still surfaces. Only near-vertical faces are walls.
            if (Math.Abs(t.N.Z) < WallNormalZ) continue;
            int i0 = Math.Max(0, (int)Math.Floor((Math.Min(t.A.X, Math.Min(t.B.X, t.C.X)) - minX) / cell));
            int i1 = Math.Min(width - 1, (int)Math.Floor((Math.Max(t.A.X, Math.Max(t.B.X, t.C.X)) - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((Math.Min(t.A.Y, Math.Min(t.B.Y, t.C.Y)) - minY) / cell));
            int j1 = Math.Min(height - 1, (int)Math.Floor((Math.Max(t.A.Y, Math.Max(t.B.Y, t.C.Y)) - minY) / cell));
            double d = (t.B.Y - t.C.Y) * (t.A.X - t.C.X) + (t.C.X - t.B.X) * (t.A.Y - t.C.Y);
            if (Math.Abs(d) < 1e-9) continue;
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                {
                    double px = minX + (i + 0.5) * cell, py = minY + (j + 0.5) * cell;
                    double u = ((t.B.Y - t.C.Y) * (px - t.C.X) + (t.C.X - t.B.X) * (py - t.C.Y)) / d;
                    double v = ((t.C.Y - t.A.Y) * (px - t.C.X) + (t.A.X - t.C.X) * (py - t.C.Y)) / d;
                    double w = 1 - u - v;
                    if (u < -1e-6 || v < -1e-6 || w < -1e-6) continue;
                    (hits[Index(i, j)] ??= new List<(double, bool)>()).Add((u * t.A.Z + v * t.B.Z + w * t.C.Z, t.N.Z > 0));
                }
        }
        int pitCells = FloorBottomlessPits(hits);
        if (pitCells > 0) Console.WriteLine($"bottomless trapdoor pits: {pitCells} cells floored {BottomlessPitDepth} below their tile");
        rawHits = hits;
        grid = new List<Span>[width * height];
        if (debugRow != null)
        {
            int row = (int.Parse(debugRow.Split(',')[debugRow.Contains(',') ? 1 : 0]) - minY) / cell;
            string last = null;
            for (int i = 0; i < width; i++)
            {
                var h = hits[Index(i, row)];
                string text = h == null ? "-" : string.Join(" ", h.OrderBy(x => x.z).Select(x => $"{(x.up ? "U" : "D")}{x.z:F0}"));
                if (text != last) Console.WriteLine($"x={minX + i * cell}: {text}");
                last = text;
            }
        }
        for (int c = 0; c < grid.Length; c++)
        {
            grid[c] = new List<Span>();
            if (hits[c] == null) continue;
            double? floor = null;
            foreach (var hit in hits[c].OrderBy(h => h.z))
            {
                if (hit.up) floor = hit.z;
                else if (floor != null)
                {
                    int f = Quant(floor.Value), top = Quant(hit.z);
                    if (top - f >= MinSpan) grid[c].Add(new Span { F = f, C = top });
                    floor = null;
                }
            }
        }
    }

    // A wall crossing the line between two cell centers makes the cell behind it solid over the wall's
    // own height range. Lintels and sills therefore shape an opening instead of closing it.
    static int ApplyWalls()
    {
        var blocked = new Dictionary<(int cell, int span), List<(double lo, double hi)>>();
        foreach (var t in tris)
        {
            if (Math.Abs(t.N.Z) >= WallNormalZ) continue;
            if (Math.Abs(t.N.X) > 0.2) WallAxis(t, true, blocked);
            if (Math.Abs(t.N.Y) > 0.2) WallAxis(t, false, blocked);
        }
        ThinHangingWalls(blocked);
        int removed = 0;
        foreach (var group in blocked.GroupBy(b => b.Key.cell))
        {
            var spans = grid[group.Key];
            foreach (var entry in group.OrderByDescending(b => b.Key.span))
            {
                var span = spans[entry.Key.span];
                spans.RemoveAt(entry.Key.span);
                var pieces = SubtractWalls(span, entry.Value);
                if (pieces.Count == 0) removed++;
                spans.InsertRange(entry.Key.span, pieces);
            }
        }
        return removed;
    }

    // Bars and posts can be thinner than a cell and miss every sample line. Each separate piece of a model
    // with a footprint of at most one cell and at least waist height makes the cell at its center solid.
    static void ApplyPosts()
    {
        foreach (var model in tris.GroupBy(t => t.Instance))
        {
            var parent = new Dictionary<(int, int, int), (int, int, int)>();
            (int, int, int) Key(V3 p) => ((int)Math.Round(p.X), (int)Math.Round(p.Y), (int)Math.Round(p.Z));
            (int, int, int) Find((int, int, int) x)
            {
                if (!parent.ContainsKey(x)) parent[x] = x;
                while (!parent[x].Equals(x)) x = parent[x] = parent[parent[x]];
                return x;
            }
            foreach (var t in model)
            {
                var a = Find(Key(t.A));
                parent[Find(Key(t.B))] = a;
                parent[Find(Key(t.C))] = a;
            }
            foreach (var piece in model.GroupBy(t => Find(Key(t.A))))
            {
                var p = piece.SelectMany(t => new[] { t.A, t.B, t.C }).ToList();
                double x0 = p.Min(v => v.X), x1 = p.Max(v => v.X), y0 = p.Min(v => v.Y), y1 = p.Max(v => v.Y), lo = p.Min(v => v.Z), hi = p.Max(v => v.Z);
                if (x1 - x0 > cell || y1 - y0 > cell || hi - lo < 40) continue;
                int c = Index((int)Math.Floor(((x0 + x1) / 2 - minX) / cell), (int)Math.Floor(((y0 + y1) / 2 - minY) / cell));
                postCount++;
                if (!postCells.TryGetValue(c, out var list)) postCells[c] = list = new List<(double, double)>();
                list.Add((lo, hi));
                var spans = grid[c];
                for (int s = spans.Count - 1; s >= 0; s--)
                {
                    if (Math.Min(spans[s].C, hi) - Math.Max(spans[s].F, lo) <= 8) continue;
                    var kept = SubtractWalls(spans[s], new List<(double lo, double hi)> { (lo, hi) });
                    spans.RemoveAt(s);
                    spans.InsertRange(s, kept);
                }
            }
        }
    }

    static bool PostBlocks(int c, int f, int top) =>
        postCells.TryGetValue(c, out var list) && list.Any(w => Math.Min(top, w.hi) - Math.Max(f, w.lo) > 8);

    // A thin beam or lintel has faces on both sides of one cell boundary, which would lower the ceiling of
    // both cells. It only needs to occupy the cell nearer its middle. Walls reaching the floor are not affected.
    static void ThinHangingWalls(Dictionary<(int cell, int span), List<(double lo, double hi)>> blocked)
    {
        foreach (var pair in hanging.GroupBy(h => (h.AlongX, h.A, h.B)))
        {
            var cuts = pair.ToList();
            int origin = pair.Key.AlongX ? minX : minY;
            double lowCenter = origin + (pair.Key.A + 0.5) * cell, highCenter = lowCenter + cell;
            foreach (var cut in cuts)
            {
                var other = cuts.FirstOrDefault(o => o.Behind != cut.Behind && Math.Min(o.Hi, cut.Hi) - Math.Max(o.Lo, cut.Lo) > 8);
                if (other == null) continue;
                double middle = (cut.Position + other.Position) / 2;
                int keep = middle - lowCenter <= highCenter - middle ? pair.Key.A : pair.Key.A + 1;
                if (cut.Behind == keep || !blocked.TryGetValue(cut.Key, out var list)) continue;
                list.Remove((cut.Lo, cut.Hi));
                if (list.Count == 0) blocked.Remove(cut.Key);
            }
        }
        hanging.Clear();
    }

    // Keeps the opening at the bottom of a span: a sill may raise its floor by one step and a lintel lowers
    // its ceiling. A wall rising higher than a step is solid, because the space above it has no real floor.
    static List<Span> SubtractWalls(Span span, List<(double lo, double hi)> walls)
    {
        double bottom = span.F, top = span.C;
        foreach (var (lo, hi) in walls.OrderBy(w => w.lo))
        {
            if (lo > bottom + ZQuant) { top = lo; break; }
            bottom = Math.Max(bottom, hi);
        }
        int f = Quant(bottom), c = Quant(Math.Min(top, span.C));
        var pieces = new List<Span>();
        if (f - span.F <= StepHeight && c - f >= KeepHeight) pieces.Add(new Span { F = f, C = c });
        return pieces;
    }

    static void WallAxis(Tri t, bool alongX, Dictionary<(int, int), List<(double lo, double hi)>> blocked)
    {
        double A(V3 p) => alongX ? p.X : p.Y;
        double B(V3 p) => alongX ? p.Y : p.X;
        int originA = alongX ? minX : minY, originB = alongX ? minY : minX, countA = alongX ? width : height, countB = alongX ? height : width;
        var points = new[] { t.A, t.B, t.C };
        int b0 = Math.Max(0, (int)Math.Ceiling((points.Min(B) - originB) / cell - 0.5));
        int b1 = Math.Min(countB - 1, (int)Math.Floor((points.Max(B) - originB) / cell - 0.5));
        double normalA = alongX ? t.N.X : t.N.Y;
        for (int b = b0; b <= b1; b++)
        {
            double line = originB + (b + 0.5) * cell;
            var cuts = new List<(double a, double z)>();
            for (int e = 0; e < 3; e++)
            {
                V3 p = points[e], q = points[(e + 1) % 3];
                double bp = B(p), bq = B(q);
                if ((bp < line) == (bq < line)) continue;
                double f = (line - bp) / (bq - bp);
                cuts.Add((A(p) + f * (A(q) - A(p)), p.Z + f * (q.Z - p.Z)));
            }
            if (cuts.Count != 2) continue;
            var (c0, c1) = cuts[0].a <= cuts[1].a ? (cuts[0], cuts[1]) : (cuts[1], cuts[0]);
            int a0 = Math.Max(0, (int)Math.Floor((c0.a - originA) / cell - 0.5));
            int a1 = Math.Min(countA - 2, (int)Math.Floor((c1.a - originA) / cell - 0.5));
            for (int a = a0; a <= a1; a++)
            {
                double ca = originA + (a + 0.5) * cell, cb = ca + cell;
                double lo = Math.Max(ca, c0.a), hi = Math.Min(cb, c1.a);
                if (hi < lo) continue;
                double range = c1.a - c0.a;
                double z0 = range < 1e-6 ? c0.z : c0.z + (lo - c0.a) / range * (c1.z - c0.z);
                double z1 = range < 1e-6 ? c1.z : c0.z + (hi - c0.a) / range * (c1.z - c0.z);
                int behind = normalA > 0 ? a : a + 1;
                int index = alongX ? Index(behind, b) : Index(b, behind);
                var spans = grid[index];
                for (int s = 0; s < spans.Count; s++)
                {
                    double wallLo = Math.Min(z0, z1), wallHi = Math.Max(z0, z1);
                    double overlap = Math.Min(spans[s].C, wallHi) - Math.Max(spans[s].F, wallLo);
                    if (overlap <= 8) continue;
                    if (!blocked.TryGetValue((index, s), out var list)) blocked[(index, s)] = list = new List<(double, double)>();
                    list.Add((wallLo, wallHi));
                    if (wallLo > spans[s].F + StepHeight)
                        hanging.Add(new HangingCut { AlongX = alongX, A = a, B = b, Behind = behind, Position = (lo + hi) / 2, Lo = wallLo, Hi = wallHi, Key = (index, s) });
                }
            }
        }
    }

    static List<int>[] wallIndex;

    static void BuildWallIndex()
    {
        wallIndex = new List<int>[width * height];
        for (int t = 0; t < tris.Count; t++)
        {
            var x = tris[t];
            if (Math.Abs(x.N.Z) >= 0.5) continue;
            int i0 = Math.Max(0, (int)Math.Floor((Math.Min(x.A.X, Math.Min(x.B.X, x.C.X)) - minX) / cell));
            int i1 = Math.Min(width - 1, (int)Math.Floor((Math.Max(x.A.X, Math.Max(x.B.X, x.C.X)) - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((Math.Min(x.A.Y, Math.Min(x.B.Y, x.C.Y)) - minY) / cell));
            int j1 = Math.Min(height - 1, (int)Math.Floor((Math.Max(x.A.Y, Math.Max(x.B.Y, x.C.Y)) - minY) / cell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    (wallIndex[Index(i, j)] ??= new List<int>()).Add(t);
        }
    }

    static bool SegmentHits(V3 p, V3 q, Tri t)
    {
        V3 e1 = new V3(t.B.X - t.A.X, t.B.Y - t.A.Y, t.B.Z - t.A.Z), e2 = new V3(t.C.X - t.A.X, t.C.Y - t.A.Y, t.C.Z - t.A.Z);
        V3 d = new V3(q.X - p.X, q.Y - p.Y, q.Z - p.Z);
        V3 h = new V3(d.Y * e2.Z - d.Z * e2.Y, d.Z * e2.X - d.X * e2.Z, d.X * e2.Y - d.Y * e2.X);
        double det = e1.X * h.X + e1.Y * h.Y + e1.Z * h.Z;
        if (Math.Abs(det) < 1e-9) return false;
        V3 s = new V3(p.X - t.A.X, p.Y - t.A.Y, p.Z - t.A.Z);
        double u = (s.X * h.X + s.Y * h.Y + s.Z * h.Z) / det;
        if (u < 0 || u > 1) return false;
        V3 c = new V3(s.Y * e1.Z - s.Z * e1.Y, s.Z * e1.X - s.X * e1.Z, s.X * e1.Y - s.Y * e1.X);
        double v = (d.X * c.X + d.Y * c.Y + d.Z * c.Z) / det;
        if (v < 0 || u + v > 1) return false;
        double r = (e2.X * c.X + e2.Y * c.Y + e2.Z * c.Z) / det;
        return r >= 0 && r <= 1;
    }

    static bool WallBetween(int i0, int j0, int i1, int j1, double z)
    {
        V3 p = new V3(minX + (i0 + 0.5) * cell, minY + (j0 + 0.5) * cell, z), q = new V3(minX + (i1 + 0.5) * cell, minY + (j1 + 0.5) * cell, z);
        var tested = new HashSet<int>();
        for (int j = Math.Min(j0, j1); j <= Math.Max(j0, j1); j++)
            for (int i = Math.Min(i0, i1); i <= Math.Max(i0, i1); i++)
            {
                var list = wallIndex[Index(i, j)];
                if (list == null) continue;
                foreach (int t in list)
                    if (tested.Add(t) && SegmentHits(p, q, tris[t])) return true;
            }
        return false;
    }

    // Stair treads can be shorter than a cell, so sampling may skip one and create a step too tall to climb.
    // Lowers the upper floor slightly, only where a fine walk over the real surfaces proves the stair is climbable.
    static int RelaxStairs()
    {
        BuildWallIndex();
        var floorIndex = new List<int>[width * height];
        for (int t = 0; t < tris.Count; t++)
        {
            var x = tris[t];
            if (x.N.Z < WallNormalZ) continue;
            int i0 = Math.Max(0, (int)Math.Floor((Math.Min(x.A.X, Math.Min(x.B.X, x.C.X)) - minX) / cell));
            int i1 = Math.Min(width - 1, (int)Math.Floor((Math.Max(x.A.X, Math.Max(x.B.X, x.C.X)) - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((Math.Min(x.A.Y, Math.Min(x.B.Y, x.C.Y)) - minY) / cell));
            int j1 = Math.Min(height - 1, (int)Math.Floor((Math.Max(x.A.Y, Math.Max(x.B.Y, x.C.Y)) - minY) / cell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    (floorIndex[Index(i, j)] ??= new List<int>()).Add(t);
        }
        bool Climbable(int i0, int j0, int i1, int j1, int low, int high)
        {
            const int Samples = 8;
            double current = low;
            for (int k = 1; k <= Samples; k++)
            {
                double px = minX + (i0 + 0.5 + (i1 - i0) * (double)k / Samples) * cell, py = minY + (j0 + 0.5 + (j1 - j0) * (double)k / Samples) * cell;
                int ci = (int)Math.Floor((px - minX) / cell), cj = (int)Math.Floor((py - minY) / cell);
                var list = ci >= 0 && cj >= 0 && ci < width && cj < height ? floorIndex[Index(ci, cj)] : null;
                double? best = null;
                if (list != null)
                    foreach (int n in list)
                    {
                        var t = tris[n];
                        double d = (t.B.Y - t.C.Y) * (t.A.X - t.C.X) + (t.C.X - t.B.X) * (t.A.Y - t.C.Y);
                        if (Math.Abs(d) < 1e-9) continue;
                        double u = ((t.B.Y - t.C.Y) * (px - t.C.X) + (t.C.X - t.B.X) * (py - t.C.Y)) / d;
                        double v = ((t.C.Y - t.A.Y) * (px - t.C.X) + (t.A.X - t.C.X) * (py - t.C.Y)) / d;
                        if (u < -1e-6 || v < -1e-6 || u + v > 1 + 1e-6) continue;
                        double z = u * t.A.Z + v * t.B.Z + (1 - u - v) * t.C.Z;
                        if (z >= current - MaxStairRelax && z <= current + StepHeight && (best == null || z > best)) best = z;
                    }
                if (best == null) return false;
                current = best.Value;
            }
            return Math.Abs(current - high) <= MaxStairRelax && !WallBetween(i0, j0, i1, j1, high + 28);
        }
        var original = new Dictionary<Span, int>();
        for (int pass = 0; pass < 4; pass++)
        {
            bool changed = false;
            for (int j = 0; j < height; j++)
                for (int i = 0; i < width; i++)
                    foreach (var (di, dj) in new[] { (1, 0), (0, 1) })
                    {
                        int qi = i + di, qj = j + dj;
                        if (qi >= width || qj >= height) continue;
                        foreach (var s in grid[Index(i, j)])
                            foreach (var t in grid[Index(qi, qj)])
                            {
                                bool sLow = s.F < t.F;
                                Span low = sLow ? s : t, high = sLow ? t : s;
                                int rise = high.F - low.F;
                                if (rise <= StepHeight || rise > StepHeight + MaxStairRelax || Math.Min(s.C, t.C) - high.F < ActorHeight) continue;
                                int target = low.F + StepHeight, first = original.TryGetValue(high, out int o) ? o : high.F;
                                var highCell = grid[sLow ? Index(qi, qj) : Index(i, j)];
                                if (first - target > MaxStairRelax || highCell.Any(x => x != high && x.C > target && x.F < high.F)) continue;
                                bool climb = sLow ? Climbable(i, j, qi, qj, low.F, high.F) : Climbable(qi, qj, i, j, low.F, high.F);
                                if (!climb) continue;
                                original[high] = first;
                                high.F = target;
                                changed = true;
                            }
                    }
            if (!changed) break;
        }
        return original.Count;
    }

    // Room meshes stop short at door frames. Bridge gaps of up to 3 cells when no wall lies between the two sides.
    static int CloseGaps()
    {
        BuildWallIndex();
        var additions = new Dictionary<(int cell, int f, int c), Span>();
        var directions = new[] { (1, 0), (0, 1), (1, 1), (1, -1) };
        for (int j = 0; j < height; j++)
            for (int i = 0; i < width; i++)
                foreach (var s in grid[Index(i, j)])
                    foreach (var (di, dj) in directions)
                        for (int gap = 2; gap <= 4; gap++)
                        {
                            int qi = i + di * gap, qj = j + dj * gap;
                            if (qi < 0 || qj < 0 || qi >= width || qj >= height) break;
                            int ti = i + di * (gap - 1), tj = j + dj * (gap - 1);
                            if (grid[Index(ti, tj)].Any(x => Math.Min(x.C, s.C) - Math.Max(x.F, s.F) >= KeepHeight)) break;
                            var t = grid[Index(qi, qj)].FirstOrDefault(x => Math.Min(x.C, s.C) - Math.Max(x.F, s.F) >= KeepHeight && Math.Abs(x.F - s.F) <= StepHeight);
                            if (t == null) continue;
                            int f = Math.Max(s.F, t.F), c = Math.Min(s.C, t.C);
                            if (!WallBetween(i, j, qi, qj, f + 24) && !WallBetween(i, j, qi, qj, f + 48))
                                for (int k = 1; k < gap; k++)
                                {
                                    int m = Index(i + di * k, j + dj * k);
                                    if (grid[m].All(x => x.C <= f || x.F >= c) && !PostBlocks(m, f, c)) additions[(m, f, c)] = new Span { F = f, C = c };
                                }
                            break;
                        }
        foreach (var group in additions.GroupBy(a => a.Key.cell))
        {
            var spans = grid[group.Key];
            foreach (var add in group.OrderBy(a => a.Key.f))
                if (spans.All(x => x.C <= add.Key.f || x.F >= add.Key.c)) spans.Add(add.Value);
            spans.Sort((a, b) => a.F.CompareTo(b.F));
        }
        return additions.Count;
    }

    static void ApplyDoors()
    {
        foreach (var door in doors)
        {
            int i0 = Math.Max(0, (int)Math.Floor((door.MinX - minX) / cell)), i1 = Math.Min(width - 1, (int)Math.Floor((door.MaxX - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((door.MinY - minY) / cell)), j1 = Math.Min(height - 1, (int)Math.Floor((door.MaxY - minY) / cell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    foreach (var span in grid[Index(i, j)])
                        if (Math.Min(span.C, door.MaxZ) - Math.Max(span.F, door.MinZ) > 16 && span.Door < 0)
                            span.Door = door.Id;
        }
    }

    // Diagnostic: prints each cell along a line, and at the first stage the source faces near it.
    static void DumpLine(string stage)
    {
        if (debugLine == null) return;
        var v = debugLine.Split(',').Select(double.Parse).ToArray();
        int steps = (int)(Math.Max(Math.Abs(v[2] - v[0]), Math.Abs(v[3] - v[1])) / cell);
        Console.WriteLine($"LINE stage {stage}");
        for (int k = 0; k <= steps; k++)
        {
            double x = v[0] + (v[2] - v[0]) * k / Math.Max(1, steps), y = v[1] + (v[3] - v[1]) * k / Math.Max(1, steps);
            int i = (int)Math.Floor((x - minX) / cell), j = (int)Math.Floor((y - minY) / cell);
            string raw = stage != "grid" || rawHits[Index(i, j)] == null ? "" : " raw " + string.Join(" ", rawHits[Index(i, j)].OrderBy(h => h.z).Select(h => $"{(h.up ? "U" : "D")}{h.z:F0}"));
            Console.WriteLine($"LINE {minX + (i + 0.5) * cell},{minY + (j + 0.5) * cell}: {string.Join(" ", grid[Index(i, j)].Select(s => $"[{s.F},{s.C}{(s.Door >= 0 ? " door" : "")}]"))}{raw}");
        }
        if (stage != "grid") return;
        double bx0 = Math.Min(v[0], v[2]) - 32, bx1 = Math.Max(v[0], v[2]) + 32, by0 = Math.Min(v[1], v[3]) - 32, by1 = Math.Max(v[1], v[3]) + 32;
        foreach (var t in tris)
        {
            var p = new[] { t.A, t.B, t.C };
            if (p.Max(q => q.X) < bx0 || p.Min(q => q.X) > bx1 || p.Max(q => q.Y) < by0 || p.Min(q => q.Y) > by1 || p.Max(q => q.Z) < v[4] || p.Min(q => q.Z) > v[5]) continue;
            Console.WriteLine($"FACE m{t.Model} n({t.N.X:F2},{t.N.Y:F2},{t.N.Z:F2}) " + string.Join(" ", p.Select(q => $"({q.X:F0},{q.Y:F0},{q.Z:F0})")));
        }
        foreach (var d in doors)
            if (d.MaxX >= bx0 && d.MinX <= bx1 && d.MaxY >= by0 && d.MinY <= by1 && d.MaxZ >= v[4] && d.MinZ <= v[5])
                Console.WriteLine($"DOOR {d.Id} x {d.MinX:F0}..{d.MaxX:F0} y {d.MinY:F0}..{d.MaxY:F0} z {d.MinZ:F0}..{d.MaxZ:F0}");
    }

    // Debug view of the level at a point: '#' solid, '.' same floor, digits are floor/32 above it.
    static void DumpAround(V3 p)
    {
        int ci = (int)((p.X - minX) / cell), cj = (int)((p.Y - minY) / cell), baseZ = Quant(p.Z) - 24;
        for (int j = Math.Min(height - 1, cj + 24); j >= Math.Max(0, cj - 24); j--)
        {
            var row = new StringBuilder("MAP ");
            for (int i = Math.Max(0, ci - 34); i <= Math.Min(width - 1, ci + 34); i++)
            {
                var s = grid[Index(i, j)].FirstOrDefault(x => x.C > baseZ + 16 && x.F < baseZ + 140);
                row.Append(i == ci && j == cj ? '@' : s == null ? '#' : s.Door >= 0 ? 'D' : Math.Abs(s.F - baseZ) <= 28 ? '.' : (char)('0' + Math.Clamp((s.F - baseZ) / 32, 0, 9)));
            }
            Console.WriteLine(row);
        }
    }

    static List<Node> BuildNodes(out List<(int a, int b, bool door)> edges)
    {
        var all = new Dictionary<(int, int), List<Node>>();
        var nodes = new List<Node>();
        for (int j = 1; j < height; j++)
            for (int i = 1; i < width; i++)
            {
                var list = new List<Node>();
                foreach (var seed in grid[Index(i, j)])
                {
                    int f = seed.F, c = seed.C;
                    bool door = seed.Door >= 0, ok = true;
                    foreach (int other in new[] { Index(i - 1, j), Index(i, j - 1), Index(i - 1, j - 1) })
                    {
                        Span best = null;
                        int bestOverlap = 0;
                        foreach (var s in grid[other])
                        {
                            int overlap = Math.Min(c, s.C) - Math.Max(f, s.F);
                            if (overlap > bestOverlap) { bestOverlap = overlap; best = s; }
                        }
                        if (best == null) { ok = false; break; }
                        f = Math.Max(f, best.F); c = Math.Min(c, best.C); door |= best.Door >= 0;
                    }
                    if (!ok || c - f < ActorHeight || list.Any(n => n.F == f)) continue;
                    list.Add(new Node { I = i, J = j, F = f, C = c, Door = door, Block = BlockAt(minX + i * cell, minY + j * cell) });
                }
                if (list.Count == 0) continue;
                all[(i, j)] = list;
                if (i % 2 == 0 && j % 2 == 0)
                    foreach (var n in list) { n.Id = nodes.Count; nodes.Add(n); }
            }
        edges = new List<(int, int, bool)>();
        foreach (var n in nodes)
            foreach (var (di, dj) in new[] { (2, 0), (0, 2) })
            {
                if (!all.TryGetValue((n.I + di, n.J + dj), out var targets) || !all.TryGetValue((n.I + di / 2, n.J + dj / 2), out var mids)) continue;
                foreach (var m in targets.Where(x => x.Id >= 0 && x.I % 2 == 0 && x.J % 2 == 0))
                    foreach (var mid in mids)
                    {
                        if (Math.Min(n.C, mid.C) - Math.Max(n.F, mid.F) < ActorHeight || Math.Min(m.C, mid.C) - Math.Max(m.F, mid.F) < ActorHeight) continue;
                        bool door = n.Door || m.Door || mid.Door;
                        if (mid.F - n.F <= routeStep && m.F - mid.F <= routeStep) edges.Add((n.Id, m.Id, door));
                        if (mid.F - m.F <= routeStep && n.F - mid.F <= routeStep) edges.Add((m.Id, n.Id, door));
                        break;
                    }
            }
        edges = edges.Distinct().ToList();
        return nodes;
    }

    static int BlockAt(int x, int y)
    {
        int side = (int)Math.Round(BlockSide * PlayerScale.DoomUnitsPerDaggerfallUnit);
        for (int b = 0; b < blockRects.Count; b++)
            if (x >= blockRects[b].x && x < blockRects[b].x + side && y >= blockRects[b].y && y < blockRects[b].y + side) return b;
        return -1;
    }

    static int FindStart(List<Node> nodes, V3 entrance)
    {
        int best = -1;
        double bestDistance = double.MaxValue;
        foreach (var n in nodes)
        {
            double dx = minX + n.I * cell - entrance.X, dy = minY + n.J * cell - entrance.Y, dz = n.F + ActorHeight / 2 - entrance.Z;
            double distance = dx * dx + dy * dy + dz * dz * 4;
            if (distance < bestDistance) { bestDistance = distance; best = n.Id; }
        }
        return best;
    }

    static string WritePoints(List<Node> nodes, List<(int a, int b, bool door)> edges, int start)
    {
        var text = new StringBuilder();
        text.Append($"S {start} {minX + nodes[start].I * cell} {minY + nodes[start].J * cell} {nodes[start].F}\n");
        for (int b = 0; b < blockRects.Count; b++) text.Append("B ").Append(b).Append(' ').Append(blockRects[b].name).Append('\n');
        foreach (var n in nodes)
            text.Append($"N {n.Id} {minX + n.I * cell} {minY + n.J * cell} {n.F} {n.C} {n.Block} {(n.Door ? 1 : 0)}\n");
        foreach (var e in edges) text.Append($"E {e.a} {e.b} {(e.door ? 1 : 0)}\n");
        return text.ToString();
    }

    static string Signature(List<Span> spans) => string.Join("|", spans.Select(s => $"{(s.FP >= 0 ? "p" + s.FP : s.F.ToString())}:{(s.CP >= 0 ? "p" + s.CP : s.C.ToString())}:{s.Door}{(s.Water != NoWater ? ":w" + s.Water : "")}"));

    static (int sectors, int lines, int controls, int doorsUsed) WriteMap(string path, Node start, string points)
    {
        // Connected regions with the same vertical layout become one sector.
        var component = new int[width * height];
        Array.Fill(component, -1);
        var sectorSpans = new List<List<Span>>();
        var stack = new Stack<int>();
        for (int c = 0; c < component.Length; c++)
        {
            if (grid[c].Count == 0 || component[c] >= 0) continue;
            int id = sectorSpans.Count;
            string signature = Signature(grid[c]);
            sectorSpans.Add(grid[c]);
            component[c] = id;
            stack.Push(c);
            while (stack.Count > 0)
            {
                int p = stack.Pop(), i = p % width, j = p / width;
                foreach (var (ni, nj) in new[] { (i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1) })
                {
                    if (ni < 0 || nj < 0 || ni >= width || nj >= height) continue;
                    int q = Index(ni, nj);
                    if (component[q] < 0 && grid[q].Count > 0 && Signature(grid[q]) == signature) { component[q] = id; stack.Push(q); }
                }
            }
        }

        var vertices = new Dictionary<(long, long), int>(); // eighths of a map unit
        int Vertex(double x, double y)
        {
            var key = ((long)Math.Round(x * 8), (long)Math.Round(y * 8));
            if (!vertices.TryGetValue(key, out int v)) vertices[key] = v = vertices.Count;
            return v;
        }
        var map = new StringBuilder("namespace = \"zdoom\";\n");
        var lineText = new StringBuilder();
        var sideText = new StringBuilder();
        var sectorText = new StringBuilder();
        int sides = 0, lines = 0, sectors = sectorSpans.Count;

        int nextTag = 1;
        var tagBySignature = new Dictionary<string, int>();
        var sectorTag = new int[sectorSpans.Count];
        for (int s = 0; s < sectorSpans.Count; s++)
        {
            var spans = sectorSpans[s];
            bool needsTag = spans.Count > 1 || spans.Any(x => x.Door >= 0 || x.Water != NoWater);
            if (needsTag)
            {
                string signature = Signature(spans);
                if (!tagBySignature.TryGetValue(signature, out int tag)) tagBySignature[signature] = tag = nextTag++;
                sectorTag[s] = tag;
            }
            sectorText.Append($"sector {{ heightfloor = {spans[0].F}; heightceiling = {spans[^1].C}; texturefloor = \"FLOOR0_1\"; textureceiling = \"CEIL3_5\"; lightlevel = 176;{(sectorTag[s] > 0 ? $" id = {sectorTag[s]};" : "")}{PlaneText(spans[0].FP, false)}{PlaneText(spans[^1].CP, true)} }}\n");
        }

        int doorControlBase = nextTag + 1000;
        foreach (var d in doors) d.Control = doorControlBase + d.Id;
        int Side(int sector, bool twoSided, string middle = "STONE2")
        {
            sideText.Append(twoSided
                ? $"sidedef {{ sector = {sector}; texturetop = \"STONE2\"; texturebottom = \"STONE2\"; }}\n"
                : $"sidedef {{ sector = {sector}; texturemiddle = \"{middle}\"; }}\n");
            return sides++;
        }
        void Line(double x0, double y0, double x1, double y1, int front, int back)
        {
            // Sector "front" is on the right when walking from v1 to v2.
            if (front < 0) { (x0, y0, x1, y1) = (x1, y1, x0, y0); (front, back) = (back, front); }
            int v1 = Vertex(x0, y0), v2 = Vertex(x1, y1), sf = Side(front, back >= 0);
            string extra = back >= 0 ? $" sideback = {Side(back, true)}; twosided = true;" : " blocking = true;";
            lineText.Append($"linedef {{ v1 = {v1}; v2 = {v2}; sidefront = {sf};{extra} }}\n");
            lines++;
        }
        var runs = new List<(int x0, int y0, int x1, int y1, int front, int back)>();

        // Vertical boundaries, merged along their length.
        for (int i = 1; i < width; i++)
        {
            int runStart = -1, runLeft = -1, runRight = -1;
            for (int j = 0; j <= height; j++)
            {
                int left = j < height ? component[Index(i - 1, j)] : -1, right = j < height ? component[Index(i, j)] : -1;
                bool edge = left != right;
                if (runStart >= 0 && (!edge || left != runLeft || right != runRight))
                {
                    runs.Add((minX + i * cell, minY + runStart * cell, minX + i * cell, minY + j * cell, runRight, runLeft));
                    runStart = -1;
                }
                if (edge && runStart < 0) { runStart = j; runLeft = left; runRight = right; }
            }
        }
        // Horizontal boundaries.
        for (int j = 1; j < height; j++)
        {
            int runStart = -1, runBelow = -1, runAbove = -1;
            for (int i = 0; i <= width; i++)
            {
                int below = i < width ? component[Index(i, j - 1)] : -1, above = i < width ? component[Index(i, j)] : -1;
                bool edge = below != above;
                if (runStart >= 0 && (!edge || below != runBelow || above != runAbove))
                {
                    runs.Add((minX + i * cell, minY + j * cell, minX + runStart * cell, minY + j * cell, runAbove, runBelow));
                    runStart = -1;
                }
                if (edge && runStart < 0) { runStart = i; runBelow = below; runAbove = above; }
            }
        }

        var emitted = new List<(double x0, double y0, double x1, double y1, List<(double lo, double hi)> heights)>();
        if (gridCollision)
        {
            foreach (var r in runs)
            {
                Line(r.x0, r.y0, r.x1, r.y1, r.front, r.back);
                emitted.Add((r.x0, r.y0, r.x1, r.y1, DifferingHeights(r.front >= 0 ? sectorSpans[r.front] : null, r.back >= 0 ? sectorSpans[r.back] : null)));
            }
        }
        else
        {
            var cellCounts = new int[sectorSpans.Count];
            foreach (int c in component) if (c >= 0) cellCounts[c]++;
            foreach (var chain in RefitBoundaries(runs, sectorSpans, cellCounts))
                for (int n = 0; n + 1 < chain.Fitted.Count; n++)
                {
                    var (_, ax, ay) = chain.Fitted[n];
                    var (_, bx, by) = chain.Fitted[n + 1];
                    Line(ax, ay, bx, by, chain.Front, chain.Back);
                    emitted.Add((ax, ay, bx, by, chain.Heights));
                }
        }
        MeasureFit(emitted);

        // Control sectors for solid slabs between stacked rooms, and for closed doors.
        int controls = 0, controlX = minX, controlY = minY - 64;
        void Control(int floor, int ceiling, int targetTag, int id, int type = 1, int alpha = 255, int floorPlane = -1, int ceilingPlane = -1,
            int flags = 0, string middle = "STONE2", string floorTexture = "FLOOR0_1", string ceilingTexture = "CEIL3_5")
        {
            int s = sectors++;
            sectorText.Append($"sector {{ heightfloor = {floor}; heightceiling = {ceiling}; texturefloor = \"{floorTexture}\"; textureceiling = \"{ceilingTexture}\"; lightlevel = 176;{(id > 0 ? $" id = {id};" : "")}{PlaneText(floorPlane, false)}{PlaneText(ceilingPlane, true)} }}\n");
            int x = controlX, y = controlY, size = 8;
            int[] v = { Vertex(x, y), Vertex(x, y + size), Vertex(x + size, y + size), Vertex(x + size, y) };
            for (int e = 0; e < 4; e++)
            {
                int side = Side(s, false, middle);
                string special = e == 0 ? $" special = 160; arg0 = {targetTag}; arg1 = {type}; arg2 = {flags}; arg3 = {alpha};" : "";
                lineText.Append($"linedef {{ v1 = {v[e]}; v2 = {v[(e + 1) % 4]}; sidefront = {side}; blocking = true;{special} }}\n");
                lines++;
            }
            controls++;
            controlX += 16;
            if (controlX > minX + width * cell) { controlX = minX; controlY -= 16; }
        }
        var usedDoors = new HashSet<int>();
        foreach (var (signature, tag) in tagBySignature)
        {
            var spans = sectorSpans[Array.IndexOf(sectorTag, tag)];
            for (int s = 0; s + 1 < spans.Count; s++) Control(spans[s].C, spans[s + 1].F, tag, 0, floorPlane: spans[s].CP, ceilingPlane: spans[s + 1].FP);
            foreach (var span in spans.Where(x => x.Door >= 0))
            {
                var door = doors[span.Door];
                int top = Math.Min(span.C, Quant(door.MaxZ));
                door.Height = top - span.F;
                // Each door may cover several layouts. Only the first control sector keeps the door id,
                // so give the others the same id through a shared tag value.
                // Type 3 (non-solid, shoot-through) + 16 (not see-through): blocks sight only. Collision is the door object.
                Control(span.F, top, tag, door.Control, 19, 0);
                usedDoors.Add(door.Id);
            }
            // One swimmable volume per flooded span, so the rooms stacked around it stay as they are.
            foreach (var span in spans.Where(x => x.Water != NoWater))
            {
                bool toCeiling = span.Water == WaterToCeiling;
                Control(span.F, toCeiling ? span.C : span.Water, tag, 0, WaterFloorType, WaterAlpha, span.FP, toCeiling ? span.CP : -1,
                    WaterFloorFlags, "-", "-", toCeiling ? "-" : WaterTexture);
            }
        }

        foreach (var pair in vertices.OrderBy(p => p.Value))
            map.Append($"vertex {{ x = {(pair.Key.Item1 / 8.0).ToString("0.0##", CultureInfo.InvariantCulture)}; y = {(pair.Key.Item2 / 8.0).ToString("0.0##", CultureInfo.InvariantCulture)}; }}\n");
        map.Append(lineText).Append(sideText).Append(sectorText);
        map.Append($"thing {{ x = {minX + start.I * cell}.0; y = {minX * 0 + minY + start.J * cell}.0; height = {start.F - BaseFloor(start)}.0; angle = 0; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }}\n");

        AppendEnemies(map);
        var doorList = new StringBuilder();
        foreach (var id in usedDoors) doorList.Append($"D {doors[id].Control} {doors[id].Height} {doors[id].Block}\n");
        foreach (var d in doors) doorList.Append($"DC {d.Id} {d.Control}\n"); // door order matches DFDOORS
        WriteWad(path, map.ToString(), points + doorList, OutputMapName);
        return (sectorSpans.Count, lines, controls, usedDoors.Count);
    }

    // One enemy per Daggerfall placement (editor flat 199:15 random, 199:16 fixed). The type comes from EnemyRoster.Pick,
    // a hash of the placement's static data, so a placement always yields the same Doom class.
    static void AppendEnemies(StringBuilder map)
    {
        int placed = 0;
        var counts = new SortedDictionary<int, int>();
        foreach (var e in enemyPlacements)
        {
            int i = (int)Math.Floor((e.X - minX) / cell), j = (int)Math.Floor((e.Y - minY) / cell);
            var spans = i >= 0 && j >= 0 && i < width && j < height ? grid[Index(i, j)] : null;
            if (spans == null || spans.Count == 0) { enemiesSkipped++; continue; }
            // The span whose floor is the highest one still at or below the marker (plus a step), with room to stand.
            Span span = spans.Where(s => s.F <= e.Z + StepHeight && s.C - s.F >= ActorHeight).OrderByDescending(s => s.F).FirstOrDefault();
            if (span == null) { enemiesSkipped++; continue; }
            map.Append(FormattableString.Invariant($"thing {{ x = {minX + (i + 0.5) * cell:F1}; y = {minY + (j + 0.5) * cell:F1}; height = {span.F - spans[0].F}.0; angle = {(e.Type * 45) % 360}; type = {e.Type}; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; coop = true; dm = true; }}\n"));
            monsterIds.Append(FormattableString.Invariant($"{currentMapId} {e.Id:x16} {minX + (i + 0.5) * cell:F1} {minY + (j + 0.5) * cell:F1} {span.F}\n"));
            placed++;
            counts[e.Type] = counts.GetValueOrDefault(e.Type) + 1;
        }
        Console.WriteLine($"enemies: {placed} placed, {enemiesSkipped} skipped (no floor under the marker), of {enemyPlacements.Count} placements; types {string.Join(" ", counts.Select(c => c.Key + "x" + c.Value))}");
    }

    static int BaseFloor(Node n)
    {
        var spans = grid[Index(n.I, n.J)];
        return spans.Count > 0 ? spans[0].F : n.F;
    }

    static void WriteWad(string path, string textmap, string points, string mapName = "MAP01")
    {
        var lumps = new (string name, byte[] data)[]
        {
            (mapName, Array.Empty<byte>()), ("TEXTMAP", Encoding.ASCII.GetBytes(textmap)), ("ENDMAP", Array.Empty<byte>()),
            ("DFPOINTS", Encoding.ASCII.GetBytes(points)), ("DDMONST", Encoding.ASCII.GetBytes(monsterIds.ToString())),
        };
        using var file = new BinaryWriter(File.Create(path));
        file.Write(Encoding.ASCII.GetBytes("PWAD"));
        file.Write(lumps.Length);
        file.Write(12 + lumps.Sum(l => l.data.Length));
        foreach (var lump in lumps) file.Write(lump.data);
        int offset = 12;
        foreach (var lump in lumps)
        {
            file.Write(offset);
            file.Write(lump.data.Length);
            file.Write(Encoding.ASCII.GetBytes(lump.name.PadRight(8, '\0')));
            offset += lump.data.Length;
        }
    }

    // Checks test nodes against the raw triangles, at points that are not the grid's own ray positions.
    static (int floorMiss, int ceilingMiss) VerifyAgainstSource(List<Node> nodes)
    {
        var index = new List<int>[width * height];
        for (int t = 0; t < tris.Count; t++)
        {
            var x = tris[t];
            if (Math.Abs(x.N.Z) < WallNormalZ) continue;
            int i0 = Math.Max(0, (int)Math.Floor((Math.Min(x.A.X, Math.Min(x.B.X, x.C.X)) - minX) / cell));
            int i1 = Math.Min(width - 1, (int)Math.Floor((Math.Max(x.A.X, Math.Max(x.B.X, x.C.X)) - minX) / cell));
            int j0 = Math.Max(0, (int)Math.Floor((Math.Min(x.A.Y, Math.Min(x.B.Y, x.C.Y)) - minY) / cell));
            int j1 = Math.Min(height - 1, (int)Math.Floor((Math.Max(x.A.Y, Math.Max(x.B.Y, x.C.Y)) - minY) / cell));
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++)
                    (index[Index(i, j)] ??= new List<int>()).Add(t);
        }
        bool Near(double px, double py, int z, bool up)
        {
            int i = (int)Math.Floor((px - minX) / cell), j = (int)Math.Floor((py - minY) / cell);
            if (i < 0 || j < 0 || i >= width || j >= height || index[Index(i, j)] == null) return false;
            foreach (int k in index[Index(i, j)])
            {
                var t = tris[k];
                if (t.N.Z > 0 != up) continue;
                double d = (t.B.Y - t.C.Y) * (t.A.X - t.C.X) + (t.C.X - t.B.X) * (t.A.Y - t.C.Y);
                if (Math.Abs(d) < 1e-9) continue;
                double u = ((t.B.Y - t.C.Y) * (px - t.C.X) + (t.C.X - t.B.X) * (py - t.C.Y)) / d;
                double v = ((t.C.Y - t.A.Y) * (px - t.C.X) + (t.A.X - t.C.X) * (py - t.C.Y)) / d;
                if (u < 0 || v < 0 || u + v > 1) continue;
                if (Math.Abs(u * t.A.Z + v * t.B.Z + (1 - u - v) * t.C.Z - z) <= ZQuant + 2) return true;
            }
            return false;
        }
        int floorMiss = 0, ceilingMiss = 0;
        var offsets = new[] { (3.0, 3.0), (-3.0, 3.0), (3.0, -3.0), (-3.0, -3.0), (13.0, 13.0), (-13.0, 13.0), (13.0, -13.0), (-13.0, -13.0) };
        foreach (var n in nodes)
        {
            double x = minX + n.I * cell, y = minY + n.J * cell;
            if (!offsets.Any(o => Near(x + o.Item1, y + o.Item2, n.F, true))) floorMiss++;
            if (!offsets.Any(o => Near(x + o.Item1, y + o.Item2, n.C, false))) ceilingMiss++;
        }
        return (floorMiss, ceilingMiss);
    }

    // Independent leak check: walks each test link at waist and head height against the raw faces and door boxes.
    static (int wall, int door) AuditEdges(List<Node> nodes, List<(int a, int b, bool door)> edges, string leakPath = null)
    {
        int wallLeaks = 0, doorLeaks = 0;
        var leakText = new StringBuilder();
        var checkedPairs = new HashSet<(int, int)>();
        foreach (var e in edges)
        {
            if (!checkedPairs.Add((Math.Min(e.a, e.b), Math.Max(e.a, e.b)))) continue;
            Node n = nodes[e.a], m = nodes[e.b];
            double px = minX + n.I * cell, py = minY + n.J * cell, qx = minX + m.I * cell, qy = minY + m.J * cell;
            int floor = Math.Max(n.F, m.F), top = Math.Min(n.C, m.C);
            var heights = new[] { floor + 28.0, Math.Min(floor + 50.0, top - 2.0) };
            bool hit = false;
            for (int j = Math.Max(0, Math.Min(n.J, m.J) - 1); j <= Math.Min(height - 1, Math.Max(n.J, m.J)) && !hit; j++)
                for (int i = Math.Max(0, Math.Min(n.I, m.I) - 1); i <= Math.Min(width - 1, Math.Max(n.I, m.I)) && !hit; i++)
                {
                    var list = wallIndex[Index(i, j)];
                    if (list == null) continue;
                    foreach (int t in list)
                        if (heights.Any(z => SegmentHits(new V3(px, py, z), new V3(qx, qy, z), tris[t]))) { hit = true; break; }
                }
            if (hit) { wallLeaks++; leakText.Append($"W {e.a} {e.b} {px} {py} {qx} {qy} {floor}\n"); }
            if (!e.door && doors.Any(d => Math.Max(px, qx) >= d.MinX && Math.Min(px, qx) <= d.MaxX && Math.Max(py, qy) >= d.MinY && Math.Min(py, qy) <= d.MaxY
                && heights.Any(z => z >= d.MinZ && z <= d.MaxZ))) { doorLeaks++; leakText.Append($"D {e.a} {e.b} {px} {py} {qx} {qy} {floor}\n"); }
        }
        if (leakPath != null) File.WriteAllText(leakPath, leakText.ToString());
        return (wallLeaks, doorLeaks);
    }

    // Diagnostic: runs the leak audit on a points file from another converter version.
    static void AuditPointsFile(string pointsPath, string leakPath)
    {
        var nodes = new List<Node>();
        var edges = new List<(int a, int b, bool door)>();
        foreach (var line in File.ReadLines(pointsPath))
        {
            var f = line.Split(' ');
            if (f[0] == "N")
                nodes.Add(new Node { Id = int.Parse(f[1]), I = (int.Parse(f[2]) - minX) / cell, J = (int.Parse(f[3]) - minY) / cell, F = int.Parse(f[4]), C = int.Parse(f[5]), Door = f[7] == "1" });
            else if (f[0] == "E")
                edges.Add((int.Parse(f[1]), int.Parse(f[2]), f[3] == "1"));
        }
        var result = AuditEdges(nodes, edges, leakPath);
        Console.WriteLine($"AUDIT {pointsPath}: {edges.Count} directed links, wall crossings {result.wall}, untagged door crossings {result.door}");
    }

    static void WriteStats(string path, string name, DFLocation location, List<Node> nodes, List<(int a, int b, bool door)> edges, int start, int walled,
        (int sectors, int lines, int controls, int doorsUsed) map)
    {
        int open = grid.Count(g => g.Count > 0), stacked = grid.Count(g => g.Count > 1), maxStack = grid.Max(g => g.Count);
        var adjacency = edges.ToLookup(e => e.a, e => e.b);
        var seen = new HashSet<int> { start };
        var queue = new Queue<int>(seen);
        while (queue.Count > 0)
            foreach (int next in adjacency[queue.Dequeue()])
                if (seen.Add(next)) queue.Enqueue(next);
        var text = new StringBuilder();
        text.AppendLine($"dungeon: {location.RegionName}/{location.Name}");
        text.AppendLine($"blocks: {location.Dungeon.Blocks.Length}");
        text.AppendLine($"triangles: {tris.Count}; non-door action models removed by --open-actions: {skippedActions}");
        text.AppendLine($"grid: {width}x{height} cells of {cell} units");
        text.AppendLine($"open cells: {open}");
        text.AppendLine($"vertically stacked cells: {stacked} ({100.0 * stacked / Math.Max(1, open):F1}%), max layers {maxStack}");
        text.AppendLine($"spans removed by walls: {walled}, gap spans added: {gapCells}, stair floors adjusted: {relaxedStairs}, solid posts: {postCount}");
        text.AppendLine($"door models: {doors.Count}, with a sight blocker in map: {map.doorsUsed}");
        text.AppendLine($"sectors: {map.sectors}, control sectors: {map.controls}, lines: {map.lines}");
        text.AppendLine($"test nodes: {nodes.Count}, directed edges: {edges.Count}");
        text.AppendLine($"nodes reachable from entrance in source model: {seen.Count} ({100.0 * seen.Count / Math.Max(1, nodes.Count):F1}%)");
        // Undirected components show whether the map splits into separate areas.
        var undirected = edges.SelectMany(e => new[] { (e.a, e.b), (e.b, e.a) }).ToLookup(e => e.Item1, e => e.Item2);
        var visited = new HashSet<int>();
        var parts = new List<(int size, int zMin, int zMax, int x, int y, bool hasStart)>();
        foreach (var n in nodes)
        {
            if (!visited.Add(n.Id)) continue;
            var part = new List<int> { n.Id };
            for (int q = 0; q < part.Count; q++)
                foreach (int next in undirected[part[q]])
                    if (visited.Add(next)) part.Add(next);
            parts.Add((part.Count, part.Min(p => nodes[p].F), part.Max(p => nodes[p].F), minX + n.I * cell, minY + n.J * cell, part.Contains(start)));
        }
        var source = VerifyAgainstSource(nodes);
        text.AppendLine($"nodes with no raw source floor near their height: {source.floorMiss} ({100.0 * source.floorMiss / nodes.Count:F2}%); no raw ceiling: {source.ceilingMiss} ({100.0 * source.ceilingMiss / nodes.Count:F2}%)");
        var audit = AuditEdges(nodes, edges, Path.ChangeExtension(path, null).Replace(".stats", "") + ".leaks.txt");
        text.AppendLine($"walkable links crossing a raw wall at body height: {audit.wall}; crossing a door box without a door tag: {audit.door}");
        text.AppendLine($"entrance marker: {entranceMarker.X:F0},{entranceMarker.Y:F0},{entranceMarker.Z:F0}; start node floor {nodes[start].F}");
        text.AppendLine($"connected areas: {parts.Count}; largest:");
        foreach (var p in parts.OrderByDescending(p => p.size).Take(8))
            text.AppendLine($"  {p.size} nodes, floors {p.zMin}..{p.zMax}, near {p.x},{p.y}{(p.hasStart ? " (entrance)" : "")}");
        // A door touching two separate areas is a connection the converter failed to make.
        var areaOf = new Dictionary<int, int>();
        foreach (var n in nodes)
        {
            if (areaOf.ContainsKey(n.Id)) continue;
            var part = new List<int> { n.Id };
            areaOf[n.Id] = n.Id;
            for (int q = 0; q < part.Count; q++)
                foreach (int next in undirected[part[q]])
                    if (areaOf.TryAdd(next, n.Id)) part.Add(next);
        }
        var areaSize = areaOf.Values.GroupBy(v => v).ToDictionary(g => g.Key, g => g.Count());
        int splitDoors = 0, doorsNoNodes = 0;
        var splitText = new StringBuilder();
        foreach (var d in doors)
        {
            var touching = nodes.Where(n => minX + n.I * cell >= d.MinX - 56 && minX + n.I * cell <= d.MaxX + 56 && minY + n.J * cell >= d.MinY - 56 && minY + n.J * cell <= d.MaxY + 56
                && n.F >= d.MinZ - 32 && n.F <= d.MinZ + 32).Select(n => areaOf[n.Id]).Distinct().ToList();
            if (touching.Count == 0) doorsNoNodes++;
            if (touching.Count < 2) continue;
            splitDoors++;
            if (splitDoors <= 8)
                splitText.AppendLine($"  door {d.Id} block {blockRects[d.Block].name} at {(d.MinX + d.MaxX) / 2:F0},{(d.MinY + d.MaxY) / 2:F0},z{d.MinZ:F0} joins areas of {string.Join("/", touching.Select(t => areaSize[t]))} nodes");
        }
        text.AppendLine($"doors touching two separate areas: {splitDoors} of {doors.Count}; doors with no walkable node beside them: {doorsNoNodes}");
        text.Append(splitText);
        // For each cut-off area, the closest point to the entrance's area shows what separates them.
        var main = seen.Select(id => nodes[id]).ToLookup(n => (n.I / 8, n.J / 8));
        text.AppendLine("closest approach of cut-off nodes to the reachable area (same level):");
        var gaps = new List<(int d, Node a, Node b)>();
        var counted = new HashSet<int>(seen);
        foreach (var n in nodes)
        {
            if (!counted.Add(n.Id)) continue;
            var part = new List<int> { n.Id };
            for (int q = 0; q < part.Count; q++)
                foreach (int next in undirected[part[q]])
                    if (counted.Add(next)) part.Add(next);
            (int d, Node a, Node b) best = (int.MaxValue, null, null);
            foreach (var id in part)
            {
                var a = nodes[id];
                for (int di = -2; di <= 2; di++)
                    for (int dj = -2; dj <= 2; dj++)
                        foreach (var b in main[(a.I / 8 + di, a.J / 8 + dj)])
                        {
                            if (Math.Abs(a.F - b.F) > 32) continue;
                            int d = Math.Abs(a.I - b.I) + Math.Abs(a.J - b.J);
                            if (d < best.d) best = (d, a, b);
                        }
            }
            if (part.Count >= 100) gaps.Add(best.a != null ? best : (-part.Count, nodes[part[0]], nodes[part[0]]));
        }
        foreach (var g in gaps.OrderBy(g => g.d).Take(14))
            text.AppendLine($"  {(g.d < 0 ? $"no same-level neighbor, {-g.d} nodes" : $"{g.d * cell} units")}: {minX + g.a.I * cell},{minY + g.a.J * cell},z{g.a.F} to {minX + g.b.I * cell},{minY + g.b.J * cell},z{g.b.F}");
        File.WriteAllText(path, text.ToString());
    }
}
