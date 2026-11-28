// Doomerfall: the level that scales the world (what exists, spawns, or drops).
//
// Classic Daggerfall scales the world to the player's level. Doomerfall scales it to the area level of the place
// where it happens instead. Outside a Doomerfall bridge session no provider is set and Current is the player's
// level, so normal Daggerfall Unity behaves as before. Character rules (HP gains, skills, training costs, quest
// offers) keep reading PlayerEntity.Level directly and never come here.

using System;
using DaggerfallConnect;

namespace DaggerfallWorkshop.Game
{
    public static class WorldLevel
    {
        /// <summary>Doomerfall sets this in a bridge session: the area level where the player is now, or 0 if unknown.</summary>
        public static Func<int> CurrentPlaceProvider;

        /// <summary>Doomerfall sets this in a bridge session: the danger level where the player is now (a building's own level never applies), or 0 if unknown.</summary>
        public static Func<int> DangerProvider;

        /// <summary>Doomerfall sets this in a bridge session: the dungeon level of a location, or 0 if unknown.</summary>
        public static Func<DFLocation, int> DungeonProvider;

        /// <summary>Doomerfall sets this in a bridge session: the shop level of a shop building, or 0 if unknown.</summary>
        public static Func<PlayerGPS.DiscoveredBuilding, int> ShopProvider;

        static int scoped;

        /// <summary>True when the world level comes from area levels instead of the player.</summary>
        public static bool UsesAreaLevel { get { return CurrentPlaceProvider != null; } }

        /// <summary>The level that scales the world here and now.</summary>
        public static int Current
        {
            get
            {
                if (scoped > 0)
                    return scoped;
                if (CurrentPlaceProvider != null)
                {
                    int level = CurrentPlaceProvider();
                    if (level > 0)
                        return level;
                }
                return GameManager.Instance.PlayerEntity.Level;
            }
        }

        /// <summary>Doomerfall sets this in a bridge session: the area level of the place where a quest is being given (the giver's town), or 0 if unknown.</summary>
        public static Func<int> QuestRewardProvider;

        /// <summary>
        /// The level quest rewards (magic items, gold) are rolled for. In a Doomerfall session the area level of the
        /// place the quest is given in (owner, 2026-11-27), never the player's level; the player's level otherwise.
        /// Which quests are offered still follows the player's level and never comes here.
        /// </summary>
        public static int QuestReward
        {
            get
            {
                if (!UsesAreaLevel)
                    return GameManager.Instance.PlayerEntity.Level;
                if (scoped > 0)
                    return scoped;
                int level = QuestRewardProvider != null ? QuestRewardProvider() : 0;
                return level > 0 ? level : Current;
            }
        }

        /// <summary>
        /// The level enemies are made at here and now. Same as Current, except inside a shop, house or guild hall,
        /// whose own level is wealth (what is rolled there), not danger. Outside Doomerfall it is Current.
        /// </summary>
        public static int Danger
        {
            get
            {
                if (scoped > 0 || DangerProvider == null)
                    return Current;
                int level = DangerProvider();
                return level > 0 ? level : Current;
            }
        }

        /// <summary>Scope for building a dungeon's layout before the player is inside it. Does nothing outside Doomerfall.</summary>
        public static Scope ForDungeon(in DFLocation location)
        {
            int level = DungeonProvider != null ? DungeonProvider(location) : 0;
            return new Scope(level);
        }

        /// <summary>Scope for restocking a shop's shelves: they roll at the shop's level. Does nothing outside Doomerfall.</summary>
        public static Scope ForShop(in PlayerGPS.DiscoveredBuilding building)
        {
            int level = ShopProvider != null ? ShopProvider(building) : 0;
            return new Scope(level);
        }

        /// <summary>Doomerfall sets this in a bridge session: the level of a building being entered (shop, or a house or guild hall in a town), or 0 for the area level.</summary>
        public static Func<PlayerGPS.DiscoveredBuilding, int> BuildingProvider;

        /// <summary>Scope for laying out a building's interior before the player is inside it. Does nothing outside Doomerfall.</summary>
        public static Scope ForBuilding(in PlayerGPS.DiscoveredBuilding building)
        {
            int level = BuildingProvider != null ? BuildingProvider(building) : 0;
            return new Scope(level);
        }

        /// <summary>World rolls inside this scope use the given level. A level of 0 or less leaves Current as it was.</summary>
        public struct Scope : IDisposable
        {
            readonly int saved;
            bool open;

            public Scope(int level)
            {
                saved = scoped;
                open = level > 0;
                if (open)
                    scoped = level;
            }

            public void Dispose()
            {
                if (!open)
                    return;
                open = false;
                scoped = saved;
            }
        }
    }
}
