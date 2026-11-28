// Doomerfall test only (-dflockpicksurvey): once Daggerfall is in a game, surveys where lockpicks come from
// (lockpickshops 01). Logs, with PASS or FAIL against the targets in DoomerfallLockpick:
// - shops: for each shop type, 120 shops run through DoomerfallShopLedger for 40 simulated days; the share of visits
//   (days 21-40) with lockpicks on the shelves, and the share of shops that had them at least once;
// - Daggerfall-engine enemy loot: every Daggerfall enemy type rolled through DoomerfallDrops.RollEnemy with 300 fixed
//   loot seeds; the share of drops with lockpicks per group (class enemies, monsters whose loot table carries gold,
//   monsters whose table does not);
// - treasure piles: 600 seeded dungeon piles;
// - that every survey gives the same result twice (seeded).

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLockpickSurveyTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        bool done;

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dflockpicksurvey") >= 0)
                owner.gameObject.AddComponent<DoomerfallLockpickSurveyTest>().bridge = owner;
        }

        void Log(string s) { bridge.LogLine("lockpicks: " + s); }
        static string Mark(bool ok) { return ok ? "PASS" : "FAIL"; }

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
            Log(Mark(DoomerfallLockpick.IsRegistered) + " lockpick item registered");
            int day0 = DoomerfallShopLedger.Day(DaggerfallUnity.Instance.WorldTime.Now);
            StringBuilder a = new StringBuilder(), b = new StringBuilder();
            Shops(day0, a, true);
            Shops(day0, b, false);
            Log(Mark(a.ToString() == b.ToString()) + " shop survey gives the same shelves twice (" + a.Length + " chars)");
            a.Length = 0; b.Length = 0;
            Enemies(a, true);
            Enemies(b, false);
            Log(Mark(a.ToString() == b.ToString()) + " enemy loot survey gives the same drops twice (" + a.Length + " chars)");
            a.Length = 0; b.Length = 0;
            Piles(a, true);
            Piles(b, false);
            Log(Mark(a.ToString() == b.ToString()) + " treasure pile survey gives the same piles twice (" + a.Length + " chars)");
            Log(string.Format("done in {0:F1}s", Time.realtimeSinceStartup - started));
        }

        static int Picks(ItemCollection items)
        {
            return DoomerfallLockpick.Count(items);
        }

        void Shops(int day0, StringBuilder sig, bool report)
        {
            const int ShopsPer = 120, Days = 40, From = 21, Level = 10;
            DFLocation.BuildingTypes[] types = {
                DFLocation.BuildingTypes.GeneralStore, DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.WeaponSmith,
                DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.Alchemist, DFLocation.BuildingTypes.Bookseller,
                DFLocation.BuildingTypes.ClothingStore, DFLocation.BuildingTypes.GemStore };
            foreach (DFLocation.BuildingTypes type in types)
            {
                int visits = 0, withPicks = 0, shopsEver = 0;
                long picks = 0;
                for (int s = 0; s < ShopsPer; s++)
                {
                    int location = 30000 + s * 7;
                    PlayerGPS.DiscoveredBuilding building = new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = 1 + s % 20, buildingKey = 11 + s };
                    DaggerfallLoot shelf = new GameObject("Doomerfall lockpick survey shelf").AddComponent<DaggerfallLoot>();
                    bool ever = false;
                    using (new WorldLevel.Scope(Level))
                        for (int d = 1; d <= Days; d++)
                        {
                            DoomerfallShopLedger.Restock(shelf, building, location, 0, 1, day0 + d, Level);
                            int n = Picks(shelf.Items);
                            if (d >= From)
                            {
                                visits++;
                                if (n > 0) { withPicks++; picks += n; ever = true; }
                                sig.Append(n).Append(',');
                            }
                        }
                    if (ever) shopsEver++;
                    Destroy(shelf.gameObject);
                }
                if (!report)
                    continue;
                float share100 = 100f * withPicks / visits;
                bool main = type == DFLocation.BuildingTypes.GeneralStore || type == DFLocation.BuildingTypes.PawnShop;
                bool metal = type == DFLocation.BuildingTypes.WeaponSmith || type == DFLocation.BuildingTypes.Armorer;
                bool ok = main ? share100 >= 60 : metal ? share100 >= 4 && share100 <= 35 : withPicks == 0;
                Log(string.Format("{0} {1}: lockpicks on {2:F1}% of {3} visits (target {4}), {5} of {6} shops had them at some point, mean stack {7:F1}",
                    Mark(ok), type, share100, visits, main ? "regularly, 60%+" : metal ? "occasionally, 4-35%" : "never",
                    shopsEver, ShopsPer, withPicks > 0 ? (double)picks / withPicks : 0));
            }
        }

        void Enemies(StringBuilder sig, bool report)
        {
            const int Seeds = 300, AreaLevel = 10;
            int[] rolls = new int[3], hits = new int[3];
            string[] groups = { "class enemies", "monsters whose loot table carries gold", "monsters whose loot table has no gold" };
            StringBuilder perType = new StringBuilder();
            foreach (MobileEnemy mobile in EnemyBasics.Enemies)
            {
                bool isClass = DaggerfallEntity.IsClassEnemyId(mobile.ID);
                int g = isClass ? 0 : DoomerfallLockpick.CarriesPicks(EntityTypes.EnemyMonster, mobile.LootTableKey) ? 1 : 2;
                int typeHits = 0;
                for (int s = 0; s < Seeds; s++)
                {
                    int seed = LootSeed.Of(LootSeed.DoomerfallEnemy, "lockpick survey", mobile.ID, s);
                    ItemCollection items = DoomerfallDrops.RollEnemy((MobileTypes)mobile.ID, AreaLevel, null, seed);
                    int n = Picks(items);
                    rolls[g]++;
                    if (n > 0) { hits[g]++; typeHits++; }
                    sig.Append(n);
                }
                perType.Append(string.Format(" {0}({1})={2:F0}%", (MobileTypes)mobile.ID, mobile.LootTableKey, 100f * typeHits / Seeds));
            }
            if (!report)
                return;
            for (int g = 0; g < 3; g++)
            {
                float p = rolls[g] > 0 ? 100f * hits[g] / rolls[g] : 0;
                bool ok = g == 2 ? hits[g] == 0 : p >= 4 && p <= 13;
                Log(string.Format("{0} {1}: lockpicks in {2:F1}% of {3} drops (target {4})", Mark(ok), groups[g], p, rolls[g], g == 2 ? "never" : "sometimes, about 8%"));
            }
            Log("per enemy type (loot table):" + perType);
        }

        void Piles(StringBuilder sig, bool report)
        {
            const int Piles = 600;
            int hits = 0;
            for (int s = 0; s < Piles; s++)
            {
                DaggerfallLoot loot = new GameObject("Doomerfall lockpick survey pile").AddComponent<DaggerfallLoot>();
                LootTables.GenerateLoot(loot, s % 19, LootSeed.Of(LootSeed.DungeonPile, "lockpick survey", s));
                int n = Picks(loot.Items);
                if (n > 0) hits++;
                sig.Append(n);
                Destroy(loot.gameObject);
            }
            if (report)
            {
                float p = 100f * hits / Piles;
                Log(string.Format("{0} treasure piles: lockpicks in {1:F1}% of {2} piles (target about 8%)", Mark(p >= 4 && p <= 13), p, Piles));
            }
        }
    }
}
