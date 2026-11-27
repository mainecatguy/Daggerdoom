// Doomerfall: the area level (1 to 30) of every Daggerfall location and of the open wilderness.
//
// Inputs:  classic MAPS.BSA and POLITIC.PAK, read straight from Arena2 so mods that add locations or repaint
//          regions cannot change the ranking, plus the hand tables and fixed seeds below.
// Outputs: Dungeon level per location (ranked within its size class), terrain level per land map pixel
//          (ranked over all land pixels), town level per town (the higher of its terrain level and its class level),
//          and ForLocation / ForMapPixel / ForCurrentPlace lookups.
//
// This is a port of tools/area_level/area_level.py, the formula the owner approved on 2026-11-23
// (work/notes/20261123-225515-area-level-proposal.md). Keep the two in step: same tables, same seeds, and the
// same order of floating point operations, so both give the same level for every place. A place's level is a
// pure function of the classic data, so it never changes between launches, saves, or players. A location a mod
// adds is not ranked; its score is placed among the classic scores, so classic levels stay put.
//
// The ranking runs once on a worker thread, started by Warm() as soon as Daggerfall's data path is known. The same
// worker then builds DoomerfallShopLevels from the MAPS.BSA it loaded.

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

        // Story places with a fixed level, applied after ranking. Every new character wakes up in Privateer's Hold.
        static readonly Dictionary<int, int> Overrides = new Dictionary<int, int> { { 187853213, 1 } };

        // ---- Towns (owner, 2026-11-24 and 2026-11-26) ------------------------------------------------------------
        // Outdoors in a town the area level is the town's level: the higher of the terrain level and the class level.
        // It is a danger level only (guards, night spawns); it never sets shop quality or any building's wealth.
        // Classes by location type ("type" scheme): village small, hamlet medium, city large, and a city named after
        // its region a capital. Same table and aliases as tools/area_level/area_level.py.
        const int TypeCity = 0, TypeHamlet = 1, TypeVillage = 2;
        internal const int TownSmall = 5, TownMedium = 10, TownLarge = 15, TownCapital = 20;
        static readonly Dictionary<string, string> CapitalAlias = new Dictionary<string, string>
        {
            { "Glenumbra Moors", "Glenumbra" }, { "Dragontail Mountains", "Dragontail" }, { "Wrothgarian Mountains", "Wrothgaria" },
            { "Antiphyllos", "Antyphyllos" }, { "Orsinium Area", "Orsinium" }, { "Alik'r Desert", "Alik'ra" },
        };

        // The town level holds over the whole town Doom map. The player is on UZDoom's town map only while within 20
        // tiles (256 Daggerfall units each) of the location's rectangle: it hands off to the overworld there
        // (dd_treadmill.cpp, Town::ExitMargin with margin 24), and enters it at 12 tiles. TownRectangle is the same
        // rectangle the converter gives UZDoom.
        internal const int TownEdge = 20 * 256;

        // Location type bytes that pick a size class. Everything else with a dungeon is a labyrinth.
        const int TypeKeep = 7, TypeRuin = 10, TypeGraveyard = 12;
        const int ClassLabyrinth = 0, ClassKeep = 1, ClassRuin = 2, ClassGraveyard = 3, ClassCount = 4;
        const int MapWidth = 1000, MapHeight = 500;

        internal struct Level
        {
            internal int dungeon;   // 0 when the place has no dungeon
            internal int terrain;   // the countryside around the place
            internal int town;      // outdoors in a town: max(terrain, class level); 0 when the place is not a town
            /// <summary>The level the travel map shows: the town level for a town, otherwise Area.</summary>
            internal int Place { get { return town > 0 ? town : Area; } }
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

        /// <summary>Waits for the worker (starting it if needed), as every lookup here does.</summary>
        internal static void WaitUntilBuilt()
        {
            Ready();
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
            string region = location.RegionIndex >= 0 && location.RegionIndex < MapsFile.RegionNames.Length ? MapsFile.RegionNames[location.RegionIndex] : "";
            level.town = TownLevel(level.terrain, (int)map.LocationType, region, location.Name ?? "");
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

        /// <summary>
        /// Where the player is now: the dungeon's level inside a dungeon, the town level outdoors on a town's Doom map,
        /// otherwise the terrain level of the map pixel (building interiors included, until they get their own). 0 if unknown.
        /// </summary>
        internal static int ForCurrentPlace()
        {
            GameManager game = GameManager.Instance;
            if (game == null || game.PlayerGPS == null)
                return 0;
            Level level;
            PlayerEnterExit enter = game.PlayerEnterExit;
            if (enter && enter.IsPlayerInsideDungeon && game.PlayerGPS.HasCurrentLocation
                && ForLocation(game.PlayerGPS.CurrentLocation, out level) && level.dungeon > 0)
                return level.dungeon;
            // Outdoors only. An interior being laid out (PlayerEnterExit sets interior before DoLayout, and
            // IsPlayerInside only after it) counts as indoors, so building loot keeps the terrain level.
            bool building = enter && (enter.IsPlayerInside || (enter.Interior && enter.Interior.gameObject.activeInHierarchy));
            if (!building)
            {
                int town = TownAt(game.PlayerGPS.WorldX, game.PlayerGPS.WorldZ);
                if (town > 0)
                    return town;
            }
            DaggerfallConnect.Utility.DFPosition pixel = game.PlayerGPS.CurrentMapPixel;
            return ForMapPixel(pixel.X, pixel.Y);
        }

        /// <summary>
        /// The town level at a Daggerfall world position, or 0 when it is not on a town's Doom map, taken as the
        /// town's location rectangle extended by TownEdge. Looks at the position's map pixel and its neighbours, since
        /// a town map near a pixel edge reaches into the next pixel. The highest town wins where two overlap.
        /// Main thread only.
        /// </summary>
        internal static int TownAt(int worldX, int worldZ)
        {
            Table t = Ready();
            DaggerfallUnity dfu = DaggerfallUnity.Instance;
            if (t == null || t.error != null || dfu == null || !dfu.IsReady)
                return 0;
            DaggerfallConnect.Utility.DFPosition pixel = MapsFile.WorldCoordToMapPixel(worldX, worldZ);
            int best = 0;
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++)
                {
                    TownRect rect;
                    if (!TownRectAt(dfu, pixel.X + dx, pixel.Y + dy, out rect) || rect.level <= best)
                        continue;
                    if (worldX >= rect.minX - TownEdge && worldX <= rect.maxX + TownEdge && worldZ >= rect.minZ - TownEdge && worldZ <= rect.maxZ + TownEdge)
                        best = rect.level;
                }
            return best;
        }

        struct TownRect { internal int minX, maxX, minZ, maxZ, level; }

        static readonly Dictionary<int, TownRect> townRects = new Dictionary<int, TownRect>();
        static readonly HashSet<int> notTowns = new HashSet<int>();

        // A town's location rectangle in world units, worked out as PlayerGPS.SetLocationRect does. Cached per pixel.
        static bool TownRectAt(DaggerfallUnity dfu, int x, int y, out TownRect rect)
        {
            rect = default(TownRect);
            if (x < 0 || x >= MapWidth || y < 0 || y >= MapHeight)
                return false;
            int key = y * MapWidth + x;
            if (townRects.TryGetValue(key, out rect))
                return true;
            if (notTowns.Contains(key))
                return false;
            if (townRects.Count + notTowns.Count > 4096)
            {
                townRects.Clear();
                notTowns.Clear();
            }
            DaggerfallWorkshop.Utility.ContentReader.MapSummary summary;
            DFLocation location;
            Level level;
            if (!dfu.ContentReader.HasLocation(x, y, out summary) || !IsTownType((int)summary.LocationType)
                || !dfu.ContentReader.GetLocation(summary.RegionIndex, summary.MapIndex, out location)
                || !ForLocation(location, out level) || level.town <= 0)
            {
                notTowns.Add(key);
                return false;
            }
            TownRectangle(dfu, location, x, y, out rect.minX, out rect.maxX, out rect.minZ, out rect.maxZ);
            rect.level = level.town;
            townRects[key] = rect;
            return true;
        }

        /// <summary>
        /// A location's rectangle in world units as UZDoom's town map uses it: the ground tiles of its blocks plus
        /// Daggerfall Unity's clearance, as TerrainHelper.SetLocationTiles works it out (the converter's
        /// WorldTerrain.cs ports the same code). Falls back to the block rectangle if no block has ground tiles.
        /// </summary>
        internal static void TownRectangle(DaggerfallUnity dfu, in DFLocation location, int pixelX, int pixelY, out int minX, out int maxX, out int minZ, out int maxZ)
        {
            const int TileUnits = 2 * MapsFile.WorldMapTileDim, BlockTiles = 16;
            DaggerfallConnect.Utility.DFPosition origin = MapsFile.MapPixelToWorldCoord(pixelX, pixelY);
            DaggerfallConnect.Utility.DFPosition tile = TerrainHelper.GetLocationTerrainTileOrigin(location);
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            int x0 = int.MaxValue, y0 = int.MaxValue, x1 = 0, y1 = 0;
            for (int by = 0; by < height; by++)
                for (int bx = 0; bx < width; bx++)
                {
                    DFBlock block;
                    if (!dfu.ContentReader.GetBlock(dfu.ContentReader.MapFileReader.GetRmbBlockName(location, bx, by), out block)
                        || block.RmbBlock.FldHeader.GroundData.GroundTiles == null)
                        continue;
                    for (int ty = 0; ty < BlockTiles; ty++)
                        for (int tx = 0; tx < BlockTiles; tx++)
                            if (block.RmbBlock.FldHeader.GroundData.GroundTiles[tx, BlockTiles - 1 - ty].TextureRecord < 56)
                            {
                                int px = tile.X + bx * BlockTiles + tx, py = tile.Y + by * BlockTiles + ty;
                                x0 = Math.Min(x0, px); x1 = Math.Max(x1, px);
                                y0 = Math.Min(y0, py); y1 = Math.Max(y1, py);
                            }
                }
            if (x0 == int.MaxValue)
            {
                x0 = tile.X; x1 = tile.X + width * BlockTiles;
                y0 = tile.Y; y1 = tile.Y + height * BlockTiles;
            }
            else
            {
                int clearance = location.MapTableData.LocationType == DFRegion.LocationTypes.TownCity ? 3 : 2;
                x0 -= clearance; x1 += clearance; y0 -= clearance; y1 += clearance;
            }
            minX = origin.X + x0 * TileUnits; maxX = origin.X + x1 * TileUnits;
            minZ = origin.Y + y0 * TileUnits; maxZ = origin.Y + y1 * TileUnits;
        }

        static bool IsTownType(int locationType)
        {
            return locationType == TypeCity || locationType == TypeHamlet || locationType == TypeVillage;
        }

        /// <summary>The class level of a town (5, 10, 15 or 20), or 0 for any other location type.</summary>
        internal static int TownClassLevel(int locationType, string regionName, string locationName)
        {
            if (locationType == TypeVillage) return TownSmall;
            if (locationType == TypeHamlet) return TownMedium;
            if (locationType != TypeCity) return 0;
            string capital;
            if (!CapitalAlias.TryGetValue(regionName, out capital))
                capital = regionName;
            return string.Equals(locationName.Trim(), capital.Trim(), StringComparison.OrdinalIgnoreCase) ? TownCapital : TownLarge;
        }

        static int TownLevel(int terrain, int locationType, string regionName, string locationName)
        {
            int cls = TownClassLevel(locationType, regionName, locationName);
            return cls > 0 ? Math.Max(terrain, cls) : 0;
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
                BsaFile maps = BuildLocations(t, Path.Combine(arena2, "MAPS.BSA"));
                DoomerfallShopLevels.Build(maps); // shop levels share the loaded MAPS.BSA; they catch their own errors
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

        static BsaFile BuildLocations(Table t, string mapsPath)
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
                    level.town = TownLevel(level.terrain, ltype, MapsFile.RegionNames[region], Latin1Name(names, 4 + i * 32));
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
            return maps;
        }

        // A 32-byte, zero-padded location name from the names record, read as Latin-1 like the script.
        static string Latin1Name(byte[] names, int offset)
        {
            char[] chars = new char[32];
            int n = 0;
            while (n < 32 && offset + n < names.Length && names[offset + n] != 0)
            {
                chars[n] = (char)names[offset + n];
                n++;
            }
            return new string(chars, 0, n);
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
