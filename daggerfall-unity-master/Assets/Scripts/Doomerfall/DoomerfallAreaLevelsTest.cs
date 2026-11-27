// Doomerfall test only (-dfarealeveldump <dir>): writes the runtime area levels so tools/area_level/compare_runtime.py
// can check them against the proposal script, then quits. Needs no bridge session.
//
// Writes, into <dir>:
//   levels.csv   map_id,dungeon,terrain for every classic location
//   terrain.bin  1000 x 500 bytes, the terrain level of each map pixel (0 for water)
//   sample.txt   named places through the same call the enemy drops use, the mod-added fallback checked
//                against every classic dungeon, a few enemy picks at the computed level, and timings

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
    internal sealed class DoomerfallAreaLevelsTest : MonoBehaviour
    {
        static readonly string[][] Samples =
        {
            new[] { "Daggerfall", "Privateer's Hold" }, new[] { "Daggerfall", "Daggerfall" },
            new[] { "Daggerfall", "Castle Necromoghan" }, new[] { "Betony", "Tristore Laboratory" },
            new[] { "Ykalon", "Castle Llugwych" }, new[] { "Sentinel", "Sentinel" }, new[] { "Wayrest", "Wayrest" },
            new[] { "Wayrest", "Woodborne Hall" }, new[] { "Menevia", "Lysandus' Tomb" },
            new[] { "Dragontail Mountains", "Scourg Barrow" }, new[] { "Isle of Balfiera", "Direnni Tower" },
            new[] { "Wrothgarian Mountains", "Shedungent" }, new[] { "Orsinium Area", "Orsinium" },
            new[] { "High Rock sea coast", "Mantellan Crux" }, new[] { "Daggerfall", "Jubithiva's Den" },
            new[] { "Daggerfall", "The Fortress of Ashham" }, new[] { "Daggerfall", "Gothway Garden" },
        };

        string dir;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfarealeveldump");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallAreaLevelsTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallAreaLevelsTest>().dir = args[at + 1];
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

            StringBuilder csv = new StringBuilder("map_id,dungeon,terrain,town\n");
            foreach (KeyValuePair<int, DoomerfallAreaLevels.Level> entry in DoomerfallAreaLevels.Classic())
                csv.AppendFormat("{0},{1},{2},{3}\n", entry.Key, entry.Value.dungeon, entry.Value.terrain, entry.Value.town);
            File.WriteAllText(Path.Combine(dir, "levels.csv"), csv.ToString());

            byte[] terrain = new byte[1000 * 500];
            for (int y = 0; y < 500; y++)
                for (int x = 0; x < 1000; x++)
                {
                    int politic = DaggerfallUnity.Instance.ContentReader.MapFileReader.GetPoliticIndex(x, y);
                    terrain[y * 1000 + x] = politic == 64 || politic < 128 ? (byte)0 : (byte)DoomerfallAreaLevels.ForMapPixel(x, y);
                }
            File.WriteAllBytes(Path.Combine(dir, "terrain.bin"), terrain);

            ContentReader reader = DaggerfallUnity.Instance.ContentReader;
            foreach (string[] sample in Samples)
            {
                DFLocation location;
                if (!reader.GetLocation(sample[0], sample[1], out location))
                {
                    report.AppendFormat("sample {0} / {1}: not found\n", sample[0], sample[1]);
                    continue;
                }
                DoomerfallAreaLevels.Level level;
                DoomerfallAreaLevels.ForLocation(location, out level);
                report.AppendFormat("sample {0} / {1}: map_id {2}, drops area level {3}, dungeon {4}, terrain {5}\n", sample[0], sample[1],
                    location.MapTableData.MapId, DoomerfallDrops.AreaLevel(location), level.dungeon, level.terrain);
                if (location.HasDungeon)
                    ReportPicks(report, location, DoomerfallDrops.AreaLevel(location));
            }

            // The fallback for mod-added places, run on every classic dungeon: it should land each on its own rank.
            clock = Stopwatch.StartNew();
            int checkedCount = 0, same = 0, off = 0;
            for (int region = 0; region < reader.MapFileReader.RegionCount; region++)
            {
                DFRegion data = reader.MapFileReader.GetRegion(region);
                for (int i = 0; i < data.LocationCount; i++)
                {
                    DFRegion.RegionMapTable row = data.MapTable[i];
                    if ((int)row.DungeonType >= 19 || row.MapId == 187853213)
                        continue;
                    DFLocation location;
                    if (!reader.GetLocation(region, i, out location))
                        continue;
                    DoomerfallAreaLevels.Level ranked, placed;
                    DoomerfallAreaLevels.ForLocation(location, out ranked);
                    DoomerfallAreaLevels.PlaceAmongClassic(location, out placed);
                    checkedCount++;
                    if (ranked.dungeon == placed.dungeon && ranked.terrain == placed.terrain) same++;
                    else if (off++ < 5) report.AppendFormat("fallback differs at {0}: ranked {1}/{2}, placed {3}/{4}\n", row.MapId, ranked.dungeon, ranked.terrain, placed.dungeon, placed.terrain);
                }
            }
            report.AppendFormat("fallback on {0} classic dungeons: {1} same, {2} differ ({3} ms)\n", checkedCount, same, off, clock.ElapsedMilliseconds);
            DoomerfallTownLevelsTest.Run(report);
        }

        // The same picker BuildPlacements uses, so the computed level changes which enemies the drops come from.
        static void ReportPicks(StringBuilder report, DFLocation location, int areaLevel)
        {
            int id = location.Dungeon.RecordElement.Header.LocationId;
            foreach (int level in new[] { 1, areaLevel })
            {
                DoomerfallDrops.EnemyPicker picker = new DoomerfallDrops.EnemyPicker(id, location.MapTableData.DungeonType, level, 0, false);
                StringBuilder picks = new StringBuilder();
                for (ulong hash = 1; hash <= 8; hash++)
                    picks.Append(picker.PickRandom(hash * 0x9E3779B97F4A7C15UL, 0, 0, 10000)).Append(' ');
                report.AppendFormat("    picks at level {0}: {1}\n", level, picks);
            }
        }
    }
}
