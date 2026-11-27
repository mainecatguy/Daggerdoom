// Doomerfall test only (-dftravelhintshots <dir>): opens Daggerfall's travel map, points it at fixed places of
// different area levels, and saves a screenshot of each, plus one of the Find Location confirmation box, then quits.
// Needs no bridge session.
//
// Writes, into <dir>: one PNG per place, confirm.png, and report.txt (place, area level, word, label text).
//
// The window below is the real DaggerfallTravelMapWindow. It only replaces the mouse hover test with a fixed
// place, so the label and confirmation box go through the same code a player's hover does.

using System;
using System.Collections;
using System.IO;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTravelHintTest : MonoBehaviour
    {
        // Region, place. Dungeons of several levels show a word; the hamlet, the coven and the two cities (which have
        // palace dungeons) show none. report.txt prints each place's current type, level and shown word.
        const string CovenMarker = "*coven";

        static readonly string[][] Places =
        {
            new[] { "Daggerfall", "Privateer's Hold" },     // dungeon
            new[] { "Daggerfall", "Gothway Garden" },       // hamlet, no dungeon
            new[] { "Daggerfall", CovenMarker },            // the region's first Coven-type place, no dungeon
            new[] { "Daggerfall", "Daggerfall" },           // city with a palace dungeon
            new[] { "Wayrest", "Wayrest" },                 // city with a palace dungeon
            new[] { "Daggerfall", "Castle Necromoghan" },   // dungeon
            new[] { "Wayrest", "Woodborne Hall" },          // dungeon
            new[] { "Orsinium Area", "Orsinium" },          // dungeon
        };

        string dir;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dftravelhintshots");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallTravelHintTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallTravelHintTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            // Daggerfall stays on its startup screen, so load the game scene the way DoomerfallNewGame does.
            float giveUp = Time.realtimeSinceStartup + 60;
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            Application.runInBackground = true;
            if (GameObject.FindWithTag("Player") == null)
                yield return SceneManager.LoadSceneAsync(1);
            while ((GameObject.FindWithTag("Player") == null || DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady
                || DaggerfallUI.Instance == null || !GameManager.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            StartGameBehaviour start = FindObjectOfType<StartGameBehaviour>();
            if (start != null)
                start.EnableVideos = false;
            if (DaggerfallUI.Instance != null)
                DaggerfallUI.Instance.enableVideos = false;
            for (int i = 0; i < 5; i++)
                yield return null;
            if (DaggerfallUI.Instance != null)
                DaggerfallUI.Instance.PopToHUD();
            Directory.CreateDirectory(dir);
            if (GameObject.FindWithTag("Player") == null)
            {
                File.WriteAllText(Path.Combine(dir, "report.txt"), "error: the game scene never loaded (is the Arena2 path set?)\n");
                Application.Quit();
                yield break;
            }
            yield return new WaitForSecondsRealtime(2f);
            StringBuilder report = new StringBuilder();
            IEnumerator run = Run(report);
            while (true)
            {
                bool more;
                try { more = run.MoveNext(); }
                catch (Exception e) { report.AppendLine("error " + e); more = false; }
                if (!more) break;
                yield return run.Current;
            }
            File.WriteAllText(Path.Combine(dir, "report.txt"), report.ToString());
            Application.Quit();
        }

        IEnumerator Run(StringBuilder report)
        {
            DoomerfallAreaLevels.Warm();
            report.AppendLine(DoomerfallAreaLevels.Status());
            IUserInterfaceManager ui = DaggerfallUI.Instance.UserInterfaceManager;
            TestWindow window = new TestWindow(ui);
            ui.PushWindow(window);
            yield return null;
            yield return null;

            foreach (string[] entry in Places)
            {
                string[] place = entry[1] == CovenMarker ? new[] { entry[0], FirstOfType(entry[0], DFRegion.LocationTypes.Coven) } : entry;
                ContentReader.MapSummary summary;
                DFLocation location;
                if (!Find(place[0], place[1], out summary, out location))
                {
                    report.AppendFormat("{0} / {1}: not found\n", place[0], place[1]);
                    continue;
                }
                window.Show(summary);
                for (int i = 0; i < 10; i++)
                    yield return null;
                DoomerfallAreaLevels.Level level;
                DoomerfallAreaLevels.ForLocation(location, out level);
                string file = Safe(place[1]) + ".png";
                report.AppendFormat("{0} / {1}: type {2}, dungeon {3}, terrain {4}, area {5}, shown word {6}, label \"{7}\", file {8}\n", place[0], place[1],
                    summary.LocationType, level.dungeon, level.terrain, level.Area, DoomerfallTravelHint.ForLocation(summary) ?? "(none)", window.Label, file);
                ScreenCapture.CaptureScreenshot(Path.Combine(dir, file));
                yield return new WaitForEndOfFrame();
                yield return null;
            }

            // The confirmation box the Find Location button shows: the castle has a Danger line, the city none.
            yield return ConfirmShot(window, ui, report, "Castle Necromoghan", "confirm.png");
            yield return ConfirmShot(window, ui, report, "Daggerfall", "confirm_city.png");
            report.AppendLine("done");
        }

        IEnumerator ConfirmShot(TestWindow window, IUserInterfaceManager ui, StringBuilder report, string name, string file)
        {
            ContentReader.MapSummary summary;
            DFLocation unused;
            if (!Find("Daggerfall", name, out summary, out unused))
                yield break;
            for (int pops = 0; ui.TopWindow != window && pops < 5; pops++)
            {
                ui.PopWindow();
                yield return null;
            }
            window.Show(summary);
            for (int i = 0; i < 5; i++)
                yield return null;
            window.Confirm();
            for (int i = 0; i < 10; i++)
                yield return null;
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, file));
            yield return new WaitForEndOfFrame();
            yield return null;
            report.AppendLine("confirm " + name + ": top window " + ui.TopWindow.GetType().Name + ", file " + file);
        }

        static bool Find(string region, string name, out ContentReader.MapSummary summary, out DFLocation location)
        {
            summary = default(ContentReader.MapSummary);
            if (!DaggerfallUnity.Instance.ContentReader.GetLocation(region, name, out location))
                return false;
            DFPosition pixel = MapsFile.LongitudeLatitudeToMapPixel(location.MapTableData.Longitude, location.MapTableData.Latitude);
            return DaggerfallUnity.Instance.ContentReader.HasLocation(pixel.X, pixel.Y, out summary);
        }

        static string FirstOfType(string region, DFRegion.LocationTypes type)
        {
            DFRegion data = DaggerfallUnity.Instance.ContentReader.MapFileReader.GetRegion(region);
            for (int i = 0; data.MapTable != null && i < data.MapTable.Length; i++)
                if (data.MapTable[i].LocationType == type)
                    return data.MapNames[i];
            return "(no " + type + " in " + region + ")";
        }

        static string Safe(string name)
        {
            StringBuilder b = new StringBuilder();
            foreach (char c in name)
                b.Append(char.IsLetterOrDigit(c) ? c : '_');
            return b.ToString();
        }

        sealed class TestWindow : DaggerfallTravelMapWindow
        {
            bool forced;
            ContentReader.MapSummary forcedSummary;

            internal TestWindow(IUserInterfaceManager uiManager) : base(uiManager) { }

            internal string Label { get { return regionLabel.Text; } }

            internal void Show(ContentReader.MapSummary summary)
            {
                forcedSummary = summary;
                forced = true;
                if (!RegionSelected || selectedRegion != summary.RegionIndex)
                    OpenRegionPanel(summary.RegionIndex);
                UpdateMouseOverLocation(); // the real window calls this only when the mouse moves
            }

            internal void Confirm()
            {
                CreateConfirmationPopUp();
            }

            protected override void UpdateMouseOverLocation()
            {
                if (!forced)
                {
                    base.UpdateMouseOverLocation();
                    return;
                }
                mouseOverRegion = selectedRegion;
                locationSummary = forcedSummary;
                locationSelected = true;
            }
        }
    }
}
