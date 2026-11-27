// Doomerfall: the area level (1 to 30) of every Daggerfall location and of the open wilderness.
//
// Inputs:  classic MAPS.BSA and POLITIC.PAK, read straight from Arena2 so mods that add locations or repaint
//          regions cannot change the ranking, plus the hand tables and fixed seeds below.
// Outputs: Dungeon level per location (ranked within its size class), terrain level per land map pixel
//          (ranked over all land pixels), and ForLocation / ForMapPixel / ForCurrentPlace lookups.
//
// This is a port of tools/area_level/area_level.py, the formula the owner approved on 2026-11-23
// (work/notes/20261123-225515-area-level-proposal.md). Keep the two in step: same tables, same seeds, and the
// same order of floating point operations, so both give the same level for every place. A place's level is a
// pure function of the classic data, so it never changes between launches, saves, or players. A location a mod
// adds is not ranked; its score is placed among the classic scores, so classic levels stay put.
//
// The ranking runs once on a worker thread, started by Warm() as soon as Daggerfall's data path is known.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallAreaLevels
    {
        internal const int MaxLevel = 30;

        // ---- Tunables, identical to area_level.py ------------------------------------------------------------
        const double RegionW = 0.85, GeoW = 0.9, TypeW = 0.8, NoiseW = 1.0;
        const double ExceptionChance = 0.07, ExceptionMin = 2.5, ExceptionMax = 5.0;
        const uint SeedGeoA = 0xA17E0001, SeedGeoB = 0xA17E0002, SeedLoc = 0xA17E0003;
        const int GeoCellA = 48, GeoCellB = 16;

        static readonly Dictionary<string, int> RegionLean = new Dictionary<string, int>
        {
            { "Daggerfall", -2 }, { "Glenpoint", -2 }, { "Tulune", -2 }, { "Glenumbra Moors", -2 },
            { "Betony", -2 }, { "Northmoor", -2 },
            { "Ilessan Hills", -1 }, { "Shalgora", -1 }, { "Anticlere", -1 }, { "Ykalon", -1 },
            { "Daenia", -1 }, { "Abibon-Gora", -1 }, { "Kairou", -1 }, { "Myrkwasa", -1 }, { "Pothago", -1 },
            { "Sentinel", 0 }, { "Urvaius", 0 }, { "Phrygias", 0 }, { "Bhoriane", 0 }, { "Kambria", 0 },
            { "Dwynnen", 0 }, { "Ayasofya", 0 }, { "Tigonus", 0 }, { "Antiphyllos", 0 }, { "Bergama", 0 },
            { "Cybiades", 0 },
            { "Wayrest", 1 }, { "Lainlyn", 1 }, { "Koegria", 1 }, { "Alcaire", 1 }, { "Menevia", 1 },
            { "Kozanset", 1 }, { "Satakalaam", 1 }, { "Totambu", 1 }, { "Mournoth", 1 }, { "Santaki", 1 },
            { "Gavaudon", 1 }, { "Dak'fron", 1 }, { "Ephesus", 1 },
            { "Alik'r Desert", 2 }, { "Dragontail Mountains", 2 }, { "Wrothgarian Mountains", 2 },
            { "Orsinium Area", 2 }, { "Isle of Balfiera", 2 }, { "High Rock sea coast", 2 },
        };

        // By dungeon type byte, in MAPS.BSA order: Crypt, OrcStronghold, HumanStronghold, Prison, DesecratedTemple,
        // Mine, NaturalCave, Coven, VampireHaunt, Laboratory, HarpyNest, RuinedCastle, SpiderNest, GiantStronghold,
        // DragonsDen, BarbarianStronghold, VolcanicCaves, ScorpionNest, Cemetery.
        static readonly double[] TypeLean = { -0.5, 0, 0, -0.5, 0.5, -1.5, -1.5, 1, 1.5, 1, -1, 0, -1, 1, 2, 0, 1.5, -0.5, 0 };

        // Main quest dungeons: a fixed level that rises in main quest order, applied after ranking, and a story encounter
        // theme where noted (a row name in doomerfall_encounters.txt's theme table, sent to Doom in place of the dungeon
        // type's name; null keeps the type). A place keeps the level of its first main quest visit. Owner-approved table,
        // 2026-11-26 (work/notes/20261124-202353.md, "Proposed table"). area_level.py's OVERRIDES must match the levels.
        static readonly KeyValuePair<int, KeyValuePair<int, string>>[] MainQuest =
        {
            Row(187853213, 1, "PlainHumanoid"), // Privateer's Hold: every new character wakes up here; plain Former Humans only
            Row(701948302, 5, null),            // Scourg Barrow
            Row(728811286, 5, null),            // Shedungent
            Row(9570447, 8, null),              // Castle Necromoghan
            Row(43196334, 10, null),            // Direnni Tower
            Row(325404, 10, null),              // Castle Faallem (Missing Prince uses this or Fhojum)
            Row(5585279, 10, null),             // Fortress of Fhojum
            Row(2352284, 10, null),             // Tristore Laboratory
            Row(336619236, 17, "Humanoid"),     // Castle Llugwych (the Blades)
            Row(207828842, 17, null),           // Lysandus' Tomb
            Row(19021260, 21, "Humanoid"),      // Orsinium (orcs)
            Row(83032363, 24, "Humanoid"),      // Woodborne Hall
            Row(1001, 30, null),                // Mantellan Crux
            Row(1291010263, 3, "Humanoid"),     // Castle Daggerfall (the city of Daggerfall's dungeon)
            Row(630439035, 14, "Humanoid"),     // Castle Wayrest
            Row(6634853, 14, "Humanoid"),       // Castle Sentinel
        };

        static KeyValuePair<int, KeyValuePair<int, string>> Row(int mapId, int level, string theme)
        {
            return new KeyValuePair<int, KeyValuePair<int, string>>(mapId, new KeyValuePair<int, string>(level, theme));
        }

        static readonly Dictionary<int, int> Overrides = new Dictionary<int, int>();
        static readonly Dictionary<int, string> StoryThemes = new Dictionary<int, string>();

        static DoomerfallAreaLevels()
        {
            foreach (KeyValuePair<int, KeyValuePair<int, string>> row in MainQuest)
            {
                Overrides[row.Key] = row.Value.Key;
                if (row.Value.Value != null)
                    StoryThemes[row.Key] = row.Value.Value;
            }
        }

        /// <summary>The story encounter theme of a main quest dungeon by MapId, or null to use its dungeon type.</summary>
        internal static string StoryTheme(int mapId)
        {
            string theme;
            return StoryThemes.TryGetValue(mapId, out theme) ? theme : null;
        }

        // Location type bytes that pick a size class. Everything else with a dungeon is a labyrinth.
        const int TypeKeep = 7, TypeRuin = 10, TypeGraveyard = 12;
        const int ClassLabyrinth = 0, ClassKeep = 1, ClassRuin = 2, ClassGraveyard = 3, ClassCount = 4;
        const int MapWidth = 1000, MapHeight = 500;

        internal struct Level
        {
            internal int dungeon;   // 0 when the place has no dungeon
            internal int terrain;   // the countryside around the place
            internal int Area { get { return dungeon > 0 ? dungeon : terrain; } }
        }

        sealed class Table
        {
            internal byte[] terrain;                       // per map pixel, 0 for water
            internal Dictionary<int, Level> byMapId;       // every classic location
            internal double[][] classScores;               // sorted classic dungeon scores per size class
            internal double[] regionLean;                  // by region index
            internal string error;
            internal long milliseconds;
        }

        static Table table;
        static Thread worker;
        static readonly object gate = new object();

        /// <summary>Starts the one-time ranking on a worker thread. Safe to call every frame.</summary>
        internal static void Warm()
        {
            if (worker != null || table != null)
                return;
            DaggerfallUnity dfu = DaggerfallUnity.Instance;
            if (dfu == null || !dfu.IsReady || string.IsNullOrEmpty(dfu.Arena2Path))
                return;
            string arena2 = dfu.Arena2Path;
            lock (gate)
            {
                if (worker != null)
                    return;
                worker = new Thread(() => { Table t = Build(arena2); lock (gate) table = t; }) { IsBackground = true, Name = "Doomerfall area levels" };
                worker.Start();
            }
        }

        static long waitedMs;

        static Table Ready()
        {
            if (table == null)
            {
                Warm();
                Thread t = worker;
                if (t != null)
                {
                    Stopwatch clock = Stopwatch.StartNew();
                    t.Join();
                    waitedMs += clock.ElapsedMilliseconds;
                }
            }
            return table;
        }

        /// <summary>One line for logs: how long the ranking took, how long the main thread waited for it, or why it failed.</summary>
        internal static string Status()
        {
            Table t = Ready();
            if (t == null) return "area levels: not built";
            if (t.error != null) return "area levels: failed, " + t.error;
            return string.Format("area levels: {0} locations ranked in {1} ms on a worker, main thread waited {2} ms", t.byMapId.Count, t.milliseconds, waitedMs);
        }

        /// <summary>True once the ranking has finished (or failed), so lookups no longer wait. Starts it if needed; never blocks.</summary>
        internal static bool IsFinished
        {
            get { Warm(); return table != null; }
        }

        /// <summary>Levels of a classic location by its full MapId. False for a mod-added location or if the table could not be built.</summary>
        internal static bool ForMapId(int mapId, out Level level)
        {
            level = default(Level);
            Table t = Ready();
            return t != null && t.error == null && t.byMapId.TryGetValue(mapId, out level);
        }

        /// <summary>Levels of a location. Returns false if the table could not be built.</summary>
        internal static bool ForLocation(in DFLocation location, out Level level)
        {
            level = default(Level);
            Table t = Ready();
            if (t == null || t.error != null)
                return false;
            if (t.byMapId.TryGetValue(location.MapTableData.MapId, out level))
                return true;
            level = PlaceAmongClassic(t, location);
            return true;
        }

        /// <summary>For a location a mod added: scores it like a classic place and finds where it falls among the classic scores.</summary>
        internal static bool PlaceAmongClassic(in DFLocation location, out Level level)
        {
            level = default(Level);
            Table t = Ready();
            if (t == null || t.error != null)
                return false;
            level = PlaceAmongClassic(t, location);
            return true;
        }

        /// <summary>Every classic location's levels, by MapId. Empty if the table could not be built.</summary>
        internal static IEnumerable<KeyValuePair<int, Level>> Classic()
        {
            Table t = Ready();
            return t == null || t.error != null ? (IEnumerable<KeyValuePair<int, Level>>)new KeyValuePair<int, Level>[0] : t.byMapId;
        }

        static Level PlaceAmongClassic(Table t, in DFLocation location)
        {
            Level level = default(Level);
            DFRegion.RegionMapTable map = location.MapTableData;
            int x = map.Longitude / 128, y = 499 - map.Latitude / 128;
            level.terrain = TerrainAt(t, x, y);
            int dtype = (int)map.DungeonType;
            if (dtype >= 0 && dtype < TypeLean.Length)
            {
                double lean = location.RegionIndex >= 0 && location.RegionIndex < t.regionLean.Length ? t.regionLean[location.RegionIndex] : 0;
                double raw = DungeonRaw(lean, x, y, dtype, map.MapId);
                double[] scores = t.classScores[SizeClass((int)map.LocationType)];
                int below = LowerBound(scores, raw);
                level.dungeon = Math.Min(MaxLevel, 1 + (int)((long)below * MaxLevel / Math.Max(1, scores.Length)));
            }
            return level;
        }

        /// <summary>Terrain level of a map pixel, for the open wilderness. 0 if the table could not be built.</summary>
        internal static int ForMapPixel(int x, int y)
        {
            Table t = Ready();
            return t == null || t.error != null ? 0 : TerrainAt(t, x, y);
        }

        /// <summary>Where the player is now: the dungeon's level inside a dungeon, otherwise the terrain level of the map pixel. 0 if unknown.</summary>
        internal static int ForCurrentPlace()
        {
            GameManager game = GameManager.Instance;
            if (game == null || game.PlayerGPS == null)
                return 0;
            Level level;
            if (game.PlayerEnterExit && game.PlayerEnterExit.IsPlayerInsideDungeon && game.PlayerGPS.HasCurrentLocation
                && ForLocation(game.PlayerGPS.CurrentLocation, out level) && level.dungeon > 0)
                return level.dungeon;
            DaggerfallConnect.Utility.DFPosition pixel = game.PlayerGPS.CurrentMapPixel;
            return ForMapPixel(pixel.X, pixel.Y);
        }

        static int TerrainAt(Table t, int x, int y)
        {
            // Water and pixels off the map, such as Mantellan Crux at (1, 1), count as 1, as in the script.
            if (x < 0 || x >= MapWidth || y < 0 || y >= MapHeight)
                return 1;
            byte v = t.terrain[y * MapWidth + x];
            return v == 0 ? 1 : v;
        }

        // ---- Building the table -------------------------------------------------------------------------------

        static Table Build(string arena2)
        {
            Table t = new Table();
            Stopwatch clock = Stopwatch.StartNew();
            try
            {
                t.regionLean = new double[MapsFile.RegionNames.Length];
                for (int r = 0; r < t.regionLean.Length; r++)
                {
                    int lean;
                    t.regionLean[r] = RegionLean.TryGetValue(MapsFile.RegionNames[r], out lean) ? lean : 0;
                }
                BuildTerrain(t, Path.Combine(arena2, "POLITIC.PAK"));
                BuildLocations(t, Path.Combine(arena2, "MAPS.BSA"));
            }
            catch (Exception e)
            {
                t.error = e.GetType().Name + ": " + e.Message;
            }
            t.milliseconds = clock.ElapsedMilliseconds;
            return t;
        }

        static void BuildTerrain(Table t, string politicPath)
        {
            PakFile politic = new PakFile();
            if (!politic.Load(politicPath))
                throw new IOException("could not read " + politicPath);
            List<double> raws = new List<double>(MapWidth * MapHeight / 2);
            List<int> keys = new List<int>(MapWidth * MapHeight / 2);
            for (int y = 0; y < MapHeight; y++)
                for (int x = 0; x < MapWidth; x++)
                {
                    int v = politic.GetValue(x + 1, y); // Daggerfall Unity adds 1 to x to line up with the height map
                    if (v == 64 || v < 128)
                        continue;
                    int region = (v - 128) & 0x7F;
                    if (region >= t.regionLean.Length)
                        continue;
                    raws.Add(TerrainRaw(t.regionLean[region], x, y));
                    keys.Add(y * MapWidth + x);
                }
            double[] r = raws.ToArray();
            int[] k = keys.ToArray();
            int[] order = RankOrder(r, k);
            t.terrain = new byte[MapWidth * MapHeight];
            for (int i = 0; i < order.Length; i++)
                t.terrain[k[order[i]]] = (byte)(1 + (long)i * MaxLevel / order.Length);
        }

        static void BuildLocations(Table t, string mapsPath)
        {
            BsaFile maps = new BsaFile();
            if (!maps.Load(mapsPath, FileUsage.UseMemory, true))
                throw new IOException("could not read " + mapsPath);
            t.byMapId = new Dictionary<int, Level>();
            List<double>[] raws = new List<double>[ClassCount];
            List<uint>[] ties = new List<uint>[ClassCount];
            List<int>[] ids = new List<int>[ClassCount];
            for (int c = 0; c < ClassCount; c++)
            {
                raws[c] = new List<double>();
                ties[c] = new List<uint>();
                ids[c] = new List<int>();
            }

            int regions = Math.Min(maps.Count / 4, t.regionLean.Length);
            for (int region = 0; region < regions; region++)
            {
                byte[] names = maps.GetRecordBytes(region * 4 + 3);
                byte[] mapTable = maps.GetRecordBytes(region * 4 + 2);
                if (names == null || mapTable == null || names.Length < 4 || mapTable.Length == 0)
                    continue;
                // The count in the names record is the classic count, as Daggerfall Unity's ReadLocationCount reads it.
                uint count = BitConverter.ToUInt32(names, 0);
                for (int i = 0; i < count; i++)
                {
                    int o = i * 17;
                    int mapId = BitConverter.ToInt32(mapTable, o);
                    uint bits = BitConverter.ToUInt32(mapTable, o + 4);
                    int latRaw = BitConverter.ToInt32(mapTable, o + 8);
                    int dtype = mapTable[o + 12];
                    int lon = (int)(bits & 0x1FFFFFF) >> 8;
                    int ltype = (int)(unchecked(4 * bits) >> 27);
                    int lat = (latRaw & 0xFFFFFF) >> 8;
                    int x = lon / 128, y = 499 - lat / 128;

                    Level level = new Level { terrain = TerrainAt(t, x, y) };
                    t.byMapId[mapId] = level;
                    if (dtype >= TypeLean.Length)
                        continue;
                    int c = SizeClass(ltype);
                    raws[c].Add(DungeonRaw(t.regionLean[region], x, y, dtype, mapId));
                    ties[c].Add(unchecked((uint)mapId));
                    ids[c].Add(mapId);
                }
            }

            t.classScores = new double[ClassCount][];
            for (int c = 0; c < ClassCount; c++)
            {
                double[] r = raws[c].ToArray();
                uint[] tie = ties[c].ToArray();
                int[] order = RankOrder(r, tie);
                double[] sorted = new double[order.Length];
                for (int i = 0; i < order.Length; i++)
                {
                    sorted[i] = r[order[i]];
                    int mapId = ids[c][order[i]];
                    Level level = t.byMapId[mapId];
                    level.dungeon = 1 + (int)((long)i * MaxLevel / order.Length);
                    t.byMapId[mapId] = level;
                }
                t.classScores[c] = sorted;
            }
            foreach (KeyValuePair<int, int> fixedLevel in Overrides)
            {
                Level level;
                if (t.byMapId.TryGetValue(fixedLevel.Key, out level))
                {
                    level.dungeon = fixedLevel.Value;
                    t.byMapId[fixedLevel.Key] = level;
                }
            }
        }

        static int SizeClass(int locationType)
        {
            if (locationType == TypeGraveyard) return ClassGraveyard;
            if (locationType == TypeRuin) return ClassRuin;
            if (locationType == TypeKeep) return ClassKeep;
            return ClassLabyrinth; // labyrinths and the three cities with dungeons
        }

        // Indices of raw sorted by (raw, tiebreak), as the script's sort of (raw, tiebreak) tuples.
        static int[] RankOrder(double[] raw, int[] tie)
        {
            long[] t = new long[tie.Length];
            for (int i = 0; i < tie.Length; i++) t[i] = tie[i];
            return RankOrder(raw, t);
        }

        static int[] RankOrder(double[] raw, uint[] tie)
        {
            long[] t = new long[tie.Length];
            for (int i = 0; i < tie.Length; i++) t[i] = tie[i];
            return RankOrder(raw, t);
        }

        static int[] RankOrder(double[] raw, long[] tie)
        {
            int[] order = new int[raw.Length];
            for (int i = 0; i < order.Length; i++) order[i] = i;
            Array.Sort(order, (a, b) =>
            {
                int c = raw[a].CompareTo(raw[b]);
                return c != 0 ? c : tie[a].CompareTo(tie[b]);
            });
            return order;
        }

        static int LowerBound(double[] sorted, double value)
        {
            int lo = 0, hi = sorted.Length;
            while (lo < hi)
            {
                int mid = (lo + hi) >> 1;
                if (sorted[mid] < value) lo = mid + 1; else hi = mid;
            }
            return lo;
        }

        // ---- Formula ------------------------------------------------------------------------------------------

        static double TerrainRaw(double regionLean, int x, int y)
        {
            return RegionW * regionLean + GeoW * GeoField(x, y);
        }

        static double DungeonRaw(double regionLean, int x, int y, int dtype, int mapId)
        {
            double terrain = TerrainRaw(regionLean, x, y);
            return terrain + TypeW * TypeLean[dtype] + NoiseW * LocationNoise(unchecked((uint)mapId));
        }

        // lowbias32 by Chris Wellons.
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

        static double Unit(uint a, uint b, uint c)
        {
            uint h = Hash32(a);
            h = Hash32(h ^ b);
            h = Hash32(h ^ c);
            return h / 4294967296.0;
        }

        static double Lattice(int ix, int iy, uint seed)
        {
            return Unit(seed, unchecked((uint)ix), unchecked((uint)iy)) * 2.0 - 1.0;
        }

        static double ValueNoise(int x, int y, int cell, uint seed)
        {
            double fx = (double)x / cell, fy = (double)y / cell;
            int ix = (int)Math.Floor(fx), iy = (int)Math.Floor(fy);
            double tx = fx - ix, ty = fy - iy;
            tx = tx * tx * (3 - 2 * tx);
            ty = ty * ty * (3 - 2 * ty);
            double a = Lattice(ix, iy, seed);
            double b = Lattice(ix + 1, iy, seed);
            double c = Lattice(ix, iy + 1, seed);
            double d = Lattice(ix + 1, iy + 1, seed);
            return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty;
        }

        static double GeoField(int x, int y)
        {
            return (ValueNoise(x, y, GeoCellA, SeedGeoA) + 0.5 * ValueNoise(x, y, GeoCellB, SeedGeoB)) * 2.0;
        }

        static double LocationNoise(uint mapId)
        {
            double n = (Unit(SeedLoc, mapId, 1) + Unit(SeedLoc, mapId, 2) + Unit(SeedLoc, mapId, 3) - 1.5) * 2.0;
            if (Unit(SeedLoc, mapId, 4) < ExceptionChance)
            {
                double kick = ExceptionMin + (ExceptionMax - ExceptionMin) * Unit(SeedLoc, mapId, 5);
                n += Unit(SeedLoc, mapId, 6) < 0.5 ? kick : -kick;
            }
            return n;
        }
    }
}
