// Doomerfall test only (-dftownlevellog): writes a bridge log line whenever the area level where the player stands
// changes, with the town level, the terrain level, the world position, and whether Daggerfall counts the player as
// inside the location rect. Attached from DoomerfallWorldLevelTest.Attach. Nothing reaches the screen.

using System;
using DaggerfallConnect.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTownLevelWatch : MonoBehaviour
    {
        DoomerfallBridge bridge;
        string last;
        float next;

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dftownlevellog") >= 0)
                owner.gameObject.AddComponent<DoomerfallTownLevelWatch>().bridge = owner;
        }

        void Update()
        {
            if (Time.unscaledTime < next || !GameManager.HasInstance || GameManager.Instance.PlayerGPS == null
                || !GameManager.Instance.StateManager.GameInProgress || !DoomerfallAreaLevels.IsFinished)
                return;
            next = Time.unscaledTime + 0.25f;
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            DFPosition pixel = gps.CurrentMapPixel;
            bool inside = GameManager.Instance.PlayerEnterExit && GameManager.Instance.PlayerEnterExit.IsPlayerInside;
            string place = string.Format("place level {0} (WorldLevel.Current {1}), town level here {2}, terrain {3}, location {4}, in location rect {5}, inside {6}",
                DoomerfallAreaLevels.ForCurrentPlace(), WorldLevel.Current, inside ? 0 : DoomerfallAreaLevels.TownAt(gps.WorldX, gps.WorldZ),
                DoomerfallAreaLevels.ForMapPixel(pixel.X, pixel.Y), gps.HasCurrentLocation ? gps.CurrentLocation.Name : "none", gps.IsPlayerInLocationRect, inside);
            if (place == last)
                return;
            last = place;
            bridge.LogLine(string.Format("townlevel: {0} at world {1},{2} pixel {3},{4}", place, gps.WorldX, gps.WorldZ, pixel.X, pixel.Y));
        }
    }
}
