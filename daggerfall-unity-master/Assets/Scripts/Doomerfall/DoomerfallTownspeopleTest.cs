// Doomerfall: test hooks for persistent townspeople. Inactive unless Daggerfall starts with a test flag.
//
//   -dftownreport     logs a census of each town's roster, and every 2 seconds the people listed near the player.
//   -dftownhour <h>   sets the clock once to hour h of the current day, so separate launches share a time.
//
// DoomerfallTownspeople holds one of these only when a flag is given, and calls it after each poll.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTownspeopleTest
    {
        readonly bool report;
        double hour = -1;
        float nextReport;
        TownRoster censused;

        DoomerfallTownspeopleTest(bool report, double hour)
        {
            this.report = report;
            this.hour = hour;
        }

        // Null in normal play.
        internal static DoomerfallTownspeopleTest FromCommandLine()
        {
            string[] args = Environment.GetCommandLineArgs();
            bool report = Array.IndexOf(args, "-dftownreport") >= 0;
            double hour = -1;
            int at = Array.IndexOf(args, "-dftownhour");
            if (at >= 0 && at + 1 < args.Length)
                double.TryParse(args[at + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out hour);
            return report || hour >= 0 ? new DoomerfallTownspeopleTest(report, hour) : null;
        }

        // Called once per poll while in game, before anything is listed.
        internal void BeforePoll(DoomerfallBridge bridge)
        {
            if (hour < 0)
                return;
            DaggerfallDateTime now = DaggerfallUnity.Instance.WorldTime.Now;
            now.FromSeconds((now.ToSeconds() / 86400UL) * 86400UL + (ulong)(hour * 3600));
            bridge.LogLine(string.Format("town: test clock set to {0}", now.LongDateTimeString()));
            hour = -1;
        }

        // Called after the people near the player are listed to Doom.
        internal void AfterPublish(DoomerfallBridge bridge, TownRoster roster, List<DoomerfallTownspeople.Candidate> candidates, double hours, double px, double pz, int deadCount)
        {
            if (!report)
                return;
            if (roster != censused)
            {
                censused = roster;
                Census(bridge, roster);
            }
            if (Time.unscaledTime < nextReport)
                return;
            nextReport = Time.unscaledTime + 2;
            ulong digest = 17;
            foreach (DoomerfallTownspeople.Candidate c in candidates)
                digest = TownRoster.Hash(digest, c.person.id ^ (ulong)(long)Math.Round(c.pose.x) * 31 ^ (ulong)(long)Math.Round(c.pose.z));
            bridge.LogLine(string.Format("town: report hour {0:F3} player {1:F0},{2:F0} visible {3} digest {4:x16} dead {5}", hours % 24, px, pz, candidates.Count, digest, deadCount));
            for (int i = 0; i < candidates.Count && i < 6; i++)
                bridge.LogLine(string.Format("townrow {0:x16} {1:F1} {2:F1} {3:F2} {4:F2} {5}", candidates[i].person.id, candidates[i].pose.x, candidates[i].pose.z, candidates[i].pose.vx, candidates[i].pose.vz, candidates[i].person.habit));
        }

        // Who lives here and where they spend their days. Independent of the live clock, so launches can be compared.
        static void Census(DoomerfallBridge bridge, TownRoster roster)
        {
            StringBuilder all = new StringBuilder();
            foreach (TownPerson p in roster.People)
                all.AppendFormat("{0:x16}{1}{2}{3}{4:F3}{5:F3};", p.id, p.archive, p.home, p.habit, p.wake, p.sleep);
            bridge.LogLine(string.Format("town: census {0} people, digest {1:x16}", roster.People.Length, TownRoster.Hash(Fnv(all.ToString()), 1)));
            int day = (int)(DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() / 86400UL);
            int shown = 0, near = 0, samples = 0;
            for (int i = 0; i < roster.People.Length && i < 40; i++)
            {
                TownPerson p = roster.People[i];
                int seen = 0, close = 0;
                // Seven days at four daytime hours: how often the person is at one of their own places.
                for (int d = 0; d < 7; d++)
                    foreach (double h in new[] { 9.0, 12.0, 15.0, 18.0 })
                    {
                        TownRoster.Step step;
                        if (!roster.FindStep(p, (day + d) * 24 + h, out step))
                            continue;
                        seen++;
                        if (step.kind != 2)
                            close++;
                    }
                near += close;
                samples += seen;
                if (shown++ < 12)
                    bridge.LogLine(string.Format("town: person {0} {1:x16} {2} archive {3} {4}, home {5} ({6}), haunts {7}, awake {8:F1}-{9:F1}, at own places {10}/{11}",
                        p.index, p.id, p.Name, p.archive, p.habit, roster.Sites[p.home].key, roster.Sites[p.home].type,
                        string.Join(",", Array.ConvertAll(p.haunts, s => roster.Sites[s].type.ToString())), p.wake, p.sleep, close, seen));
            }
            bridge.LogLine(string.Format("town: first 40 people were at one of their own places in {0} of {1} daytime samples", near, samples));
            HomeOrdinals(bridge, roster);
        }

        // Each lived-in home as "townhome ordinal key residents". The ordinal counts building records block by block,
        // rows then columns, as the converter's --list-buildings does, so a harness can find the home's door.
        static void HomeOrdinals(DoomerfallBridge bridge, TownRoster roster)
        {
            DFLocation location = GameManager.Instance.PlayerGPS.CurrentLocation;
            DFBlock[] blocks = RMBLayout.GetLocationBuildingData(location);
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            Dictionary<int, int> residents = new Dictionary<int, int>();
            foreach (TownPerson p in roster.People)
            {
                int key = roster.Sites[p.home].key, n;
                residents.TryGetValue(key, out n);
                residents[key] = n + 1;
            }
            int ordinal = 0;
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++)
                {
                    int records = blocks[y * width + x].RmbBlock.SubRecords.Length;
                    for (int r = 0; r < records; r++, ordinal++)
                    {
                        int key = BuildingDirectory.MakeBuildingKey((byte)x, (byte)y, (byte)r), n;
                        if (residents.TryGetValue(key, out n))
                            bridge.LogLine(string.Format("townhome {0} {1} {2}", ordinal, key, n));
                    }
                }
        }

        static ulong Fnv(string s)
        {
            ulong h = 14695981039346656037UL;
            foreach (char c in s)
            {
                h ^= c;
                h *= 1099511628211UL;
            }
            return h;
        }
    }
}
