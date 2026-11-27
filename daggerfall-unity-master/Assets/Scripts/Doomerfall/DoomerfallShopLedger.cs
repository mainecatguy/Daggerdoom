// Doomerfall: a shop's shelves are a ledger (Shops 5). Runs only in a bridge session (WorldLevel.ShopProvider set);
// otherwise Daggerfall's classic restock (clear and roll a full shop) runs unchanged.
//
// Each day since the shelf was last stocked is one period, and the day number is the delivery number:
//   1. Every item on the shelf is "sold to other customers" with a fixed chance per day from its unit value
//      (SellChance): cheap goods leave in days, Daedric goods linger for months. Nothing else removes items.
//   2. If the shelf is below its share of the building's stock (StockTarget from the shop level, split over the
//      building's shelves), one classic delivery is rolled and items from it are added until the share is full.
//      Doom ammo from the delivery is always added (it restocks often and sells fast).
// Every roll in a period draws from Unity's generator seeded by (location, building, delivery number, shelf), so the
// same building on the same day always gets the same goods. Weapon and armor material uses the owner's approved odds
// (DoomerfallDrops.RollMaterial) at the shop's level instead of Daggerfall's classic curve.
// Items the player sells (TakeSold) go on the building's emptiest shelf and sell off the same way.
// Shelf contents and stockedDate are saved by Daggerfall's own loot container serialization.

