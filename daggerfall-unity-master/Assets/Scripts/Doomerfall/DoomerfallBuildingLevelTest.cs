// Doomerfall test only (-dfbuildingleveltest <file>): each time the player is inside a new building, appends one line
// to <file>: the building, WorldLevel.Current (what is rolled there), WorldLevel.Danger (what enemies are made at),
// the level DoomerfallShopLevels.ForBuilding gives it, and PASS or FAIL. Starts itself; no game class calls it.

using System;
using System.IO;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallBuildingLevelTest : MonoBehaviour
    {
        string file;
        int lastKey = -1, lastMap;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfbuildingleveltest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallBuildingLevelTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallBuildingLevelTest>().file = args[at + 1];
        }

        void Update()
        {
            if (!GameManager.HasInstance || !GameManager.Instance.PlayerEnterExit || GameManager.Instance.PlayerGPS == null)
                return;
            PlayerEnterExit enterExit = GameManager.Instance.PlayerEnterExit;
            if (!enterExit.IsPlayerInsideBuilding)
            {
                lastKey = -1;
                return;
            }
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            int key = enterExit.BuildingDiscoveryData.buildingKey, map = gps.CurrentLocation.MapTableData.MapId;
            if (key == lastKey && map == lastMap)
                return;
            BuildingDirectory directory = GameManager.Instance.StreamingWorld.GetCurrentBuildingDirectory();
            BuildingSummary summary;
            if (!directory || !directory.GetBuildingSummary(key, out summary))
                return;
            lastKey = key;
            lastMap = map;
            int expected = DoomerfallShopLevels.ForBuilding(directory.LocationData, summary);
            int danger = DoomerfallAreaLevels.ForCurrentDanger();
            int current = WorldLevel.Current, enemies = WorldLevel.Danger;
            bool pass = (expected > 0 ? current == expected : current == Math.Max(1, danger)) && enemies == Math.Max(1, danger);
            File.AppendAllText(file, string.Format("building {0} / {1}: {2} quality {3} faction {4}: current {5}, danger {6}, ForBuilding {7}, place danger {8}: {9}\n",
                gps.CurrentLocation.RegionName, gps.CurrentLocation.Name, summary.BuildingType, summary.Quality, summary.FactionId,
                current, enemies, expected, danger, pass ? "PASS" : "FAIL"));
        }
    }
}
