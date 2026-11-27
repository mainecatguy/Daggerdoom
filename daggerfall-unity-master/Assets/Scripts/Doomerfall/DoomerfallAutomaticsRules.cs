// Doomerfall: the Automatics skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_AUTO_*); Doom applies them to guns whose skill is Automatics
// (mods/doomerfall/src/zscript/DoomerfallAutomatics.zs).
//
// Owner rules (work/backlog/skills-in-doom.md, Automatics; the perks card):
//   - damage +0% to +60% by skill;
//   - 25: burst fire, +30% damage on the first 3 shots of a burst, restarting 0.3 s after the burst ends;
//   - 50: one ammo per 2 shots;
//   - 75: each hit makes the enemy take +1% damage from all sources, stacking to +15%, permanently;
//   - 100: one ammo per 4 shots.
// Still open, so not sent: the 75 suppression slow and the three fire-rate bands.
//
// The live skill decides, as the gun's skill choice does (DoomerfallWeaponCategory.SkillSlotOf), so a drained or
// fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallAutomaticsRules
    {
        public const int MaxDamageBp = 6000;
        public const int BurstLevel = 25, BurstBp = 3000, BurstShots = 3, BurstResetMs = 300;
        public const int HalfAmmoLevel = 50, QuarterAmmoLevel = 100;
        public const int SunderLevel = 75, SunderBp = 100, SunderMaxBp = 1500;

        public static void Fill(int[] values, PlayerEntity player)
        {
            int skill = player.Skills.GetLiveSkillValue((DFCareer.Skills)Dfb.SKILL_AUTOMATICS);
            Fill(values, skill);
        }

        public static void Fill(int[] values, int skill)
        {
            int clamped = skill < 0 ? 0 : skill > 100 ? 100 : skill;
            values[Dfb.SHEET_AUTO_DAMAGE_BP] = MaxDamageBp * clamped / 100;
            bool burst = skill >= BurstLevel;
            values[Dfb.SHEET_AUTO_BURST_BP] = burst ? BurstBp : 0;
            values[Dfb.SHEET_AUTO_BURST_SHOTS] = burst ? BurstShots : 0;
            values[Dfb.SHEET_AUTO_BURST_RESET_MS] = burst ? BurstResetMs : 0;
            values[Dfb.SHEET_AUTO_SHOTS_PER_AMMO] = skill >= QuarterAmmoLevel ? 4 : skill >= HalfAmmoLevel ? 2 : 1;
            bool sunder = skill >= SunderLevel;
            values[Dfb.SHEET_AUTO_SUNDER_BP] = sunder ? SunderBp : 0;
            values[Dfb.SHEET_AUTO_SUNDER_MAX_BP] = sunder ? SunderMaxBp : 0;
        }
    }
}
