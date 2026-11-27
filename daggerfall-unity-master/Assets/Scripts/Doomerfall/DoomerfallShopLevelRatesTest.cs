// Doomerfall test only (-dfshoplevelrates): once Daggerfall is in a game, stocks a quality-20 weapon smith shelf and
// armorer shelf 1,000 times each inside WorldLevel.Scope at several shop levels, through Daggerfall's own
// StockShopShelf, and logs the share of shelves with at least one Daedric weapon or armor piece. Compare with the
// per-shelf table in work/notes/20261124-124736-shop-levels.md (classic items only; modded items counted apart).
// Also logs that WorldLevel.ForShop does nothing without a provider and uses the provider's level with one.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopLevelRatesTest : MonoBehaviour
    {
        const int Shelves = 1000, Quality = 20;
        static readonly int[] Levels = { 4, 15, 18, 20, 30 };
        static readonly DFLocation.BuildingTypes[] Types = { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.Armorer };

        DoomerfallBridge bridge;
        int step = -1;

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshoplevelrates") >= 0)
                owner.gameObject.AddComponent<DoomerfallShopLevelRatesTest>().bridge = owner;
        }

        void Log(string text) { bridge.LogLine("shoplevelrates: " + text); }

        void Update()
        {
            if (!GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || GameManager.Instance.PlayerGPS == null || Time.frameCount < 600)
                return;
            if (step < 0)
            {
                CheckScope();
                step = 0;
                return;
            }
            if (step >= Levels.Length * Types.Length)
            {
                if (step == Levels.Length * Types.Length)
                    Log("done");
                step = int.MaxValue;
                return;
            }
            try { Stock(Types[step / Levels.Length], Levels[step % Levels.Length]); }
            catch (Exception e) { Log("error: " + e); }
            step++;
        }

        void CheckScope()
        {
            Func<PlayerGPS.DiscoveredBuilding, int> provider = WorldLevel.ShopProvider;
            int before = WorldLevel.Current, without, withProvider;
            try
            {
                WorldLevel.ShopProvider = null;
                using (WorldLevel.ForShop(new PlayerGPS.DiscoveredBuilding()))
                    without = WorldLevel.Current;
                WorldLevel.ShopProvider = b => 23;
                using (WorldLevel.ForShop(new PlayerGPS.DiscoveredBuilding()))
                    withProvider = WorldLevel.Current;
            }
            finally { WorldLevel.ShopProvider = provider; }
            Log(string.Format("scope: current {0}, no provider {1} ({2}), provider 23 gives {3} ({4}), after {5}; bridge provider set {6}",
                before, without, without == before ? "PASS" : "FAIL", withProvider, withProvider == 23 ? "PASS" : "FAIL", WorldLevel.Current, provider != null));
        }

        void Stock(DFLocation.BuildingTypes type, int level)
        {
            ItemHelper helper = DaggerfallUnity.Instance.ItemHelper;
            HashSet<int> customWeapons = new HashSet<int>(helper.GetCustomItemsForGroup(ItemGroups.Weapons));
            HashSet<int> customArmor = new HashSet<int>(helper.GetCustomItemsForGroup(ItemGroups.Armor));
            GameObject holder = new GameObject("Doomerfall shop level rates test");
            DaggerfallLoot shelf = holder.AddComponent<DaggerfallLoot>();
            int classic = 0, modded = 0, any = 0, magic = 0;
            long items = 0;
            int seen = -1;
            for (int n = 0; n < Shelves; n++)
            {
                using (new WorldLevel.Scope(level))
                {
                    seen = WorldLevel.Current;
                    // One fresh classic delivery per sample with the approved material odds, as the shop ledger rolls it
                    // (StockShopShelf on a reused shelf would go to the ledger and not restock again the same day).
                    shelf.Items.Clear();
                    FormulaHelper.DoomerfallMaterialRoll = DoomerfallDrops.RollMaterial;
                    try { shelf.AddShopDelivery(new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = Quality }, shelf.Items); }
                    finally { FormulaHelper.DoomerfallMaterialRoll = null; }
                }
                bool c = false, m = false;
                for (int i = 0; i < shelf.Items.Count; i++)
                {
                    DaggerfallUnityItem item = shelf.Items.GetItem(i);
                    bool daedric = (item.ItemGroup == ItemGroups.Weapons && item.nativeMaterialValue == (int)WeaponMaterialTypes.Daedric)
                        || (item.ItemGroup == ItemGroups.Armor && item.nativeMaterialValue == (int)ArmorMaterialTypes.Daedric);
                    bool custom = (item.ItemGroup == ItemGroups.Weapons && customWeapons.Contains(item.TemplateIndex))
                        || (item.ItemGroup == ItemGroups.Armor && customArmor.Contains(item.TemplateIndex));
                    if (item.ItemGroup == ItemGroups.MagicItems)
                        magic++;
                    if (daedric && custom) m = true;
                    else if (daedric) c = true;
                }
                items += shelf.Items.Count;
                if (c) classic++;
                if (m) modded++;
                if (c || m) any++;
            }
            Destroy(holder);
            Log(string.Format("{0} level {1} (current inside scope {2}): {3} shelves, Daedric classic {4:F1}%, modded {5:F1}%, any {6:F1}%, {7:F1} items per shelf, {8} magic items",
                type, level, seen, Shelves, 100.0 * classic / Shelves, 100.0 * modded / Shelves, 100.0 * any / Shelves, (double)items / Shelves, magic));
        }
    }
}
