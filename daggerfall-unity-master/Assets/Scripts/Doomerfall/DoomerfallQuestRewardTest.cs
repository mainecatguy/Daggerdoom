// Doomerfall test only, run by -dfworldleveltest: proves quest rewards follow the area level of the place a giver
// offers the quest in, stay at the fixed level for quests no giver offers, and ignore the player's level.
//
// Builds quest reward items through Daggerfall's own quest code (Questing.Item from the script lines a quest uses,
// "Item _reward_ magic_item" and "Item _gold_ gold") with fixed seeds. At each of several area levels (a WorldLevel
// scope stands in for the giver's town), the same seeds are rolled with the player at level 1 and at level 25 and must
// match; the same seeds at area levels 1 and 20 must differ. It logs a gold table by area level. A control pass
// repeats this with the Doomerfall providers switched off, as normal Daggerfall Unity would roll, and must differ by
// player level. It also tallies the materials of many quest magic items at area levels 1 and 20, so
// tools/world_level/world_level.py can compare them with the approved odds at those levels.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Utility;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Questing;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallQuestRewardTest
    {
        const int Seeds = 12;
        const int GoldSeeds = 200;
        const int TallyRolls = 3000;
        static readonly int[] PlayerLevels = { 1, 25 };
        static readonly int[] AreaLevels = { 1, 2, 4, 6, 8, 10, 14, 18, 20, 30 };
        static readonly int[] TallyLevels = { 1, 20 };
        const ushort NeutralPrice = 1000, LowPrice = 750, HighPrice = 1250;

        /// <summary>Logs the quest reward rolls and checks; returns the rolls at the current place.</summary>
        internal static string Run(DoomerfallBridge bridge)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            int saved = player.Level, region = GameManager.Instance.PlayerGPS.CurrentRegionIndex;
            ushort savedPrice = player.RegionData[region].PriceAdjustment;
            try
            {
                // A new game rolls each region's price adjustment in 750-1250 (FormulaHelper.RandomRegionalPriceAdjustment);
                // this harness leaves it 0, which would halve quest gold. 1000 is the neutral middle.
                int giverLevel;
                using (WorldLevel.ForQuestGiver())
                    giverLevel = WorldLevel.QuestReward;
                bridge.LogLine(string.Format("questreward: place level here {0} (harness region price adjustment {1}, test uses {2})",
                    giverLevel, savedPrice, NeutralPrice));
                bridge.LogLine(string.Format("questreward: quest no giver offers (follow-up, letter, timer) here: level {0} {1}",
                    WorldLevel.QuestReward, WorldLevel.QuestReward == WorldLevel.DoomerfallUnplacedQuestRewardLevel ? "PASS" : "FAIL"));
                player.RegionData[region].PriceAdjustment = NeutralPrice;
                RealPlaces(bridge, player, region);

                // The same quest at several area levels, at two player levels.
                bool allMatch = true;
                Dictionary<int, string> byArea = new Dictionary<int, string>();
                foreach (int area in AreaLevels)
                {
                    string[] rolls = new string[PlayerLevels.Length];
                    for (int i = 0; i < PlayerLevels.Length; i++)
                    {
                        player.Level = PlayerLevels[i];
                        using (new WorldLevel.Scope(area))
                            rolls[i] = Rolls();
                    }
                    allMatch &= rolls[0] == rolls[1];
                    byArea[area] = rolls[0];

                    bridge.LogLine(string.Format("questreward: table area level {0}: {1}; player levels {2} and {3}: {4}",
                        area, GoldRange(player, region, area), PlayerLevels[0], PlayerLevels[1], rolls[0] == rolls[1] ? "MATCH" : "MISMATCH"));
                }
                foreach (string line in byArea[AreaLevels[0]].Split('\n'))
                    if (line.Length > 0) bridge.LogLine("questreward: area level " + AreaLevels[0] + " " + line);
                bridge.LogLine(string.Format("questreward: reward by area level, player levels {0} and {1}: {2}",
                    PlayerLevels[0], PlayerLevels[1], allMatch ? "MATCH" : "MISMATCH"));
                bridge.LogLine(string.Format("questreward: same quest at area levels 1 and 20: {0}",
                    byArea[1] != byArea[20] ? "DIFFER (expected)" : "SAME (not scaled)"));

                string[] classic = new string[PlayerLevels.Length];
                for (int i = 0; i < PlayerLevels.Length; i++)
                {
                    player.Level = PlayerLevels[i];
                    classic[i] = Classic(Rolls);
                }
                bridge.LogLine(string.Format("questreward: control (normal Daggerfall Unity) player levels {0} and {1}: {2}",
                    PlayerLevels[0], PlayerLevels[1], classic[0] == classic[1] ? "SAME (test not sensitive)" : "DIFFER (expected)"));

                // Materials of quest magic items, at a low player level so player-level odds would show.
                player.Level = 1;
                foreach (int area in TallyLevels)
                {
                    DoomerfallMaterialOddsTest.Tally magic = new DoomerfallMaterialOddsTest.Tally();
                    Quest quest = new Quest();
                    using (new WorldLevel.Scope(area))
                        for (int i = 0; i < TallyRolls; i++)
                            using (new LootSeed.Scope(LootSeed.Of(8100, "questmagic", i)))
                            {
                                magic.rolls++;
                                magic.Add(new Item(quest, "Item _reward_ magic_item").DaggerfallUnityItem);
                            }
                    bridge.LogLine(string.Format("materialodds: quest level {0} questmagic {1}", area, magic.Line()));
                }
                return byArea[1];
            }
            finally
            {
                player.Level = saved;
                player.RegionData[region].PriceAdjustment = savedPrice;
            }
        }

        // Gold of the same quest line at an area level: at the neutral price adjustment, and the extremes a new game can roll.
        static string GoldRange(PlayerEntity player, int region, int area)
        {
            StringBuilder s = new StringBuilder();
            foreach (ushort price in new ushort[] { NeutralPrice, LowPrice, HighPrice })
            {
                player.RegionData[region].PriceAdjustment = price;
                List<int> gold = new List<int>();
                using (new WorldLevel.Scope(area))
                    for (int seed = 0; seed < GoldSeeds; seed++)
                        gold.Add(Gold(seed));
                gold.Sort();
                long sum = 0;
                foreach (int g in gold) sum += g;
                s.AppendFormat("{0}gold at price {1}: {2}-{3} mean {4} (n={5})", s.Length > 0 ? ", " : "", price, gold[0], gold[gold.Count - 1], sum / gold.Count, gold.Count);
            }
            player.RegionData[region].PriceAdjustment = NeutralPrice;
            return s.ToString();
        }

        // The real provider's per-location level (DoomerfallDrops.QuestRewardLevelAt, what QuestRewardLevel returns for
        // the player's current location) at real places, and the range of reward levels over every classic town.
        static void RealPlaces(DoomerfallBridge bridge, PlayerEntity player, int playerRegion)
        {
            ContentReader reader = DaggerfallUnity.Instance.ContentReader;
            string[] wanted = { "village", "hamlet", "city", "capital", "other" };
            int[] min = { 99, 99, 99, 99, 99 }, max = new int[5], count = new int[5];
            bool[] shown = new bool[5];
            int daggerfall = Array.IndexOf(MapsFile.RegionNames, "Daggerfall");
            for (int r = 0; r < reader.MapFileReader.RegionCount; r++)
            {
                DFRegion dfRegion = reader.MapFileReader.GetRegion(r);
                for (int i = 0; i < dfRegion.LocationCount; i++)
                {
                    int type = (int)dfRegion.MapTable[i].LocationType;
                    int cls = DoomerfallAreaLevels.TownClassLevel(type, MapsFile.RegionNames[r], dfRegion.MapNames[i]);
                    int k = cls == DoomerfallAreaLevels.TownSmall ? 0 : cls == DoomerfallAreaLevels.TownMedium ? 1
                        : cls == DoomerfallAreaLevels.TownLarge ? 2 : cls == DoomerfallAreaLevels.TownCapital ? 3 : 4;
                    DoomerfallAreaLevels.Level level;
                    if (!DoomerfallAreaLevels.ForMapId(dfRegion.MapTable[i].MapId, out level))
                        continue;
                    count[k]++;
                    min[k] = Math.Min(min[k], level.Place);
                    max[k] = Math.Max(max[k], level.Place);
                    // One example of each kind in the Daggerfall region, through the provider's own per-location code.
                    DFLocation location;
                    if (r == daggerfall && !shown[k] && reader.GetLocation(r, i, out location))
                    {
                        shown[k] = true;
                        int reward = DoomerfallDrops.QuestRewardLevelAt(location);
                        bridge.LogLine(string.Format("questreward: real place {0} ({1}, type {2}): quest reward level {3}; {4}",
                            dfRegion.MapNames[i], wanted[k], dfRegion.MapTable[i].LocationType, reward, GoldRange(player, playerRegion, reward)));
                    }
                }
            }
            // The New Game arrival hamlet and the main quest's first capital.
            foreach (string name in new[] { "Gothway Garden", "Daggerfall" })
            {
                DFLocation location;
                if (reader.GetLocation("Daggerfall", name, out location))
                {
                    int reward = DoomerfallDrops.QuestRewardLevelAt(location);
                    bridge.LogLine(string.Format("questreward: real place {0} (named): quest reward level {1}; {2}", name, reward, GoldRange(player, playerRegion, reward)));
                }
            }
            for (int k = 0; k < wanted.Length; k++)
                bridge.LogLine(string.Format("questreward: all classic {0} locations: {1}, quest reward level {2}-{3}", wanted[k], count[k], min[k], max[k]));
        }

        /// <summary>Quest reward rolls at the current reward level (each line starts "quest").</summary>
        internal static string Rolls()
        {
            StringBuilder s = new StringBuilder();
            Quest quest = new Quest();
            for (int seed = 0; seed < Seeds; seed++)
            {
                using (new LootSeed.Scope(LootSeed.Of(8000, "questmagic", seed)))
                {
                    DaggerfallUnityItem item = new Item(quest, "Item _reward_ magic_item").DaggerfallUnityItem;
                    s.AppendFormat("quest magic {0}: {1} material {2}\n", seed, item.LongName, item.nativeMaterialValue);
                }
                s.AppendFormat("quest gold {0}: {1}\n", seed, Gold(seed));
            }
            return s.ToString();
        }

        static int Gold(int seed)
        {
            using (new LootSeed.Scope(LootSeed.Of(8000, "questgold", seed)))
                return new Item(new Quest(), "Item _gold_ gold").DaggerfallUnityItem.stackCount;
        }

        static string Classic(Func<string> roll)
        {
            Func<int> place = WorldLevel.CurrentPlaceProvider;
            Func<int, WeaponMaterialTypes> materials = FormulaHelper.DoomerfallMaterialRoll;
            WorldLevel.CurrentPlaceProvider = null;
            FormulaHelper.DoomerfallMaterialRoll = null;
            try { return roll(); }
            finally
            {
                WorldLevel.CurrentPlaceProvider = place;
                FormulaHelper.DoomerfallMaterialRoll = materials;
            }
        }
    }
}
