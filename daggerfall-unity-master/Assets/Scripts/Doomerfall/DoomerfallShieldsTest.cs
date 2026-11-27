// Doomerfall test only (-dfshieldtest), run by tools/shields/shields_paired.py: once the new character is in play,
// checks that shields are out of the game (DoomerfallShields) and logs every result to the bridge log.
//   1. The new character carries no shield.
//   2. Survey through Daggerfall's own generators: random armor, magic items, every shop type's shelf, house
//      containers, every loot table, and every enemy type's equipment (DoomerfallDrops.RollEnemy). Counts shields
//      and, as a control, all armor.
//   3. A shield made directly cannot be equipped.
//   4. A save that holds an equipped shield (made as an older save would hold it: through the equip table's
//      deserializer, which has no shield check) saves, loads without errors, and comes back unequipped but carried.

using System;
using System.Collections;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShieldsTest : MonoBehaviour
    {
        const string SaveName = "ShieldTest";
        static readonly DFLocation.BuildingTypes[] Shops = {
            DFLocation.BuildingTypes.Alchemist, DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.Bookseller,
            DFLocation.BuildingTypes.ClothingStore, DFLocation.BuildingTypes.GemStore, // no FurnitureStore: Daggerfall has no stock table for it
            DFLocation.BuildingTypes.GeneralStore, DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.WeaponSmith };
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        int shields, armor, items;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync sync)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshieldtest") < 0)
                return;
            DoomerfallShieldsTest test = owner.gameObject.AddComponent<DoomerfallShieldsTest>();
            test.bridge = owner;
            test.sync = sync;
            test.StartCoroutine(test.Run());
        }

        void Log(string line) { bridge.LogLine("shield test: " + line); }

        void Count(ItemCollection collection)
        {
            for (int i = 0; i < collection.Count; i++)
                Count(collection.GetItem(i));
        }

        void Count(DaggerfallUnityItem item)
        {
            if (item == null)
                return;
            items++;
            if (item.ItemGroup == ItemGroups.Armor)
                armor++;
            if (item.ItemGroup == ItemGroups.Armor && item.IsShield)
            {
                shields++;
                Log("FOUND SHIELD " + item.LongName);
            }
        }

        void Report(string what)
        {
            Log(string.Format("survey {0}: {1} items, {2} armor, {3} shields", what, items, armor, shields));
            items = armor = shields = 0;
        }

        IEnumerator Run()
        {
            while (!sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            Log("active " + DoomerfallShields.Active);

            Count(player.Items);
            Report("new character");

            for (int i = 0; i < 3000; i++)
                Count(ItemBuilder.CreateRandomArmor(1 + i % 30, player.Gender, player.Race));
            Report("random armor x3000");
            for (int i = 0; i < 2000; i++)
                Count(ItemBuilder.CreateRandomMagicItem(1 + i % 30, player.Gender, player.Race));
            Report("magic items x2000");

            GameObject holder = new GameObject("Doomerfall shield test");
            DaggerfallLoot container = holder.AddComponent<DaggerfallLoot>();
            foreach (DFLocation.BuildingTypes type in Enum.GetValues(typeof(DFLocation.BuildingTypes)))
            {
                if (type < DFLocation.BuildingTypes.Alchemist || type > DFLocation.BuildingTypes.Town23)
                    continue;
                for (int i = 0; i < 40; i++)
                {
                    PlayerGPS.DiscoveredBuilding building = new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = 1 + i % 20 };
                    if (Array.IndexOf(Shops, type) >= 0)
                    {
                        container.StockShopShelf(building);
                        Count(container.Items);
                    }
                    try
                    {
                        container.StockHouseContainer(building);
                        Count(container.Items);
                    }
                    catch (Exception e)
                    {
                        if (i == 0) Log("house container " + type + " not stocked: " + e.GetType().Name);
                    }
                }
            }
            Destroy(holder);
            Report("shop shelves and house containers, every building type x40");

            foreach (LootChanceMatrix matrix in LootTables.DefaultLootTables)
                for (int i = 0; i < 200; i++)
                    foreach (DaggerfallUnityItem item in LootTables.GenerateRandomLoot(matrix, player))
                        Count(item);
            Report("every loot table x200");

            int seed = 1;
            foreach (MobileTypes type in Enum.GetValues(typeof(MobileTypes)))
                for (int i = 0; i < 30; i++)
                    Count(DoomerfallDrops.RollEnemy(type, 1 + i, null, seed++));
            Report("every enemy type's equipment x30 levels");

            int bannedIndexes = 0;
            for (int g = 0; g < DaggerfallUnity.Instance.ItemHelper.GetEnumArray(ItemGroups.Armor).Length; g++)
                if (DoomerfallShields.BannedGroupIndex(ItemGroups.Armor, g))
                    bannedIndexes++;
            Log("quest random armor: " + bannedIndexes + " of the armor group indexes are rerolled (expect 4)");

            // 3. Equip refused.
            DaggerfallUnityItem shield = ItemBuilder.CreateArmor(player.Gender, player.Race, Armor.Kite_Shield, ArmorMaterialTypes.Steel);
            player.Items.AddItem(shield);
            bool refused = player.ItemEquipTable.EquipItem(shield) == null && !player.ItemEquipTable.IsEquipped(shield);
            Log("equip refused " + refused);
            string armorBefore = string.Join(",", player.ArmorValues);
            DoomerfallHotkeys hotkeys = bridge.GetComponent<DoomerfallHotkeys>();
            hotkeys.Use(2, 1, shield);
            hotkeys.Use(2, 1, shield);
            Log(string.Format("hotkey refused {0}, armor unchanged {1}", !player.ItemEquipTable.IsEquipped(shield),
                armorBefore == string.Join(",", player.ArmorValues)));

            // 4. An older save with the shield equipped.
            ulong[] table = player.ItemEquipTable.SerializeEquipTable();
            table[(int)EquipSlots.LeftHand] = shield.UID;
            player.ItemEquipTable.DeserializeEquipTable(table, player.Items);
            player.UpdateEquippedArmorValues(shield, true);
            Log("before save: equipped " + player.ItemEquipTable.IsEquipped(shield) + ", armor " + string.Join(",", player.ArmorValues));
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            string character = player.Name;
            saves.Save(character, SaveName);
            yield return new WaitForSecondsRealtime(2f);
            saves.EnumerateSaves();
            bool loaded = false;
            SaveLoadManager.OnLoadEventHandler onLoad = null;
            onLoad = data => { SaveLoadManager.OnLoad -= onLoad; loaded = true; };
            SaveLoadManager.OnLoad += onLoad;
            saves.Load(character, SaveName);
            float deadline = Time.realtimeSinceStartup + 20f;
            while (!loaded && Time.realtimeSinceStartup < deadline)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            player = GameManager.Instance.PlayerEntity;
            int carried = 0;
            for (int i = 0; i < player.Items.Count; i++)
                if (player.Items.GetItem(i).ItemGroup == ItemGroups.Armor && player.Items.GetItem(i).IsShield)
                    carried++;
            Log(string.Format("after load: loaded {0}, shields carried {1}, left hand {2}, armor {3}", loaded, carried,
                player.ItemEquipTable.GetItem(EquipSlots.LeftHand) == null ? "empty" : player.ItemEquipTable.GetItem(EquipSlots.LeftHand).LongName,
                string.Join(",", player.ArmorValues)));
            Log("done");
        }
    }
}
