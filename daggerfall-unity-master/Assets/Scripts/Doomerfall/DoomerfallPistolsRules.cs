// Doomerfall: the Pistols skill's rules. Daggerfall owns skills and their perks, so it decides the numbers and sends
// them to Doom in the character sheet (DFB_SHEET_PIST_*); Doom applies them to guns whose skill is Pistols
// (mods/doomerfall/src/zscript/DoomerfallPistols.zs): stock Doom's Pistol and DRLA's pistol-type guns, never a rifle.
//
// Owner rules (the Pistols perks card):
//   - 25: reloads 20% faster;
//   - 50: overkill carry-through; a 100-damage bonus pool that each shot spends and that refills every 0.5 s; reloads 40% faster;
//   - 75: reloads 60% faster;
//   - 100: every pistol hit bursts into 3 fragments, each doing 33% of the hit, turning to an enemy within 5 degrees.
// Not built, because the owner has not decided them: the 25 and 75 fire-rate damage multipliers (how fire rate is
// measured, which rates are fast and slow, how the multipliers scale between them, whether they multiply the pool).
// Their sheet slots (DFB_SHEET_PIST_RESERVED_*) stay 0.
//
// The live skill decides, as for the other gun skills, so a drained or fortified skill counts.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallPistolsRules
    {
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
            bool pool = skill >= PoolLevel, shrapnel = skill >= ShrapnelLevel;
            int steps = (skill >= 75 ? 1 : 0) + (skill >= 50 ? 1 : 0) + (skill >= 25 ? 1 : 0);
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
