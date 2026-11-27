// Doomerfall test only (-dfstatustest <file>): logs the top Daggerfall window each time it changes, with the text of a
// message box, and Daggerfall's area, location and time, so a test can see Doom's Status key show Daggerfall's
// location and time box and then its health box, indoors and outdoors.

using System;
using System.IO;
using System.Reflection;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallStatusTest : MonoBehaviour
    {
        string path, last;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfstatustest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallStatusTest");
            DontDestroyOnLoad(host);
            DoomerfallStatusTest test = host.AddComponent<DoomerfallStatusTest>();
            test.path = args[at + 1];
            File.WriteAllText(test.path, "status: started\n");
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
            if (!DaggerfallUI.Instance || !GameManager.HasInstance || !GameManager.Instance.IsReady)
                return "none";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            string text = "";
            if (top is DaggerfallMessageBox)
            {
                var label = (MultiFormatTextLabel)typeof(DaggerfallMessageBox).GetField("label", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(top);
                foreach (TextLabel l in label.TextLabels)
                    text += (text.Length > 0 ? " / " : "") + l.Text;
            }
            PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
            string area = enter.IsPlayerInsideDungeon ? "dungeon" : enter.IsPlayerInside ? "building" : "outside";
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            string here = gps.HasCurrentLocation ? gps.CurrentLocation.Name : "";
            // The minute is left out, so the line changes only when the window, text or place does.
            return string.Format("top {0} | area {1} | here '{2}' | hour {3} | text '{4}'", top == null ? "none" : top.GetType().Name, area, here,
                DaggerfallUnity.Instance.WorldTime.Now.Hour, text);
        }
    }
}
