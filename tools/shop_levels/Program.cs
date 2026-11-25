// Shop and town level research dump (work/notes/20261124-124736-shop-levels.md).
//
// Inputs:  classic MAPS.BSA, BLOCKS.BSA and ARCH3D.BSA from an Arena2 folder.
// Outputs: <out>/buildings.csv, one row per building in every location with an exterior, with the building data
//          merged the way Daggerfall Unity's RMBLayout.GetLocationBuildingData merges it (named buildings take their
//          type order, name seed and quality from the location's list; others keep the block's), plus model size and
//          interior shelf counts; <out>/locations.csv, one row per location.
// The CSVs are derived from game data: write them outside the repository and never commit them.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static class Program
{
    static readonly HashSet<uint> ShelfGroups = new HashSet<uint> { 5, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 26, 28, 29, 31, 35, 36, 37, 40, 41, 42, 44, 46, 47, 48, 49, 808 };
    static readonly HashSet<uint> HouseContainerGroups = new HashSet<uint> { 3, 4, 7, 8, 27, 32, 33, 34, 35, 37, 38, 50, 51 };

    static bool IsNamed(DFLocation.BuildingTypes t)
    {
        switch (t)
        {
            case DFLocation.BuildingTypes.Alchemist: case DFLocation.BuildingTypes.Armorer: case DFLocation.BuildingTypes.Bank:
            case DFLocation.BuildingTypes.Bookseller: case DFLocation.BuildingTypes.ClothingStore: case DFLocation.BuildingTypes.FurnitureStore:
            case DFLocation.BuildingTypes.GemStore: case DFLocation.BuildingTypes.GeneralStore: case DFLocation.BuildingTypes.Library:
            case DFLocation.BuildingTypes.GuildHall: case DFLocation.BuildingTypes.PawnShop: case DFLocation.BuildingTypes.WeaponSmith:
            case DFLocation.BuildingTypes.Temple: case DFLocation.BuildingTypes.Tavern: case DFLocation.BuildingTypes.Palace:
                return true;
        }
        return false;
    }

    static string Q(string s) => "\"" + (s ?? "").Replace("\"", "'") + "\"";

    static int Main(string[] args)
    {
        if (args.Length < 2) { Console.Error.WriteLine("usage: ShopLevels <arena2> <out dir>"); return 2; }
        string arena2 = args[0], outDir = args[1];
        Directory.CreateDirectory(outDir);
        var inv = CultureInfo.InvariantCulture;
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        var meshSize = new Dictionary<uint, (float x, float y, float z)>();
        var blockCache = new Dictionary<string, DFBlock>();

        var b = new StringBuilder("region,regionName,locIndex,mapId,locName,locType,blockX,blockY,blockName,record,buildingType,named,quality,nameSeed,factionId,modelId,sizeX,sizeY,sizeZ,interiorObjects,shelves,houseContainers,poolMiss\n");
        var l = new StringBuilder("region,regionName,locIndex,mapId,locName,locType,dungeonType,pixelX,pixelY,width,height,buildingCount,listCount\n");
        int warnings = 0;
        for (int r = 0; r < maps.RegionCount; r++)
        {
            DFRegion region = maps.GetRegion(r);
            for (int li = 0; li < region.LocationCount; li++)
            {
                DFLocation loc = maps.GetLocation(r, li);
                if (!loc.Loaded) continue;
                var pixel = MapsFile.LongitudeLatitudeToMapPixel(loc.MapTableData.Longitude, loc.MapTableData.Latitude);
                int w = loc.Exterior.ExteriorData.Width, h = loc.Exterior.ExteriorData.Height;
                l.AppendLine(string.Join(",", r, Q(loc.RegionName), li, loc.MapTableData.MapId, Q(loc.Name), (int)loc.MapTableData.LocationType,
                    (int)loc.MapTableData.DungeonType, pixel.X, pixel.Y, w, h, loc.Exterior.BuildingCount, loc.Exterior.Buildings?.Length ?? 0));
                if (w == 0 || h == 0) continue;

                // Named building pool, as RMBLayout.GetLocationBuildingData.
                var pool = new List<(DFLocation.BuildingData data, bool used)>();
                for (int i = 0; i < loc.Exterior.BuildingCount; i++)
                    if (IsNamed(loc.Exterior.Buildings[i].BuildingType))
                        pool.Add((loc.Exterior.Buildings[i], false));

                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++)
                    {
                        string name = blocks.CheckName(maps.GetRmbBlockName(loc, x, y));
                        if (!blockCache.TryGetValue(name, out DFBlock block)) { block = blocks.GetBlock(name); blockCache[name] = block; }
                        var subs = block.RmbBlock.SubRecords;
                        if (subs == null) continue;
                        for (int i = 0; i < subs.Length; i++)
                        {
                            DFLocation.BuildingData bd = block.RmbBlock.FldHeader.BuildingDataList[i];
                            bool named = IsNamed(bd.BuildingType), miss = false;
                            if (named)
                            {
                                int k = pool.FindIndex(p => !p.used && p.data.BuildingType == bd.BuildingType);
                                if (k < 0) { miss = true; bd.Quality = 0; bd.NameSeed = 0; bd.FactionId = 0; warnings++; }   // DFU uses a default item here
                                else
                                {
                                    var it = pool[k]; pool[k] = (it.data, true);
                                    bd.NameSeed = it.data.NameSeed; bd.FactionId = it.data.FactionId; bd.Quality = it.data.Quality;
                                }
                                if (block.RmbBlock.FldHeader.OtherNames != null && block.RmbBlock.FldHeader.OtherNames[i] == "KRAVE01.HS2")
                                { bd.BuildingType = DFLocation.BuildingTypes.GuildHall; bd.FactionId = 414; }
                            }
                            uint model = subs[i].Exterior.Block3dObjectRecords.Length > 0 ? subs[i].Exterior.Block3dObjectRecords[0].ModelIdNum : 0;
                            if (!meshSize.TryGetValue(model, out var size))
                            {
                                int rec = model == 0 ? -1 : arch.GetRecordIndex(model);
                                if (rec >= 0) { var m = arch.GetMesh(rec); size = (m.Size.X, m.Size.Y, m.Size.Z); }
                                meshSize[model] = size;
                            }
                            var objs = subs[i].Interior.Block3dObjectRecords ?? new DFBlock.RmbBlock3dObjectRecord[0];
                            int shelves = 0, house = 0;
                            foreach (var o in objs)
                            {
                                uint g = o.ModelIdNum - 41000;
                                if (ShelfGroups.Contains(g)) shelves++;
                                if (HouseContainerGroups.Contains(g)) house++;
                            }
                            b.AppendLine(string.Join(",", r, Q(loc.RegionName), li, loc.MapTableData.MapId, Q(loc.Name), (int)loc.MapTableData.LocationType,
                                x, y, name, i, (int)bd.BuildingType, named ? 1 : 0, bd.Quality, bd.NameSeed, bd.FactionId, model,
                                size.x.ToString("0", inv), size.y.ToString("0", inv), size.z.ToString("0", inv), objs.Length, shelves, house, miss ? 1 : 0));
                        }
                    }
            }
        }
        File.WriteAllText(Path.Combine(outDir, "buildings.csv"), b.ToString());
        File.WriteAllText(Path.Combine(outDir, "locations.csv"), l.ToString());
        Console.WriteLine($"done; named buildings with no list entry: {warnings}");
        return 0;
    }
}
