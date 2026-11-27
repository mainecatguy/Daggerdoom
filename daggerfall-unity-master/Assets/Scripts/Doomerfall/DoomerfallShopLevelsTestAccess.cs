// Doomerfall test only: accessors DoomerfallShopLevelsTest (-dfshopleveldump) uses to dump the shop level table,
// report its build time, and force the mod-added fallback. No game code calls these.

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallWorkshop.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static partial class DoomerfallShopLevels
    {
        /// <summary>One line for the test log: how long the table took on the worker, or why it failed.</summary>
        internal static string TestStatus()
        {
            if (table == null)
                DoomerfallAreaLevels.WaitUntilBuilt();
            Table t = table;
            if (t == null) return "shop levels: not built";
            if (t.error != null) return "shop levels: failed, " + t.error;
            return string.Format("shop levels: {0} shops in {1} ms on the area level worker", t.levelById.Count, t.milliseconds);
        }

        /// <summary>The fallback for shops the classic list does not hold, run on any shop.</summary>
        internal static int TestPlaceAmongClassic(in DFLocation location, in BuildingSummary building)
        {
            Table t = Ready();
            if (t == null || !RMBLayout.IsShop(building.BuildingType))
                return 0;
            return PlaceAmongClassic(t, building.Quality, TownClassOf(location), Seed(location.MapTableData.MapId, (int)building.BuildingType, building.NameSeed & 0xFFFF));
        }

        /// <summary>Every classic shop as (MapId, type, NameSeed, quality, level).</summary>
        internal static IEnumerable<int[]> TestClassic()
        {
            Table t = Ready();
            if (t == null)
                yield break;
            foreach (KeyValuePair<ulong, int> entry in t.levelById)
            {
                ulong id = entry.Key;
                yield return new[] { (int)(uint)(id >> 32), (int)(id >> 24) & 0xFF, (int)(id >> 8) & 0xFFFF, (int)(id & 0xFF), entry.Value };
            }
        }
    }
}
