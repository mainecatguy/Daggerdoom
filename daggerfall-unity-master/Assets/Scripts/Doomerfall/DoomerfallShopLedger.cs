// Doomerfall: a shop's shelves are a ledger (Shops 5). Runs only in a bridge session (WorldLevel.ShopProvider set);
// otherwise Daggerfall's classic restock (clear and roll a full shop) runs unchanged.
//
// Each day since the shelf was last stocked is one period, and the day number is the delivery number:
//   1. Every item on the shelf is "sold to other customers" with a fixed chance per day from its unit value
//      (SellChance): cheap goods leave in days, Daedric goods linger for months. Nothing else removes items.
//   2. If the shelf is below its share of the building's stock (StockTarget from the shop level, split over the
//      building's shelves), lots arrive until the share is full (DoomerfallShopLots, Shops 7; the classic delivery
//      is the regular-supply lot).
//      Doom ammo and the horse and cart do not count against the share. Doom ammo restocks every day (it sells fast),
//      as one delivery per building on its first shelf, outside the stock target. A general store's one horse and one
//      cart are kept on the first shelf as well.
// Every roll in a period draws from Unity's generator seeded by (location, building, delivery number, shelf), so the
// same building on the same day always gets the same goods. Weapon and armor material uses the owner's approved odds
// (DoomerfallDrops.RollMaterial) at the shop's level instead of Daggerfall's classic curve.
// Items the player sells (TakeSold) go on the building's emptiest shelf and sell off the same way.
// Shelf contents and stockedDate are saved by Daggerfall's own loot container serialization.

using System.Collections.Generic;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
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
            int before = shelf.Items.Count;
            Restock(shelf, building, location, index, Mathf.Max(1, shelves.Count), Day(DaggerfallUnity.Instance.WorldTime.Now), WorldLevel.Current);
            bool recorded = DoomerfallItems.RecordShelf(shelf);   // the Doom item ledger owns shelf state across re-entry, save, and load
            DoomerfallBridge bridge = Object.FindObjectOfType<DoomerfallBridge>();
            if (bridge)
                bridge.LogLine(string.Format("shop ledger: shelf {0} of {1} restocked from {2} to {3} items{4}; today's lots:{5}", index, shelves.Count, before, shelf.Items.Count, recorded ? " (recorded)" : " (not recorded)", LastLots.Length > 0 ? LastLots : " none"));
            return true;
        }

        /// <summary>The lots the last simulated day put on the shelf, for the log.</summary>
        internal static string LastLots = "";

        internal static void Restock(DaggerfallLoot shelf, PlayerGPS.DiscoveredBuilding building, int location, int shelfIndex, int shelfCount, int today, int level, DoomerfallShopLots.Place place = null)
        {
            if (place == null)
                place = DoomerfallShopLots.Place.Here();
            LastLots = "";
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
                    LastLots = Deliver(shelf, building, share, shelfIndex, location, day, level, place);
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
            int count = sold.Count;
            PutOnShelves(sold, shelves);
            string counts = "";
            foreach (DaggerfallLoot shelf in shelves)
            {
                counts += " " + shelf.Items.Count + (DoomerfallItems.RecordShelf(shelf) ? " (recorded)" : " (not recorded)");
            }
            DoomerfallBridge bridge = Object.FindObjectOfType<DoomerfallBridge>();
            if (bridge)
                bridge.LogLine(string.Format("shop ledger: {0} sold items put on the shelves; shelf item counts now{1}", count, counts));
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
                if (!item.IsQuestItem && item.ItemGroup != ItemGroups.Transportation && Random.value < SellChance(item))
                    gone.Add(item);
            }
            foreach (DaggerfallUnityItem item in gone)
                items.RemoveItem(item);
        }

        /// <summary>Items on a shelf that count against its share of the stock target: everything except Doom ammo and the horse and cart.</summary>
        internal static int Stocked(ItemCollection items)
        {
            int n = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (!(item is DoomerfallAmmoItem) && item.ItemGroup != ItemGroups.Transportation)
                    n++;
            }
            return n;
        }

        // Doom ammo sits outside the stock target: the building gets one ammo delivery a day, on its first shelf
        // (takesAmmo), and the other shelves drop the ammo from their deliveries.
        // The classic delivery is always rolled: its Doom ammo and the horse and cart go on the first shelf, and its other
        // goods are the regular-supply lot that DoomerfallShopLots.Fill draws from (Shops 7 lots).
        static string Deliver(DaggerfallLoot shelf, PlayerGPS.DiscoveredBuilding building, int share, int shelfIndex, int location, int day, int level, DoomerfallShopLots.Place place)
        {
            ItemCollection delivery = new ItemCollection();
            shelf.AddShopDelivery(building, delivery);
            List<DaggerfallUnityItem> goods = new List<DaggerfallUnityItem>();
            for (int i = 0; i < delivery.Count; i++)
            {
                DaggerfallUnityItem item = delivery.GetItem(i);
                bool ammo = item is DoomerfallAmmoItem;
                bool transport = item.ItemGroup == ItemGroups.Transportation;
                if (!ammo && !transport)
                    goods.Add(item);
                else if (shelfIndex == 0 && !(transport && shelf.Items.Contains(item.ItemGroup, item.TemplateIndex)))
                    shelf.Items.AddItem(item, ItemCollection.AddPosition.Back, !ammo);   // ammo joins a matching stack; one horse, one cart
            }
            int room = share - Stocked(shelf.Items);   // may be 0 or less: Fill still delivers an exception lot
            return DoomerfallShopLots.Fill(shelf.Items, building, goods, room, shelfIndex, location, day, level, place);
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
