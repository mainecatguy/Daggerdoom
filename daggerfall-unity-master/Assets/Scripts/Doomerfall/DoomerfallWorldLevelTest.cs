// Doomerfall test only (-dfworldleveltest <player level>): proves the world ignores the player's level.
//
// As soon as Daggerfall has a player, sets the player's level to the given value. Once in a game, it runs fixed-seed
// rolls through Daggerfall's own code at the current place and at a fixed dungeon (Daggerfall city's): treasure piles,
// shop shelves, a house container, class enemies (level, health, loot, equipment), random encounter picks, and a
// slain Doom enemy's drop. It logs every result and one hash per section. Two runs at different player levels must
// give the same "area" hash. The "control" section repeats the rolls with the area level provider switched off,
// as normal Daggerfall Unity would roll them, so its hash must differ between the runs.

using System;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallWorldLevelTest : MonoBehaviour
    {
        const int Seeds = 4;
        static readonly string[] LootKeys = { "A", "K", "N", "P", "T" };
        static readonly MobileTypes[] ClassEnemies = { MobileTypes.Knight_CityWatch, MobileTypes.Mage, MobileTypes.Warrior, MobileTypes.Nightblade };
        static readonly MobileTypes[] Drops = { MobileTypes.Orc, MobileTypes.Knight };
        static readonly DFLocation.BuildingTypes[] Shops = { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.Armorer, DFLocation.BuildingTypes.GeneralStore, DFLocation.BuildingTypes.PawnShop, DFLocation.BuildingTypes.Alchemist };

        DoomerfallBridge bridge;
        int playerLevel;
        bool levelSet, done;

        internal static void Attach(DoomerfallBridge owner)
        {
            DoomerfallTownLevelWatch.Attach(owner); // test only: -dftownlevellog
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfworldleveltest");
            int level;
            if (at >= 0 && at + 1 < args.Length && int.TryParse(args[at + 1], out level))
            {
                DoomerfallWorldLevelTest test = owner.gameObject.AddComponent<DoomerfallWorldLevelTest>();
                test.bridge = owner;
                test.playerLevel = Mathf.Max(1, level);
            }
        }

        void Update()
        {
            if (done || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || GameManager.Instance.PlayerGPS == null)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!levelSet)
            {
                player.Level = playerLevel;
                levelSet = true;
                bridge.LogLine("worldleveltest: player level set to " + playerLevel);
            }
            if (Time.frameCount < 600 || !DoomerfallAreaLevels.IsFinished)
                return;
            done = true;
            player.Level = playerLevel; // in case a load replaced the player since

            StringBuilder area = new StringBuilder(), control = new StringBuilder();
            DFLocation dungeon;
            bool hasDungeon = DaggerfallUnity.Instance.ContentReader.GetLocation("Daggerfall", "Daggerfall", out dungeon);
            Roll(area, hasDungeon, dungeon);

            Func<int> place = WorldLevel.CurrentPlaceProvider;
            Func<DFLocation, int> dungeons = WorldLevel.DungeonProvider;
            WorldLevel.CurrentPlaceProvider = null;
            WorldLevel.DungeonProvider = null;
            try { Roll(control, hasDungeon, dungeon); }
            finally
            {
                WorldLevel.CurrentPlaceProvider = place;
                WorldLevel.DungeonProvider = dungeons;
            }

            DFPosition pixel = GameManager.Instance.PlayerGPS.CurrentMapPixel;
            bridge.LogLine(string.Format("worldleveltest: player level {0}, map pixel {1},{2}, place level {3}, dungeon {4}",
                player.Level, pixel.X, pixel.Y, DoomerfallDrops.CurrentWorldLevel(), hasDungeon ? DoomerfallDrops.DungeonWorldLevel(dungeon).ToString() : "missing"));
            foreach (string line in area.ToString().Split('\n'))
                if (line.Length > 0) bridge.LogLine("worldleveltest: area " + line);
            bridge.LogLine(string.Format("worldleveltest: area hash {0:x8} ({1} chars)", Hash(area.ToString()), area.Length));
            bridge.LogLine(string.Format("worldleveltest: control hash {0:x8} ({1} chars)", Hash(control.ToString()), control.Length));
        }

        static void Roll(StringBuilder s, bool hasDungeon, in DFLocation dungeon)
        {
            s.AppendFormat("here level {0}\n", WorldLevel.Current);
            RollAll(s, "here");
            if (hasDungeon)
            {
                using (WorldLevel.ForDungeon(dungeon))
                {
                    s.AppendFormat("dungeon level {0}\n", WorldLevel.Current);
                    RollAll(s, "dungeon");
                    // A dungeon's encounter table, as Daggerfall's layout and Doomerfall's placements read it.
                    RandomEncounterTable table = RandomEncounters.EncounterTables[(int)dungeon.MapTableData.DungeonType];
                    for (int seed = 0; seed < Seeds; seed++)
                        using (new LootSeed.Scope(9000 + seed))
                            s.AppendFormat("dungeon pick {0}: {1}\n", seed, RDBLayout.ChooseRandomEnemyType(table, WorldLevel.Current));
                }
            }
        }

        static void RollAll(StringBuilder s, string where)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            for (int seed = 0; seed < Seeds; seed++)
            {
                foreach (string key in LootKeys)
                    using (new LootSeed.Scope(LootSeed.Of(1000, key, seed)))
                        s.AppendFormat("{0} pile {1}/{2}:{3}\n", where, key, seed, Items(LootTables.GenerateRandomLoot(LootTables.GetMatrix(key), player)));

                foreach (DFLocation.BuildingTypes type in Shops)
                {
                    GameObject holder = new GameObject("Doomerfall world level test");
                    DaggerfallLoot shelf = holder.AddComponent<DaggerfallLoot>();
                    using (new LootSeed.Scope(LootSeed.Of(2000, type.ToString(), seed)))
                        shelf.StockShopShelf(new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = 20 });
                    s.AppendFormat("{0} shop {1}/{2}:{3}\n", where, type, seed, Items(shelf.Items));
                    shelf.Items.Clear();
                    shelf.TextureRecord = 15;
                    using (new LootSeed.Scope(LootSeed.Of(2500, type.ToString(), seed)))
                        shelf.StockHouseContainer(new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.House1, quality = 10 });
                    s.AppendFormat("{0} house {1}/{2}:{3}\n", where, type, seed, Items(shelf.Items));
                    Destroy(holder);
                }

                foreach (MobileTypes type in ClassEnemies)
                {
                    MobileEnemy mobile;
                    if (!EnemyBasics.GetEnemy(type, out mobile))
                        continue;
                    GameObject holder = new GameObject("Doomerfall world level test enemy");
                    holder.SetActive(false);
                    EnemyEntity enemy = new EnemyEntity(holder.AddComponent<DaggerfallEntityBehaviour>());
                    using (new LootSeed.Scope(LootSeed.Of(3000, type.ToString(), seed)))
                    {
                        LootSeed.SetEnemy(LootSeed.Of(3500, type.ToString(), seed));
                        try { enemy.SetEnemyCareer(mobile, EntityTypes.EnemyClass); }
                        finally { LootSeed.ClearEnemy(); }
                    }
                    s.AppendFormat("{0} enemy {1}/{2}: level {3} health {4}{5}\n", where, type, seed, enemy.Level, enemy.MaxHealth, Items(enemy.Items));
                    enemy.DetachFromGameEvents();
                    Destroy(holder);
                }

                using (new LootSeed.Scope(LootSeed.Of(4000, where, seed)))
                    s.AppendFormat("{0} encounter {1}: {2} {3}\n", where, seed, RandomEncounters.ChooseRandomEnemy(false), RandomEncounters.ChooseRandomEnemy(false));

                foreach (MobileTypes type in Drops)
                    s.AppendFormat("{0} drop {1}/{2}:{3}\n", where, type, seed, Items(DoomerfallDrops.RollEnemy(type, WorldLevel.Current, null, LootSeed.Of(5000, type.ToString(), seed))));
            }
        }

        static string Items(DaggerfallUnityItem[] items)
        {
            ItemCollection c = new ItemCollection();
            c.AddItems(items);
            return Items(c);
        }

        static string Items(ItemCollection items)
        {
            StringBuilder s = new StringBuilder();
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                s.AppendFormat(" [{0} x{1}]", item.LongName, item.stackCount);
            }
            return s.ToString();
        }

        static uint Hash(string text)
        {
            uint h = 2166136261;
            foreach (char c in text)
            {
                h ^= c;
                h *= 16777619;
            }
            return h;
        }
    }
}
