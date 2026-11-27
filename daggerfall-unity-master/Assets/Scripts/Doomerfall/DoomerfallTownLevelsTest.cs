// Doomerfall test only: the town level part of -dfarealeveldump (DoomerfallAreaLevelsTest). Writes to its sample.txt:
// the town class counts against the shop level notes, named towns with their terrain, class and town level, the
// travel word, the level at the town's centre and either side of the town map's edge, and a wilderness pixel next to
// a capital. Every check line ends in PASS or FAIL.

using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallTownLevelsTest
    {
        // Region, town, expected town level (0: just log it).
        static readonly object[][] Towns =
        {
            new object[] { "Daggerfall", "Gothway Garden", 10 },      // the New Game arrival hamlet, terrain 1
            new object[] { "Daggerfall", "Daggerfall", 20 },          // the main quest's first capital, terrain 2
            new object[] { "Wayrest", "Wayrest", 20 },
            new object[] { "Sentinel", "Akhahanu", 15 },              // a large city
            new object[] { "Sentinel", "Sentinel", 24 },              // a capital whose terrain is above 20
            new object[] { "Wrothgarian Mountains", "Pening Minster", 30 }, // a village at terrain 30
        };

        internal static void Run(StringBuilder report)
        {
            ContentReader reader = DaggerfallUnity.Instance.ContentReader;
            report.AppendLine("towns:");
            CountClasses(report, reader);

            DFLocation village = default(DFLocation);
            bool haveVillage = false;
            DFRegion daggerfall = reader.MapFileReader.GetRegion("Daggerfall");
            for (int i = 0; i < daggerfall.LocationCount && !haveVillage; i++)
                if (daggerfall.MapTable[i].LocationType == DFRegion.LocationTypes.TownVillage)
                    haveVillage = reader.GetLocation("Daggerfall", daggerfall.MapNames[i], out village);
            if (haveVillage)
                Town(report, village, 0);
            foreach (object[] t in Towns)
            {
                DFLocation location;
                if (reader.GetLocation((string)t[0], (string)t[1], out location))
                    Town(report, location, (int)t[2]);
                else
                    report.AppendFormat("  {0} / {1}: not found FAIL\n", t[0], t[1]);
            }

            DFLocation hold;
            DoomerfallAreaLevels.Level holdLevel;
            if (reader.GetLocation("Daggerfall", "Privateer's Hold", out hold) && DoomerfallAreaLevels.ForLocation(hold, out holdLevel))
                report.AppendFormat("  Privateer's Hold: dungeon {0}, town {1} {2}\n", holdLevel.dungeon, holdLevel.town,
                    holdLevel.dungeon == 1 && holdLevel.town == 0 ? "PASS" : "FAIL");

            Wilderness(report, reader, "Daggerfall", "Daggerfall");
        }

        static void CountClasses(StringBuilder report, ContentReader reader)
        {
            int small = 0, medium = 0, large = 0, capital = 0, levelled = 0, mismatched = 0;
            for (int r = 0; r < reader.MapFileReader.RegionCount; r++)
            {
                DFRegion region = reader.MapFileReader.GetRegion(r);
                for (int i = 0; i < region.LocationCount; i++)
                {
                    int cls = DoomerfallAreaLevels.TownClassLevel((int)region.MapTable[i].LocationType, MapsFile.RegionNames[r], region.MapNames[i]);
                    if (cls == DoomerfallAreaLevels.TownSmall) small++;
                    else if (cls == DoomerfallAreaLevels.TownMedium) medium++;
                    else if (cls == DoomerfallAreaLevels.TownLarge) large++;
                    else if (cls == DoomerfallAreaLevels.TownCapital) capital++;
                    DoomerfallAreaLevels.Level level;
                    if (!DoomerfallAreaLevels.ForMapId(region.MapTable[i].MapId, out level))
                        continue;
                    int want = cls > 0 ? System.Math.Max(cls, level.terrain) : 0;
                    if (level.town == want) levelled++; else mismatched++;
                }
            }
            bool ok = small == 1834 && medium == 1200 && large == 371 && capital == 39;
            report.AppendFormat("  classes: small {0}, medium {1}, large {2}, capital {3} (notes: 1834, 1200, 371, 39) {4}\n",
                small, medium, large, capital, ok ? "PASS" : "FAIL");
            report.AppendFormat("  town level = max(terrain, class) for {0} classic locations, {1} differ {2}\n", levelled, mismatched, mismatched == 0 ? "PASS" : "FAIL");
        }

        static void Town(StringBuilder report, DFLocation location, int expected)
        {
            DoomerfallAreaLevels.Level level;
            DoomerfallAreaLevels.ForLocation(location, out level);
            int minX, maxX, minZ, maxZ;
            Rect(location, out minX, out maxX, out minZ, out maxZ);
            int cx = (minX + maxX) / 2, cz = (minZ + maxZ) / 2, edge = DoomerfallAreaLevels.TownEdge;
            int centre = DoomerfallAreaLevels.TownAt(cx, cz);
            int inside = DoomerfallAreaLevels.TownAt(maxX + edge - 1, cz);
            int outside = DoomerfallAreaLevels.TownAt(maxX + edge + 256, cz);
            int outsidePixelLevel = DoomerfallAreaLevels.ForMapPixel(MapsFile.WorldCoordToMapPixel(maxX + edge + 256, cz).X, MapsFile.WorldCoordToMapPixel(maxX + edge + 256, cz).Y);
            bool ok = (expected == 0 || level.town == expected) && centre == level.town && inside == level.town && outside == 0;
            report.AppendFormat("  {0} / {1} ({2}, map_id {3}): terrain {4}, class {5}, town {6}, dungeon {7}, travel word {8}; level at centre {9}, just inside the town map edge {10}, one tile past it {11} (then terrain {12}) {13}\n",
                location.RegionName, location.Name, location.MapTableData.LocationType, location.MapTableData.MapId, level.terrain,
                DoomerfallAreaLevels.TownClassLevel((int)location.MapTableData.LocationType, location.RegionName, location.Name),
                level.town, level.dungeon, DoomerfallTravelHint.Word(level.Place), centre, inside, outside, outsidePixelLevel, ok ? "PASS" : "FAIL");
        }

        // A wilderness pixel next to a town: no location there, and away from the town map its level is the terrain level.
        static void Wilderness(StringBuilder report, ContentReader reader, string regionName, string townName)
        {
            DFLocation town;
            if (!reader.GetLocation(regionName, townName, out town))
                return;
            int px = town.MapTableData.Longitude / 128, py = 499 - town.MapTableData.Latitude / 128;
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++)
                {
                    ContentReader.MapSummary summary;
                    if ((dx == 0 && dy == 0) || reader.HasLocation(px + dx, py + dy, out summary))
                        continue;
                    DFPosition origin = MapsFile.MapPixelToWorldCoord(px + dx, py + dy);
                    // The far corner of the neighbour pixel, away from the town.
                    int wx = origin.X + (dx >= 0 ? MapsFile.WorldMapTerrainDim - 1 : 0);
                    int wz = origin.Y + (dy <= 0 ? MapsFile.WorldMapTerrainDim - 1 : 0);
                    int terrain = DoomerfallAreaLevels.ForMapPixel(px + dx, py + dy);
                    int townHere = DoomerfallAreaLevels.TownAt(wx, wz);
                    report.AppendFormat("  wilderness pixel ({0}, {1}) next to {2}: terrain {3}, town level at its far corner {4} {5}\n",
                        px + dx, py + dy, townName, terrain, townHere, townHere == 0 ? "PASS" : "FAIL");
                    return;
                }
            report.AppendFormat("  no wilderness pixel next to {0}\n", townName);
        }

        // Same rectangle as PlayerGPS.SetLocationRect.
        static void Rect(DFLocation location, out int minX, out int maxX, out int minZ, out int maxZ)
        {
            int px = location.MapTableData.Longitude / 128, py = 499 - location.MapTableData.Latitude / 128;
            DFPosition origin = MapsFile.MapPixelToWorldCoord(px, py);
            DFPosition tile = TerrainHelper.GetLocationTerrainTileOrigin(location);
            minX = origin.X + tile.X * 2 * MapsFile.WorldMapTileDim;
            minZ = origin.Y + tile.Y * 2 * MapsFile.WorldMapTileDim;
            maxX = minX + location.Exterior.ExteriorData.Width * MapsFile.WorldMapRMBDim;
            maxZ = minZ + location.Exterior.ExteriorData.Height * MapsFile.WorldMapRMBDim;
        }
    }
}
