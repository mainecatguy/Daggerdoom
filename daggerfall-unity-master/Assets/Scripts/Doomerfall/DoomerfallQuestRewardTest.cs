// Doomerfall test only, run by -dfworldleveltest: proves quest rewards ignore the player's level.
//
// Builds quest reward items through Daggerfall's own quest code (Questing.Item from the script lines a quest uses,
// "Item _reward_ magic_item" and "Item _gold_ gold") with fixed seeds, once with the player at level 1 and once at
// level 25, and logs whether they match. A control pass repeats this with the Doomerfall providers switched off, as
// normal Daggerfall Unity would roll, and must differ. It also tallies the materials of many quest magic items, so
// tools/world_level/world_level.py can compare them with the approved odds at the fixed reward level.

using System;
using System.Text;
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
        const int TallyRolls = 3000;
        static readonly int[] PlayerLevels = { 1, 25 };

        /// <summary>Logs the quest reward rolls and returns their text, for the caller's cross-run hash.</summary>
        internal static string Run(DoomerfallBridge bridge)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            int saved = player.Level;
            try
            {
                string[] doomerfall = new string[PlayerLevels.Length], classic = new string[PlayerLevels.Length];
                for (int i = 0; i < PlayerLevels.Length; i++)
                {
                    player.Level = PlayerLevels[i];
                    doomerfall[i] = Rolls();
                    classic[i] = Classic(Rolls);
                }
                foreach (string line in doomerfall[0].Split('\n'))
                    if (line.Length > 0) bridge.LogLine("questreward: " + line);
                bridge.LogLine(string.Format("questreward: reward level {0}, player levels {1} and {2}: {3}", WorldLevel.QuestReward,
                    PlayerLevels[0], PlayerLevels[1], doomerfall[0] == doomerfall[1] ? "MATCH" : "MISMATCH"));
                bridge.LogLine(string.Format("questreward: control (normal Daggerfall Unity) player levels {0} and {1}: {2}",
                    PlayerLevels[0], PlayerLevels[1], classic[0] == classic[1] ? "SAME (test not sensitive)" : "DIFFER (expected)"));

                // Materials of quest magic items, at a low player level so the approved odds at level 1 would show.
                player.Level = 1;
                DoomerfallMaterialOddsTest.Tally magic = new DoomerfallMaterialOddsTest.Tally();
                Quest quest = new Quest();
                for (int i = 0; i < TallyRolls; i++)
                    using (new LootSeed.Scope(LootSeed.Of(8100, "questmagic", i)))
                    {
                        magic.rolls++;
                        magic.Add(new Item(quest, "Item _reward_ magic_item").DaggerfallUnityItem);
                    }
                bridge.LogLine(string.Format("materialodds: quest level {0} questmagic {1}", WorldLevel.QuestReward, magic.Line()));
                return doomerfall[0];
            }
            finally
            {
                player.Level = saved;
            }
        }

        /// <summary>Quest reward rolls at the player's current level (each line starts "quest").</summary>
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
                using (new LootSeed.Scope(LootSeed.Of(8000, "questgold", seed)))
                    s.AppendFormat("quest gold {0}: {1}\n", seed, new Item(quest, "Item _gold_ gold").DaggerfallUnityItem.stackCount);
            }
            return s.ToString();
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
