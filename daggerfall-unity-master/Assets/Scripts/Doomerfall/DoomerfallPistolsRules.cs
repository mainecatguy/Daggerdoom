// Doomerfall: the Pistols skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_PIST_*); Doom applies them to guns whose skill is Pistols
// (mods/doomerfall/src/zscript/DoomerfallPistols.zs): stock Doom's Pistol and DRLA's pistol-type guns, never a rifle.
//
// Owner rules (the Pistols perks card):
//   - 25: a damage multiplier by fire rate, x2.5 for fast-firing pistols down to x1.5 for slow ones; reloads 20% faster;
//   - 50: overkill carry-through; a 100-damage bonus pool that refills every 0.5 s; reloads 40% faster;
//   - 75: Deadeye, x1.5 for fast-firing pistols up to x3 for slow ones (multiplies with the 25 one); reloads 60% faster;
//   - 100: every pistol hit bursts into 3 fragments, each doing 33% of the hit, turning to an enemy within 5 degrees.
// Still open, so not chosen: which fire rates count as fast and slow, and how the multipliers scale between them. The
// fast and slow fire cycles are sent as 0, which turns both multipliers off; Doom scales linearly between them once
// they are set. Also open: whether Deadeye multiplies the bonus pool (today the pool is added after every multiplier).
//
// The live skill decides, as for the other gun skills, so a drained or fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallPistolsRules
    {
        public const int RateFastTics = 0, RateSlowTics = 0; // Open: which fire rates are fast and slow.
        public const int SprayLevel = 25, SprayFastBp = 25000, SpraySlowBp = 15000;
        public const int DeadeyeLevel = 75, DeadeyeFastBp = 15000, DeadeyeSlowBp = 30000;
        public const int ReloadStepBp = 2000; // 20% at 25, 40% at 50, 60% at 75
        public const int CarryLevel = 50, PoolLevel = 50, Pool = 100, PoolRefillMs = 500;
        public const int ShrapnelLevel = 100, Fragments = 3, FragmentBp = 3300, FragmentTurnDegrees = 5;

        public static void Fill(int[] values, PlayerEntity player)
        {
            int skill = player.Skills.GetLiveSkillValue((DFCareer.Skills)Dfb.SKILL_PISTOLS);
            Fill(values, skill);
        }

        public static void Fill(int[] values, int skill)
        {
            bool spray = skill >= SprayLevel, deadeye = skill >= DeadeyeLevel, pool = skill >= PoolLevel, shrapnel = skill >= ShrapnelLevel;
            int steps = (skill >= 75 ? 1 : 0) + (skill >= 50 ? 1 : 0) + (skill >= 25 ? 1 : 0);
            values[Dfb.SHEET_PIST_RATE_FAST_TICS] = RateFastTics;
            values[Dfb.SHEET_PIST_RATE_SLOW_TICS] = RateSlowTics;
            values[Dfb.SHEET_PIST_SPRAY_FAST_BP] = spray ? SprayFastBp : 0;
            values[Dfb.SHEET_PIST_SPRAY_SLOW_BP] = spray ? SpraySlowBp : 0;
            values[Dfb.SHEET_PIST_DEADEYE_FAST_BP] = deadeye ? DeadeyeFastBp : 0;
            values[Dfb.SHEET_PIST_DEADEYE_SLOW_BP] = deadeye ? DeadeyeSlowBp : 0;
            values[Dfb.SHEET_PIST_RELOAD_BP] = ReloadStepBp * steps;
            values[Dfb.SHEET_PIST_CARRY] = skill >= CarryLevel ? 1 : 0;
            values[Dfb.SHEET_PIST_POOL] = pool ? Pool : 0;
            values[Dfb.SHEET_PIST_POOL_REFILL_MS] = pool ? PoolRefillMs : 0;
            values[Dfb.SHEET_PIST_FRAGMENTS] = shrapnel ? Fragments : 0;
            values[Dfb.SHEET_PIST_FRAGMENT_BP] = shrapnel ? FragmentBp : 0;
            values[Dfb.SHEET_PIST_FRAGMENT_TURN] = shrapnel ? FragmentTurnDegrees : 0;
        }
    }
}
