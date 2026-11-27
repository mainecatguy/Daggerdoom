// Doomerfall: the Explosives skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_EXPL_*); Doom applies them to shots from guns whose skill is
// Explosives (mods/doomerfall/src/zscript/DoomerfallExplosives.zs).
//
// Owner rules (work/backlog/skills-in-doom.md, Explosives; the perks card):
//   - damage +0% to +60% by skill;
//   - 25: the player's own splash damage is cut by 95%;
//   - 50: bonus damage to the enemy a shot hits directly. The amount is still open, so 0 is sent (rule off);
//   - 75: the player's own splash damage is cut by 99%;
//   - 100: Inpulsa's Broken Heart: an enemy the explosives kill explodes for 25% of its maximum health, chaining, each
//     generation at half the last, never hurting the player. The radius (128, a Doom rocket's) is an engineering pick.
//
// The live skill decides, as the gun's skill choice does (DoomerfallWeaponCategory.SkillSlotOf), so a drained or
// fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallExplosivesRules
    {
        public const int MaxDamageBp = 6000;
        public const int SelfCutLevel = 25, SelfCutBp = 9500;
        public const int DirectLevel = 50, DirectBp = 0; // open: the owner has not set the amount
        public const int SelfCut2Level = 75, SelfCut2Bp = 9900;
        public const int ChainLevel = 100, ChainBp = 2500, ChainRadius = 128;

        public static void Fill(int[] values, PlayerEntity player)
        {
            int skill = player.Skills.GetLiveSkillValue((DFCareer.Skills)Dfb.SKILL_EXPLOSIVES);
            Fill(values, skill);
        }

        public static void Fill(int[] values, int skill)
        {
            int clamped = skill < 0 ? 0 : skill > 100 ? 100 : skill;
            values[Dfb.SHEET_EXPL_DAMAGE_BP] = MaxDamageBp * clamped / 100;
            values[Dfb.SHEET_EXPL_SELF_CUT_BP] = skill >= SelfCut2Level ? SelfCut2Bp : skill >= SelfCutLevel ? SelfCutBp : 0;
            values[Dfb.SHEET_EXPL_DIRECT_BP] = skill >= DirectLevel ? DirectBp : 0;
            bool chain = skill >= ChainLevel;
            values[Dfb.SHEET_EXPL_CHAIN_BP] = chain ? ChainBp : 0;
            values[Dfb.SHEET_EXPL_CHAIN_RADIUS] = chain ? ChainRadius : 0;
        }
    }
}
