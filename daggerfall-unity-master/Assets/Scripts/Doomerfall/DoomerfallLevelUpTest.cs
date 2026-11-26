// Doomerfall test only (-dfleveluptest <file> [travel]): once the game runs, earns the character exactly one level by
// raising its primary skills, then runs Daggerfall's own skill check, as resting and fast travel do
// (PlayerEntity.RaiseSkills). With "travel" it skips that call, so the check comes from a real fast travel instead.
// Daggerfall then opens its character sheet with the level-up bonus points by itself. Logs, each time it changes, the
// top window, whether the sheet is levelling and its bonus pool, and the player's level, stats and max health, so a
// test can see Doom show the sheet, the points being spent, and the result.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLevelUpTest : MonoBehaviour
    {
        const BindingFlags Field = BindingFlags.Instance | BindingFlags.NonPublic;

        string path, last;
        DoomerfallPositionSync sync;
        float readyAt;
        bool earned, travel;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfleveluptest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallLevelUpTest");
            DontDestroyOnLoad(host);
            DoomerfallLevelUpTest test = host.AddComponent<DoomerfallLevelUpTest>();
            test.path = args[at + 1];
            test.travel = at + 2 < args.Length && args[at + 2] == "travel";
            File.WriteAllText(test.path, "levelup: started\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Earn(); }
            catch (Exception e) { Write("earn error " + e.GetType().Name + " " + e.Message); earned = true; }
            string line;
            try { line = Describe(); }
            catch (Exception e) { line = "error " + e.GetType().Name + " " + e.Message; }
            if (line == last)
                return;
            last = line;
            Write(line);
        }

        void Earn()
        {
            if (earned || !GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null)
            {
                readyAt = 0;
                return;
            }
            if (readyAt == 0)
                readyAt = Time.realtimeSinceStartup + 3f; // Let the test start's placement settle first.
            if (Time.realtimeSinceStartup < readyAt)
                return;
            earned = true;

            // Raise primary skills one point at a time until Daggerfall's level formula gives exactly one more level.
            int level = player.Level, raised = 0;
            var primary = player.GetPrimarySkills();
            for (int i = 0; i < 600 && FormulaHelper.CalculatePlayerLevel(player.StartingLevelUpSkillSum, player.CurrentLevelUpSkillSum) <= level; i++)
            {
                DFCareer.Skills skill = primary[i % primary.Count];
                short value = player.Skills.GetPermanentSkillValue(skill);
                if (value >= 95)
                    continue;
                player.Skills.SetPermanentSkillValue(skill, (short)(value + 1));
                player.SetCurrentLevelUpSkillSum();
                raised++;
            }
            Write(string.Format("earned level {0} -> formula {1} after {2} skill points", level,
                FormulaHelper.CalculatePlayerLevel(player.StartingLevelUpSkillSum, player.CurrentLevelUpSkillSum), raised));

            // The skill check resting and fast travel run. Its six-hour wait is skipped.
            player.TimeOfLastSkillIncreaseCheck = 0;
            if (travel)
            {
                Write("waiting for a fast travel to run the skill check");
                return;
            }
            player.RaiseSkills();
            Write("skill check ran, ready to level up " + player.ReadyToLevelUp);
        }

        static string Describe()
        {
            if (!DaggerfallUI.Instance || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return "none";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            string view = "";
            var sheet = top as DaggerfallCharacterSheetWindow;
            if (sheet != null)
            {
                Type t = typeof(DaggerfallCharacterSheetWindow);
                bool leveling = (bool)t.GetField("leveling", Field).GetValue(sheet);
                var rollout = (StatsRollout)t.GetField("statsRollout", Field).GetValue(sheet);
                view = string.Format("leveling {0} pool {1}", leveling, leveling && rollout != null ? rollout.BonusPool : -1);
                if (leveling && rollout != null && rollout.WorkingStats != null)
                    view += " working " + Stats(rollout.WorkingStats);
            }
            else if (top is DaggerfallMessageBox)
            {
                view = "message box";
            }
            PlayerEntity p = GameManager.Instance.PlayerEntity;
            return string.Format("top {0} view {1} | level {2} stats {3} maxhp {4}", top == null ? "none" : top.GetType().Name, view,
                p.Level, Stats(p.Stats), p.MaxHealth);
        }

        static string Stats(DaggerfallStats stats)
        {
            var values = new string[DaggerfallStats.Count];
            for (int i = 0; i < DaggerfallStats.Count; i++)
                values[i] = stats.GetPermanentStatValue(i).ToString();
            return string.Join(",", values);
        }
    }
}
