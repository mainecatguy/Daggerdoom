// Doomerfall test only (-dfshopledgertest): once Daggerfall is in a game, runs DoomerfallShopLedger over a simulated
// clock (no real time passes) and logs: how long items of each price band stay on the shelf, that a player-sold item
// goes on the shelf and later sells off, that two runs give identical stock, and how often a top weapon smith (level
// 30, quality 20, three shelves) has a Daedric weapon or armor piece on its shelves.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopLedgerTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        bool done;
        const int Shelves = 3;
        const int BuildingKey = 5;

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshopledgertest") >= 0)
                owner.gameObject.AddComponent<DoomerfallShopLedgerTest>().bridge = owner;
        }

        void Log(string s) { bridge.LogLine("shopledger: " + s); }

        static bool IsDaedric(DaggerfallUnityItem item)
        {
            return (item.ItemGroup == ItemGroups.Weapons && item.nativeMaterialValue == (int)WeaponMaterialTypes.Daedric)
                || (item.ItemGroup == ItemGroups.Armor && item.nativeMaterialValue == (int)ArmorMaterialTypes.Daedric);
        }

        void Update()
        {
            if (done || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || GameManager.Instance.PlayerGPS == null || Time.frameCount < 600)
                return;
            done = true;
            try { Run(); }
            catch (Exception e) { Log("FAILED with exception " + e); }
        }

        void Run()
        {
            float started = Time.realtimeSinceStartup;
            int day0 = DoomerfallShopLedger.Day(DaggerfallUnity.Instance.WorldTime.Now);
            string first = Months(1001, day0, true);
            string second = Months(1001, day0, false);
            Log(first == second ? "PASS two runs give identical stock (" + first.Length + " chars of daily signature)" : "FAIL two runs differ");

            foreach (int[] c in new[] { new[] { 1, 6, 3 }, new[] { 5, 6, 5 }, new[] { 10, 8, 2 }, new[] { 30, 20, 3 }, new[] { 30, 20, 6 } })
                StockSize(c[0], c[1], c[2], day0);
            foreach (int level in new[] { 30, 20 })
                DaedricRate(level, day0);
            Log(string.Format("done in {0:F1}s", Time.realtimeSinceStartup - started));
        }

        DaggerfallLoot[] MakeShelves(int count = Shelves)
        {
            DaggerfallLoot[] shelves = new DaggerfallLoot[count];
            for (int i = 0; i < count; i++)
                shelves[i] = new GameObject("Doomerfall ledger test shelf").AddComponent<DaggerfallLoot>();
            return shelves;
        }

        static void Free(DaggerfallLoot[] shelves) { foreach (DaggerfallLoot s in shelves) Destroy(s.gameObject); }

        static void Day(DaggerfallLoot[] shelves, int location, int day, int level, int quality = 20)
        {
            PlayerGPS.DiscoveredBuilding smith = new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.WeaponSmith, quality = quality, buildingKey = BuildingKey };
            using (new WorldLevel.Scope(level))
                for (int i = 0; i < shelves.Length; i++)
                    DoomerfallShopLedger.Restock(shelves[i], smith, location, i, shelves.Length, day, level);
        }

        /// <summary>180 days at one top weapon smith. Returns a signature of every day's stock.</summary>
        string Months(int location, int day0, bool report)
        {
            const int Days = 180, SoldDay = 30;
            DaggerfallLoot[] shelves = MakeShelves();
            Dictionary<DaggerfallUnityItem, int> seen = new Dictionary<DaggerfallUnityItem, int>();
            string[] bands = { "under 100 gold", "100-999 gold", "1000+ gold (not Daedric)", "Daedric" };
            int[] left = new int[4]; long[] life = new long[4];
            int[] stillThere = new int[4]; long[] stillAge = new long[4];
            DaggerfallUnityItem playerSold = null;
            int playerSoldOn = -1, playerSoldGone = -1;
            long kept = 0, keptMissing = 0, sold = 0, soldStill = 0;
            int longest = 0; string longestName = "";
            StringBuilder sig = new StringBuilder();
            for (int d = 1; d <= Days; d++)
            {
                // Persistence check: replay the day's seeded sell-off rolls on yesterday's shelves, then require that every
                // item whose roll failed is still on the same shelf after the restock, and every item whose roll hit is gone.
                List<DaggerfallUnityItem>[] keep = new List<DaggerfallUnityItem>[Shelves], sell = new List<DaggerfallUnityItem>[Shelves];
                for (int i = 0; i < Shelves; i++)
                    Predict(shelves[i], location, day0 + d, i, keep[i] = new List<DaggerfallUnityItem>(), sell[i] = new List<DaggerfallUnityItem>());
                Day(shelves, location, day0 + d, 30);
                for (int i = 0; i < Shelves; i++)
                {
                    HashSet<DaggerfallUnityItem> on = new HashSet<DaggerfallUnityItem>();
                    for (int k = 0; k < shelves[i].Items.Count; k++) on.Add(shelves[i].Items.GetItem(k));
                    foreach (DaggerfallUnityItem item in keep[i]) { kept++; if (!on.Contains(item)) keptMissing++; }
                    foreach (DaggerfallUnityItem item in sell[i]) { sold++; if (on.Contains(item)) soldStill++; }
                }
                if (d == SoldDay)   // the player sells after the day's restock, as in game
                {
                    playerSold = ItemBuilder.CreateWeapon(Weapons.Longsword, WeaponMaterialTypes.Steel);
                    ItemCollection basket = new ItemCollection();
                    basket.AddItem(playerSold);
                    DoomerfallShopLedger.PutOnShelves(basket, new List<DaggerfallLoot>(shelves));
                }
                HashSet<DaggerfallUnityItem> now = new HashSet<DaggerfallUnityItem>();
                foreach (DaggerfallLoot s in shelves)
                {
                    sig.Append(s.Items.Count).Append(':');
                    for (int i = 0; i < s.Items.Count; i++)
                    {
                        DaggerfallUnityItem item = s.Items.GetItem(i);
                        now.Add(item);
                        if (!seen.ContainsKey(item))
                            seen[item] = d;
                        sig.Append(item.ItemGroup).Append('.').Append(item.TemplateIndex).Append('.').Append(item.nativeMaterialValue).Append('.').Append(item.value).Append(',');
                    }
                    sig.Append('|');
                }
                if (playerSold != null && playerSoldOn < 0 && now.Contains(playerSold))
                    playerSoldOn = d;
                if (playerSold != null && playerSoldOn > 0 && playerSoldGone < 0 && !now.Contains(playerSold))
                    playerSoldGone = d;
                List<DaggerfallUnityItem> gone = new List<DaggerfallUnityItem>();
                foreach (KeyValuePair<DaggerfallUnityItem, int> kv in seen)
                    if (!now.Contains(kv.Key))
                        gone.Add(kv.Key);
                foreach (DaggerfallUnityItem item in gone)
                {
                    if (d - seen[item] > longest) { longest = d - seen[item]; longestName = string.Format("{0} ({1} gold, days {2}-{3})", item.LongName, item.value, seen[item], d - 1); }
                    if (item != playerSold && !(item is DoomerfallAmmoItem))
                    {
                        int b = Band(item);
                        left[b]++;
                        life[b] += d - seen[item];
                    }
                    seen.Remove(item);
                }
                sig.Append('\n');
            }
            if (report)
            {
                foreach (KeyValuePair<DaggerfallUnityItem, int> kv in seen)
                    if (kv.Key != playerSold && !(kv.Key is DoomerfallAmmoItem))
                    {
                        int b = Band(kv.Key);
                        stillThere[b]++;
                        stillAge[b] += Days + 1 - kv.Value;
                    }
                int total = 0, stocked = 0;
                foreach (DaggerfallLoot s in shelves) { total += s.Items.Count; stocked += DoomerfallShopLedger.Stocked(s.Items); }
                Log(string.Format("top weapon smith, level 30, {0} shelves sharing a stock target of {1}, {2} days; at the end {3} items on the shelves: {4} stocked goods (incl. the player-sold sword if still there), {5} Doom ammo stacks",
                    Shelves, DoomerfallShopLedger.StockTarget(30), Days, total, stocked, total - stocked));
                for (int b = 0; b < 4; b++)
                    Log(string.Format("  {0}: {1} sold off, mean {2:F1} days on the shelf; {3} still there at the end (mean age {4:F1} days)",
                        bands[b], left[b], left[b] > 0 ? (double)life[b] / left[b] : 0, stillThere[b], stillThere[b] > 0 ? (double)stillAge[b] / stillThere[b] : 0));
                Log(string.Format("{0} player-sold steel longsword ({1} gold, {2:P0} a day): sold to the shop on day {3}, seen on a shelf on day {4}, sold off on day {5}",
                    playerSoldOn == SoldDay ? "PASS" : "FAIL", playerSold.value, DoomerfallShopLedger.SellChance(playerSold), SoldDay, playerSoldOn,
                    playerSoldGone < 0 ? "(still there)" : playerSoldGone.ToString()));
                Log(string.Format("{0} unsold items persist: {1} item-days whose replayed sell-off roll failed, {2} missing after the restock; {3} whose roll hit, {4} still there; longest stay of a sold-off item {5} days: {6}",
                    keptMissing == 0 && soldStill == 0 && kept > 0 ? "PASS" : "FAIL", kept, keptMissing, sold, soldStill, longest, longestName));
                Log(string.Format("{0} expensive items linger longer than cheap ones", MeanLife(left, life, stillThere, stillAge, 0) < MeanLife(left, life, stillThere, stillAge, 2) ? "PASS" : "FAIL"));
            }
            Free(shelves);
            return sig.ToString();
        }

        /// <summary>180 days at one weapon smith: on the shop's delivery days the stocked goods (not ammo, horse or cart)
        /// across all shelves are refilled to the building's stock target, whatever the shelf count; they never exceed it;
        /// and new non-ammo goods keep arriving to the end.</summary>
        void StockSize(int level, int quality, int count, int day0)
        {
            const int Days = 180, WarmUp = 30;
            DoomerfallShopLots.ExceptionsEnabled = false;   // ordinary deliveries; the lots test surveys exceptions
            DaggerfallLoot[] shelves = MakeShelves(count);
            int target = DoomerfallShopLedger.StockTarget(level), cap = count * ((target + count - 1) / count);
            int min = int.MaxValue, max = 0, ammoMax = 0, lateArrivals = 0, deliveryMin = int.MaxValue, deliveryDays = 0;
            int location = 7000 + level * 10 + count;
            DoomerfallShopIdentity id = DoomerfallShopIdentity.For(location, new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.WeaponSmith, quality = quality, buildingKey = BuildingKey });
            long sum = 0, ammoSum = 0;
            HashSet<DaggerfallUnityItem> known = new HashSet<DaggerfallUnityItem>();
            for (int d = 1; d <= Days; d++)
            {
                Day(shelves, location, day0 + d, level, quality);
                int stocked = 0, ammo = 0;
                foreach (DaggerfallLoot s in shelves)
                {
                    stocked += DoomerfallShopLedger.Stocked(s.Items);
                    for (int i = 0; i < s.Items.Count; i++)
                    {
                        DaggerfallUnityItem item = s.Items.GetItem(i);
                        if (item is DoomerfallAmmoItem) ammo++;
                        else if (known.Add(item) && d > Days - 30) lateArrivals++;
                    }
                }
                if (d > WarmUp)
                {
                    min = Mathf.Min(min, stocked); max = Mathf.Max(max, stocked); sum += stocked;
                    ammoMax = Mathf.Max(ammoMax, ammo); ammoSum += ammo;
                    if (id.DeliversOn(day0 + d)) { deliveryMin = Mathf.Min(deliveryMin, stocked); deliveryDays++; }
                }
            }
            Free(shelves);
            DoomerfallShopLots.ExceptionsEnabled = true;
            int n = Days - WarmUp;
            // Shops 6: goods arrive only on the shop's delivery days (the owner's "sparse stock between" for big deliveries),
            // so the lower bound of 3/4 of the target is checked on those days, after the delivery.
            bool pass = max <= cap && deliveryDays > 0 && deliveryMin >= target * 3 / 4 && lateArrivals > 0;
            Log(string.Format("{0} stock size: weapon smith level {1}, quality {2}, {3} shelves, target {4} (cap {5} with rounding), {12} every {13} days: on {14} delivery days stocked goods at least {15} (need {16}); all days {6}-{7}, mean {8:F1}; Doom ammo stacks (outside the target, first shelf) mean {9:F1}, max {10}; {11} new non-ammo items in the last 30 days",
                pass ? "PASS" : "FAIL", level, quality, count, target, cap, min, max, (double)sum / n, (double)ammoSum / n, ammoMax, lateArrivals,
                id.Big ? "big delivery" : "trickle", id.Interval, deliveryDays, deliveryDays > 0 ? deliveryMin : 0, target * 3 / 4));
        }

        /// <summary>Replays DoomerfallShopLedger's sell-off for one day (same seed, same roll order) without touching the shelf.</summary>
        static void Predict(DaggerfallLoot shelf, int location, int day, int index, List<DaggerfallUnityItem> keep, List<DaggerfallUnityItem> sell)
        {
            UnityEngine.Random.State saved = UnityEngine.Random.state;
            UnityEngine.Random.InitState(DoomerfallShopLedger.Seed(location, BuildingKey, day, index));
            for (int i = 0; i < shelf.Items.Count; i++)
            {
                DaggerfallUnityItem item = shelf.Items.GetItem(i);
                bool gone = !item.IsQuestItem && item.ItemGroup != ItemGroups.Transportation && UnityEngine.Random.value < DoomerfallShopLedger.SellChance(item);
                (gone ? sell : keep).Add(item);
            }
            UnityEngine.Random.state = saved;
        }

        static double MeanLife(int[] left, long[] life, int[] still, long[] age, int b)
        {
            int n = left[b] + still[b];
            return n > 0 ? (double)(life[b] + age[b]) / n : 0;
        }

        static int Band(DaggerfallUnityItem item)
        {
            if (IsDaedric(item)) return 3;
            return item.value < 100 ? 0 : item.value < 1000 ? 1 : 2;
        }

        /// <summary>Over many top weapon smiths, the share with a Daedric item on its shelves on a given day, after warm-up.</summary>
        void DaedricRate(int level, int day0)
        {
            const int Buildings = 60, WarmUp = 60, Samples = 30;
            int withDaedric = 0, samples = 0, firstDelivery = 0;
            int pieces = 0, daedricPieces = 0, armor = 0, daedricArmor = 0, plate = 0;
            for (int b = 0; b < Buildings; b++)
            {
                DaggerfallLoot[] shelves = MakeShelves();
                for (int d = 1; d <= WarmUp + Samples; d++)
                {
                    Day(shelves, 5000 + b, day0 + d, level);
                    bool any = false;
                    foreach (DaggerfallLoot s in shelves)
                        for (int i = 0; i < s.Items.Count; i++)
                        {
                            DaggerfallUnityItem item = s.Items.GetItem(i);
                            if (IsDaedric(item)) any = true;
                            if (d == 1 && item.ItemGroup == ItemGroups.Weapons)
                            {
                                pieces++;
                                if (IsDaedric(item)) daedricPieces++;
                            }
                            if (d == 1 && item.ItemGroup == ItemGroups.Armor)
                            {
                                armor++;
                                if (IsDaedric(item)) daedricArmor++;
                                if (item.nativeMaterialValue >= 0x0200) plate++;
                            }
                        }
                    if (d == 1 && any) firstDelivery++;
                    if (d > WarmUp) { samples++; if (any) withDaedric++; }
                }
                Free(shelves);
            }
            Log(string.Format("level {0} (first stocking = the shop's most recent delivery, up to 30 days back, and the sell-off since; fresh-arrival odds are in -dfshopidentitytest): first stocking has a Daedric item in {1:F1}% of shops; Daedric share of weapons on first stocking {2:F2}% ({3} of {4}; approved odds give {5:F2}%); after {6} days, a shop has a Daedric item on {7:F1}% of days ({8} shop-days)",
                level, 100.0 * firstDelivery / Buildings, 100.0 * daedricPieces / Mathf.Max(1, pieces), daedricPieces, pieces, 100 * DoomerfallDrops.DaedricChance(level),
                WarmUp, 100.0 * withDaedric / Mathf.Max(1, samples), samples));
            Log(string.Format("level {0}: armor on first stocking: {1} pieces, {2} plate ({3:F1}%), {4} Daedric = {5:F2}% of armor, {6:F2}% of plate (approved odds {7:F2}%)",
                level, armor, plate, 100.0 * plate / Mathf.Max(1, armor), daedricArmor, 100.0 * daedricArmor / Mathf.Max(1, armor), 100.0 * daedricArmor / Mathf.Max(1, plate),
                100 * DoomerfallDrops.DaedricChance(level)));
        }
    }
}
