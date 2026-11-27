// Doomerfall dev mode (-dfdevtravel): marks about half of all dungeons as discovered on the travel map, so high level
// dungeons of every type can be reached by fast travel at once. The other half stays hidden and can still be found
// the normal way. The pick is a fixed hash of each location's MapId, so it is the same half every time.
// Off (no flag) changes nothing. On, it only adds discovered locations to the player's discovery data (and so to
// saves); it runs on a new game, when a game starts, and after every load, and never removes anything.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallDevTravel
    {
        const string Flag = "-dfdevtravel";
        const uint Seed = 0xDE7A0001;
        const int DungeonTypeCount = 19; // DFRegion.DungeonTypes Crypt..Cemetery; 255 means no dungeon

        static DoomerfallBridge bridge;

        internal static void Attach(DoomerfallBridge owner)
        {
            if (bridge != null || Array.IndexOf(Environment.GetCommandLineArgs(), Flag) < 0)
                return;
            bridge = owner;
            StartGameBehaviour.OnNewGame += () => Reveal("new game"); // a new character's cleanup clears discoveries just before this
            StartGameBehaviour.OnStartGame += (s, e) => Reveal("game start");
            SaveLoadManager.OnLoad += data => Reveal("load");
            bridge.LogLine("devtravel: on, half of all dungeons will be marked discovered");
        }

        static void Reveal(string when)
        {
            try
            {
                RevealNow(when);
            }
            catch (Exception e)
            {
                bridge.LogLine("devtravel: failed, " + e.GetType().Name + ": " + e.Message);
            }
        }

        static void RevealNow(string when)
        {
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            MapsFile maps = DaggerfallUnity.Instance.ContentReader.MapFileReader;
            Dictionary<int, PlayerGPS.DiscoveredLocation> known = gps.GetDiscoverySaveData();
            int dungeons = 0, picked = 0, added = 0, alreadyKnown = 0;
            var byType = new int[DungeonTypeCount];
            var byLevel = new int[DoomerfallAreaLevels.MaxLevel + 1];
            var samples = new List<string>();
            for (int r = 0; r < maps.RegionCount; r++)
            {
                DFRegion region = maps.GetRegion(r);
                if (region.MapTable == null)
                    continue;
                for (int i = 0; i < region.LocationCount && i < region.MapTable.Length; i++)
                {
                    DFRegion.RegionMapTable map = region.MapTable[i];
                    int dtype = (int)map.DungeonType;
                    if (dtype < 0 || dtype >= DungeonTypeCount)
                        continue;
                    dungeons++;
                    if (Unit((uint)map.MapId) >= 0.5)
                        continue;
                    picked++;
                    byType[dtype]++;
                    DoomerfallAreaLevels.Level level;
                    int dungeonLevel = DoomerfallAreaLevels.ForMapId(map.MapId, out level) ? level.dungeon : 0;
                    if (dungeonLevel >= 0 && dungeonLevel < byLevel.Length)
                        byLevel[dungeonLevel]++;
                    int pixel = MapsFile.GetMapPixelIDFromLongitudeLatitude((int)map.Longitude, map.Latitude);
                    if (map.Discovered || known.ContainsKey(pixel))
                    {
                        alreadyKnown++;
                        continue;
                    }
                    known[pixel] = new PlayerGPS.DiscoveredLocation
                    {
                        mapID = map.MapId,
                        mapPixelID = pixel,
                        regionName = region.Name,
                        locationName = region.MapNames[i],
                    };
                    added++;
                    if (samples.Count < 12 && (dungeonLevel >= 25 || samples.Count < 6))
                        samples.Add(string.Format("{0} ({1}, {2}, level {3})", region.MapNames[i], region.Name, map.DungeonType, dungeonLevel));
                }
            }
            bridge.LogLine(string.Format("devtravel ({0}): {1} dungeons, {2} picked, {3} newly discovered, {4} were already known",
                when, dungeons, picked, added, alreadyKnown));
            var types = new List<string>();
            for (int t = 0; t < DungeonTypeCount; t++)
                types.Add(((DFRegion.DungeonTypes)t) + " " + byType[t]);
            bridge.LogLine("devtravel picked by type: " + string.Join(", ", types.ToArray()));
            var levels = new List<string>();
            for (int l = 0; l < byLevel.Length; l++)
                if (byLevel[l] > 0)
                    levels.Add(l + ":" + byLevel[l]);
            bridge.LogLine("devtravel picked by level: " + string.Join(" ", levels.ToArray()));
            if (samples.Count > 0)
                bridge.LogLine("devtravel examples: " + string.Join("; ", samples.ToArray()));
        }

        // lowbias32 by Chris Wellons, as in DoomerfallAreaLevels.
        static double Unit(uint mapId)
        {
            unchecked
            {
                uint x = Seed ^ mapId;
                for (int round = 0; round < 2; round++)
                {
                    x ^= x >> 16;
                    x *= 0x7FEB352D;
                    x ^= x >> 15;
                    x *= 0x846CA68B;
                    x ^= x >> 16;
                }
                return x / 4294967296.0;
            }
        }
    }
}
