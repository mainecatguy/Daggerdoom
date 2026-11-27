// Doomerfall: no shields for now (owner, 2026-11-26: "remove them from the game completely ... until we come up with
// some plan", backlog shield-support). Doom has no shield support yet. Runs only in a bridge session: every check
// below is false outside one, so plain Daggerfall Unity keeps its shields.
//
// What changes in a bridge session:
// - Random armor never rolls a shield. A shield roll is rolled again among the other armor, so an armor drop stays an
//   armor drop (ItemBuilder.CreateRandomArmor: loot piles, house containers, magic items; quests' random armor).
// - Shops never stock one (DaggerfallLoot.StockShopShelf), class enemies never carry one (ItemHelper enemy equipment),
//   a character background never grants one (BiogFile), and Create Item no longer offers the Steel Buckler.
// - Nothing can equip one (ItemEquipTable.EquipItem); the inventory says why.
// - A save that already holds a shield keeps it as an ordinary item the player can carry, drop or sell. If it was
//   equipped, loading takes it off (OnLoad), and Daggerfall recomputes armor without it.
// Known gap: the two artifact shields a quest places (Auriel's Shield, Spell Breaker) still exist, so those quests
// keep working; they cannot be equipped either.

using System;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShields
    {
        internal const string EquipMessage = "Shields cannot be used.";

        static bool registered;
        static Action<string> log;

        /// <summary>True in a bridge session, where shields are out of the game.</summary>
        internal static bool Active { get { return DoomerfallBridge.SessionActive; } }

        /// <summary>True for a shield while shields are out of the game.</summary>
        internal static bool Banned(DaggerfallUnityItem item)
        {
            return Active && item != null && item.ItemGroup == ItemGroups.Armor && item.IsShield;
        }

        /// <summary>True for a shield template index (Armor.Buckler to Armor.Tower_Shield) while shields are out.</summary>
        internal static bool Banned(ItemGroups group, int templateIndex)
        {
            return Active && group == ItemGroups.Armor && templateIndex >= (int)Armor.Buckler && templateIndex <= (int)Armor.Tower_Shield;
        }

        /// <summary>The same, for an item group index (the position within the group, as quests and shops count).</summary>
        internal static bool BannedGroupIndex(ItemGroups group, int groupIndex)
        {
            return Active && group == ItemGroups.Armor && Banned(group, DaggerfallUnity.Instance.ItemHelper.GetItemTemplate(group, groupIndex).index);
        }

        /// <summary>The inventory's equip check: true (after telling the player) for a shield.</summary>
        internal static bool BlockEquip(DaggerfallUnityItem item)
        {
            if (!Banned(item))
                return false;
            DaggerfallUI.MessageBox(EquipMessage);
            return true;
        }

        /// <summary>DoomerfallBridge, once per run.</summary>
        internal static void Register(DoomerfallBridge bridge)
        {
            log = bridge.LogLine;
            if (registered)
                return;
            registered = true;
            SaveLoadManager.OnLoad += OnLoad;
        }

        // A save from before this change may have a shield equipped. Take it off; it stays in the inventory.
        static void OnLoad(SaveData_v1 saveData)
        {
            if (!Active || !GameManager.HasInstance)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (player == null)
                return;
            DaggerfallUnityItem left = player.ItemEquipTable.GetItem(EquipSlots.LeftHand);
            if (!Banned(left))
                return;
            player.ItemEquipTable.UnequipItem(EquipSlots.LeftHand);
            player.UpdateEquippedArmorValues(left, false);
            log?.Invoke("shields: took off \"" + left.LongName + "\" from the loaded save; it stays in the inventory");
        }
    }
}
