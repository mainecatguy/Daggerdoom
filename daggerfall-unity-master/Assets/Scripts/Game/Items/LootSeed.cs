// Doomerfall: fixed loot seeds. A random loot roll at a fixed place (a dungeon or building treasure pile, or a
// placed enemy's corpse loot) seeds Unity's generator from fixed facts about that place, so every game rolls the
// same loot there. The save, the time, and the player are never inputs. This is the loot seed only; encounter
// seeds are a separate definition.
//
// Each seeded roll saves and restores Unity's and DFRandom's shared state, so nothing else becomes deterministic.
// The player's level, gender, and race still feed the roll itself until area level replaces them.

using System;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Items
{
    public static class LootSeed
    {
        // Salts keep each kind of roll on its own stream, so a pile and an enemy at the same spot differ.
        public const long DungeonPile = 1, InteriorPile = 2, DungeonEnemy = 3, DoomerfallEnemy = 4, QuestFoe = 5, DoomFloorItem = 6, DoomStarterGun = 7;
        // Used by the dungeon converter, which copies Of: a dungeon's fixed lean among Doom pickups (PickupExport.cs).
        public const long DoomPickupLean = 8;
        // Separate streams for the rolls Daggerfall makes after an enemy's spells are set.
        public const long EnemyExtras = 101;

        static int depth;
        static bool hasBlock;
        static int blockMap, blockX, blockZ;
        static string blockName;
        static bool hasEnemy;
        static int enemySeed;

        /// <summary>True while a seeded roll is running.</summary>
        public static bool Active { get { return depth > 0; } }

        /// <summary>Seed from fixed values. Strings mix in by character, so the result never depends on .NET's string hash.</summary>
        public static int Of(long kind, string text, params long[] values)
        {
            ulong h = Mix(14695981039346656037UL, 0x6c6f6f74L); // "loot"
            h = Mix(h, kind);
            foreach (long v in values)
                h = Mix(h, v);
            if (text != null)
                foreach (char c in text)
                    h = Mix(h, c);
            h ^= h >> 32;
            h *= 0x9E3779B97F4A7C15UL;
            h ^= h >> 29;
            return (int)(h ^ (h >> 32));
        }

        static ulong Mix(ulong h, long v)
        {
            for (int k = 0; k < 8; k++)
            {
                h ^= (byte)(v >> (8 * k));
                h *= 1099511628211UL;
            }
            return h;
        }

        /// <summary>Runs rolls from this seed, then puts the shared generators back as they were.</summary>
        public struct Scope : IDisposable
        {
            readonly UnityEngine.Random.State unityState;
            readonly uint dfState;
            bool open;

            public Scope(int seed)
            {
                unityState = UnityEngine.Random.state;
                dfState = DFRandom.Seed;
                UnityEngine.Random.InitState(seed);
                DFRandom.Seed = (uint)seed;
                open = true;
                depth++;
            }

            public void Dispose()
            {
                if (!open)
                    return;
                open = false;
                depth--;
                UnityEngine.Random.state = unityState;
                DFRandom.Seed = dfState;
            }
        }

        /// <summary>Dungeon layout code below this call does not know its location, so the layout names the block it builds.</summary>
        public static void BeginDungeonBlock(int mapId, string name, int x, int z)
        {
            hasBlock = true;
            blockMap = mapId;
            blockName = name;
            blockX = x;
            blockZ = z;
        }

        public static void EndDungeonBlock()
        {
            hasBlock = false;
        }

        /// <summary>Seed for something placed in an RDB block at Daggerfall position x, y, z.</summary>
        public static int ForDungeonObject(long kind, string fallbackBlock, int x, int y, int z)
        {
            if (hasBlock)
                return Of(kind, blockName, blockMap, blockX, blockZ, x, y, z);
            // Outside a dungeon layout: the map the player is on, and the block alone.
            int map = GameManager.HasInstance ? GameManager.Instance.PlayerGPS.CurrentMapID : 0;
            return Of(kind, fallbackBlock, map, 0, 0, x, y, z);
        }

        /// <summary>The next EnemyEntity loot roll uses this seed. Cleared by ClearEnemy.</summary>
        public static void SetEnemy(int seed)
        {
            hasEnemy = true;
            enemySeed = seed;
        }

        public static void ClearEnemy()
        {
            hasEnemy = false;
        }

        /// <summary>Takes the pending enemy seed, if a placed enemy is being built.</summary>
        public static bool TakeEnemy(out int seed)
        {
            seed = enemySeed;
            bool had = hasEnemy;
            hasEnemy = false;
            return had;
        }
    }
}
