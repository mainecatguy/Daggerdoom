// Doomerfall: Climbing skill uses from Doom's climb. Doom climbs (mods/doomerfall/src/zscript/DoomerfallClimb.zs) with the
// chances DoomerfallSheet publishes. Input: DFB_KIND_CLIMB_USES, the skill rolls Doom made. Output: Daggerfall's own
// TallySkill, one use per roll as ClimbingMotor does, so advancement stays Daggerfall's.

using DaggerfallConnect;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallClimb
    {
        internal static void OnUses(DoomerfallBridge bridge, uint uses)
        {
            if (!GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || uses == 0)
                return;
            short amount = (short)System.Math.Min(uses, 100u); // Doom rolls about once a second, so a large value is a fault.
            GameManager.Instance.PlayerEntity.TallySkill(DFCareer.Skills.Climbing, amount);
            if (bridge.LogEnabled)
                bridge.LogLine(string.Format("climb: tallied {0} Climbing uses, total {1}", amount,
                    GameManager.Instance.PlayerEntity.SkillUses[(int)DFCareer.Skills.Climbing]));
        }
    }
}
