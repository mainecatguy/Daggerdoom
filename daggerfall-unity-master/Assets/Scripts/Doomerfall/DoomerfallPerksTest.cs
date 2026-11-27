// Doomerfall test only (-dfperktest <skill name>, for example Jumping): a while after play starts, sets that skill's
// permanent value to 20 and then to 26, so DoomerfallPerks sees it cross 25 and opens the perk window.
// -dfperksteps <v1,v2,...> sets those values instead, one every StepSeconds (tools/automatics/automatics_paired.py).

using System;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallPerksTest : MonoBehaviour
    {
        const float StartAfterSeconds = 8f, RaiseAfterSeconds = 1f, StepSeconds = 7f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DFCareer.Skills skill;
        float lowered, playSince;
        int step;
        int[] values = { 20, 26 };

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-dfperktest");
            if (i < 0)
                return;
            DoomerfallPerksTest test = owner.gameObject.AddComponent<DoomerfallPerksTest>();
            test.bridge = owner;
            test.sync = positionSync;
            string name = i + 1 < args.Length ? args[i + 1] : "Jumping";
            if (!Enum.IsDefined(typeof(DFCareer.Skills), name))
            {
                owner.LogLine("perktest: no skill named " + name);
                Destroy(test);
                return;
            }
            test.skill = (DFCareer.Skills)Enum.Parse(typeof(DFCareer.Skills), name);
            int s = Array.IndexOf(args, "-dfperksteps");
            if (s >= 0 && s + 1 < args.Length)
                test.values = Array.ConvertAll(args[s + 1].Split(','), int.Parse);
        }

        void Update()
        {
            if (step >= values.Length || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || !sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY)
            {
                playSince = 0;
                return;
            }
            if (playSince == 0)
                playSince = Time.unscaledTime;
            if (step == 0 && Time.unscaledTime - playSince > StartAfterSeconds && DaggerfallUI.UIManager.TopWindow is DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallHUD)
            {
                GameManager.Instance.PlayerEntity.Skills.SetPermanentSkillValue(skill, (short)values[0]);
                lowered = Time.unscaledTime;
                step = 1;
                bridge.LogLine("perktest: " + skill + " set to " + values[0]);
            }
            else if (step >= 1 && Time.unscaledTime - lowered > (step == 1 ? RaiseAfterSeconds : StepSeconds))
            {
                GameManager.Instance.PlayerEntity.Skills.SetPermanentSkillValue(skill, (short)values[step]);
                lowered = Time.unscaledTime;
                bridge.LogLine("perktest: " + skill + " raised to " + values[step]);
                step++;
            }
        }
    }
}
