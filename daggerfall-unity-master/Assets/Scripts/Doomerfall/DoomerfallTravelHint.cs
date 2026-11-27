// Doomerfall: the danger word the travel map shows for a dungeon, taken from the place's own area level.
// Cities, towns and other non-dungeon places show no word (owner, 2026-11-26).
//
// The owner asked for a feeling rather than a number (beginner, weak, moderate, very hard, legendary), coming only
// from the place's level, never its type. Levels are percentile ranks 1 to 30, so equal six-level bands give each
// word a fifth of all dungeons; the ranges and the measured shares are in work/notes/20261124-002814.md.
// A town shows its town level (owner, 2026-11-26: the higher of its terrain level and its class level).

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallTravelHint
    {
        // Each word covers six levels: 1-6, 7-12, 13-18, 19-24, 25-30.
        static readonly string[] Words = { "Beginner", "Weak", "Moderate", "Very hard", "Legendary" };
        const int LevelsPerWord = 6;

        static int cachedMapId;
        static string cachedWord;
        static bool hasCache;

        /// <summary>The danger word for an area level, or null for 0 (unknown).</summary>
        internal static string Word(int level)
        {
            if (level <= 0)
                return null;
            int i = (level - 1) / LevelsPerWord;
            return Words[i < Words.Length ? i : Words.Length - 1];
        }

        /// <summary>
        /// True for the location types that have a dungeon: labyrinths, keeps, ruins and graveyards. Covens are left
        /// out (as in Daggerfall's own dungeon checks): they have no dungeon, only outdoor NPCs.
        /// </summary>
        internal static bool IsDungeon(DFRegion.LocationTypes type)
        {
            switch (type)
            {
                case DFRegion.LocationTypes.DungeonLabyrinth:
                case DFRegion.LocationTypes.DungeonKeep:
                case DFRegion.LocationTypes.DungeonRuin:
                case DFRegion.LocationTypes.Graveyard:
                    return true;
                default:
                    return false;
            }
        }

        /// <summary>
        /// The danger word for a travel map dungeon (null for any other place), or null while the levels are still being ranked or if they
        /// failed. Never waits for the ranking, so the map label can call it every frame.
        /// </summary>
        internal static string ForLocation(ContentReader.MapSummary summary)
        {
            // Owner (2026-11-26): only dungeons get a word. A city's level comes from its palace dungeon, which says
            // nothing about its streets, so towns, homes, temples and taverns show none.
            if (!IsDungeon(summary.LocationType))
                return null;
            if (hasCache && cachedMapId == summary.MapID)
                return cachedWord;
            if (!DoomerfallAreaLevels.IsFinished)
                return null;

            DoomerfallAreaLevels.Level level;
            DFLocation location;
            string word = null;
            if (DoomerfallAreaLevels.ForMapId(summary.MapID, out level))
                word = Word(level.Place); // the town level for a town
            else if (DaggerfallUnity.Instance.ContentReader.GetLocation(summary.RegionIndex, summary.MapIndex, out location)
                && DoomerfallAreaLevels.ForLocation(location, out level))
                word = Word(level.Place); // a location a mod added

            cachedMapId = summary.MapID;
            cachedWord = word;
            hasCache = true;
            return word;
        }

        /// <summary>
        /// Adds a "Danger: Word" line under Daggerfall's "Do you wish to travel to" text. Waits for the ranking if it
        /// is still running, since this is a one-off click. Returns the tokens unchanged if there is no word.
        /// </summary>
        internal static TextFile.Token[] AddToConfirmation(TextFile.Token[] tokens, ContentReader.MapSummary summary)
        {
            if (!DoomerfallAreaLevels.IsFinished)
                DoomerfallAreaLevels.Status(); // waits for the worker
            string word = ForLocation(summary);
            if (word == null || tokens == null)
                return tokens;

            List<TextFile.Token> list = new List<TextFile.Token>(tokens);
            TextFile.Formatting lineEnd = TextFile.Formatting.NewLine;
            int last = list.Count - 1;
            while (last >= 0 && list[last].formatting == TextFile.Formatting.EndOfRecord)
                last--;
            // Classic text ends each line with a justify token; reuse it so the new line lines up with the rest.
            if (last >= 0 && (list[last].formatting == TextFile.Formatting.JustifyCenter || list[last].formatting == TextFile.Formatting.JustifyLeft))
                lineEnd = list[last].formatting;
            else if (last >= 0)
                list.Insert(++last, new TextFile.Token(TextFile.Formatting.NewLine));
            list.Insert(last + 1, new TextFile.Token(TextFile.Formatting.Text, "Danger: " + word));
            if (lineEnd != TextFile.Formatting.NewLine)
                list.Insert(last + 2, new TextFile.Token(lineEnd));
            return list.ToArray();
        }

        /// <summary>" (Word)" to append to a location name, or empty if there is no word.</summary>
        internal static string Suffix(ContentReader.MapSummary summary)
        {
            string word = ForLocation(summary);
            return word == null ? string.Empty : " (" + word + ")";
        }
    }
}
