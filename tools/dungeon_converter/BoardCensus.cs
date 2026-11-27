// Diagnostic: which location groups hold Daggerfall's bulletin board (RMBLayout.BulletinBoardModelID), and the model's size.
// Usage: DungeonConverter --list-boards [--arena2 <dir>]
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    const uint BulletinBoardModel = 41739;

    static int BoardCensus(string arena2)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var blocksFile = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        var mesh = arch.GetMesh(arch.GetRecordIndex(BulletinBoardModel));
        var points = mesh.SubMeshes.SelectMany(s => s.Planes).SelectMany(p => p.Points).ToList();
        Console.WriteLine($"MODEL {BulletinBoardModel} x {points.Min(p => p.X):F0}..{points.Max(p => p.X):F0} y {points.Min(p => -p.Y):F0}..{points.Max(p => -p.Y):F0} z {points.Min(p => p.Z):F0}..{points.Max(p => p.Z):F0} (Daggerfall units)");
        WorldTerrain.Load(arena2, maps, blocksFile);
        var perBlock = new Dictionary<string, (int sub, int misc)>();
        (int sub, int misc) Count(string name)
        {
            if (perBlock.TryGetValue(name, out var c)) return c;
            var data = blocksFile.GetBlock(name).RmbBlock;
            int sub = data.SubRecords.Sum(s => s.Exterior.Block3dObjectRecords.Count(o => o.ModelIdNum == BulletinBoardModel));
            int misc = data.Misc3dObjectRecords.Count(o => o.ModelIdNum == BulletinBoardModel);
            return perBlock[name] = (sub, misc);
        }
        var groups = WorldTerrain.Groups();
        int withBoards = 0, boards = 0;
        var byType = new SortedDictionary<string, (int groups, int with)>();
        for (int g = 0; g < groups.Count; g++)
        {
            int n = 0, inSub = 0;
            foreach (var place in groups[g])
            {
                var loc = maps.GetLocation(place.RegionIndex, place.LocationIndex);
                for (int y = 0; y < place.BlocksHigh; y++)
                    for (int x = 0; x < place.BlocksWide; x++)
                    {
                        var c = Count(maps.GetRmbBlockName(loc, x, y));
                        n += c.sub + c.misc;
                        inSub += c.sub;
                    }
            }
            string type = groups[g][0].Type.ToString();
            byType.TryGetValue(type, out var t);
            byType[type] = (t.groups + 1, t.with + (n > 0 ? 1 : 0));
            if (n == 0) continue;
            withBoards++;
            boards += n;
            if (withBoards <= 40)
                Console.WriteLine($"GROUP {g} {groups[g][0].Name} ({groups[g][0].Region}, {type}): {n} boards, {inSub} in building records");
        }
        foreach (var (type, t) in byType)
            Console.WriteLine($"TYPE {type}: {t.with} of {t.groups} groups have boards");
        Console.WriteLine($"TOTAL {withBoards} groups, {boards} boards; blocks with boards: {string.Join(" ", perBlock.Where(b => b.Value.sub + b.Value.misc > 0).Select(b => b.Key))}");
        return 0;
    }
}
