// Which Expanded Inventory tab lists a Doomerfall item. Doom items are Daggerfall Misc items, so the mod would put
// them all on Clothing & Misc. Doomerfall lists Doom guns and ammo with the weapons (as Daggerfall lists arrows, and
// as the stock window's Weapons & Armor tab does) and Doom armor with the armor.
using DaggerfallWorkshop.Game.Doomerfall;
using DaggerfallWorkshop.Game.Items;

namespace ExpandedInventoryModHook
{
    public static class ExpandedInventoryDoom
    {
        public static void Tab(DaggerfallUnityItem item, out bool weapon, out bool armor)
        {
            weapon = armor = false;
            if (!DoomerfallDoomItem.InWeaponsAndArmorTab(item))
                return;
            DoomerfallDoomItem doom = item as DoomerfallDoomItem;
            armor = doom != null && doom.IsArmor && !doom.IsGun;
            weapon = !armor;
        }
    }
}
