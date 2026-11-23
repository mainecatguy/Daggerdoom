// Building interiors converted during play, and the door data that links them to towns.
//
// A space id is SpaceBase + group * SpacePerGroup + building, where building counts every RMB subrecord of the
// group in site, block, record order. The map name is DDS plus the id's offset in five base-36 digits.
// Placement follows PlayerEnterExit.TransitionInterior: closest enter marker to the exterior door, then the closest
// interior door to that marker, then a step along the door's normal.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    static string OutputMapName = "MAP01";

    public struct DoorPlane { public int Type; public V3 Centre, Normal; public double HalfHeight; }

    static partial class City
    {
        public const int SpaceBase = 1000000, SpacePerGroup = 1024, MaxBuildings = 1000;
        public const int DoorBuilding = 1, DoorEntrance = 2, DoorExit = 3;
        const int EnterMarker = 8, RestMarker = 4, PropModel = 3;
        const double LandingDf = 14 + 16; // Daggerfall Unity's player radius plus its 0.4 m landing gap

        public static string SpaceMapName(int id)
        {
            const string digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
            int v = id - SpaceBase;
            var c = new char[5];
            for (int i = 4; i >= 0; i--) { c[i] = digits[v % 36]; v /= 36; }
            return "DDS" + new string(c);
        }

        // MeshReader.GetModelData's door rules, in Unity axes at Daggerfall scale.
        public static IEnumerable<DoorPlane> DoorPlanes(DFMesh mesh)
        {
            foreach (var sub in mesh.SubMeshes)
            {
                int archive = sub.TextureArchive;
                if (archive > 100 && archive != 331 && archive != 156) archive %= 100;
                int type = archive == 74 ? DoorBuilding : archive == 56 ? DoorEntrance : archive == 331 && sub.TextureRecord > 0 ? DoorEntrance : archive == 95 ? DoorExit : 0;
                if (type == 0) continue;
                foreach (var plane in sub.Planes)
                {
                    V3 P(int i) => new V3(plane.Points[i].X, -plane.Points[i].Y, plane.Points[i].Z);
                    V3 a = P(0), b = P(1), c = P(2);
                    double ux = a.X - c.X, uy = a.Y - c.Y, uz = a.Z - c.Z, vx = a.X - b.X, vy = a.Y - b.Y, vz = a.Z - b.Z;
                    double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, length = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                    if (length < 1e-6) continue;
                    yield return new DoorPlane { Type = type, Centre = new V3((a.X + c.X) / 2, (a.Y + c.Y) / 2, (a.Z + c.Z) / 2), Normal = new V3(nx / length, ny / length, nz / length), HalfHeight = Math.Abs(a.Y - c.Y) / 2 };
                }
            }
        }

        static V3 Scaled(V3 p, V3 s) => new V3(p.X * s.X, p.Y * s.Y, p.Z * s.Z);
        static double Distance(V3 a, V3 b) => Math.Sqrt((a.X - b.X) * (a.X - b.X) + (a.Y - b.Y) * (a.Y - b.Y) + (a.Z - b.Z) * (a.Z - b.Z));

        public static int RunInterior(int id, string ddtPath, string outDir, string arena2)
        {
            var clock = System.Diagnostics.Stopwatch.StartNew();
            int groupId = (id - SpaceBase) / SpacePerGroup, wanted = (id - SpaceBase) % SpacePerGroup;
            PlayerScale.DoomUnitsPerDaggerfallUnit = 0.75;
            double s = S;
            var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
            var blocksFile = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
            var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
            WorldTerrain.Load(arena2, maps, blocksFile);
            var groups = WorldTerrain.Groups();
            if (groupId >= groups.Count) { Console.Error.WriteLine("no such group: " + groupId); return 1; }

            DFLocation location = default;
            DFBlock.RmbSubRecord record = default;
            string blockName = null;
            int recordIndex = -1, ordinal = 0;
            foreach (var place in groups[groupId])
            {
                var loc = maps.GetLocation(place.RegionIndex, place.LocationIndex);
                for (int y = 0; y < place.BlocksHigh && blockName == null; y++)
                    for (int x = 0; x < place.BlocksWide && blockName == null; x++)
                    {
                        string name = maps.GetRmbBlockName(loc, x, y);
                        var subs = blocksFile.GetBlock(name).RmbBlock.SubRecords;
                        for (int r = 0; r < subs.Length; r++, ordinal++)
                            if (ordinal == wanted) { location = loc; record = subs[r]; blockName = name; recordIndex = r; break; }
                    }
                if (blockName != null) break;
            }
            if (blockName == null) { Console.Error.WriteLine($"group {groupId} has no building {wanted}"); return 1; }

            const double toRad = Math.PI / 180;
            double div = BlocksFile.RotationDivisor;
            var scene = new Scene(arena2, location, 0, 0);
            var interiorDoors = new List<(V3 at, V3 normal, double half)>();
            V3 ScaleOf(DFBlock.RmbBlock3dObjectRecord o) => new V3(o.XScale == 0 ? 1 : o.XScale, o.YScale == 0 ? 1 : o.YScale, o.ZScale == 0 ? 1 : o.ZScale);
            foreach (var o in record.Interior.Block3dObjectRecords)
            {
                // DaggerfallInterior.IsBadInteriorModel: this model traps the player upstairs.
                if (o.ModelIdNum == 31000 && recordIndex == 1 && blockName.Equals("ARMRGL01.RMB", StringComparison.OrdinalIgnoreCase)) continue;
                int modelRecord = arch.GetRecordIndex(o.ModelIdNum);
                if (modelRecord < 0) continue;
                var mesh = arch.GetMesh(modelRecord);
                V3 position = new V3(o.XPos, -o.YPos, o.ZPos);
                if (o.ObjectType == PropModel) // props are placed by their lowest point
                {
                    double bottom = mesh.SubMeshes.SelectMany(q => q.Planes).SelectMany(q => q.Points).Min(q => (double)-q.Y);
                    position = new V3(o.XPos, o.YPos - bottom, o.ZPos);
                }
                double rx = -o.XRotation / div * toRad, ry = -o.YRotation / div * toRad, rz = -o.ZRotation / div * toRad;
                var scale = ScaleOf(o);
                scene.AddModel(arch, o.ModelIdNum, position, rx, ry, rz, scale, new V3(0, 0, 0), 0);
                foreach (var door in DoorPlanes(mesh))
                    interiorDoors.Add((Rotate(Scaled(door.Centre, scale), rx, ry, rz) + position, Rotate(door.Normal, rx, ry, rz), door.HalfHeight * Math.Abs(scale.Y)));
            }
            var markers = new List<V3>();
            foreach (var f in record.Interior.BlockFlatObjectRecords)
            {
                if (f.TextureArchive == 199)
                {
                    if (f.TextureRecord == EnterMarker || f.TextureRecord == RestMarker) markers.Add(new V3(f.XPos, -f.YPos, f.ZPos));
                    continue;
                }
                if (f.FactionID == 0) scene.AddFlat(f.TextureArchive, f.TextureRecord, f.XPos, -f.YPos, f.ZPos, true);
            }
            if (scene.Colliders.Count == 0 || (interiorDoors.Count == 0 && markers.Count == 0)) { Console.Error.WriteLine("building has no usable interior"); return 1; }

            // One landing for each exterior door of this building, in the exterior door order the town uses.
            var info = new StringBuilder("space\n");
            int entryIndex = 0;
            V3? firstLanding = null;
            foreach (var o in record.Exterior.Block3dObjectRecords)
            {
                int modelRecord = arch.GetRecordIndex(o.ModelIdNum);
                if (modelRecord < 0) continue;
                foreach (var door in DoorPlanes(arch.GetMesh(modelRecord)))
                {
                    if (door.Type != DoorBuilding) continue;
                    V3 check = door.Centre;
                    if (markers.Count > 0) { var from = check; check = markers.OrderBy(m => Distance(m, from)).First(); }
                    V3 land;
                    double yaw = 0;
                    if (interiorDoors.Count > 0)
                    {
                        var from = check;
                        var near = interiorDoors.OrderBy(d => Distance(d.at, from)).First();
                        land = new V3(near.at.X + near.normal.X * LandingDf, near.at.Y - near.half, near.at.Z + near.normal.Z * LandingDf);
                        yaw = Math.Atan2(near.normal.Z, near.normal.X) * 180 / Math.PI;
                    }
                    else land = check;
                    info.Append(FormattableString.Invariant($"entry {entryIndex++} {land.X * s:F3} {land.Z * s:F3} {land.Y * s + 2:F3} {yaw:F3}\n"));
                    firstLanding ??= land;
                }
            }
            if (firstLanding == null) { Console.Error.WriteLine("building has no exterior door"); return 1; }
            foreach (var d in interiorDoors)
                info.Append(FormattableString.Invariant($"exit {d.at.X * s:F3} {d.at.Z * s:F3} {(d.at.Y - d.half) * s:F3} {d.normal.X:F4} {d.normal.Z:F4}\n"));

            // The dungeon collision pipeline handles stairs, balconies, and low ceilings.
            for (int i = 0; i < scene.Colliders.Count; i++)
            {
                var c = scene.Colliders[i];
                tris.Add(new Tri { A = c.a, B = c.b, C = c.c, N = scene.ColliderNormals[i], Model = scene.ColliderModels[i].id, Instance = scene.ColliderModels[i].instance });
            }
            ApplyWorldScale(false);
            Directory.CreateDirectory(outDir);
            OutputMapName = SpaceMapName(id);
            var start = firstLanding.Value;
            entranceMarker = new V3(start.X * s, start.Z * s, start.Y * s + 2);
            BuildGrid();
            ApplyWalls();
            ApplyPosts();
            RelaxStairs();
            CloseGaps();
            RelieveCeilings();
            ApplyDoors();
            AssignPlanes();
            var nodes = BuildNodes(out var edges);
            int startNode = FindStart(nodes, entranceMarker);
            string wad = Path.Combine(outDir, "interior.wad");
            var stats = WriteMap(wad, nodes[startNode], WritePoints(nodes, edges, startNode));
            scene.WriteRuntimeEntry(ddtPath, wad, info.ToString(), OutputMapName);
            File.Delete(wad);
            Console.WriteLine($"interior {OutputMapName} {location.Name} {blockName}:{recordIndex} models {scene.Models} triangles {scene.Triangles} sectors {stats.sectors} doors {interiorDoors.Count} entries {entryIndex} {clock.ElapsedMilliseconds} ms");
            return 0;
        }
    }
}
