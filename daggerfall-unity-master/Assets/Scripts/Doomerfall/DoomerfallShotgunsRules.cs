// Doomerfall: the Shotguns skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_SHOT_*); Doom applies them to guns whose skill is Shotguns
// (mods/doomerfall/src/zscript/DoomerfallShotguns.zs).
//
// Owner rules (the Shotguns perks card):
//   - damage +0% to +75% by skill;
//   - 25: reloads about 35% faster;
//   - 50: +50% pellets;
//   - 75: knockback scaled by enemy size, with stagger, up to +200 damage on a wall slam, once per shot;
//   - 100: +100% pellets, knockback and its damage up to 2x.
// Still open, so not chosen: how much damage a knocked enemy and what it collides with take (sent as 0, so off), how
// much faster reloads are at 100 (it stays at the 25 perk's 35%), and how a slower shotgun's stronger knockback is
// measured.
//
// The live skill decides, as for Automatics, so a drained or fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShotgunsRules
    {
        public const int MaxDamageBp = 7500;
        public const int ReloadLevel = 25, ReloadBp = 3500;
        public const int MorePelletsLevel = 50, MorePelletsBp = 5000;
        public const int KnockLevel = 75, KnockBp = 10000, SlamDamage = 200;
        public const int MostPelletsLevel = 100, MostPelletsBp = 10000, MostKnockBp = 20000, MostSlamDamage = 400;
        public const int CollideDamage = 0, MostCollideDamage = 0; // Open: owner tentative 200 at 75, 400 at 100.

        public static void Fill(int[] values, PlayerEntity player)
        {
            int skill = player.Skills.GetLiveSkillValue((DFCareer.Skills)Dfb.SKILL_SHOTGUNS);
            Fill(values, skill);
        }

        public static void Fill(int[] values, int skill)
        {
            int clamped = skill < 0 ? 0 : skill > 100 ? 100 : skill;
            bool most = skill >= MostPelletsLevel, knock = skill >= KnockLevel;
            values[Dfb.SHEET_SHOT_DAMAGE_BP] = MaxDamageBp * clamped / 100;
            values[Dfb.SHEET_SHOT_RELOAD_BP] = skill >= ReloadLevel ? ReloadBp : 0;
            values[Dfb.SHEET_SHOT_PELLET_BP] = most ? MostPelletsBp : skill >= MorePelletsLevel ? MorePelletsBp : 0;
            values[Dfb.SHEET_SHOT_KNOCK_BP] = most ? MostKnockBp : knock ? KnockBp : 0;
            values[Dfb.SHEET_SHOT_SLAM_DAMAGE] = most ? MostSlamDamage : knock ? SlamDamage : 0;
            values[Dfb.SHEET_SHOT_COLLIDE_DAMAGE] = most ? MostCollideDamage : knock ? CollideDamage : 0;
        }
    }
}
