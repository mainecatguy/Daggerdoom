// Doomerfall: the Pistols skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_PIST_*); Doom applies them to guns whose skill is Pistols
// (mods/doomerfall/src/zscript/DoomerfallPistols.zs): stock Doom's Pistol and DRLA's pistol-type guns, never a rifle.
//
// Owner rules (the Pistols perks card):
//   - 25: damage x2.5 for the fastest pistols down to x1.5 for the slowest; reloads 20% faster;
//   - 50: overkill carry-through; a 100-damage bonus pool that every shot spends (hit or miss) and that refills every
//     0.5 s, added after the multipliers; reloads 40% faster;
//   - 75: Deadeye, damage x1.5 for the fastest pistols up to x3 for the slowest, multiplying with the skill 25 one but
//     not the pool; reloads 60% faster;
//   - 100: every pistol hit bursts into 3 hitscan fragments in a 30-degree V, each doing 33% of the hit, locking on to an
//     enemy within 2.5 degrees of its path.
// Fast and slow are DRLA's Scout definition (owner, 2026-11-27): the Scout's pistol damage multiplier, x3 for the
// fastest guns to x8 for the slowest. Doom knows each gun's Scout multiplier; Daggerfall sends the two ends of the scale.
//
// The live skill decides, as for the other gun skills, so a drained or fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallPistolsRules
    {
        public const int SprayLevel = 25, SprayFastBp = 25000, SpraySlowBp = 15000;
        public const int DeadeyeLevel = 75, DeadeyeFastBp = 15000, DeadeyeSlowBp = 30000;
        public const int ScoutFast = 3, ScoutSlow = 8;
        public const int ReloadStepBp = 2000; // 20% at 25, 40% at 50, 60% at 75
        public const int CarryLevel = 50, PoolLevel = 50, Pool = 100, PoolRefillMs = 500;
        public const int ShrapnelLevel = 100, Fragments = 3, FragmentBp = 3300, FragmentTurnCentidegrees = 250;

        public static void Fill(int[] values, PlayerEntity player)
        {
            int skill = player.Skills.GetLiveSkillValue((DFCareer.Skills)Dfb.SKILL_PISTOLS);
            Fill(values, skill);
        }

        public static void Fill(int[] values, int skill)
        {
            bool spray = skill >= SprayLevel, deadeye = skill >= DeadeyeLevel;
            bool pool = skill >= PoolLevel, shrapnel = skill >= ShrapnelLevel;
            int steps = (skill >= 75 ? 1 : 0) + (skill >= 50 ? 1 : 0) + (skill >= 25 ? 1 : 0);
            values[Dfb.SHEET_PIST_SPRAY_FAST_BP] = spray ? SprayFastBp : 0;
            values[Dfb.SHEET_PIST_SPRAY_SLOW_BP] = spray ? SpraySlowBp : 0;
            values[Dfb.SHEET_PIST_DEADEYE_FAST_BP] = deadeye ? DeadeyeFastBp : 0;
            values[Dfb.SHEET_PIST_DEADEYE_SLOW_BP] = deadeye ? DeadeyeSlowBp : 0;
            values[Dfb.SHEET_PIST_SCALE_FAST] = spray ? ScoutFast : 0;
            values[Dfb.SHEET_PIST_SCALE_SLOW] = spray ? ScoutSlow : 0;
            values[Dfb.SHEET_PIST_RELOAD_BP] = ReloadStepBp * steps;
            values[Dfb.SHEET_PIST_CARRY] = skill >= CarryLevel ? 1 : 0;
            values[Dfb.SHEET_PIST_POOL] = pool ? Pool : 0;
            values[Dfb.SHEET_PIST_POOL_REFILL_MS] = pool ? PoolRefillMs : 0;
            values[Dfb.SHEET_PIST_FRAGMENTS] = shrapnel ? Fragments : 0;
            values[Dfb.SHEET_PIST_FRAGMENT_BP] = shrapnel ? FragmentBp : 0;
            values[Dfb.SHEET_PIST_FRAGMENT_TURN_CDEG] = shrapnel ? FragmentTurnCentidegrees : 0;
        }
    }
}
