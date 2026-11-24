// Doomerfall test only (-dfreflexprobe <Daggerfall folder> <report file>): a plain Daggerfall Unity launch, with no
// bridge session. Opens the real new game wizard, fills in its default character, closes the bonus skills screen as
// its OK would, and writes which window the wizard opens next. Outside a Doom session that must still be Daggerfall's
// Reflexes screen. Needs a portable install so the Daggerfall folder is set in memory only. Quits when done.

using System;
using System.Collections;
using System.IO;
using System.Reflection;
using System.Text;
using DaggerfallWorkshop.Game.Player;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallReflexProbe : MonoBehaviour
    {
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        string daggerfallPath, reportPath;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfreflexprobe");
            if (at < 0 || at + 2 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallReflexProbe");
            DontDestroyOnLoad(host);
            DoomerfallReflexProbe probe = host.AddComponent<DoomerfallReflexProbe>();
            probe.daggerfallPath = args[at + 1];
            probe.reportPath = args[at + 2];
        }

        IEnumerator Start()
        {
            StringBuilder report = new StringBuilder();
            if (!DaggerfallUnityApplication.IsPortableInstall)
            {
                File.WriteAllText(reportPath, "error: needs a portable install, so the owner's settings stay untouched\n");
                Application.Quit();
                yield break;
            }
            DaggerfallUnity.Settings.MyDaggerfallPath = daggerfallPath; // In memory only.
            Application.runInBackground = true;
            float giveUp = Time.realtimeSinceStartup + 60;
            yield return SceneManager.LoadSceneAsync(1);
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady || GameManager.Instance == null
                || !GameManager.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            for (int i = 0; i < 5; i++)
                yield return null;

            IEnumerator run = Run(report);
            while (true)
            {
                bool more;
                try { more = run.MoveNext(); }
                catch (Exception e) { report.AppendLine("error " + e); more = false; }
                if (!more) break;
                yield return run.Current;
            }
            File.WriteAllText(reportPath, report.ToString());
            Application.Quit();
        }

        static object Stage(StartNewGameWizard wizard)
        {
            return typeof(StartNewGameWizard).GetField("wizardStage", Private).GetValue(wizard);
        }

        IEnumerator Run(StringBuilder report)
        {
            IUserInterfaceManager ui = DaggerfallUI.UIManager;
            report.AppendLine("bridge session: " + DoomerfallBridge.SessionActive + ", fixed reflexes: " + DoomerfallNewGame.FixedReflexes);
            DaggerfallUI.Instance.PopToHUD();
            StartNewGameWizard wizard = new StartNewGameWizard(ui);
            ui.PushWindow(wizard);
            for (int i = 0; i < 3; i++)
                yield return null;
            report.AppendLine("top after opening: " + ui.TopWindow.GetType().Name);

            // The race screen cleared the race. Put the default Breton back, then go to the bonus skills screen.
            CharacterDocument doc = (CharacterDocument)typeof(StartNewGameWizard).GetField("characterDocument", Private).GetValue(wizard);
            doc.raceTemplate = CharacterDocument.GetRaceTemplate(Entity.Races.Breton);
            doc.biographyEffects = new System.Collections.Generic.List<string>();
            typeof(StartNewGameWizard).GetMethod("SetAddBonusSkillsWindow", Private).Invoke(wizard, null);
            yield return null;
            report.AppendLine("stage: " + Stage(wizard) + ", top: " + ui.TopWindow.GetType().Name);

            // Its OK closes it without cancelling. The wizard then picks the next screen.
            ((DaggerfallPopupWindow)ui.TopWindow).CloseWindow();
            for (int i = 0; i < 3; i++)
                yield return null;
            report.AppendLine("after bonus skills OK: stage " + Stage(wizard) + ", top " + ui.TopWindow.GetType().Name);
            CreateCharReflexSelect reflexWindow = ui.TopWindow as CreateCharReflexSelect;
            if (reflexWindow != null)
                report.AppendLine("reflexes offered, preselected " + reflexWindow.PlayerReflexes);
            report.AppendLine(reflexWindow != null ? "result: REFLEXES OFFERED" : "result: REFLEXES SKIPPED");
        }
    }
}
