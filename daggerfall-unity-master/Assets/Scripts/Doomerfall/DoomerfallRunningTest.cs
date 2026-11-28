// Doomerfall test only (-dfrunningtest <file> [prime]): follows Daggerfall's Running skill tally in a paired run (running
// in Doom, DoomerfallRunning.cs), writing each change to <file> with the time, so a runner can measure the rate.
// With "prime", Running starts Primed uses short of Daggerfall's advancement threshold (and again after each rise), and
// after each tally Daggerfall's own skill check (PlayerEntity.RaiseSkills) runs, so a few seconds of running show the
// skill rising. If a rise earns a level, it closes the character sheet Daggerfall opens, so Doom keeps running.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallRunningTest : MonoBehaviour
    {
        const DFCareer.Skills Running = DFCareer.Skills.Running;
        const int Primed = 40;

        string path;
        bool prime, ready;
        float readyAt, sheetSeenAt;
        short uses, value;
        DoomerfallPositionSync sync;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfrunningtest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallRunningTest");
            DontDestroyOnLoad(host);
            DoomerfallRunningTest test = host.AddComponent<DoomerfallRunningTest>();
            test.path = args[at + 1];
            test.prime = at + 2 < args.Length && args[at + 2] == "prime";
            File.WriteAllText(test.path, "running: started" + (test.prime ? " (prime)" : "") + "\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F3} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Step(); }
            catch (Exception e) { Write("error " + e.GetType().Name + " " + e.Message); }
        }

        void Step()
        {
            if (!GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null)
            {
                readyAt = 0;
                return;
            }
            if (!ready)
            {
                if (readyAt == 0)
                    readyAt = Time.realtimeSinceStartup + 1f;
                if (Time.realtimeSinceStartup < readyAt)
                    return;
                ready = true;
                Prime(player);
                Write(string.Format("start Running: skill {0}, uses {1} of {2} needed, Daggerfall {3:F4} s per use, Doom {4:F4} s per use",
                    value, uses, DoomerfallSkillBasicsTest.UsesToAdvance(player, Running), DoomerfallRunning.DaggerfallSecondsPerUse,
                    DoomerfallRunning.DaggerfallSecondsPerUse / 1.5));
            }
            Watch(player);
            CloseLevelUpSheet();
        }

        // A rise can earn a level, and Daggerfall then opens the character sheet, which holds Doom still. The timed run
        // must go on, so the test closes it after a moment (the bonus points stay unspent).
        void CloseLevelUpSheet()
        {
            var sheet = DaggerfallUI.Instance ? DaggerfallUI.UIManager.TopWindow as UserInterfaceWindows.DaggerfallCharacterSheetWindow : null;
            if (sheet == null)
            {
                sheetSeenAt = 0;
                return;
            }
            if (sheetSeenAt == 0)
                sheetSeenAt = Time.realtimeSinceStartup;
            if (Time.realtimeSinceStartup - sheetSeenAt < 0.5f)
                return;
            Write("closing the character sheet Daggerfall opened for a level up");
            sheet.CloseWindow();
            sheetSeenAt = 0;
        }

        void Prime(PlayerEntity player)
        {
            if (prime)
                player.SkillUses[(int)Running] = (short)Math.Max(0, DoomerfallSkillBasicsTest.UsesToAdvance(player, Running) - Primed);
            uses = player.SkillUses[(int)Running];
            value = player.Skills.GetPermanentSkillValue(Running);
        }

        void Watch(PlayerEntity player)
        {
            short now = player.SkillUses[(int)Running];
            if (now == uses)
                return;
            Write(string.Format("tally Running: uses {0} -> {1}", uses, now));
            bool tallied = now > uses;
            uses = now;
            if (!tallied || !prime)
                return;
            player.TimeOfLastSkillIncreaseCheck = 0;
            player.RaiseSkills();
            short raised = player.Skills.GetPermanentSkillValue(Running);
            if (raised != value)
            {
                Write(string.Format("advance Running: skill {0} -> {1}, uses now {2}", value, raised, player.SkillUses[(int)Running]));
                Prime(player);
                Write(string.Format("primed again: uses {0}", uses));
            }
            uses = player.SkillUses[(int)Running];
        }
    }
}
