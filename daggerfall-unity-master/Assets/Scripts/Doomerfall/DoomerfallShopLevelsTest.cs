// Doomerfall test only (-dfshopleveldump <dir>): writes the runtime shop levels so tools/shop_levels/shop_level.py
// --runtime <dir> can check them against the Python port, then quits. Needs no bridge session.
//
// Writes, into <dir>:
//   classic.csv  map_id,type,name_seed,quality,level for every shop in the classic table
//   shops.csv    the same for every shop Daggerfall Unity builds (RMBLayout building summaries of every location
//                that has a shop), read through ForShop, the call the game will use
//   sample.txt   timings, per-level counts, the band contract check, named sample shops (Gothway Garden, the City
//                of Daggerfall and others), and the mod-added fallback run on every shop

using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopLevelsTest : MonoBehaviour
    {
        static readonly string[][] Samples =
        {
            new[] { "Daggerfall", "Gothway Garden" }, new[] { "Daggerfall", "Daggerfall" }, new[] { "Sentinel", "Sentinel" },
            new[] { "Wayrest", "Wayrest" }, new[] { "Alik'r Desert", "Mesascuza" },
        };

        string dir;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfshopleveldump");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallShopLevelsTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallShopLevelsTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            float giveUp = Time.realtimeSinceStartup + 60;
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady || string.IsNullOrEmpty(DaggerfallUnity.Instance.Arena2Path)
                || QuestMachine.Instance == null) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            yield return null;
            Directory.CreateDirectory(dir);
            StringBuilder report = new StringBuilder();
            try
            {
                Run(report);
            }
            catch (Exception e)
            {
                report.AppendLine("error " + e);
            }
            File.WriteAllText(Path.Combine(dir, "sample.txt"), report.ToString());
            Application.Quit();
        }

        void Run(StringBuilder report)
        {
            Stopwatch clock = Stopwatch.StartNew();
            DoomerfallAreaLevels.Warm();
            report.AppendFormat("warm call on main thread {0:0.000} ms\n", clock.Elapsed.TotalMilliseconds);
            report.AppendLine(DoomerfallAreaLevels.Status());
            report.AppendLine(DoomerfallShopLevels.Status());

            StringBuilder csv = new StringBuilder("map_id,type,name_seed,quality,level\n");
            foreach (int[] s in DoomerfallShopLevels.Classic())
                csv.AppendFormat("{0},{1},{2},{3},{4}\n", s[0], s[1], s[2], s[3], s[4]);
            File.WriteAllText(Path.Combine(dir, "classic.csv"), csv.ToString());

            int[] counts = DoomerfallShopLevels.Counts();
            StringBuilder line = new StringBuilder("counts:");
            for (int level = 1; level < counts.Length; level++)
                line.AppendFormat(" {0}:{1}", level, counts[level]);
            report.AppendLine(line.ToString());

            ContentReader reader = DaggerfallUnity.Instance.ContentReader;
            foreach (string[] sample in Samples)
            {
                DFLocation location;
                if (!reader.GetLocation(sample[0], sample[1], out location))
                {
                    report.AppendFormat("sample {0} / {1}: not found\n", sample[0], sample[1]);
                    continue;
                }
                report.AppendFormat("sample {0} / {1} ({2}, map_id {3}):\n", sample[0], sample[1], location.MapTableData.LocationType, location.MapTableData.MapId);
                foreach (BuildingSummary b in Summaries(location))
                    if (RMBLayout.IsShop(b.BuildingType))
                        report.AppendFormat("    {0} \"{1}\" (name seed {2}) quality {3}: level {4}\n", b.BuildingType,
                            Name(b, location), b.NameSeed, b.Quality, DoomerfallShopLevels.ForShop(location, b));
            }

            // Every shop the game builds, through ForShop, plus the band contract and the mod-added fallback.
            clock = Stopwatch.StartNew();
            StringBuilder shops = new StringBuilder("map_id,type,name_seed,quality,level\n");
            int[] bandMin = { 99, 99, 99, 99, 99 }, bandMax = new int[5];
            List<int[]> all = new List<int[]>();
            int total = 0, fallbackSame = 0, zero = 0;
            for (int region = 0; region < reader.MapFileReader.RegionCount; region++)
            {
                DFRegion data = reader.MapFileReader.GetRegion(region);
                for (int i = 0; i < data.LocationCount; i++)
                {
                    DFRegion.LocationTypes type = data.MapTable[i].LocationType;
                    if (type != DFRegion.LocationTypes.TownCity && type != DFRegion.LocationTypes.TownHamlet
                        && type != DFRegion.LocationTypes.TownVillage && type != DFRegion.LocationTypes.DungeonKeep)
                        continue;
                    DFLocation location;
                    if (!reader.GetLocation(region, i, out location) || location.Exterior.ExteriorData.Width == 0)
                        continue;
                    foreach (BuildingSummary b in Summaries(location))
                    {
                        if (!RMBLayout.IsShop(b.BuildingType))
                            continue;
                        int level = DoomerfallShopLevels.ForShop(location, b);
                        total++;
                        if (level == 0) zero++;
                        if (DoomerfallShopLevels.PlaceAmongClassic(location, b) == level) fallbackSame++;
                        int band = b.Quality <= 3 ? 0 : b.Quality <= 7 ? 1 : b.Quality <= 13 ? 2 : b.Quality <= 17 ? 3 : 4;
                        bandMin[band] = Math.Min(bandMin[band], level);
                        bandMax[band] = Math.Max(bandMax[band], level);
                        all.Add(new[] { band, level });
                        shops.AppendFormat("{0},{1},{2},{3},{4}\n", location.MapTableData.MapId, (int)b.BuildingType, b.NameSeed, b.Quality, level);
                    }
                }
            }
            File.WriteAllText(Path.Combine(dir, "shops.csv"), shops.ToString());
            int broken = 0;
            foreach (int[] s in all)
                if (s[0] > 0 && s[1] < bandMax[s[0] - 1]) broken++;
            report.AppendFormat("shops built from building summaries: {0} ({1} with level 0) in {2} ms\n", total, zero, clock.ElapsedMilliseconds);
            for (int band = 0; band < 5; band++)
                report.AppendFormat("band {0}: levels {1}-{2}\n", band + 1, bandMin[band], bandMax[band]);
            report.AppendFormat("contract: {0} shops below the top level of the band beneath\n", broken);
            report.AppendFormat("fallback on every shop: {0} of {1} land on their own level\n", fallbackSame, total);
        }

        // Some name forms read the player's position, and there is no player in this test.
        static string Name(BuildingSummary b, DFLocation location)
        {
            try { return BuildingNames.GetName(b.NameSeed, b.BuildingType, b.FactionId, location.Name, location.RegionName); }
            catch (Exception) { return "(name needs a player)"; }
        }

        static IEnumerable<BuildingSummary> Summaries(DFLocation location)
        {
            DFBlock[] blocks = RMBLayout.GetLocationBuildingData(location);
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++)
                {
                    BuildingSummary[] buildings = RMBLayout.GetBuildingData(blocks[y * width + x], x, y);
                    if (buildings != null)
                        foreach (BuildingSummary b in buildings)
                            yield return b;
                }
        }
    }
}
