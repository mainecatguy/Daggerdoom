// Doomerfall test only (-dftownlevellog): writes a bridge log line whenever the area level where the player stands
// changes (and every 3 seconds), with the town level, the terrain level, the world position, and whether Daggerfall counts the player as
// inside the location rect. Attached from DoomerfallWorldLevelTest.Attach. Nothing reaches the screen.

using System;
using System.Reflection;
using DaggerfallConnect.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTownLevelWatch : MonoBehaviour
    {
        DoomerfallBridge bridge;
        string last;
        float next, heartbeat;
        bool layoutChecked;

        // Recreates the state while PlayerEnterExit.TransitionInterior lays out a building in town (interior set,
        // IsPlayerInside still false, where DaggerfallInterior rolls its treasure piles) and logs the world level then.
        void CheckLayout(PlayerEnterExit enter, int terrain)
        {
            layoutChecked = true;
            FieldInfo field = typeof(PlayerEnterExit).GetField("interior", BindingFlags.NonPublic | BindingFlags.Instance);
            if (!enter || field == null)
                return;
            int outdoors = WorldLevel.Current;
            GameObject holder = new GameObject("Doomerfall town level test interior");
            object saved = field.GetValue(enter);
            field.SetValue(enter, holder.AddComponent<DaggerfallInterior>());
            int during = WorldLevel.Current;
            field.SetValue(enter, saved);
            Destroy(holder);
            bridge.LogLine(string.Format("townlevel: building layout in town: outdoors level {0}, while an interior is laid out {1} (terrain {2}) {3}",
                outdoors, during, terrain, during == terrain ? "PASS" : "FAIL"));
        }

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dftownlevellog") >= 0)
                owner.gameObject.AddComponent<DoomerfallTownLevelWatch>().bridge = owner;
        }

        void Update()
        {
            if (Time.unscaledTime < next || !GameManager.HasInstance || GameManager.Instance.PlayerGPS == null || !DoomerfallAreaLevels.IsFinished)
                return;
            next = Time.unscaledTime + 0.25f;
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            DFPosition pixel = gps.CurrentMapPixel;
            bool inside = GameManager.Instance.PlayerEnterExit && GameManager.Instance.PlayerEnterExit.IsPlayerInside;
            string place = string.Format("place level {0} (WorldLevel.Current {1}), town level here {2}, terrain {3}, location {4}, in location rect {5}, inside {6}, Doom town map {7}",
                DoomerfallAreaLevels.ForCurrentPlace(), WorldLevel.Current, inside ? 0 : DoomerfallAreaLevels.TownAt(gps.WorldX, gps.WorldZ),
                DoomerfallAreaLevels.ForMapPixel(pixel.X, pixel.Y), gps.HasCurrentLocation ? gps.CurrentLocation.Name : "none", gps.IsPlayerInLocationRect, inside,
                DoomerfallAreaLevels.DoomTownMap);
            if (!layoutChecked && !inside && DoomerfallAreaLevels.DoomTownMap != 0 && DoomerfallAreaLevels.TownAt(gps.WorldX, gps.WorldZ) > 0)
                CheckLayout(GameManager.Instance.PlayerEnterExit, DoomerfallAreaLevels.ForMapPixel(pixel.X, pixel.Y));
            if (place == last && Time.unscaledTime < heartbeat)
                return;
            last = place;
            heartbeat = Time.unscaledTime + 3;
            bridge.LogLine(string.Format("townlevel: {0} at world {1},{2} pixel {3},{4}", place, gps.WorldX, gps.WorldZ, pixel.X, pixel.Y));
        }
    }
}
