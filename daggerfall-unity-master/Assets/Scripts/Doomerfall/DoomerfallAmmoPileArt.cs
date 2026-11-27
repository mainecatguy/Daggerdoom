// Doomerfall: what a dropped pile of ammo looks like in Doom (owner, 2026-11-26: "dropped ammo should look like ammo";
// gamedesign/decisions/20261126-ammo-pile-look-owner.md).
//
// A dropped pile that holds nothing but one ammo type is listed to Doom with the art code AmmoArchive and a record that
// names the type, and Doom draws that ammo's own pickup sprite (DoomerfallItems.zs). Any other pile, including ammo
// mixed with other items, keeps its loot pile picture. The look follows the contents, so the pile's record and
// Daggerfall's save need nothing extra: a pile put back after leaving or loading looks the same because it holds the
// same items, and adding a sword to a bullet pile turns it into a loot pile.

using DaggerfallWorkshop.Game.Items;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallAmmoPileArt
    {
        // Above any Daggerfall texture archive. Keep in step with DoomerfallItems.zs (DoomerfallWorldItem.AmmoArchive).
        internal const int AmmoArchive = 9100;
        // Record = ammo type (DoomerfallAmmo.Types order), plus BoxRecord for at least a box's worth (Doom's box sizes).
        internal const int BoxRecord = 4;
        static readonly int[] BoxRounds = { 50, 20, 5, 100 };

        // True when the pile is a dropped pile of a single ammo type; archive and record are then its art code.
        internal static bool TryGet(DaggerfallLoot loot, out int archive, out int record)
        {
            archive = record = 0;
            if (!loot || !loot.customDrop || loot.ContainerType != LootContainerTypes.DroppedLoot || loot.Items.Count == 0)
                return false;
            int type = -1, rounds = 0;
            for (int i = 0; i < loot.Items.Count; i++)
            {
                DoomerfallAmmoItem ammo = loot.Items.GetItem(i) as DoomerfallAmmoItem;
                int t = ammo != null ? ammo.AmmoType : -1;
                if (t < 0 || (type >= 0 && t != type))
                    return false;
                type = t;
                rounds += ammo.stackCount;
            }
            archive = AmmoArchive;
            record = type + (rounds >= BoxRounds[type] ? BoxRecord : 0);
            return true;
        }
    }
}
