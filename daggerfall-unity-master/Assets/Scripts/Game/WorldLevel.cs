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

        /// <summary>Doomerfall sets this in a bridge session: the dungeon level of a location, or 0 if unknown.</summary>
        public static Func<DFLocation, int> DungeonProvider;

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

        /// <summary>Scope for building a dungeon's layout before the player is inside it. Does nothing outside Doomerfall.</summary>
        public static Scope ForDungeon(in DFLocation location)
        {
            int level = DungeonProvider != null ? DungeonProvider(location) : 0;
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
