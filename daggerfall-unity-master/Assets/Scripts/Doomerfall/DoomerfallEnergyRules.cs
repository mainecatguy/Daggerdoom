// Doomerfall: the Energy Weapons skill's rules, before burn (perks card 06). Daggerfall owns skills and their perks, so
// it decides the numbers and sends them to Doom in the character sheet (DFB_SHEET_ENERGY_*); Doom applies them to shots
// from guns whose skill is Energy Weapons (mods/doomerfall/src/zscript/DoomerfallEnergy.zs).
//
// Owner rules (work/backlog/skills-in-doom.md, Energy Weapons, final design 2026-11-26):
//   - damage +0% to +50% by skill;
//   - 25: a hit that does not explode also deals 20% of its damage to other enemies nearby (radius 64, from the approved
//     Revision 2 numbers; never the player, never the enemy that was hit);
//   - 25, 50, 75, 100: the guns' projectiles fly 15% faster at each, so +60% at 100.
// Plasma burn (cards 07 and 08) is not sent yet.
//
// The live skill decides, as for the other gun skills, so a drained or fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallEnergyRules
    {
        public const int MaxDamageBp = 5000;
        public const int SplashLevel = 25, SplashBp = 2000, SplashRadius = 64;
        public const int SpeedStepBp = 1500; // at each of 25, 50, 75 and 100

        public static void Fill(int[] values, PlayerEntity player)
        {
            int skill = player.Skills.GetLiveSkillValue((DFCareer.Skills)Dfb.SKILL_ENERGY);
            Fill(values, skill);
        }

        public static void Fill(int[] values, int skill)
        {
            int clamped = skill < 0 ? 0 : skill > 100 ? 100 : skill;
            values[Dfb.SHEET_ENERGY_DAMAGE_BP] = MaxDamageBp * clamped / 100;
            bool splash = skill >= SplashLevel;
            values[Dfb.SHEET_ENERGY_SPLASH_BP] = splash ? SplashBp : 0;
            values[Dfb.SHEET_ENERGY_SPLASH_RADIUS] = splash ? SplashRadius : 0;
            values[Dfb.SHEET_ENERGY_SPEED_BP] = SpeedStepBp * (clamped / 25);
        }
    }
}
