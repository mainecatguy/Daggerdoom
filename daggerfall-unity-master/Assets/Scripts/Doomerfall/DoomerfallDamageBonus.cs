// Doomerfall: the player's damage bonus. Daggerfall tabulates it (gamedesign/damage.md) and publishes it every frame in
// dfb_df_state.damage_bonus_bp; Doom multiplies the damage the player deals by it. Elements multiply with each other:
// a +100% material and a +20% skill bonus give 2.0 x 1.2 = 2.4 times base damage.
//
// Elements so far (owner, 2026-11-24): the material of the ammo loaded in the ready gun (DoomerfallAmmo.LoadedMaterialBonus),
// and the Daggerfall material of the gun itself: Daggerfall's to-hit bonus (material modifier x 10) read as a percent
// damage modifier, Iron -10% up to Daedric +60% (work/backlog/weapon-material-damage-bonus.md).
// Backstabbing (owner, 2026-11-25): x1 at skill 0 rising evenly to x5 at skill 100, only on hits to unaware enemies. Which
// enemy is unaware is known only to Doom, hit by hit, so this element is published on its own (backstab_bonus_bp) and
// Doom multiplies it in on those hits (UZDoom/src/dd_backstab.cpp). Add an element only when the owner decides it.

using System;
using DaggerfallConnect;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallDamageBonus
    {
        readonly DoomerfallBridge bridge;
        readonly DoomerfallPositionSync sync;
        int lastBp, lastBackstabBp;

        // Test only (DoomerfallDamageBonusTest): replaces the tabulated multiplier while set.
        internal double? TestMultiplier;

        public DoomerfallDamageBonus(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
        }

        // Where the loaded ammo comes from. Set once the ammo tracker exists.
        internal DoomerfallAmmo Ammo;

        // The material bonus of the ammo loaded in the ready gun, as a fraction (0.5 is +50%). It follows the ready gun,
        // so it changes when a gun is equipped or the loaded ammo changes. 0 until tiered ammo exists.
        double AmmoMaterialBonus()
        {
            return Ammo != null ? Ammo.LoadedMaterialBonus() : 0.0;
        }

        // The material bonus of the gun Daggerfall has drawn, while Doom holds it ready, as a fraction (-0.1 is -10%).
        // Daggerfall's own modifier (GetWeaponMaterialModifier, -1 Iron to +6 Daedric) times 10 percent, as its to-hit
        // bonus is. 0 with no drawn gun, mid-swap, or while Doom holds fists or another melee weapon.
        double WeaponMaterialBonus()
        {
            DoomerfallDoomItem gun = Ammo != null ? Ammo.UpGun : null;
            return gun != null ? 0.10 * gun.GetWeaponMaterialModifier() : 0.0;
        }

        // The backstab element: 1 + 4 x the live Backstabbing skill / 100, the skill counted from 0 to 100, so x1 at 0,
        // x3 at 50 and x5 at 100. Doom applies it only on hits to unaware enemies, on top of Multiplier().
        public static double BackstabMultiplier(int liveSkill)
        {
            return 1.0 + 4.0 * Math.Max(0, Math.Min(liveSkill, 100)) / 100.0;
        }

        double BackstabMultiplier()
        {
            var player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            return player != null ? BackstabMultiplier(player.Skills.GetLiveSkillValue(DFCareer.Skills.Backstabbing)) : 1.0;
        }

        // Every element that applies to every hit, multiplied together. 1.0 means no bonus.
        public double Multiplier()
        {
            if (TestMultiplier.HasValue) return TestMultiplier.Value;
            return (1.0 + AmmoMaterialBonus()) * (1.0 + WeaponMaterialBonus());
        }

        // Fills the damage bonus of the published state. Runs every frame. Outside a game the bonus is none.
        public void Fill(ref DfbDfState state)
        {
            int bp = 0, backstabBp = 0;
            if (sync.InGame)
            {
                bp = ToBp(Multiplier());
                backstabBp = ToBp(BackstabMultiplier());
            }
            state.damageBonusBp = bp;
            state.backstabBonusBp = backstabBp;
            if (backstabBp != lastBackstabBp)
            {
                bridge.LogLine(string.Format("damage bonus: publishing backstab {0} bp (x{1:0.####} on unaware enemies)",
                    backstabBp, 1.0 + backstabBp / 10000.0));
                lastBackstabBp = backstabBp;
            }
            if (bp != lastBp)
            {
                bridge.LogLine(string.Format("damage bonus: publishing {0} bp (x{1:0.####})", bp, 1.0 + bp / 10000.0));
                lastBp = bp;
            }
        }

        static int ToBp(double multiplier)
        {
            return (int)Math.Round(Math.Max(0.0, Math.Min(multiplier, 100.0)) * 10000.0) - 10000;
        }
    }
}
