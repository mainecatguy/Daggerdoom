// Doomerfall: the shop level (1 to 30) of every classic shop. The level is the shop's wealth, what its shelves hold,
// not a danger level. Nothing reads it yet.
//
// Inputs:  each classic location's building list, map table and names from MAPS.BSA, read once by
//          DoomerfallAreaLevels on its worker thread and handed to Build().
// Outputs: ForShop(location, building) -> level, 0 if the building is not a shop.
//
// The rule is proposal C, band-locked rank, which the owner chose on 2026-11-26
// (work/notes/20261124-124736-shop-levels.md). This is a port of tools/shop_levels/shop_level.py: keep the two in
// step. Daggerfall's quality band picks a fixed level range; inside the band shops are sorted by (quality, town
// class, seed) and spread evenly: level = lo + rank * width / shops in band. The seed is a hash of
// (MapId, building type, NameSeed), which is unique for every classic shop and is on the runtime BuildingSummary,
// so no block data is needed. A pure function of classic data: it never reads the player or any save.
// A shop the classic list does not hold (a mod-added location, or a building a mod replaced) is placed among the
// classic keys of its band without being counted, so classic levels never move.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShopLevels
    {
        // ---- Tables, identical to shop_level.py ---------------------------------------------------------------
        static readonly int[] BandLow = { 1, 5, 11, 19, 25 };
        static readonly int[] BandHigh = { 4, 10, 18, 24, 30 };
        const uint SeedShop = 0x5B0F0001;
        const int TownCity = 0, TownHamlet = 1, TownVillage = 2;

        // Region names whose capital is spelled differently. Orsinium is listed but is not a city, so never a capital.
        static readonly Dictionary<string, string> CapitalAlias = new Dictionary<string, string>
        {
            { "Glenumbra Moors", "Glenumbra" }, { "Dragontail Mountains", "Dragontail" }, { "Wrothgarian Mountains", "Wrothgaria" },
            { "Antiphyllos", "Antyphyllos" }, { "Orsinium Area", "Orsinium" }, { "Alik'r Desert", "Alik'ra" },
        };

        struct Shop
        {
            internal int mapId, type, nameSeed, quality, townClass;
            internal uint seed;
            internal ulong Key { get { return ((ulong)quality << 40) | ((ulong)townClass << 32) | seed; } }
        }

        sealed class Table
        {
            internal Dictionary<ulong, int> levelById;   // (MapId, type, NameSeed, quality) -> level
            internal ulong[][] bandKeys;                  // sorted classic keys per band, for shops that are not classic
            internal int[] counts;                        // shops per level, index 1..30
            internal int locations;
            internal long milliseconds;
            internal string error;
        }

        static volatile Table table;

        /// <summary>Called by DoomerfallAreaLevels on its worker thread with the MAPS.BSA it already loaded.</summary>
        internal static void Build(BsaFile maps)
        {
            Table t = new Table();
            Stopwatch clock = Stopwatch.StartNew();
            try
            {
                Fill(t, maps);
            }
            catch (Exception e)
            {
                t.error = e.GetType().Name + ": " + e.Message;
            }
            t.milliseconds = clock.ElapsedMilliseconds;
            table = t;
        }

        static Table Ready()
        {
            if (table == null)
                DoomerfallAreaLevels.WaitUntilBuilt();
            Table t = table;
            return t != null && t.error == null ? t : null;
        }

        /// <summary>One line for logs: how long the table took on the worker, or why it failed.</summary>
        internal static string Status()
        {
            if (table == null)
                DoomerfallAreaLevels.WaitUntilBuilt();
            Table t = table;
            if (t == null) return "shop levels: not built";
            if (t.error != null) return "shop levels: failed, " + t.error;
            return string.Format("shop levels: {0} shops in {1} locations in {2} ms on the area level worker", t.levelById.Count, t.locations, t.milliseconds);
        }

        /// <summary>
        /// Level of a shop, 1 to 30, or 0 if the building is not a shop or the table could not be built.
        /// </summary>
        internal static int ForShop(in DFLocation location, in BuildingSummary building)
        {
            if (!RMBLayout.IsShop(building.BuildingType))
                return 0;
            Table t = Ready();
            if (t == null)
                return 0;
            int type = (int)building.BuildingType, nameSeed = building.NameSeed & 0xFFFF;
            int level;
            if (t.levelById.TryGetValue(Id(location.MapTableData.MapId, type, nameSeed, building.Quality), out level))
                return level;
            return PlaceAmongClassic(t, building.Quality, TownClassOf(location), Seed(location.MapTableData.MapId, type, nameSeed));
        }

        /// <summary>For a shop the classic list does not hold: where its key falls among the classic keys of its band.</summary>
        internal static int PlaceAmongClassic(in DFLocation location, in BuildingSummary building)
        {
            Table t = Ready();
            if (t == null || !RMBLayout.IsShop(building.BuildingType))
                return 0;
            return PlaceAmongClassic(t, building.Quality, TownClassOf(location), Seed(location.MapTableData.MapId, (int)building.BuildingType, building.NameSeed & 0xFFFF));
        }

        /// <summary>Shops per level, index 1 to 30. Null if the table could not be built.</summary>
        internal static int[] Counts()
        {
            Table t = Ready();
            return t == null ? null : (int[])t.counts.Clone();
        }

        /// <summary>Every classic shop as (MapId, type, NameSeed, quality, level). Empty if the table could not be built.</summary>
        internal static IEnumerable<int[]> Classic()
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

        static int PlaceAmongClassic(Table t, int quality, int townClass, uint seed)
        {
            int b = Band(quality);
            ulong[] keys = t.bandKeys[b];
            ulong key = new Shop { quality = Math.Max(0, Math.Min(255, quality)), townClass = townClass, seed = seed }.Key;
            int lo = 0, hi = keys.Length;
            while (lo < hi)
            {
                int mid = (lo + hi) >> 1;
                if (keys[mid] < key) lo = mid + 1; else hi = mid;
            }
            int width = BandHigh[b] - BandLow[b] + 1;
            return Math.Min(BandHigh[b], BandLow[b] + (int)((long)lo * width / Math.Max(1, keys.Length)));
        }

        // ---- Building the table -------------------------------------------------------------------------------

        static void Fill(Table t, BsaFile maps)
        {
            List<Shop>[] bands = new List<Shop>[BandLow.Length];
            for (int b = 0; b < bands.Length; b++)
                bands[b] = new List<Shop>();
            HashSet<int> locations = new HashSet<int>();
            int regions = Math.Min(maps.Count / 4, MapsFile.RegionNames.Length);
            for (int region = 0; region < regions; region++)
            {
                byte[] names = maps.GetRecordBytes(region * 4 + 3);
                byte[] mapTable = maps.GetRecordBytes(region * 4 + 2);
                byte[] items = maps.GetRecordBytes(region * 4 + 0);
                if (names == null || mapTable == null || items == null || names.Length < 4 || mapTable.Length == 0 || items.Length == 0)
                    continue;
                uint count = BitConverter.ToUInt32(names, 0);
                for (int i = 0; i < count; i++)
                {
                    int mapId = BitConverter.ToInt32(mapTable, i * 17);
                    int ltype = (int)(unchecked(4 * BitConverter.ToUInt32(mapTable, i * 17 + 4)) >> 27);
                    StringBuilder name = new StringBuilder(32);
                    for (int c = 4 + i * 32; c < 4 + i * 32 + 32 && names[c] != 0; c++)
                        name.Append((char)names[c]); // Latin-1, as shop_level.py decodes it
                    int townClass = TownClass(ltype, IsCapital(MapsFile.RegionNames[region], name.ToString(), ltype));

                    // MapPItem: offsets, then per location the door list, a 112-byte header, the building count,
                    // 5 unknown bytes and 26 bytes per building (MapsFile.ReadMapPItem).
                    int pos = (int)(count * 4 + BitConverter.ToUInt32(items, i * 4));
                    int doors = (int)BitConverter.ToUInt32(items, pos);
                    int p = pos + 4 + doors * 6 + 112;
                    int buildings = BitConverter.ToUInt16(items, p);
                    p += 7;
                    for (int k = 0; k < buildings; k++)
                    {
                        int o = p + k * 26;
                        int type = items[o + 24];
                        if (!RMBLayout.IsShop((DFLocation.BuildingTypes)type))
                            continue;
                        int nameSeed = BitConverter.ToUInt16(items, o);
                        int quality = items[o + 25];
                        bands[Band(quality)].Add(new Shop { mapId = mapId, type = type, nameSeed = nameSeed, quality = quality, townClass = townClass, seed = Seed(mapId, type, nameSeed) });
                        locations.Add(mapId);
                    }
                }
            }

            t.levelById = new Dictionary<ulong, int>();
            t.bandKeys = new ulong[bands.Length][];
            t.counts = new int[DoomerfallAreaLevels.MaxLevel + 1];
            t.locations = locations.Count;
            for (int b = 0; b < bands.Length; b++)
            {
                Shop[] members = bands[b].ToArray();
                Array.Sort(members, Compare);
                int width = BandHigh[b] - BandLow[b] + 1;
                t.bandKeys[b] = new ulong[members.Length];
                for (int i = 0; i < members.Length; i++)
                {
                    int level = BandLow[b] + (int)((long)i * width / members.Length);
                    t.levelById[Id(members[i].mapId, members[i].type, members[i].nameSeed, members[i].quality)] = level;
                    t.bandKeys[b][i] = members[i].Key;
                    t.counts[level]++;
                }
            }
        }

        // (quality, town class, seed), then (MapId, type, NameSeed) for the rare seed tie, as shop_level.py sort_key.
        static int Compare(Shop a, Shop b)
        {
            int c = a.Key.CompareTo(b.Key);
            if (c != 0) return c;
            c = unchecked((uint)a.mapId).CompareTo(unchecked((uint)b.mapId));
            if (c != 0) return c;
            c = a.type.CompareTo(b.type);
            return c != 0 ? c : a.nameSeed.CompareTo(b.nameSeed);
        }

        static ulong Id(int mapId, int type, int nameSeed, int quality)
        {
            return ((ulong)unchecked((uint)mapId) << 32) | ((ulong)(type & 0xFF) << 24) | ((ulong)(nameSeed & 0xFFFF) << 8) | (ulong)(quality & 0xFF);
        }

        static int Band(int quality)
        {
            return quality <= 3 ? 0 : quality <= 7 ? 1 : quality <= 13 ? 2 : quality <= 17 ? 3 : 4;
        }

        static bool IsCapital(string regionName, string locationName, int ltype)
        {
            if (ltype != TownCity || regionName == null || locationName == null)
                return false;
            string want;
            if (!CapitalAlias.TryGetValue(regionName, out want))
                want = regionName;
            return string.Equals(locationName.Trim(), want.Trim(), StringComparison.OrdinalIgnoreCase);
        }

        // 0 village (and castles), 1 hamlet, 2 city, 3 capital.
        static int TownClass(int ltype, bool capital)
        {
            if (capital) return 3;
            if (ltype == TownCity) return 2;
            if (ltype == TownHamlet) return 1;
            return 0;
        }

        static int TownClassOf(in DFLocation location)
        {
            int ltype = (int)location.MapTableData.LocationType;
            return TownClass(ltype, IsCapital(location.RegionName, location.Name, ltype));
        }

        static uint Seed(int mapId, int type, int nameSeed)
        {
            uint h = Hash32(SeedShop);
            h = Hash32(h ^ unchecked((uint)mapId));
            return Hash32(h ^ (uint)((type << 16) | (nameSeed & 0xFFFF)));
        }

        // lowbias32 by Chris Wellons, as DoomerfallAreaLevels.
        static uint Hash32(uint x)
        {
            unchecked
            {
                x ^= x >> 16;
                x *= 0x7FEB352D;
                x ^= x >> 15;
                x *= 0x846CA68B;
                x ^= x >> 16;
                return x;
            }
        }
    }
}
