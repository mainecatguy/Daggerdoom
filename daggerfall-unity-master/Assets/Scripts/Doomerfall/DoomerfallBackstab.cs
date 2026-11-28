// Doomerfall: Backstabbing skill uses from hits on unaware enemies. Doom decides which hits are on unaware enemies and
// reports them (UZDoom/src/dd_backstab.cpp, DFB_KIND_SNEAK_HITS); the damage side is the backstab element of
// DoomerfallDamageBonus. Output: Daggerfall's own TallySkill(Backstabbing), so advancement stays Daggerfall's.
// Rate (owner, 2026-11-25): each hit on an unaware enemy tallies 10 times what a weapon skill gets for a hit on an aware
// one. That "normal" per-hit tally is Daggerfall's: WeaponManager tallies the weapon skill once per hit that lands. Use
// based rates are being reworked (skillresearch 02); until that is approved, Daggerfall's 1 per hit is the base.

using System;
using DaggerfallConnect;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallBackstab
    {
        const int NormalUsesPerHit = 1;      // WeaponManager: TallySkill(weapon skill, 1) per hit
        const int RateMultiplier = 10;       // owner, 2026-11-25
        internal const int UsesPerSneakHit = NormalUsesPerHit * RateMultiplier;

        internal static void OnSneakHits(DoomerfallBridge bridge, uint hits)
        {
            if (!GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || hits == 0)
                return;
            if (hits > 1000)
                return; // Doom reports once a frame, so a large value is a fault.
            short uses = (short)(hits * UsesPerSneakHit);
            GameManager.Instance.PlayerEntity.TallySkill(DFCareer.Skills.Backstabbing, uses);
            if (bridge.LogEnabled)
                bridge.LogLine(string.Format("backstab: {0} sneak hits, tallied {1} Backstabbing uses, total {2}", hits, uses,
                    GameManager.Instance.PlayerEntity.SkillUses[(int)DFCareer.Skills.Backstabbing]));
        }
    }
}
