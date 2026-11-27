// Doomerfall test only (-dfattrhelptest <dir>): opens Daggerfall's character sheet, left-clicks each attribute through
// the sheet's own click handler, and saves a screenshot of each popup (stat_<n>_<name>.png) plus report.txt with the
// popup's text, then quits. Needs no bridge session: it sets DoomerfallAttributeHelp.ShowWithoutSession, and gives the
// player fixed attributes and level so the "Yours" lines can be checked against the formulas by hand.
// Starts itself from the flag; no game class calls it.

using System;
using System.Collections;
using System.IO;
using System.Reflection;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAttributeHelpTest : MonoBehaviour
    {
        // Strength, Intelligence, Willpower, Agility, Endurance, Personality, Speed, Luck.
        static readonly int[] TestStats = { 62, 45, 70, 33, 55, 40, 80, 120 };
        const int TestLevel = 5;

        string dir;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfattrhelptest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallAttributeHelpTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallAttributeHelpTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            // Same scene start as DoomerfallHotkeyShotsTest.
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
            var report = new StringBuilder();
            if (GameObject.FindWithTag("Player") == null)
                report.AppendLine("error: the game scene never loaded (is the Arena2 path set?)");
            else
            {
                yield return new WaitForSecondsRealtime(2f);
                IEnumerator run = Run(report);
                while (true)
                {
                    bool more;
                    try { more = run.MoveNext(); }
                    catch (Exception e) { report.AppendLine("error " + e); more = false; }
                    if (!more) break;
                    yield return run.Current;
                }
            }
            File.WriteAllText(Path.Combine(dir, "report.txt"), report.ToString());
            Application.Quit();
        }

        IEnumerator Run(StringBuilder report)
        {
            DoomerfallAttributeHelp.ShowWithoutSession = true;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            player.Level = TestLevel;
            for (int i = 0; i < DaggerfallStats.Count; i++)
                player.Stats.SetPermanentStatValue(i, TestStats[i]);
            report.AppendLine("level " + player.Level + " live stats " + string.Join(",", Array.ConvertAll(TestStats, s => s.ToString())));

            IUserInterfaceManager ui = DaggerfallUI.Instance.UserInterfaceManager;
            var sheet = new DaggerfallCharacterSheetWindow(ui);
            ui.PushWindow(sheet);
            for (int i = 0; i < 10; i++)
                yield return null;
            MethodInfo click = typeof(DaggerfallCharacterSheetWindow).GetMethod("StatButton_OnMouseClick", BindingFlags.Instance | BindingFlags.NonPublic);
            if (click == null)
            {
                report.AppendLine("error: StatButton_OnMouseClick not found");
                yield break;
            }

            for (int i = 0; i < DaggerfallStats.Count; i++)
            {
                var stat = (DFCareer.Stats)i;
                int id = DaggerfallUnity.Instance.TextProvider.GetStatDescriptionTextID(stat);
                var button = new Button { Tag = id };
                click.Invoke(sheet, new object[] { button, Vector2.zero });
                for (int f = 0; f < 5; f++)
                    yield return null;
                var box = ui.TopWindow as DaggerfallMessageBox;
                report.AppendLine(string.Format("== {0} (text {1}) top {2}", stat, id, ui.TopWindow == null ? "none" : ui.TopWindow.GetType().Name));
                foreach (TextFile.Token t in DoomerfallAttributeHelp.Build(id, player) ?? new TextFile.Token[0])
                    if (t.formatting == TextFile.Formatting.Text)
                        report.AppendLine("  " + t.text);
                string file = string.Format("stat_{0}_{1}.png", i, stat);
                ScreenCapture.CaptureScreenshot(Path.Combine(dir, file));
                yield return new WaitForEndOfFrame();
                yield return null;
                if (box != null)
                    box.CloseWindow();
                for (int f = 0; f < 3; f++)
                    yield return null;
            }
            report.AppendLine("done");
        }
    }
}
