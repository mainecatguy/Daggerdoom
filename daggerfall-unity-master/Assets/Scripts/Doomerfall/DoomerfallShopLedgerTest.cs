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

            foreach (int level in new[] { 30, 20 })
                DaedricRate(level, day0);
            Log(string.Format("done in {0:F1}s", Time.realtimeSinceStartup - started));
        }

        DaggerfallLoot[] MakeShelves()
        {
            DaggerfallLoot[] shelves = new DaggerfallLoot[Shelves];
            for (int i = 0; i < Shelves; i++)
                shelves[i] = new GameObject("Doomerfall ledger test shelf").AddComponent<DaggerfallLoot>();
            return shelves;
        }

        static void Free(DaggerfallLoot[] shelves) { foreach (DaggerfallLoot s in shelves) Destroy(s.gameObject); }

        static void Day(DaggerfallLoot[] shelves, int location, int day, int level)
        {
            PlayerGPS.DiscoveredBuilding smith = new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.WeaponSmith, quality = 20, buildingKey = 5 };
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
            StringBuilder sig = new StringBuilder();
            for (int d = 1; d <= Days; d++)
            {
                Day(shelves, location, day0 + d, 30);
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
                int total = 0;
                foreach (DaggerfallLoot s in shelves) total += s.Items.Count;
                Log(string.Format("top weapon smith, level 30, {0} shelves sharing a stock target of {1}, {2} days; {3} items on the shelves at the end",
                    Shelves, DoomerfallShopLedger.StockTarget(30), Days, total));
                for (int b = 0; b < 4; b++)
                    Log(string.Format("  {0}: {1} sold off, mean {2:F1} days on the shelf; {3} still there at the end (mean age {4:F1} days)",
                        bands[b], left[b], left[b] > 0 ? (double)life[b] / left[b] : 0, stillThere[b], stillThere[b] > 0 ? (double)stillAge[b] / stillThere[b] : 0));
                Log(string.Format("{0} player-sold steel longsword ({1} gold, {2:P0} a day): sold to the shop on day {3}, seen on a shelf on day {4}, sold off on day {5}",
                    playerSoldOn == SoldDay ? "PASS" : "FAIL", playerSold.value, DoomerfallShopLedger.SellChance(playerSold), SoldDay, playerSoldOn,
                    playerSoldGone < 0 ? "(still there)" : playerSoldGone.ToString()));
                Log(string.Format("{0} expensive items linger longer than cheap ones", MeanLife(left, life, stillThere, stillAge, 0) < MeanLife(left, life, stillThere, stillAge, 2) ? "PASS" : "FAIL"));
            }
            Free(shelves);
            return sig.ToString();
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
            int pieces = 0, daedricPieces = 0;
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
                            if (d == 1 && (item.ItemGroup == ItemGroups.Weapons || item.ItemGroup == ItemGroups.Armor))
                            {
                                pieces++;
                                if (IsDaedric(item)) daedricPieces++;
                            }
                        }
                    if (d == 1 && any) firstDelivery++;
                    if (d > WarmUp) { samples++; if (any) withDaedric++; }
                }
                Free(shelves);
            }
            Log(string.Format("level {0}: first stocking has a Daedric item in {1:F1}% of shops; Daedric share of weapons and armor on first stocking {2:F2}% ({3} of {4}; approved odds give {5:F2}%); after {6} days, a shop has a Daedric item on {7:F1}% of days ({8} shop-days)",
                level, 100.0 * firstDelivery / Buildings, 100.0 * daedricPieces / Mathf.Max(1, pieces), daedricPieces, pieces, 100 * DoomerfallDrops.DaedricChance(level),
                WarmUp, 100.0 * withDaedric / Mathf.Max(1, samples), samples));
        }
    }
}
