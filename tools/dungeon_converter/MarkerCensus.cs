// Editor markers (flat archive 199): which ones the converters skip, and --list-markers, a census of every marker kind
// in the 187 dungeon (RDB) and 920 town (RMB) block templates, with what Daggerfall Unity and Doomerfall do with each.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    const int PassiveReaction = 99, InvalidMobileType = 99; // DFBlock.EnemyReactionTypes.Passive; RDBLayout.AddFixedRDBEnemy

    // RDBLayout.AddFlat switches enemy markers off, so nothing else in DFU reads their Action field as an action.
    static bool IsEnemyMarker(DFBlock.RdbFlatResource f) =>
        f.TextureArchive == EditorArchive && (f.TextureRecord == RandomEnemyRecord || f.TextureRecord == FixedEnemyRecord);

    // RDBLayout.AddFixedRDBEnemy places nothing for mobile type 99 ("known invalid type").
    static bool IsSkippedFixedEnemy(DFBlock.RdbFlatResource f) =>
        f.TextureArchive == EditorArchive && f.TextureRecord == FixedEnemyRecord && !f.IsCustomData && (f.FactionOrMobileId & 0xff) == InvalidMobileType;

    static readonly Dictionary<int, string> DungeonHandling = new Dictionary<int, string>
    {
        [8] = "enter marker: entrance when no start marker (Program.LoadGeometry, starting block only)",
        [10] = "start marker: entrance (starting block) and block water level (Water.cs); castle flag unused",
        [11] = "quest spawn marker: quest foes (DoomerfallMonsters); quest persons have no Doom actor (quest card)",
        [15] = "random enemy: encounter marker (EnemyRoster); slot, underwater table, spawn distance not used (encounter cards)",
        [16] = "fixed enemy: encounter marker (EnemyRoster); mobile type 99 skipped as in DFU; passive ones still hostile (owner question)",
        [18] = "quest item marker: quest items have no Doom side (quest card)",
        [19] = "random treasure: treasure marker; DFU loot listed by DoomerfallItems",
    };
    static readonly Dictionary<int, string> InteriorHandling = new Dictionary<int, string>
    {
        [4] = "rest marker: landing point like enter (SiteExport, DFU FindClosestMarker accepts it)",
        [8] = "enter marker: landing point (SiteExport)",
        [11] = "quest spawn marker: quest persons and foes have no Doom side (quest cards)",
        [15] = "enemy marker: DFU spawns nothing in interiors; skipped",
        [16] = "enemy marker: DFU spawns nothing in interiors; skipped",
        [18] = "quest item marker: quest items have no Doom side (quest card)",
        [19] = "treasure: DFU loot in taverns, Thieves Guild and Dark Brotherhood only; listed by DoomerfallItems",
        [21] = "ladder bottom: DFU DaggerfallLadder; unhandled (records card 07)",
        [22] = "ladder top: DFU DaggerfallLadder; unhandled (records card 07)",
    };
    const string Ignored = "DFU gives it no meaning; skipped";

    static int ListMarkers(string arena2)
    {
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var dungeon = new SortedDictionary<int, int>();
        var dungeonActions = new SortedDictionary<string, int>();
        var passiveBlocks = new SortedDictionary<string, int>();
        var invalidBlocks = new SortedDictionary<string, int>();
        var enemyActionBlocks = new SortedDictionary<string, int>();
        var slots = new SortedDictionary<int, int>();
        var spawnDistance = new SortedDictionary<string, int>();
        int rdb = 0, rmb = 0, passive = 0, invalid = 0, underwater = 0, wetBlocks = 0, underwaterFixed = 0;
        var interior = new SortedDictionary<int, int>();
        var exterior = new SortedDictionary<int, int>();
        for (int b = 0; b < blocks.Count; b++)
        {
            var type = blocks.GetBlockType(b);
            if (type == DFBlock.BlockTypes.Rdb)
            {
                var block = blocks.GetBlock(b);
                if (block.RdbBlock.ObjectRootList == null) continue;
                rdb++;
                var flats = block.RdbBlock.ObjectRootList.Where(g => g.RdbObjects != null).SelectMany(g => g.RdbObjects)
                    .Where(o => o.Type == DFBlock.RdbResourceTypes.Flat && o.Resources.FlatResource.TextureArchive == EditorArchive).ToList();
                // DFU reads the water level from the block's first start marker (DaggerfallBillboard: -8 * SoundIndex).
                var start = flats.Where(o => o.Resources.FlatResource.TextureRecord == StartRecord).Select(o => (int?)o.Resources.FlatResource.SoundIndex).FirstOrDefault();
                int? water = start is int s && s != 0 ? -8 * s : (int?)null;
                if (water.HasValue) wetBlocks++;
                foreach (var o in flats)
                {
                    var f = o.Resources.FlatResource;
                    Bump(dungeon, f.TextureRecord);
                    if (f.Action != 0) Bump(dungeonActions, $"199:{f.TextureRecord} action {f.Action}");
                    if (!IsEnemyMarker(f)) continue;
                    if (f.Action != 0) Bump(enemyActionBlocks, blocks.GetBlockName(b));
                    Bump(spawnDistance, $"199:{f.TextureRecord} type {f.SoundIndex}");
                    bool below = water.HasValue && water.Value < o.YPos; // classic Y grows downward (RDBLayout.AddRandomRDBEnemyClassic)
                    if (f.TextureRecord == RandomEnemyRecord) { Bump(slots, f.Flags); if (below) underwater++; }
                    else
                    {
                        if (below) underwaterFixed++;
                        if (f.Action == PassiveReaction) { passive++; Bump(passiveBlocks, blocks.GetBlockName(b)); }
                        if (IsSkippedFixedEnemy(f)) { invalid++; Bump(invalidBlocks, blocks.GetBlockName(b)); }
                    }
                }
            }
            else if (type == DFBlock.BlockTypes.Rmb)
            {
                var block = blocks.GetBlock(b);
                rmb++;
                foreach (var sub in block.RmbBlock.SubRecords ?? Array.Empty<DFBlock.RmbSubRecord>())
                {
                    foreach (var f in sub.Interior.BlockFlatObjectRecords ?? Array.Empty<DFBlock.RmbBlockFlatObjectRecord>())
                        if (f.TextureArchive == EditorArchive) Bump(interior, f.TextureRecord);
                    foreach (var f in sub.Exterior.BlockFlatObjectRecords ?? Array.Empty<DFBlock.RmbBlockFlatObjectRecord>())
                        if (f.TextureArchive == EditorArchive) Bump(exterior, f.TextureRecord);
                }
                foreach (var f in block.RmbBlock.MiscFlatObjectRecords ?? Array.Empty<DFBlock.RmbBlockFlatObjectRecord>())
                    if (f.TextureArchive == EditorArchive) Bump(exterior, 1000 + f.TextureRecord); // block misc flats, printed apart
            }
        }

        Console.WriteLine($"MARKERS dungeon blocks {rdb}, town blocks {rmb}");
        foreach (var p in dungeon) Console.WriteLine($"DUNGEON 199:{p.Key} {p.Value} | {(DungeonHandling.TryGetValue(p.Key, out var h) ? h : Ignored)}");
        foreach (var p in interior) Console.WriteLine($"INTERIOR 199:{p.Key} {p.Value} | {(InteriorHandling.TryGetValue(p.Key, out var h) ? h : Ignored)}");
        foreach (var p in exterior)
            Console.WriteLine($"EXTERIOR {(p.Key >= 1000 ? "misc" : "building")} 199:{p.Key % 1000} {p.Value} | {(p.Key % 1000 is 8 or 10 ? "arrival comes from Daggerfall's position through the bridge; skipped" : Ignored)}");
        Console.WriteLine($"FIXED passive (Action 99) {passive} | no action record (enemy markers are inactive in DFU); spawns a hostile monster until the owner decides; blocks {Join(passiveBlocks)}");
        Console.WriteLine($"FIXED mobile type 99 {invalid} | skipped, as RDBLayout.AddFixedRDBEnemy; blocks {Join(invalidBlocks)}");
        foreach (var p in dungeonActions)
        {
            bool enemy = p.Key.StartsWith($"199:{RandomEnemyRecord} ") || p.Key.StartsWith($"199:{FixedEnemyRecord} ");
            Console.WriteLine($"ACTION {p.Key} {p.Value} | {(enemy ? "not exported: marker is inactive in DFU" : "exported as a flat action record, as DFU's AddActionFlatHelper")}");
        }
        Console.WriteLine($"ENEMY markers with an action field, by block: {Join(enemyActionBlocks)}");
        // Which dungeons use those blocks, and how many enemy-marker action records each loses.
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                var used = location.Dungeon.Blocks.Select(d => d.BlockName).Where(enemyActionBlocks.ContainsKey).ToList();
                if (used.Count == 0) continue;
                Console.WriteLine($"ENEMY-ACTION DUNGEON #{location.MapTableData.MapId} {region.Name}/{region.MapNames[l]}: {used.Sum(n => enemyActionBlocks[n])} records "
                    + $"({used.Sum(n => passiveBlocks.TryGetValue(n, out int p) ? p : 0)} passive), mobile 99 {used.Sum(n => invalidBlocks.TryGetValue(n, out int v) ? v : 0)}; blocks {string.Join(" ", used)}");
            }
        }
        Console.WriteLine($"RANDOM slot (Flags) {Join(slots)} | not used: classic selection gives every marker with the same slot one monster type, slot 0 a random 1-6 (encounter cards)");
        Console.WriteLine($"RANDOM underwater {underwater} in {wetBlocks} blocks with water; fixed below water {underwaterFixed} | not used: DFU picks from the underwater table 19 (encounter cards)");
        Console.WriteLine($"SPAWN distance (SoundIndex) {Join(spawnDistance)} | not used: DFU wake-up radius, EnemySenses (encounter cards)");
        return 0;
    }

    static void Bump<T>(IDictionary<T, int> d, T key) { d.TryGetValue(key, out int n); d[key] = n + 1; }
    static string Join<T>(IDictionary<T, int> d) => string.Join(" ", d.Select(p => $"{p.Key}:{p.Value}"));
}
