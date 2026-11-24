// Doomerfall: the player's damage bonus. Daggerfall tabulates it (gamedesign/damage.md) and publishes it every frame in
// dfb_df_state.damage_bonus_bp; Doom multiplies the damage the player deals by it. Elements multiply with each other:
// a +100% material and a +20% skill bonus give 2.0 x 1.2 = 2.4 times base damage.
//
// The only element so far is the material of the ammo loaded in the ready gun (DoomerfallAmmo.LoadedMaterialBonus),
// which is 0% until tiered ammo exists. Add an element only
// when the owner decides it.

using System;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallDamageBonus
    {
        readonly DoomerfallBridge bridge;
        readonly DoomerfallPositionSync sync;
        int lastBp;

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

        // Every element multiplied together. 1.0 means no bonus.
        public double Multiplier()
        {
            if (TestMultiplier.HasValue) return TestMultiplier.Value;
            return 1.0 + AmmoMaterialBonus();
        }

        // Fills the damage bonus of the published state. Runs every frame. Outside a game the bonus is none.
        public void Fill(ref DfbDfState state)
        {
            int bp = 0;
            if (sync.InGame)
            {
                double m = Multiplier();
                bp = (int)Math.Round(Math.Max(0.0, Math.Min(m, 100.0)) * 10000.0) - 10000;
            }
            state.damageBonusBp = bp;
            if (bp != lastBp)
            {
                bridge.LogLine(string.Format("damage bonus: publishing {0} bp (x{1:0.####})", bp, 1.0 + bp / 10000.0));
                lastBp = bp;
            }
        }
    }
}
