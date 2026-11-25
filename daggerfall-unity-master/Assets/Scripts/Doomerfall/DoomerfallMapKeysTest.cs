// Doomerfall test only (-dfmapkeystest <file>): logs the view of whichever Daggerfall map screen is on top, each time
// it changes, so a test can see Doom's movement keys pan it. Also logs which arrow and WASD keys Daggerfall holds
// from Doom, and the hidden player's world position, which follows Doom's player.

using System;
using System.IO;
using System.Reflection;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMapKeysTest : MonoBehaviour
    {
        const BindingFlags Field = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        static readonly KeyCode[] Watched = { KeyCode.UpArrow, KeyCode.DownArrow, KeyCode.LeftArrow, KeyCode.RightArrow, KeyCode.W, KeyCode.A, KeyCode.S, KeyCode.D };

        string path, last;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfmapkeystest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallMapKeysTest");
            DontDestroyOnLoad(host);
            DoomerfallMapKeysTest test = host.AddComponent<DoomerfallMapKeysTest>();
            test.path = args[at + 1];
            File.WriteAllText(test.path, "mapkeys: started\n");
        }

        void LateUpdate()
        {
            string line;
            try { line = Describe(); }
            catch (Exception e) { line = "error " + e.GetType().Name + " " + e.Message; }
            if (line == last)
                return;
            last = line;
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        static string Describe()
        {
            if (!DaggerfallUI.Instance || !GameManager.HasInstance)
                return "none";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            string keys = "";
            foreach (KeyCode k in Watched)
                if (DoomerfallInput.GetKey(k))
                    keys += k + ",";
            string view = "";
            if (top is DaggerfallAutomapWindow && Automap.instance && Automap.instance.CameraAutomap)
                view = V(Automap.instance.CameraAutomap.transform.position);
            else if (top is DaggerfallExteriorAutomapWindow && ExteriorAutomap.instance && ExteriorAutomap.instance.CameraExteriorAutomap)
                view = V(ExteriorAutomap.instance.CameraExteriorAutomap.transform.position);
            else if (top is DaggerfallTravelMapWindow)
            {
                Type t = typeof(DaggerfallTravelMapWindow);
                view = string.Format("region {0} part {1} zoom {2} at {3}", t.GetField("selectedRegion", Field).GetValue(top), t.GetField("mapIndex", Field).GetValue(top),
                    t.GetField("zoom", Field).GetValue(top), ((Vector2)t.GetField("zoomPosition", Field).GetValue(top)).ToString("F0"));
            }
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            return string.Format("top {0} view {1} keys {2} player {3},{4}", top == null ? "none" : top.GetType().Name, view, keys, gps.WorldX, gps.WorldZ);
        }

        static string V(Vector3 v) { return v.ToString("F1"); }
    }
}
