// Doomerfall test only (-dfshopidentitytest): once Daggerfall is in a game, surveys many simulated shops (no real time
// passes) and logs what Shops 6 promises: U-shaped breadth and rhythm, leans that are not bans, two or three regular
// suppliers with newcomers now and then, identical stock in two runs, and Daedric availability at the best smiths.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopIdentityTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        bool done;
        const int Shelves = 3, Days = 180;   // no warm-up needed: the first restock already simulates MaxCatchUpDays

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshopidentitytest") >= 0)
                owner.gameObject.AddComponent<DoomerfallShopIdentityTest>().bridge = owner;
        }

        void Log(string s) { bridge.LogLine("shopidentity: " + s); }

        void Update()
        {
            if (done || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || GameManager.Instance.PlayerGPS == null || Time.frameCount < 600)
                return;
            done = true;
            float started = Time.realtimeSinceStartup;
            try
            {
                int day0 = DoomerfallShopLedger.Day(DaggerfallUnity.Instance.WorldTime.Now);
                Shapes();
                Behaviour(day0);
                Same(day0);
                Daedric(day0);
            }
            catch (Exception e) { Log("FAILED with exception " + e); }
            Log(string.Format("done in {0:F1}s", Time.realtimeSinceStartup - started));
        }

        static PlayerGPS.DiscoveredBuilding Shop(DFLocation.BuildingTypes type, int key, int quality = 20)
        {
            return new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = quality, buildingKey = key };
        }

        static bool IsDaedric(DaggerfallUnityItem item)
        {
            return (item.ItemGroup == ItemGroups.Weapons && item.nativeMaterialValue == (int)WeaponMaterialTypes.Daedric)
                || (item.ItemGroup == ItemGroups.Armor && item.nativeMaterialValue == (int)ArmorMaterialTypes.Daedric);
        }

        static bool Stocked(DaggerfallUnityItem item) { return !(item is DoomerfallAmmoItem) && item.ItemGroup != ItemGroups.Transportation; }

        /// <summary>Breadth and rhythm over 2,000 shops of every type: both should be U-shaped.</summary>
        void Shapes()
        {
            DFLocation.BuildingTypes[] types = { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.GeneralStore,
                DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.Alchemist, DFLocation.BuildingTypes.Bookseller, DFLocation.BuildingTypes.ClothingStore, DFLocation.BuildingTypes.GemStore };
            int[] breadth = new int[5];
            SortedDictionary<int, int> intervals = new SortedDictionary<int, int>();
            int[] regulars = new int[4];
            int n = 2000, big = 0, weaponFavoured = 0, smiths = 0;
            for (int i = 0; i < n; i++)
            {
                PlayerGPS.DiscoveredBuilding b = Shop(types[i % types.Length], 11 + i * 13);
                DoomerfallShopIdentity id = DoomerfallShopIdentity.For(20000 + i, b);
                breadth[Mathf.Min(4, (int)(id.Breadth * 5))]++;
                int c; intervals.TryGetValue(id.Interval, out c); intervals[id.Interval] = c + 1;
                regulars[id.Regulars]++;
                if (id.Big) big++;
                if (b.buildingType == DFLocation.BuildingTypes.WeaponSmith)
                {
                    smiths++;
                    if (id.Favoured.Length > 0 && id.Favoured[0] / 1000 == (int)ItemGroups.Weapons) weaponFavoured++;
                }
            }
            bool uBreadth = breadth[0] > breadth[2] * 1.5f && breadth[4] > breadth[2] * 1.5f;
            Log(string.Format("{0} breadth is U-shaped: {1} shops in fifths of breadth 0..1: {2} (specialist end first)", uBreadth ? "PASS" : "FAIL", n, string.Join(" / ", Array.ConvertAll(breadth, x => x.ToString()))));
            StringBuilder s = new StringBuilder();
            foreach (KeyValuePair<int, int> kv in intervals) s.AppendFormat(" every {0} days: {1};", kv.Key, kv.Value);
            int middle = 0;
            foreach (KeyValuePair<int, int> kv in intervals) if (kv.Key >= 5 && kv.Key <= 6) middle += kv.Value;
            bool uRhythm = middle == 0 && big > n * 0.35f && big < n * 0.65f;
            Log(string.Format("{0} rhythm is U-shaped: {1} trickle shops, {2} big-delivery shops;{3} none every 5-6 days", uRhythm ? "PASS" : "FAIL", n - big, big, s));
            Log(string.Format("regular suppliers: {0} shops with two, {1} with three; weapon smiths whose first favoured kind is a weapon: {2} of {3}", regulars[2], regulars[3], weaponFavoured, smiths));
            for (int i = 0; i < 6; i++)
            {
                PlayerGPS.DiscoveredBuilding b = Shop(types[i % types.Length], 11 + i * 13);
                Log(string.Format("example {0} {1}: {2}", i, b.buildingType, DoomerfallShopIdentity.For(20000 + i, b).Describe()));
            }
        }

        /// <summary>Leans, suppliers and stock over 180 days at many weapon smiths and general stores.</summary>
        void Behaviour(int day0)
        {
            foreach (DFLocation.BuildingTypes type in new[] { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.GeneralStore })
            {
                const int Count = 60;
                double specRatio = 0, genRatio = 0; int spec = 0, gen = 0, specWithOthers = 0;
                double regularShare = 0; int deliveriesTotal = 0, lateNewcomerShops = 0, repeatNewcomerShops = 0, shops = 0;
                for (int k = 0; k < Count; k++)
                {
                    int location = 30000 + k + (int)type * 1000;
                    PlayerGPS.DiscoveredBuilding b = Shop(type, 7 + k * 17, 12);
                    DoomerfallShopIdentity id = DoomerfallShopIdentity.For(location, b);
                    DaggerfallLoot[] shelves = MakeShelves();
                    HashSet<DaggerfallUnityItem> known = new HashSet<DaggerfallUnityItem>();
                    int arrived = 0, favouredArrived = 0;
                    int[] bySupplier = new int[id.SupplierShare.Length + 1];
                    Dictionary<int, int> firstSeen = new Dictionary<int, int>();
                    int deliveries = 0, late = 0;
                    for (int d = 1; d <= Days; d++)
                    {
                        using (new WorldLevel.Scope(15))
                            for (int i = 0; i < Shelves; i++)
                                DoomerfallShopLedger.Restock(shelves[i], b, location, i, Shelves, day0 + d, 15);
                        foreach (DaggerfallLoot s in shelves)
                            for (int i = 0; i < s.Items.Count; i++)
                            {
                                DaggerfallUnityItem item = s.Items.GetItem(i);
                                if (!known.Add(item) || !Stocked(item) || d == 1) continue;
                                arrived++;
                                if (Array.IndexOf(id.Favoured, DoomerfallShopIdentity.Kind(item)) >= 0) favouredArrived++;
                            }
                        if (d > 1 && id.DeliversOn(day0 + d))
                        {
                            int sup = id.Supplier(location, b.buildingKey, day0 + d);
                            bySupplier[sup]++;
                            deliveries++;
                            if (sup >= id.Regulars && !firstSeen.ContainsKey(sup)) { firstSeen[sup] = d; if (d > Days / 2) late++; }
                        }
                    }
                    Free(shelves);
                    double raw = RawFavouredShare(id, b);
                    double ratio = raw > 0 && arrived > 0 ? favouredArrived / (double)arrived / raw : 0;
                    if (id.Breadth < 0.25f) { spec++; specRatio += ratio; if (favouredArrived < arrived) specWithOthers++; }
                    if (id.Breadth > 0.75f) { gen++; genRatio += ratio; }
                    int reg = 0; for (int i = 0; i < id.Regulars; i++) reg += bySupplier[i];
                    if (deliveries > 0) { regularShare += reg / (double)deliveries; shops++; }
                    deliveriesTotal += deliveries;
                    if (late > 0) lateNewcomerShops++;
                    int repeat = 0; for (int i = id.Regulars; i < bySupplier.Length; i++) if (bySupplier[i] >= 2) repeat++;
                    if (repeat > 0) repeatNewcomerShops++;
                }
                specRatio /= Mathf.Max(1, spec); genRatio /= Mathf.Max(1, gen); regularShare /= Mathf.Max(1, shops);
                bool lean = specRatio > 2 && genRatio < 1.6 && specWithOthers >= spec * 0.8;
                Log(string.Format("{0} {1} leans (level 15, quality 12, {2} shops, {3} days): favoured kinds arrive {4:F2}x as often as in plain classic rolls at specialists (breadth < 0.25, {5} shops), {6:F2}x at generalists (breadth > 0.75, {7} shops); {8} of the {5} specialists still got other kinds (leans, not bans)",
                    lean ? "PASS" : "FAIL", type, Count, Days, specRatio, spec, genRatio, gen, specWithOthers));
                bool suppliers = regularShare > 0.75 && lateNewcomerShops > 0 && repeatNewcomerShops > 0;
                Log(string.Format("{0} {1} suppliers: regulars made {2:P0} of {3} deliveries; a newcomer first appeared in the second half of the run at {4} of {5} shops; a newcomer delivered twice or more at {6} shops",
                    suppliers ? "PASS" : "FAIL", type, regularShare, deliveriesTotal, lateNewcomerShops, Count, repeatNewcomerShops));
            }
        }

        /// <summary>Share of favoured kinds among plain classic delivery rolls for this shop (no lean).</summary>
        static double RawFavouredShare(DoomerfallShopIdentity id, PlayerGPS.DiscoveredBuilding b)
        {
            DaggerfallLoot shelf = new GameObject("Doomerfall identity test shelf").AddComponent<DaggerfallLoot>();
            ItemCollection roll = new ItemCollection();
            int all = 0, fav = 0;
            UnityEngine.Random.State saved = UnityEngine.Random.state;
            UnityEngine.Random.InitState(b.buildingKey);
            for (int r = 0; r < 20; r++)
            {
                roll.Clear();
                shelf.AddShopDelivery(b, roll);
                for (int i = 0; i < roll.Count; i++)
                {
                    DaggerfallUnityItem item = roll.GetItem(i);
                    if (!Stocked(item)) continue;
                    all++;
                    if (Array.IndexOf(id.Favoured, DoomerfallShopIdentity.Kind(item)) >= 0) fav++;
                }
            }
            UnityEngine.Random.state = saved;
            Destroy(shelf.gameObject);
            return all > 0 ? fav / (double)all : 0;
        }

        /// <summary>The same shops over the same days give identical stock in two runs (each shop is the same in every game).</summary>
        void Same(int day0)
        {
            string a = Signature(day0), b = Signature(day0);
            Log(a == b ? "PASS two runs give identical stock at an armorer, general store, pawn shop and alchemist (" + a.Length + " chars of daily signature)" : "FAIL two runs differ");
        }

        string Signature(int day0)
        {
            StringBuilder sig = new StringBuilder();
            DFLocation.BuildingTypes[] types = { DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.GeneralStore, DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.Alchemist };
            for (int t = 0; t < types.Length; t++)
            {
                DaggerfallLoot[] shelves = MakeShelves();
                PlayerGPS.DiscoveredBuilding b = Shop(types[t], 99 + t);
                for (int d = 1; d <= 60; d++)
                {
                    using (new WorldLevel.Scope(25))
                        for (int i = 0; i < Shelves; i++)
                            DoomerfallShopLedger.Restock(shelves[i], b, 4242, i, Shelves, day0 + d, 25);
                    foreach (DaggerfallLoot s in shelves)
                    {
                        for (int i = 0; i < s.Items.Count; i++)
                        {
                            DaggerfallUnityItem item = s.Items.GetItem(i);
                            sig.Append(item.ItemGroup).Append('.').Append(item.TemplateIndex).Append('.').Append(item.nativeMaterialValue).Append('.').Append(item.stackCount).Append(',');
                        }
                        sig.Append('|');
                    }
                }
                Free(shelves);
            }
            return sig.ToString();
        }

        /// <summary>Daedric pieces on the shelves of many shops per sampled day, by level and shop type.</summary>
        void Daedric(int day0)
        {
            double top = 0, top20 = 0;
            foreach (int[] c in new[] { new[] { 30, 0 }, new[] { 25, 0 }, new[] { 20, 0 }, new[] { 15, 0 }, new[] { 30, 1 }, new[] { 30, 2 } })
            {
                int level = c[0];
                DFLocation.BuildingTypes type = c[1] == 0 ? DFLocation.BuildingTypes.WeaponSmith : c[1] == 1 ? DFLocation.BuildingTypes.Armorer : DFLocation.BuildingTypes.GeneralStore;
                int count = c[1] == 0 && level == 30 ? 120 : 60;
                long pieces = 0, stocked = 0, samples = 0, withAny = 0, arrivals = 0;
                long bigPieces = 0, bigSamples = 0, trickleStocked = 0, trickleSamples = 0, bigStocked = 0;
                int stockMin = int.MaxValue, stockMax = 0;
                for (int k = 0; k < count; k++)
                {
                    int location = 50000 + k + level * 1000 + c[1] * 100000;
                    PlayerGPS.DiscoveredBuilding b = Shop(type, 3 + k * 31);
                    DoomerfallShopIdentity id = DoomerfallShopIdentity.For(location, b);
                    DaggerfallLoot[] shelves = MakeShelves();
                    HashSet<DaggerfallUnityItem> known = new HashSet<DaggerfallUnityItem>();
                    for (int d = 1; d <= 90; d++)
                    {
                        using (new WorldLevel.Scope(level))
                            for (int i = 0; i < Shelves; i++)
                                DoomerfallShopLedger.Restock(shelves[i], b, location, i, Shelves, day0 + d, level);
                        int n = 0, st = 0;
                        foreach (DaggerfallLoot s in shelves)
                            for (int i = 0; i < s.Items.Count; i++)
                            {
                                DaggerfallUnityItem item = s.Items.GetItem(i);
                                if (IsDaedric(item)) { n++; if (known.Add(item) && d > 1) arrivals++; }
                                if (Stocked(item)) st++;
                            }
                        pieces += n; stocked += st; samples++; if (n > 0) withAny++;
                        stockMin = Mathf.Min(stockMin, st); stockMax = Mathf.Max(stockMax, st);
                        if (id.Big) { bigPieces += n; bigSamples++; bigStocked += st; } else { trickleStocked += st; trickleSamples++; }
                    }
                    Free(shelves);
                }
                double mean = pieces / (double)samples, any = withAny / (double)samples;
                double perMonth = arrivals / (double)count / 89 * 30;
                string verdict = "";
                if (c[1] == 0 && level == 30)
                {
                    top = mean;
                    verdict = (mean >= 0.7 && mean <= 1.4 && any >= 0.5 ? "PASS" : "FAIL") + " best smith target (about one Daedric piece, usually there): ";
                }
                if (c[1] == 0 && level == 20) top20 = mean;
                Log(string.Format("{0}{1} level {2} ({3} shops x 90 days, {4} shelves, stock target {5}, material budget {6:F2}/day): {7:F2} Daedric pieces on the shelves per shop-day, at least one on {8:P0} of shop-days; {9:F2} new Daedric arrivals per shop per month; stocked goods per day mean {10:F1} (min {11}, max {12}); trickle shops {13:F1}, big-delivery shops {14:F1} goods and {15:F2} Daedric",
                    verdict, type, level, count, Shelves, DoomerfallShopLedger.StockTarget(level), DoomerfallShopLedger.MaterialBudget(level), mean, any, perMonth,
                    stocked / (double)samples, stockMin, stockMax, trickleStocked / (double)Mathf.Max(1, trickleSamples), bigStocked / (double)Mathf.Max(1, bigSamples), bigPieces / (double)Mathf.Max(1, bigSamples)));
            }
            Log(string.Format("{0} a level 20 smith holds fewer Daedric pieces than a level 30 smith ({1:F2} vs {2:F2})", top20 < top ? "PASS" : "FAIL", top20, top));
        }

        DaggerfallLoot[] MakeShelves()
        {
            DaggerfallLoot[] shelves = new DaggerfallLoot[Shelves];
            for (int i = 0; i < Shelves; i++)
                shelves[i] = new GameObject("Doomerfall identity test shelf").AddComponent<DaggerfallLoot>();
            return shelves;
        }

        static void Free(DaggerfallLoot[] shelves) { foreach (DaggerfallLoot s in shelves) Destroy(s.gameObject); }
    }
}
