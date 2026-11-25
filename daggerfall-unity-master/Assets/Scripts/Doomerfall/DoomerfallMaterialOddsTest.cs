// Doomerfall test only, run by -dfworldleveltest: counts the materials of loot rolled through Daggerfall's own code
// (treasure piles, shop shelves, house containers, Mages Guild magic items, class enemies' equipment) at fixed area
// levels, so tools/world_level/world_level.py can compare the shares with the owner's approved material table.
// Every roll uses a fixed loot seed, so the counts are the same in every game.

using System;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallMaterialOddsTest
    {
        static readonly int[] Levels = { 1, 10, 20, 30 };
        const int Rounds = 400;
        const int Tiers = (int)WeaponMaterialTypes.Daedric + 1;
        static readonly string[] Piles = { "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U" };
        static readonly DFLocation.BuildingTypes[] Shops = { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.GeneralStore };
        static readonly int[] HouseModels = { 0, 2, 4, 11, 15 };
        static readonly MobileTypes[] Enemies = { MobileTypes.Knight, MobileTypes.Warrior, MobileTypes.Barbarian, MobileTypes.Spellsword };
        static readonly string[] DoomGuns = { "RLPistolPickup", "RLShotgunPickup", "RLChaingunPickup", "RLPlasmaRiflePickup" };
        const int DoomGunsPerRound = 20;

        internal sealed class Tally
        {
            public readonly int[] weapon = new int[Tiers], plate = new int[Tiers];
            public int leather, chain, rolls;

            public void Add(DaggerfallUnityItem item)
            {
                if (item == null)
                    return;
                DoomerfallDoomItem doom = item as DoomerfallDoomItem;
                if (doom != null)
                {
                    if (doom.IsGun) weapon[(int)doom.Material]++;
                }
                else if (item.ItemGroup == ItemGroups.Weapons && !item.IsOfTemplate(ItemGroups.Weapons, (int)Weapons.Arrow))
                {
                    int m = item.nativeMaterialValue;
                    if (m >= 0 && m < Tiers) weapon[m]++;
                }
                else if (item.ItemGroup == ItemGroups.Armor)
                {
                    int m = item.nativeMaterialValue;
                    if (m >= (int)ArmorMaterialTypes.Iron && m <= (int)ArmorMaterialTypes.Daedric) plate[m & 0xff]++;
                    else if (m == (int)ArmorMaterialTypes.Leather) leather++;
                    else chain++;
                }
            }

            public void Add(ItemCollection items)
            {
                for (int i = 0; i < items.Count; i++)
                    Add(items.GetItem(i));
            }

            public string Line()
            {
                return string.Format("rolls {0} weapon {1} plate {2} leather {3} chain {4}", rolls, string.Join(",", weapon), string.Join(",", plate), leather, chain);
            }
        }

        /// <summary>Logs one line per area level and loot source. With classic set, the Doomerfall material hook is off (normal Daggerfall Unity).</summary>
        internal static void Run(DoomerfallBridge bridge, bool classic)
        {
            Func<int, WeaponMaterialTypes> hook = FormulaHelper.DoomerfallMaterialRoll;
            if (classic)
                FormulaHelper.DoomerfallMaterialRoll = null;
            float started = Time.realtimeSinceStartup;
            try
            {
                foreach (int level in classic ? new[] { 20 } : Levels)
                    using (new WorldLevel.Scope(level))
                        RunLevel(bridge, classic ? "classic" : "approved", level);
            }
            finally
            {
                FormulaHelper.DoomerfallMaterialRoll = hook;
            }
            bridge.LogLine(string.Format("materialodds: {0} done in {1:0.0} s, hook {2}", classic ? "classic" : "approved",
                Time.realtimeSinceStartup - started, hook != null ? "set" : "missing"));
        }

        static void RunLevel(DoomerfallBridge bridge, string mode, int level)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            Tally piles = new Tally(), shops = new Tally(), houses = new Tally(), magic = new Tally(), enemies = new Tally(), doomGuns = new Tally();
            GameObject holder = new GameObject("Doomerfall material odds test");
            DaggerfallLoot container = holder.AddComponent<DaggerfallLoot>();
            for (int round = 0; round < Rounds; round++)
            {
                // Doom guns through the one factory every Doom item creation uses (a take, an adopted or starter gun).
                using (new LootSeed.Scope(LootSeed.Of(7600 + level, "doomgun", round)))
                    for (int i = 0; i < DoomGunsPerRound; i++)
                    {
                        doomGuns.rolls++;
                        doomGuns.Add(DoomerfallDoomItem.Create(DoomGuns[i % DoomGuns.Length], Dfb.DOOM_ITEM_GUN));
                    }

                foreach (string key in Piles)
                    using (new LootSeed.Scope(LootSeed.Of(7000 + level, key, round)))
                    {
                        piles.rolls++;
                        foreach (DaggerfallUnityItem item in LootTables.GenerateRandomLoot(LootTables.GetMatrix(key), player))
                            piles.Add(item);
                    }

                foreach (DFLocation.BuildingTypes type in Shops)
                {
                    container.Items.Clear();
                    using (new LootSeed.Scope(LootSeed.Of(7100 + level, type.ToString(), round)))
                        container.StockShopShelf(new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = 20 });
                    shops.rolls++;
                    shops.Add(container.Items);
                }

                // Daggerfall picks a container's item groups by building type and container model, so cycle both.
                for (int type = 0; type <= (int)DFLocation.BuildingTypes.Town23; type++)
                {
                    container.Items.Clear();
                    container.TextureRecord = HouseModels[(round + type) % HouseModels.Length];
                    using (new LootSeed.Scope(LootSeed.Of(7200 + level, "house", round, type)))
                        container.StockHouseContainer(new PlayerGPS.DiscoveredBuilding { buildingType = (DFLocation.BuildingTypes)type, quality = 10 });
                    houses.rolls++;
                    houses.Add(container.Items);
                }

                // The Mages Guild "buy magic items" stock is a run of these calls.
                using (new LootSeed.Scope(LootSeed.Of(7300 + level, "magic", round)))
                    for (int i = 0; i < 10; i++)
                    {
                        magic.rolls++;
                        magic.Add(ItemBuilder.CreateRandomMagicItem(WorldLevel.Current, player.Gender, player.Race));
                    }

                if (round % 4 == 0)
                    foreach (MobileTypes type in Enemies)
                    {
                        MobileEnemy mobile;
                        if (!EnemyBasics.GetEnemy(type, out mobile))
                            continue;
                        GameObject enemyHolder = new GameObject("Doomerfall material odds enemy");
                        enemyHolder.SetActive(false);
                        EnemyEntity enemy = new EnemyEntity(enemyHolder.AddComponent<DaggerfallEntityBehaviour>());
                        using (new LootSeed.Scope(LootSeed.Of(7400 + level, type.ToString(), round)))
                        {
                            LootSeed.SetEnemy(LootSeed.Of(7500 + level, type.ToString(), round));
                            try { enemy.SetEnemyCareer(mobile, EntityTypes.EnemyClass); }
                            finally { LootSeed.ClearEnemy(); }
                        }
                        enemies.rolls++;
                        enemies.Add(enemy.Items);
                        enemy.DetachFromGameEvents();
                        UnityEngine.Object.Destroy(enemyHolder);
                    }
            }
            UnityEngine.Object.Destroy(holder);
            bridge.LogLine(string.Format("materialodds: {0} level {1} piles {2}", mode, level, piles.Line()));
            bridge.LogLine(string.Format("materialodds: {0} level {1} shops {2}", mode, level, shops.Line()));
            bridge.LogLine(string.Format("materialodds: {0} level {1} houses {2}", mode, level, houses.Line()));
            bridge.LogLine(string.Format("materialodds: {0} level {1} magic {2}", mode, level, magic.Line()));
            bridge.LogLine(string.Format("materialodds: {0} level {1} enemies {2}", mode, level, enemies.Line()));
            if (mode == "approved")
            {
                bridge.LogLine(string.Format("materialodds: {0} level {1} doomguns {2}", mode, level, doomGuns.Line()));
                RoundTrip(bridge, level);
            }
        }

        // One rolled gun through Daggerfall's own item save format and back, as a save and load would carry it.
        static void RoundTrip(DoomerfallBridge bridge, int level)
        {
            DoomerfallDoomItem gun;
            using (new LootSeed.Scope(LootSeed.Of(7700 + level, "doomgun")))
                do gun = DoomerfallDoomItem.Create("RLPlasmaRiflePickup", Dfb.DOOM_ITEM_GUN);
                while (gun.Material == WeaponMaterialTypes.Iron); // Iron is also what a gun saved without a material reads as.
            ItemCollection saved = new ItemCollection();
            saved.AddItem(gun);
            string json = SaveLoadManager.Serialize(typeof(ItemData_v1[]), saved.SerializeItems());
            ItemCollection loaded = new ItemCollection();
            loaded.DeserializeItems((ItemData_v1[])SaveLoadManager.Deserialize(typeof(ItemData_v1[]), json));
            DoomerfallDoomItem back = loaded.Count == 1 ? loaded.GetItem(0) as DoomerfallDoomItem : null;
            string info = back != null ? string.Join(" | ", Array.ConvertAll(back.GetInfoTokens(), t => t.text ?? "")) : "";
            bool ok = back != null && back.Material == gun.Material && back.ItemName == gun.ItemName && back.ItemName.StartsWith(back.Material.ToString() + " ")
                && info.Contains("Material: " + back.Material) && back.GetWeaponMaterialModifier() == gun.GetWeaponMaterialModifier();
            bridge.LogLine(string.Format("materialodds: doomgun roundtrip level {0}: {1} rolled {2}, loaded {3} named \"{4}\" modifier {5}, info \"{6}\"",
                level, ok ? "PASS" : "FAIL", gun.Material, back != null ? back.Material.ToString() : "nothing", back != null ? back.ItemName : "", back != null ? back.GetWeaponMaterialModifier() : 0, info));
        }
    }
}
