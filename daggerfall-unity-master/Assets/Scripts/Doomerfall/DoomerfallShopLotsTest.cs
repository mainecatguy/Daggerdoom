// Doomerfall test only (-dfshoplotstest): once Daggerfall is in a game, runs DoomerfallShopLedger with Shops 7 lots
// over a simulated clock for many shops and logs a survey: lot template shares per shop type, pawn shops' lot kinds,
// estate kits matching themselves, bulk lots identical, Doom guns by tier against the expected rate (and none with
// guns off; other Doom sets at the tiers WeaponValues.txt gives them), two runs identical, and the rare exceptions' share and how each one breaks its shop's usual pattern.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopLotsTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        bool done;
        const int Buildings = 30, Days = 120, Shelves = 2, Level = 18, Quality = 16;
        static readonly DFLocation.BuildingTypes[] Types =
        {
            DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.GeneralStore,
            DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.Alchemist, DFLocation.BuildingTypes.GemStore,
            DFLocation.BuildingTypes.ClothingStore, DFLocation.BuildingTypes.Bookseller,
        };

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshoplotstest") >= 0)
                owner.gameObject.AddComponent<DoomerfallShopLotsTest>().bridge = owner;
        }

        void Log(string s) { bridge.LogLine("shoplots: " + s); }

        /// <summary>The chance (0-1) that one Doom gun roll keeps a gun of this tier: Daggerfall's stock rule.</summary>
        static float KeepChance(string tier, int quality, int weaponChance)
        {
            int rarity = DoomerfallShopLots.RarityOf(tier);
            return rarity > quality ? 0f : Mathf.Clamp(weaponChance * 5 * (21 - rarity) / 100, 0, 100) / 100f;
        }

        static string TierOf(DoomerfallDoomItem item)
        {
            foreach (DoomerfallShopLots.Gun g in DoomerfallShopLots.Guns())
                if (g.pickup == item.DoomClass)
                    return g.tier;
            return null;
        }

        void Update()
        {
            if (done || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || GameManager.Instance.PlayerGPS == null || Time.frameCount < 600)
                return;
            done = true;
            try { Run(); }
            catch (Exception e) { Log("FAILED with exception " + e); }
            finally { DoomerfallShopLots.Observer = null; DoomerfallShopLots.GunsEnabled = true; DoomerfallShopLots.GunSet = "DRLA"; }
        }

        sealed class Seen
        {
            public DoomerfallShopLots.Lot lot;
            public int building;
            public string[] names;
        }

        void Run()
        {
            float started = Time.realtimeSinceStartup;
            int day0 = DoomerfallShopLedger.Day(DaggerfallUnity.Instance.WorldTime.Now);
            Log("Doom guns for sale in set " + DoomerfallShopLots.GunSet + ": " + DoomerfallShopLots.Guns().Count);

            StringBuilder sigA = new StringBuilder(), sigB = new StringBuilder();
            List<Seen> lots = Survey(day0, sigA, true);
            Survey(day0, sigB, false);
            Log(sigA.ToString() == sigB.ToString() ? "PASS two runs give identical lots (" + sigA.Length + " chars of signature)" : "FAIL two runs differ");

            Templates(lots);
            Estates(lots);
            Bulks(lots);
            Guns(lots, day0);
            OtherSets(day0);
            Exceptions(lots, day0);
            Log(string.Format("done in {0:F1}s", Time.realtimeSinceStartup - started));
        }

        static DoomerfallShopLots.Place PlaceFor(int b)
        {
            return new DoomerfallShopLots.Place { region = b % 2 == 0 ? "Daggerfall" : "Sentinel", village = b % 3 == 0 };
        }

        static int Location(DFLocation.BuildingTypes type, int b) { return 20000 + (int)type * 100 + b; }

        List<Seen> Survey(int day0, StringBuilder sig, bool report)
        {
            List<Seen> seen = new List<Seen>();
            int current = 0;
            DoomerfallShopLots.Observer = lot => seen.Add(new Seen { lot = lot, building = current, names = lot.items.Select(i => i.LongName).ToArray() });
            foreach (DFLocation.BuildingTypes type in Types)
                for (int b = 0; b < Buildings; b++)
                {
                    current = b;
                    DaggerfallLoot[] shelves = new DaggerfallLoot[Shelves];
                    for (int i = 0; i < Shelves; i++)
                        shelves[i] = new GameObject("Doomerfall lots test shelf").AddComponent<DaggerfallLoot>();
                    PlayerGPS.DiscoveredBuilding building = new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = Quality, buildingKey = 7 + b };
                    using (new WorldLevel.Scope(Level))
                        for (int d = 1; d <= Days; d++)
                            for (int i = 0; i < Shelves; i++)
                                DoomerfallShopLedger.Restock(shelves[i], building, Location(type, b), i, Shelves, day0 + d, Level, PlaceFor(b));
                    foreach (DaggerfallLoot s in shelves)
                    {
                        for (int i = 0; i < s.Items.Count; i++)
                            sig.Append(s.Items.GetItem(i).LongName).Append(s.Items.GetItem(i).value).Append(';');
                        Destroy(s.gameObject);
                    }
                }
            DoomerfallShopLots.Observer = null;
            return seen;
        }

        void Templates(List<Seen> lots)
        {
            bool pawnOk = true;
            foreach (DFLocation.BuildingTypes type in Types)
            {
                List<Seen> mine = lots.Where(s => s.lot.shop == type).ToList();
                List<Seen> regularDays = mine.Where(s => !s.lot.exception).ToList();
                StringBuilder line = new StringBuilder();
                foreach (var g in regularDays.GroupBy(s => s.lot.template).OrderByDescending(g => g.Count()))
                    line.AppendFormat(" {0} {1:F1}% ({2} lots, {3:F1} items each);", g.Key, 100.0 * g.Count() / Math.Max(1, regularDays.Count), g.Count(), g.Average(s => s.lot.added));
                Log(string.Format("{0}: {1} lots:{2}", type, regularDays.Count, line));
                if (type == DFLocation.BuildingTypes.PawnShop)
                    pawnOk = regularDays.Count > 0 && regularDays.All(s => s.lot.template == "estate" || s.lot.template == "salvage" || s.lot.template == "townsfolk");
            }
            Log((pawnOk ? "PASS" : "FAIL") + " pawn shops get only estate, salvage and townsfolk lots (besides their exceptions)");
            // Example lots, one of each template, so a person can read them.
            foreach (var g in lots.GroupBy(s => s.lot.template))
            {
                Seen e = g.FirstOrDefault(s => s.lot.added >= Math.Min(4, s.lot.items.Count)) ?? g.First();
                Log(string.Format("example {0} lot at a {1} ({2}): {3}", g.Key, e.lot.shop, e.lot.detail, string.Join(", ", e.names)));
            }
        }

        void Estates(List<Seen> lots)
        {
            int kits = 0, matching = 0, worn = 0, wornItems = 0;
            string mismatch = null;
            foreach (Seen s in lots.Where(s => s.lot.template == "estate"))
            {
                kits++;
                // A magic item is a separate find, and Daggerfall arrows carry no material.
                List<DaggerfallUnityItem> kit = s.lot.items.Where(i => !i.IsEnchanted && !i.IsOfTemplate(ItemGroups.Weapons, (int)Weapons.Arrow)).ToList();
                var weapons = kit.Where(i => i.ItemGroup == ItemGroups.Weapons).Select(i => i.nativeMaterialValue).Distinct().Count();
                var armors = kit.Where(i => i.ItemGroup == ItemGroups.Armor).Select(i => i.nativeMaterialValue).Distinct().ToList();
                bool plateMatches = true;
                DaggerfallUnityItem weapon = kit.FirstOrDefault(i => i.ItemGroup == ItemGroups.Weapons);
                if (weapon != null && armors.Count == 1 && armors[0] >= 0x0200)
                    plateMatches = armors[0] - 0x0200 == weapon.nativeMaterialValue;
                if (weapons <= 1 && armors.Count <= 1 && plateMatches)
                    matching++;
                else if (mismatch == null)
                    mismatch = s.lot.detail + ": " + string.Join(", ", kit.Select(i => i.LongName + " [" + i.nativeMaterialValue + "]").ToArray());
                foreach (DaggerfallUnityItem i in s.lot.items)
                    if ((i.ItemGroup == ItemGroups.Weapons || i.ItemGroup == ItemGroups.Armor) && !i.IsOfTemplate(ItemGroups.Weapons, (int)Weapons.Arrow))
                    {
                        wornItems++;
                        if (i.currentCondition < i.maxCondition) worn++;
                    }
            }
            Log(string.Format("{0} estate kits match themselves (not counting magic items or arrows: one weapon material, one armor material, plate of the weapon's material): {1} of {2}; weapons and armor worn: {3} of {4}{5}",
                kits > 0 && matching == kits ? "PASS" : "FAIL", matching, kits, worn, wornItems, mismatch != null ? "; first mismatch: " + mismatch : ""));
        }

        void Bulks(List<Seen> lots)
        {
            int n = 0, same = 0;
            foreach (Seen s in lots.Where(s => s.lot.template == "bulk"))
            {
                n++;
                if (s.names.Distinct().Count() == 1)
                    same++;
            }
            int towns = lots.Count(s => s.lot.template == "townsfolk"), single = lots.Count(s => s.lot.template == "townsfolk" && s.lot.added == 1);
            Log(string.Format("{0} bulk lots are identical items: {1} of {2}; townsfolk lots are one item: {3} of {4}",
                n > 0 && same == n && single == towns ? "PASS" : "FAIL", same, n, single, towns));
        }

        void Guns(List<Seen> lots, int day0)
        {
            List<DoomerfallShopLots.Gun> guns = DoomerfallShopLots.Guns();
            if (guns.Count == 0)
            {
                Log("FAIL no Doom guns loaded (WeaponValues.txt missing?)");
                return;
            }
            Dictionary<string, int> got = DoomerfallShopLots.Tiers.ToDictionary(t => t, t => 0);
            foreach (Seen s in lots.Where(s => s.lot.shop == DFLocation.BuildingTypes.WeaponSmith && s.lot.template == "regular"))
                foreach (DaggerfallUnityItem i in s.lot.items)
                {
                    DoomerfallDoomItem d = i as DoomerfallDoomItem;
                    string t = d != null ? TierOf(d) : null;
                    if (t != null) got[t]++;
                }
            TierShares("DRLA", got, guns, 0);
            int top = 0;
            foreach (DaggerfallUnityItem i in lots.Where(s => s.lot.shop == DFLocation.BuildingTypes.WeaponSmith).SelectMany(s => s.lot.items))
                if (i is DoomerfallDoomItem) { top = Math.Max(top, i.value); }
            Log(string.Format("most valuable Doom gun stocked: {0} gold", top));
            int pawnRegular = lots.Count(s => s.lot.shop == DFLocation.BuildingTypes.PawnShop && !s.lot.exception && s.lot.items.Any(i => i is DoomerfallDoomItem));
            Log((pawnRegular == 0 ? "PASS" : "FAIL") + " pawn shops get Doom guns only from the estate exception: " + pawnRegular + " ordinary pawn lots with a gun");

            DoomerfallShopLots.GunsEnabled = false;
            int off = 0;
            DoomerfallShopLots.Observer = lot => off += lot.items.Count(i => i is DoomerfallDoomItem);
            foreach (DFLocation.BuildingTypes type in new[] { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.GeneralStore })
                for (int b = 0; b < Buildings; b++)
                {
                    DaggerfallLoot shelf = new GameObject("Doomerfall lots test shelf").AddComponent<DaggerfallLoot>();
                    PlayerGPS.DiscoveredBuilding building = new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = 20, buildingKey = 7 + b };
                    using (new WorldLevel.Scope(Level))
                        for (int d = 1; d <= Days; d++)
                            DoomerfallShopLedger.Restock(shelf, building, Location(type, b), 0, 1, day0 + d, Level, PlaceFor(b));
                    Destroy(shelf.gameObject);
                }
            DoomerfallShopLots.Observer = null;
            DoomerfallShopLots.GunsEnabled = true;
            Log((off == 0 ? "PASS" : "FAIL") + " guns off: " + off + " Doom guns delivered at weapon smiths, pawn shops and general stores in " + Days + " days");
        }

        void Exceptions(List<Seen> lots, int day0)
        {
            // Share: over many buildings and a year of days, the fraction of building-days inside an exception window.
            int days = 0, inWindow = 0;
            Dictionary<string, int> byName = new Dictionary<string, int>();
            foreach (DFLocation.BuildingTypes type in Types)
                for (int b = 0; b < 200; b++)
                    for (int d = 1; d <= 360; d++)
                    {
                        days++;
                        DoomerfallShopLots.Rec r = DoomerfallShopLots.ExceptionFor(30000 + b, 7 + b, type, day0 + d, PlaceFor(b));
                        string name = r == null ? null : r.name;
                        if (name == null) continue;
                        inWindow++;
                        int c; byName.TryGetValue(type + " " + name, out c); byName[type + " " + name] = c + 1;
                    }
            double share = (double)inWindow / days;
            Log(string.Format("{0} exception windows cover {1:F2}% of building-days (setting {2:F1}% of windows, for shop types that have one): {3}",
                share > 0 && share < 0.06 ? "PASS" : "FAIL", 100 * share, 100 * DoomerfallShopLots.ExceptionShare,
                string.Join(", ", byName.OrderBy(k => k.Key).Select(k => k.Key + " " + (100.0 * k.Value / (200 * 360)).ToString("F2") + "%").ToArray())));
            int totalLots = lots.Count, exLots = lots.Count(s => s.lot.exception);
            Log(string.Format("exception lots in the survey: {0} of {1} lots ({2:F2}%)", exLots, totalLots, 100.0 * exLots / Math.Max(1, totalLots)));

            // Each exception against how often ordinary lots at the same shop type show its signature.
            Signature(lots, "pawngun", DFLocation.BuildingTypes.PawnShop, "a Doom gun", s => s.lot.items.Any(i => i is DoomerfallDoomItem));
            FullShelf(day0);
            // Window exceptions shape a whole week of deliveries, so compare weeks.
            Weeks(lots, "siege", DFLocation.BuildingTypes.GeneralStore, "every item delivered (3+) is a weapon",
                items => items.Count >= 3 && items.All(i => i.ItemGroup == ItemGroups.Weapons));
            Weeks(lots, "onekind", DFLocation.BuildingTypes.WeaponSmith, "every weapon delivered (3+) is one kind", items =>
            {
                List<DaggerfallUnityItem> weapons = items.Where(i => i.ItemGroup == ItemGroups.Weapons && !i.IsOfTemplate(ItemGroups.Weapons, (int)Weapons.Arrow)).ToList();
                return weapons.Count >= 3 && weapons.Select(i => i.TemplateIndex).Distinct().Count() == 1;
            });
        }

        void Weeks(List<Seen> lots, string name, DFLocation.BuildingTypes type, string what, Func<List<DaggerfallUnityItem>, bool> shows)
        {
            int exWeeks = 0, exShows = 0, weeks = 0, ordShows = 0;
            foreach (var g in lots.Where(s => s.lot.shop == type).GroupBy(s => s.building * 100000 + s.lot.day / DoomerfallShopLots.WindowDays))
            {
                List<DaggerfallUnityItem> items = g.SelectMany(s => s.lot.items).Where(i => !(i is DoomerfallAmmoItem)).ToList();
                bool hit = shows(items);
                if (g.Any(s => s.lot.exception && s.lot.template == name)) { exWeeks++; if (hit) exShows++; }
                else if (items.Count >= 3) { weeks++; if (hit) ordShows++; }
            }
            Log(string.Format("{0} exception {1} at {2}: {3} of {4} exception weeks show '{5}'; other weeks showing it: {6} of {7}",
                exWeeks > 0 && exShows * 10 >= exWeeks * 9 && ordShows * 50 <= weeks ? "PASS" : "FAIL", name, type, exShows, exWeeks, what, ordShows, weeks));
        }

        /// <summary>A once-exception due on a full shelf still arrives, and nothing already on the shelf is removed.</summary>
        void FullShelf(int day0)
        {
            DoomerfallShopLots.Place place = PlaceFor(1);
            for (int b = 0; b < 400; b++)
                for (int d = 7; d <= 360; d++)
                {
                    DoomerfallShopLots.Rec r = DoomerfallShopLots.ExceptionFor(40000 + b, 7 + b, DFLocation.BuildingTypes.PawnShop, day0 + d, place);
                    if (r == null || r.name != "pawngun" || (day0 + d) % DoomerfallShopLots.WindowDays != 0)
                        continue;
                    DaggerfallLoot shelf = new GameObject("Doomerfall lots test shelf").AddComponent<DaggerfallLoot>();
                    PlayerGPS.DiscoveredBuilding pawn = new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.PawnShop, quality = 20, buildingKey = 7 + b };
                    using (new WorldLevel.Scope(Level))
                        DoomerfallShopLedger.Restock(shelf, pawn, 40000 + b, 0, 1, day0 + d - 1, Level, place);   // stocked yesterday
                    int share = DoomerfallShopLedger.StockTarget(Level);
                    while (DoomerfallShopLedger.Stocked(shelf.Items) < share + 20)   // full well past its share, so sell-off cannot make room
                        shelf.Items.AddItem(ItemBuilder.CreateRandomBook(), ItemCollection.AddPosition.Back, true);
                    List<DaggerfallUnityItem> before = new List<DaggerfallUnityItem>();
                    for (int i = 0; i < shelf.Items.Count; i++) before.Add(shelf.Items.GetItem(i));
                    int guns = 0;
                    DoomerfallShopLots.Observer = lot => { if (lot.exception) guns += lot.items.Count(i => i is DoomerfallDoomItem); };
                    using (new WorldLevel.Scope(Level))
                        DoomerfallShopLedger.Restock(shelf, pawn, 40000 + b, 0, 1, day0 + d, Level, place);
                    DoomerfallShopLots.Observer = null;
                    Destroy(shelf.gameObject);
                    Log(string.Format("{0} full shelf: a pawn shop {1} items over its share on its pawngun day got {2} exception Doom gun(s); deliveries never remove items (only the day's seeded sell-off does)",
                        guns > 0 ? "PASS" : "FAIL", DoomerfallShopLedger.Stocked(shelf.Items) - share, guns));
                    return;
                }
            Log("FAIL full shelf: no pawngun day found");
        }

        void Signature(List<Seen> lots, string name, DFLocation.BuildingTypes type, string what, Func<Seen, bool> shows)
        {
            List<Seen> mine = lots.Where(s => s.lot.shop == type).ToList();
            List<Seen> ex = mine.Where(s => s.lot.exception && s.lot.template == name).ToList();
            List<Seen> ordinary = mine.Where(s => !s.lot.exception).ToList();
            int exShows = ex.Count(shows), ordShows = ordinary.Count(shows);
            bool pass = ex.Count > 0 && exShows == ex.Count && ordShows * 200 <= ordinary.Count;
            Seen sample = ex.FirstOrDefault();
            Log(string.Format("{0} exception {1} at {2}: {3} lots, {4} show '{5}'; ordinary lots there showing it: {6} of {7}{8}", pass ? "PASS" : "FAIL", name, type,
                ex.Count, exShows, what, ordShows, ordinary.Count, sample != null ? "; example: " + sample.lot.detail + ": " + string.Join(", ", sample.names) : ""));
        }

        /// <summary>Tier shares among stocked guns must fall by tier (owner: rarer by tier), over the tiers the shop's
        /// quality allows and the set has guns in; tiers above the shop's quality must be 0.</summary>
        void TierShares(string set, Dictionary<string, int> got, List<DoomerfallShopLots.Gun> guns, int foreign)
        {
            string[] tiers = DoomerfallShopLots.Tiers;
            int stocked = got.Values.Sum();
            List<string> allowed = tiers.Where(t => DoomerfallShopLots.RarityOf(t) <= Quality && guns.Any(g => g.tier == t)).ToList();
            bool pass = stocked > 30 && foreign == 0;
            for (int k = 1; k < allowed.Count; k++)
                if (got[allowed[k]] >= got[allowed[k - 1]]) pass = false;
            if (tiers.Any(t => DoomerfallShopLots.RarityOf(t) > Quality && got[t] > 0)) pass = false;
            Log(string.Format("{0} {1} Doom guns at weapon smiths (quality {2}) fall by tier, {3} stocked: {4} (tiers above quality must be 0; guns from another set: {5})",
                pass ? "PASS" : "FAIL", set, Quality, stocked,
                string.Join(", ", tiers.Select(t => t + " " + (100.0 * got[t] / Math.Max(1, stocked)).ToString("F1") + "% (" + guns.Count(g => g.tier == t) + " guns in set)").ToArray()),
                foreign));
        }

        /// <summary>Guns from sets other than DRLA use the tiers WeaponValues.txt infers for them (owner, 2026-11-27).</summary>
        void OtherSets(int day0)
        {
            foreach (string set in new[] { "Doom", "Heretic", "Hexen", "Schism" })
            {
                DoomerfallShopLots.GunSet = set;
                List<DoomerfallShopLots.Gun> guns = DoomerfallShopLots.Guns();
                if (guns.Count == 0)
                {
                    Log("FAIL no " + set + " guns in WeaponValues.txt");
                    continue;
                }
                Dictionary<string, int> got = DoomerfallShopLots.Tiers.ToDictionary(t => t, t => 0);
                int foreign = 0;
                DoomerfallShopLots.Observer = lot =>
                {
                    if (lot.template != "regular") return;
                    foreach (DoomerfallDoomItem d in lot.items.OfType<DoomerfallDoomItem>())
                    {
                        string t = TierOf(d);
                        if (t != null) got[t]++; else foreign++;
                    }
                };
                for (int b = 0; b < Buildings; b++)
                {
                    DaggerfallLoot shelf = new GameObject("Doomerfall lots test shelf").AddComponent<DaggerfallLoot>();
                    PlayerGPS.DiscoveredBuilding building = new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.WeaponSmith, quality = Quality, buildingKey = 7 + b };
                    using (new WorldLevel.Scope(Level))
                        for (int d = 1; d <= Days; d++)
                            DoomerfallShopLedger.Restock(shelf, building, Location(DFLocation.BuildingTypes.WeaponSmith, b), 0, 1, day0 + d, Level, PlaceFor(b));
                    Destroy(shelf.gameObject);
                }
                DoomerfallShopLots.Observer = null;
                TierShares(set, got, guns, foreign);
            }
            DoomerfallShopLots.GunSet = "DRLA";
        }
    }
}
