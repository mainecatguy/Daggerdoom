// Doomerfall test only (-dfskillpointtest <file>): once the game runs, earns skill points the way play does, by giving
// skills enough uses and running Daggerfall's own skill check (PlayerEntity.RaiseSkills, which rest and fast travel call).
// Round 1 raises Climbing alone; round 2, a few seconds later, raises Climbing and Running in the same check. Logs each
// round and the skill values, so a test can match them to Doom's log (HUD messages and "ui sound" lines).
// With "prime" after the file it runs no check itself; see Prime.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSkillPointTest : MonoBehaviour
    {
        const float FirstDelay = 3f, RoundGap = 6f;

        string path;
        DoomerfallPositionSync sync;
        float nextAt;
        int round;
        bool prime;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfskillpointtest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallSkillPointTest");
            DontDestroyOnLoad(host);
            DoomerfallSkillPointTest test = host.AddComponent<DoomerfallSkillPointTest>();
            test.path = args[at + 1];
            test.prime = at + 2 < args.Length && args[at + 2] == "prime";
            File.WriteAllText(args[at + 1], "skill point test: started\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void Update()
        {
            if (round >= 2 || !GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || sync.LoadRunning || sync.Phase != Dfb.DF_PHASE_PLAY || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null ||
                !(prime || DaggerfallUI.UIManager.TopWindow is UserInterfaceWindows.DaggerfallHUD))
            {
                nextAt = 0;
                return;
            }
            if (nextAt == 0)
                nextAt = Time.realtimeSinceStartup + (prime ? 0.01f : round == 0 ? FirstDelay : RoundGap);
            if (Time.realtimeSinceStartup < nextAt)
                return;
            nextAt = 0;
            round++;
            if (prime)
            {
                Prime(player);
                return;
            }
            try { Raise(player, round == 1 ? new[] { DFCareer.Skills.Climbing } : new[] { DFCareer.Skills.Climbing, DFCareer.Skills.Running }); }
            catch (Exception e) { Write("error " + e.GetType().Name + " " + e.Message); round = 2; }
        }

        void Raise(PlayerEntity player, DFCareer.Skills[] skills)
        {
            // As DoomerfallLevelUpTest: line the level formula up with the current level, so these points (fewer than the
            // 15 a level needs) cannot open the level-up sheet; the blank test character's starting sum would.
            player.SetCurrentLevelUpSkillSum();
            player.StartingLevelUpSkillSum = player.CurrentLevelUpSkillSum + 28 - 15 * player.Level;
            string before = Values(player, skills);
            foreach (DFCareer.Skills skill in skills)
                player.TallySkill(skill, 20000); // Capped at 20000 by TallySkill; far more than one point needs below 95.
            player.TimeOfLastSkillIncreaseCheck = 0;
            player.RaiseSkills();
            Write(string.Format("round {0}: skill check ran, {1} -> {2} (ready to level up {3})", round, before, Values(player, skills), player.ReadyToLevelUp));
        }

        // "prime": only gives Climbing its uses and clears the six-hour wait, so the next real rest or fast travel raises it
        // through Daggerfall's own skill check. Also takes the player to a quarter of their health, so Rest Until Healed rests.
        void Prime(PlayerEntity player)
        {
            round = 2;
            player.SetCurrentLevelUpSkillSum();
            player.StartingLevelUpSkillSum = player.CurrentLevelUpSkillSum + 28 - 15 * player.Level;
            player.TallySkill(DFCareer.Skills.Climbing, 20000);
            player.TimeOfLastSkillIncreaseCheck = 0;
            player.CurrentHealth = Math.Max(1, player.MaxHealth / 4);
            Write("primed: " + Values(player, new[] { DFCareer.Skills.Climbing }) + ", the next rest or fast travel raises it");
        }

        static string Values(PlayerEntity player, DFCareer.Skills[] skills)
        {
            string text = "";
            foreach (DFCareer.Skills skill in skills)
                text += (text.Length > 0 ? ", " : "") + skill + " " + player.Skills.GetPermanentSkillValue(skill);
            return text;
        }
    }
}
