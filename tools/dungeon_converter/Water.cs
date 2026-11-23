// Daggerfall's per-block dungeon water, converted to swimmable 3D floors.
//
// Daggerfall floods everything in a block below one height. It stores that height on the block's
// Start marker (editor flat 199.10): SoundIndex * 8 native units, with 0 meaning no water. See
// DaggerfallBillboard.SetRDBResourceData and DaggerfallDungeon.FindMarkers.
//
// Each walkable span below the line gets its own volume, bounded by that span's floor and ceiling.
// Water therefore cannot leak through the slab into a room above or below it.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;

static partial class Program
{
    public const int NoWater = int.MinValue;
    const int WaterToCeiling = int.MaxValue; // the span is submerged up to its ceiling, so it has no visible surface
    const int WaterFloorType = 2, WaterFloorFlags = 1, WaterAlpha = 120; // swimmable; no light splitting
    const string WaterTexture = "FWATER1";
    const int MaxWaterProbes = 60000;

    static readonly List<int?> blockWater = new List<int?>();

    static int? BlockWaterHeight(DFBlock block)
    {
        if (block.RdbBlock.ObjectRootList == null) return null;
        foreach (var group in block.RdbBlock.ObjectRootList)
        {
            if (group.RdbObjects == null) continue;
            foreach (var obj in group.RdbObjects)
            {
                if (obj.Type != DFBlock.RdbResourceTypes.Flat) continue;
                var flat = obj.Resources.FlatResource;
                if (flat.TextureArchive != EditorArchive || flat.TextureRecord != StartRecord) continue;
                // The first Start marker decides, as in FindMarkers.
                if (flat.SoundIndex == 0) return null;
                return (int)Math.Round(8 * flat.SoundIndex * PlayerScale.DoomUnitsPerDaggerfallUnit);
            }
        }
        return null;
    }

    static void AssignWater()
    {
        if (!blockWater.Any(w => w.HasValue)) return;
        for (int j = 0; j < height; j++)
            for (int i = 0; i < width; i++)
            {
                var spans = grid[Index(i, j)];
                if (spans.Count == 0) continue;
                int block = BlockAt(minX + i * cell + cell / 2, minY + j * cell + cell / 2);
                if (block < 0 || blockWater[block] is not int line) continue;
                foreach (var span in spans)
                    if (span.F < line) span.Water = span.C <= line ? WaterToCeiling : line;
            }
    }

    // Writes <slug>_waterprobe/DFWPROBE.txt for water_check.py. Dry dungeons write nothing.
    // P x y z wet: a flat floor point and whether it should be in water.
    // S x y floor top: the deepest open water, used for the swim test.
    static void WriteWaterProbes(string outDir, string slug, Node start)
    {
        if (!blockWater.Any(w => w.HasValue)) return;
        const int margin = 3; // keeps probes clear of the surface itself
        var stacked = new List<string>();
        var plain = new List<string>();
        (int x, int y, int floor, int top, int depth) deepest = default;
        for (int j = 0; j < height; j++)
            for (int i = 0; i < width; i++)
            {
                var spans = grid[Index(i, j)];
                if (spans.Count == 0) continue;
                int x = minX + i * cell + cell / 2, y = minY + j * cell + cell / 2;
                int block = BlockAt(x, y);
                if (block < 0 || blockWater[block] is not int line) continue;
                bool mixed = spans.Any(s => s.Water != NoWater) && spans.Any(s => s.Water == NoWater);
                foreach (var span in spans)
                {
                    if (span.FP >= 0 || span.CP >= 0 || span.Door >= 0) continue;
                    int z = span.F + 1;
                    if (Math.Abs(z - line) >= margin)
                        (mixed ? stacked : plain).Add($"P {x} {y} {z} {(span.Water != NoWater ? 1 : 0)}");
                    if (span.Water == NoWater) continue;
                    int top = span.Water == WaterToCeiling ? span.C : span.Water;
                    if (top - span.F > deepest.depth) deepest = (x, y, span.F, top, top - span.F);
                }
            }
        var text = new StringBuilder();
        // Stacked cells are the requirement under test, so they are kept first.
        foreach (var line in stacked.Take(MaxWaterProbes)) text.Append(line).Append('\n');
        int room = Math.Max(0, MaxWaterProbes - stacked.Count), step = Math.Max(1, plain.Count / Math.Max(1, room));
        for (int n = 0; n < plain.Count && room > 0; n += step, room--) text.Append(plain[n]).Append('\n');
        if (deepest.depth > 0) text.Append($"S {deepest.x} {deepest.y} {deepest.floor} {deepest.top}\n");
        string dir = Path.Combine(outDir, slug + "_waterprobe");
        Directory.CreateDirectory(dir);
        File.WriteAllText(Path.Combine(dir, "DFWPROBE.txt"), text.ToString());
        var wetBlocks = blockWater.Select((w, b) => (w, b)).Where(p => p.w.HasValue).Select(p => $"{blockRects[p.b].name}@{p.w}");
        Console.WriteLine($"WATER blocks: {string.Join(" ", wetBlocks)}; stacked probes {stacked.Count}, other probes {plain.Count}, deepest {deepest.depth}");
        for (int b = 0; b < blockWater.Count; b++)
        {
            if (blockWater[b] is not int level) continue;
            var inBlock = Enumerable.Range(0, grid.Length).Where(c => BlockAt(minX + c % width * cell + cell / 2, minY + c / width * cell + cell / 2) == b).SelectMany(c => grid[c]).ToList();
            if (inBlock.Count == 0) continue;
            var depths = inBlock.Where(s => s.Water != NoWater && s.Water != WaterToCeiling).Select(s => s.Water - s.F).OrderBy(d => d).ToList();
            Console.WriteLine($"WATER {blockRects[b].name} line {level}: spans {inBlock.Count}, partly flooded {depths.Count} (median depth {(depths.Count > 0 ? depths[depths.Count / 2] : 0)}), " +
                $"flooded to ceiling {inBlock.Count(s => s.Water == WaterToCeiling)}, dry {inBlock.Count(s => s.Water == NoWater)}, floors {inBlock.Min(s => s.F)}..{inBlock.Max(s => s.F)}");
        }
    }

    // Lists every dungeon with water in at least one block. Usage: --list-water
    public static int ListWater(string arena2)
    {
        var maps = new DaggerfallConnect.Arena2.MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var blocks = new DaggerfallConnect.Arena2.BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var cache = new Dictionary<string, bool>();
        int dungeons = 0, wet = 0;
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                dungeons++;
                int count = 0;
                foreach (var b in location.Dungeon.Blocks)
                {
                    if (!cache.TryGetValue(b.BlockName, out bool hasWater))
                        cache[b.BlockName] = hasWater = BlockWaterHeight(blocks.GetBlock(b.BlockName)).HasValue;
                    if (hasWater) count++;
                }
                if (count == 0) continue;
                wet++;
                Console.WriteLine($"WET {region.Name}/{region.MapNames[l]}: {count} of {location.Dungeon.Blocks.Length} blocks");
            }
        }
        Console.WriteLine($"WATER SUMMARY: {wet} of {dungeons} dungeons have water");
        return 0;
    }
}
