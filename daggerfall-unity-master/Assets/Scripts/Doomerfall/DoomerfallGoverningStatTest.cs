// Doomerfall test only (-dfgovstattest <file>): writes the text the character sheet's skill lists draw for each weapon
// skill (name, value, governing attribute) and its advancement multiplier to the file, then quits. Needs no bridge
// session. Starts itself from the flag; no game class calls it.

using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallGoverningStatTest : MonoBehaviour
    {
        string file;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfgovstattest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallGoverningStatTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallGoverningStatTest>().file = args[at + 1];
        }

        IEnumerator Start()
        {
            float giveUp = Time.realtimeSinceStartup + 60;
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            Application.runInBackground = true;
            if (GameObject.FindWithTag("Player") == null)
                yield return SceneManager.LoadSceneAsync(1);
            while ((GameObject.FindWithTag("Player") == null || !GameManager.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            yield return new WaitForSecondsRealtime(2f);

            var report = new StringBuilder();
            try
            {
                var weapons = new[]
                {
                    DFCareer.Skills.Shotguns, DFCareer.Skills.Automatics, DFCareer.Skills.Explosives, DFCareer.Skills.Pistols,
                    DFCareer.Skills.Rifles, DFCareer.Skills.EnergyWeapons, DFCareer.Skills.Melee
                };
                foreach (DFCareer.Skills skill in weapons)
                {
                    var drawn = DaggerfallUnity.Instance.TextProvider.GetSkillSummary(skill, 0)
                        .Where(t => !string.IsNullOrEmpty(t.text)).Select(t => t.text).ToArray();
                    report.AppendLine(string.Join(" | ", drawn) + " | advancement " + DaggerfallSkills.GetAdvancementMultiplier(skill));
                }
                report.AppendLine("done");
            }
            catch (Exception e)
            {
                report.AppendLine("error " + e);
            }
            File.WriteAllText(file, report.ToString());
            Application.Quit();
        }
    }
}