using System.Collections.Generic;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShopLedger
    {
        /// <summary>At most this many missed days are simulated on one visit; a longer absence is the same as this.</summary>
        internal const int MaxCatchUpDays = 120;
        const int DaysPerYear = 360;

        static bool Active { get { return WorldLevel.ShopProvider != null; } }

        /// <summary>Hook from DaggerfallLoot.StockShopShelf. Returns false outside a bridge session.</summary>
        internal static bool Restock(DaggerfallLoot shelf, PlayerGPS.DiscoveredBuilding building)
        {
            if (!Active)
                return false;
            List<DaggerfallLoot> shelves = ShelvesHere();
            int index = Mathf.Max(0, shelves.IndexOf(shelf));
            int location = GameManager.HasInstance && GameManager.Instance.PlayerGPS != null ? GameManager.Instance.PlayerGPS.CurrentMapID : 0;
            Restock(shelf, building, location, index, Mathf.Max(1, shelves.Count), Day(DaggerfallUnity.Instance.WorldTime.Now), WorldLevel.Current);
            return true;
        }

        internal static void Restock(DaggerfallLoot shelf, PlayerGPS.DiscoveredBuilding building, int location, int shelfIndex, int shelfCount, int today, int level)
        {
            int last = shelf.stockedDate == 0 ? today - 1 : StampToDay(shelf.stockedDate);
            int periods = Mathf.Clamp(today - last, 0, MaxCatchUpDays);
            int share = Mathf.Max(1, (StockTarget(level) + shelfCount - 1) / shelfCount);
            Random.State saved = Random.state;
            System.Func<int, WeaponMaterialTypes> savedRoll = FormulaHelper.DoomerfallMaterialRoll;
            try
            {
                FormulaHelper.DoomerfallMaterialRoll = DoomerfallDrops.RollMaterial;
                for (int day = today - periods + 1; day <= today; day++)
                {
                    Random.InitState(Seed(location, building.buildingKey, day, shelfIndex));
                    SellOff(shelf.Items);
                    Deliver(shelf, building, share);
                }
            }
            finally
            {
                FormulaHelper.DoomerfallMaterialRoll = savedRoll;
                Random.state = saved;
            }
            shelf.stockedDate = DayToStamp(today);
        }

        /// <summary>Hook from the trade window's sell confirmation. Returns false when there is no shop shelf to take the goods.</summary>
        internal static bool TakeSold(ItemCollection sold)
        {
            if (!Active || sold == null)
                return false;
            List<DaggerfallLoot> shelves = ShelvesHere();
            if (shelves.Count == 0)
                return false;
            foreach (DaggerfallLoot shelf in shelves)
                if (shelf.stockedDate < DaggerfallLoot.CreateStockedDate(DaggerfallUnity.Instance.WorldTime.Now))
                    using (WorldLevel.ForShop(GameManager.Instance.PlayerEnterExit.BuildingDiscoveryData))
                        shelf.StockShopShelf(GameManager.Instance.PlayerEnterExit.BuildingDiscoveryData);
            PutOnShelves(sold, shelves);
            return true;
        }

        internal static void PutOnShelves(ItemCollection sold, List<DaggerfallLoot> shelves)
        {
            List<DaggerfallUnityItem> goods = new List<DaggerfallUnityItem>();
            for (int i = 0; i < sold.Count; i++)
                goods.Add(sold.GetItem(i));
            foreach (DaggerfallUnityItem item in goods)
            {
                if (item.IsQuestItem)
                    continue;
                DaggerfallLoot emptiest = shelves[0];
                foreach (DaggerfallLoot shelf in shelves)
                    if (shelf.Items.Count < emptiest.Items.Count)
                        emptiest = shelf;
                sold.RemoveItem(item);
                emptiest.Items.AddItem(item, ItemCollection.AddPosition.Back, true);
            }
            sold.Clear();
        }

        /// <summary>Items a building keeps on its shelves in all, from the shop level (1 to 30).</summary>
        internal static int StockTarget(int level)
        {
            return 15 + 2 * Mathf.Clamp(level, 1, 30);
        }

        /// <summary>Chance per day that an item is sold to another customer: 50% at 25 gold or less, falling with the square root of value, at least 1%.</summary>
        internal static float SellChance(DaggerfallUnityItem item)
        {
            if (item is DoomerfallAmmoItem)
                return 0.5f;
            int value = Mathf.Max(1, item.value);
            return Mathf.Clamp(0.5f * Mathf.Sqrt(25f / value), 0.01f, 0.5f);
        }

        static void SellOff(ItemCollection items)
        {
            List<DaggerfallUnityItem> gone = new List<DaggerfallUnityItem>();
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (!item.IsQuestItem && Random.value < SellChance(item))
                    gone.Add(item);
            }
            foreach (DaggerfallUnityItem item in gone)
                items.RemoveItem(item);
        }

        static void Deliver(DaggerfallLoot shelf, PlayerGPS.DiscoveredBuilding building, int share)
        {
            ItemCollection delivery = new ItemCollection();
            shelf.AddShopDelivery(building, delivery);
            List<DaggerfallUnityItem> goods = new List<DaggerfallUnityItem>();
            for (int i = 0; i < delivery.Count; i++)
                goods.Add(delivery.GetItem(i));
            for (int i = goods.Count - 1; i > 0; i--)   // seeded shuffle, so a full shelf does not always skip the same groups
            {
                int j = Random.Range(0, i + 1);
                DaggerfallUnityItem t = goods[i]; goods[i] = goods[j]; goods[j] = t;
            }
            foreach (DaggerfallUnityItem item in goods)
            {
                bool ammo = item is DoomerfallAmmoItem;
                if (!ammo && shelf.Items.Count >= share)
                    continue;
                if (item.ItemGroup == ItemGroups.Transportation && shelf.Items.Contains(item.ItemGroup, item.TemplateIndex))
                    continue;   // one horse, one cart
                shelf.Items.AddItem(item, ItemCollection.AddPosition.Back, true);
            }
        }

        static List<DaggerfallLoot> ShelvesHere()
        {
            List<DaggerfallLoot> shelves = new List<DaggerfallLoot>();
            foreach (DaggerfallLoot loot in Object.FindObjectsOfType<DaggerfallLoot>())
                if (loot.ContainerType == LootContainerTypes.ShopShelves)
                    shelves.Add(loot);
            shelves.Sort((a, b) => a.LoadID.CompareTo(b.LoadID));
            return shelves;
        }

        internal static int Day(DaggerfallDateTime date) { return StampToDay(DaggerfallLoot.CreateStockedDate(date)); }
        static int StampToDay(int stamp) { return stamp / 1000 * DaysPerYear + stamp % 1000; }
        static int DayToStamp(int day) { int d = (day - 1) % DaysPerYear + 1; return (day - d) / DaysPerYear * 1000 + d; }

        internal static int Seed(int location, int buildingKey, int delivery, int shelf)
        {
            unchecked
            {
                int h = (int)2166136261;
                h = (h ^ location) * 16777619;
                h = (h ^ buildingKey) * 16777619;
                h = (h ^ delivery) * 16777619;
                h = (h ^ shelf) * 16777619;
                return h;
            }
        }
    }
}
