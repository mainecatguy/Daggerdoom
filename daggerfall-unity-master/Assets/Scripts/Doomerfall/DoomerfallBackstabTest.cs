// Doomerfall test only (-dfbackstabtest <file> <skill>): sets the character's Backstabbing skill to <skill> once a game is
// running, then writes the backstab multiplier Daggerfall publishes and every change to the Backstabbing tally to <file>,
// with the time, so a paired runner (tools/backstab/backstab.py) can check the damage and the uses from sneak hits.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallBackstabTest : MonoBehaviour
    {
        const DFCareer.Skills Backstabbing = DFCareer.Skills.Backstabbing;

        string path;
        short skill;
        bool ready;
        float readyAt;
        short uses;
        DoomerfallPositionSync sync;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfbackstabtest");
            short skill;
            if (at < 0 || at + 2 >= args.Length || !short.TryParse(args[at + 2], out skill))
                return;
            GameObject host = new GameObject("DoomerfallBackstabTest");
            DontDestroyOnLoad(host);
            DoomerfallBackstabTest test = host.AddComponent<DoomerfallBackstabTest>();
            test.path = args[at + 1];
            test.skill = skill;
            File.WriteAllText(test.path, "backstab: started, skill " + skill + "\n");
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
                player.Skills.SetPermanentSkillValue(Backstabbing, skill);
                uses = player.SkillUses[(int)Backstabbing];
                int live = player.Skills.GetLiveSkillValue(Backstabbing);
                Write(string.Format("start Backstabbing: skill {0}, live {1}, multiplier x{2:0.####}, uses {3}, {4} uses per sneak hit",
                    skill, live, DoomerfallDamageBonus.BackstabMultiplier(live), uses, DoomerfallBackstab.UsesPerSneakHit));
            }
            short now = player.SkillUses[(int)Backstabbing];
            if (now != uses)
            {
                Write(string.Format("tally Backstabbing: uses {0} -> {1}", uses, now));
                uses = now;
            }
        }
    }
}
