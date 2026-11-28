// Doomerfall: the Automatics skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_AUTO_*); Doom applies them to guns whose skill is Automatics
// (mods/doomerfall/src/zscript/DoomerfallAutomatics.zs).
//
// Owner rules (work/backlog/skills-in-doom.md, Automatics; skillperks 02 and 09; gamedesign/decisions/
// 20261127-automatics-tuning-owner.md):
//   - damage +0% to +60% by skill;
//   - 25: burst fire, +30% damage on the first 3 shots of a burst, restarting 0.3 s after the burst ends;
//         every third shot spends no ammo (until 50);
//   - 50: one ammo per 2 shots (replaces the 25 saving); band bonuses by the gun's own base tics between shots:
//         slow (4+) +25 base damage and +1 penetration, middle (3) +7 and +1 penetration, fast (1-2) a 10% chance of
//         one extra free bullet per shot;
//   - 75: each hit makes the enemy take +1% damage from all sources, stacking to +15%, permanently; each hit slows
//         the enemy's movement 5% more, up to 40%, fading evenly to nothing over 5 s after the last hit;
//   - 100: one ammo per 4 shots; the damage-taken stack grows +2% per hit, to +30% in total.
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
        public const int FreeEveryLevel = 25, FreeEvery = 3;
        public const int HalfAmmoLevel = 50, QuarterAmmoLevel = 100;
        public const int BandLevel = 50, SlowDamage = 25, SlowPen = 1, MidDamage = 7, MidPen = 1, FastExtraBp = 1000;
        public const int SunderLevel = 75, SunderBp = 100, SunderMaxBp = 1500;
        public const int BigSunderLevel = 100, BigSunderBp = 200, BigSunderMaxBp = 3000;
        public const int SuppressLevel = 75, SuppressHitBp = 500, SuppressMaxBp = 4000, SuppressFadeMs = 5000;

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
            int perAmmo = skill >= QuarterAmmoLevel ? 4 : skill >= HalfAmmoLevel ? 2 : 1;
            values[Dfb.SHEET_AUTO_SHOTS_PER_AMMO] = perAmmo;
            values[Dfb.SHEET_AUTO_FREE_EVERY] = skill >= FreeEveryLevel && perAmmo == 1 ? FreeEvery : 0; // they do not stack
            bool bands = skill >= BandLevel;
            values[Dfb.SHEET_AUTO_SLOW_DAMAGE] = bands ? SlowDamage : 0;
            values[Dfb.SHEET_AUTO_SLOW_PEN] = bands ? SlowPen : 0;
            values[Dfb.SHEET_AUTO_MID_DAMAGE] = bands ? MidDamage : 0;
            values[Dfb.SHEET_AUTO_MID_PEN] = bands ? MidPen : 0;
            values[Dfb.SHEET_AUTO_FAST_EXTRA_BP] = bands ? FastExtraBp : 0;
            bool big = skill >= BigSunderLevel, sunder = skill >= SunderLevel;
            values[Dfb.SHEET_AUTO_SUNDER_BP] = big ? BigSunderBp : sunder ? SunderBp : 0;
            values[Dfb.SHEET_AUTO_SUNDER_MAX_BP] = big ? BigSunderMaxBp : sunder ? SunderMaxBp : 0;
            bool suppress = skill >= SuppressLevel;
            values[Dfb.SHEET_AUTO_SLOW_HIT_BP] = suppress ? SuppressHitBp : 0;
            values[Dfb.SHEET_AUTO_SLOW_MAX_BP] = suppress ? SuppressMaxBp : 0;
            values[Dfb.SHEET_AUTO_SLOW_FADE_MS] = suppress ? SuppressFadeMs : 0;
        }
    }
}
