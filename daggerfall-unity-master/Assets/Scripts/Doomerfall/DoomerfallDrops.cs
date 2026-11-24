// Doomerfall: decides which Daggerfall enemy a dungeon placement is, and rolls what that enemy carries.
// Runs only in a bridge session.
//
// The world does not scale to the player, so every level below is the area level. Daggerfall's own encounter
// tables, loot tables, and equipment code do the work. A placement's type is a pure function of the location,
// the placement, and the area level, so it stays the same through save, load, and re-entry.

using System;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallDrops
    {
        internal const int MinAreaLevel = 0, MaxAreaLevel = 30;

        // Used only if the area level table could not be built. Level 1 is what a new character sees in Daggerfall.
        const int UndefinedAreaLevel = 1;
        const int WaterTable = 19, ClassicSlots = 256, InvalidFixedType = 99;
        const int NoWater = 10000;

        static int testAreaLevel = int.MinValue;

        /// <summary>The location's area level from DoomerfallAreaLevels: its dungeon level, or the terrain level if it has no dungeon. -dfarealevel N overrides it for tests.</summary>
        internal static int AreaLevel(in DFLocation location)
        {
            int test = TestAreaLevel();
            if (test >= 0)
                return test;
            DoomerfallAreaLevels.Level level;
            return DoomerfallAreaLevels.ForLocation(location, out level) ? level.Area : UndefinedAreaLevel;
        }

        /// <summary>
        /// WorldLevel's provider in a bridge session: the area level where the player is now (the dungeon's level
        /// inside a dungeon, otherwise the terrain level of the map pixel). Never the player's level.
        /// </summary>
        internal static int CurrentWorldLevel()
        {
            int test = TestAreaLevel();
            if (test >= 0)
                return Mathf.Max(1, test);
            int level = DoomerfallAreaLevels.ForCurrentPlace();
            return level > 0 ? Mathf.Min(level, MaxAreaLevel) : UndefinedAreaLevel;
        }

        /// <summary>WorldLevel's dungeon provider in a bridge session: the level a dungeon is built at, before the player is inside.</summary>
        internal static int DungeonWorldLevel(DFLocation location)
        {
            int test = TestAreaLevel();
            if (test >= 0)
                return Mathf.Max(1, test);
            DoomerfallAreaLevels.Level level;
            if (!DoomerfallAreaLevels.ForLocation(location, out level))
                return UndefinedAreaLevel;
            return Mathf.Clamp(level.Area, 1, MaxAreaLevel);
        }

        /// <summary>The -dfarealevel N test override, or -1 without one.</summary>
        internal static int TestAreaLevel()
        {
            if (testAreaLevel == int.MinValue)
            {
                testAreaLevel = -1;
                string[] args = Environment.GetCommandLineArgs();
                int at = Array.IndexOf(args, "-dfarealevel");
                int value;
                if (at >= 0 && at + 1 < args.Length && int.TryParse(args[at + 1], out value))
                    testAreaLevel = Mathf.Clamp(value, MinAreaLevel, MaxAreaLevel);
            }
            return testAreaLevel;
        }

        /// <summary>Chooses enemies for one dungeon by Daggerfall's rules, with stable draws in place of its time-seeded ones.</summary>
        internal sealed class EnemyPicker
        {
            readonly RandomEncounterTable land, water;
            readonly MobileTypes[] classicLand, classicWater;
            readonly float power;
            readonly int variance;
            readonly bool valid;

            internal EnemyPicker(int locationId, DFRegion.DungeonTypes dungeonType, int areaLevel, int monsterVariance, bool alternateSelection)
            {
                int index = (int)dungeonType;
                if (dungeonType == DFRegion.DungeonTypes.NoDungeon || index < 0 || index >= RandomEncounters.EncounterTables.Length)
                    return;
                int level = Mathf.Max(1, areaLevel);
                valid = true;
                land =RandomEncounters.EncounterTables[index];
                water = RandomEncounters.EncounterTables[WaterTable];
                power = Mathf.Clamp01(level / 20f);
                variance = monsterVariance;
                if (alternateSelection)
                    return;

                // Classic fills two lists from a generator seeded by the location, then each marker picks a slot.
                uint saved = DFRandom.Seed;
                DFRandom.srand(locationId);
                classicLand = new MobileTypes[ClassicSlots];
                classicWater = new MobileTypes[ClassicSlots];
                for (int i = 0; i < ClassicSlots; i++)
                    classicLand[i] = RDBLayout.ChooseRandomEnemyType(land, level);
                for (int i = 0; i < ClassicSlots; i++)
                    classicWater[i] = RDBLayout.ChooseRandomEnemyType(water, level);
                DFRandom.Seed = saved;
            }

            internal MobileTypes PickRandom(ulong placementHash, int flags, int y, int waterLevel)
            {
                if (!valid)
                    return MobileTypes.None;
                bool underwater = waterLevel < y;   // Classic values: a greater y is lower.
                MobileTypes type;
                if (classicLand != null)
                {
                    int slot = flags != 0 ? flags & 0xff : 1 + (int)((placementHash >> 8) % 6);
                    type = underwater ? classicWater[slot] : classicLand[slot];
                }
                else
                {
                    RandomEncounterTable table = underwater ? water : land;
                    int center = (int)(table.Enemies.Length * power);
                    int min = Mathf.Max(center - variance, 0);
                    int max = Mathf.Min(center + variance, table.Enemies.Length - 1);
                    type = table.Enemies[min + (int)((placementHash >> 8) % (ulong)(max - min + 1))];
                }
                return PlacedInWater(type, y, waterLevel) ? type : MobileTypes.None;
            }
        }

        internal static MobileTypes PickFixed(int mobile, bool custom, int y, int waterLevel)
        {
            if (!custom && (mobile & 0xff) == InvalidFixedType)
                return MobileTypes.None;
            MobileTypes type = custom ? (MobileTypes)mobile : (MobileTypes)(mobile & 0xff);
            return PlacedInWater(type, y, waterLevel) ? type : MobileTypes.None;
        }

        // Daggerfall places no water creature at a marker out of the water.
        static bool PlacedInWater(MobileTypes type, int y, int waterLevel)
        {
            bool needsWater = type == MobileTypes.Slaughterfish || type == MobileTypes.Dreugh || type == MobileTypes.Lamia;
            return !needsWater || (waterLevel != NoWater && waterLevel - 20 <= y);
        }

        /// <summary>
        /// Builds a real Daggerfall enemy of this type at the area level and returns everything its corpse would hold:
        /// loot table items, generated equipment, map, potion, recipe, and any items a quest queued on it.
        /// The roll uses the fixed loot seed (LootSeed), so the same enemy gives the same drop in every game.
        /// </summary>
        internal static ItemCollection RollEnemy(MobileTypes type, int areaLevel, DaggerfallUnityItem[] queued, int lootSeed)
        {
            ItemCollection result = new ItemCollection();
            MobileEnemy mobile;
            if (type != MobileTypes.None && EnemyBasics.GetEnemy(type, out mobile))
            {
                GameObject holder = new GameObject("Doomerfall drop roll");
                holder.SetActive(false);
                EnemyEntity enemy = new EnemyEntity(holder.AddComponent<DaggerfallEntityBehaviour>());
                WorldLevel.Scope level = new WorldLevel.Scope(Mathf.Clamp(areaLevel, 1, MaxAreaLevel));
                Func<int, WeaponMaterialTypes> sessionRoll = FormulaHelper.DoomerfallMaterialRoll;
                try
                {
                    FormulaHelper.DoomerfallMaterialRoll = RollMaterial;
                    LootSeed.SetEnemy(lootSeed);
                    enemy.SetEnemyCareer(mobile, DaggerfallEntity.IsClassEnemyId(mobile.ID) ? EntityTypes.EnemyClass : EntityTypes.EnemyMonster);
                }
                finally
                {
                    FormulaHelper.DoomerfallMaterialRoll = sessionRoll;   // the bridge keeps it set for the whole session
                    LootSeed.ClearEnemy();
                    level.Dispose();
                    enemy.DetachFromGameEvents();
                    UnityEngine.Object.Destroy(holder);
                }
                // As EnemyDeath does, so equipment is not marked as equipped once it is loot.
                for (int i = (int)EquipSlots.Head; i <= (int)EquipSlots.Feet; i++)
                    if (enemy.ItemEquipTable.GetItem((EquipSlots)i) != null)
                        enemy.ItemEquipTable.UnequipItem((EquipSlots)i);
                result.TransferAll(enemy.Items);
            }
            if (queued != null)
                result.AddItems(queued);
            return result;
        }

        /// <summary>
        /// The owner's approved material odds: a separate Daedric check, then a falling share per tier.
        /// Draws from Unity's generator, which the enemy's loot seed has seeded during a drop roll.
        /// </summary>
        internal static WeaponMaterialTypes RollMaterial(int level)
        {
            if (UnityEngine.Random.value < DaedricChance(level))
                return WeaponMaterialTypes.Daedric;
            double falloff = TierFalloff(level), weight = 1, total = 0;
            const int Tiers = (int)WeaponMaterialTypes.Orcish + 1;
            for (int i = 0; i < Tiers; i++, weight *= falloff)
                total += weight;
            double roll = UnityEngine.Random.value * total;
            weight = 1;
            for (int i = 0; i < Tiers - 1; i++, weight *= falloff)
            {
                if (roll < weight)
                    return (WeaponMaterialTypes)i;
                roll -= weight;
            }
            return WeaponMaterialTypes.Orcish;
        }

        internal static double DaedricChance(int level)
        {
            level = Mathf.Clamp(level, 1, MaxAreaLevel);
            return level <= 20 ? 0.025 * Math.Pow((level - 1) / 19.0, 3) : 0.025 + 0.025 * (level - 20) / 10.0;
        }

        internal static double TierFalloff(int level)
        {
            level = Mathf.Clamp(level, 1, MaxAreaLevel);
            return level <= 20 ? 0.50 + 0.30 * (level - 1) / 19.0 : 0.80 + 0.10 * (level - 20) / 10.0;
        }
    }
}
