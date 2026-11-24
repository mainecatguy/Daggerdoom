// Ordinary dungeon billboards and animated textures, following what Daggerfall Unity loads.
// RDBLayout.AddFlats decides which flats exist, DaggerfallBillboard hides editor markers and sets the frame rate,
// MeshReader.GetBillboardMesh sets the size, and GameObjectHelper.AssignAnimatedMaterialComponent animates model textures.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    const int EditorFlatArchive = 199, AnimalFlatArchive = 201, LightFlatArchive = 210, FixedTreasureFlatArchive = 216, FireWallArchive = 356;
    static readonly HashSet<int> NpcFlatArchives = new HashSet<int> { 334, 346, 357, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184 }; // RDBLayout.NPCFlatArchives

    // Treasure is drawn by Daggerfall too, but it is an interactive system. Showing it as scenery would promise loot that does not work yet. NPCs are exported with an id.
    static bool IsOrdinaryFlat(int archive) => archive != EditorFlatArchive && archive != FixedTreasureFlatArchive && !NpcFlatArchives.Contains(archive);

    static double BillboardFps(int archive) => archive == LightFlatArchive ? 12 : 5; // animals and everything else run at 5
    static double ModelTextureFps(int archive) => archive == FireWallArchive ? 5 : 12;

    static string FlatTextureName(int archive, int record, int frame = 0) => $"dfflat/a{archive:D3}r{record:D2}{(frame > 0 ? $"_f{frame}" : "")}.png";
    static string ModelTextureName(int archive, int record, int frame = 0) => $"dfmesh/a{archive:D3}r{record:D2}{(frame > 0 ? $"_f{frame}" : "")}.png";

    // MeshReader.GetBillboardMesh: each axis grows by a truncated fraction of its pixel size.
    static (double x, double y) BillboardScale(TextureFile file, int record)
    {
        var size = file.GetSize(record);
        var scale = file.GetScale(record);
        int xChange = (int)(size.Width * (scale.Width / (double)BlocksFile.ScaleDivisor)), yChange = (int)(size.Height * (scale.Height / (double)BlocksFile.ScaleDivisor));
        double s = PlayerScale.DoomUnitsPerDaggerfallUnit;
        return (s * (size.Width + xChange) / size.Width, s * (size.Height + yChange) / size.Height);
    }

    static void AppendAnimation(StringBuilder animdefs, Func<int, string> name, int frames, double fps)
    {
        double tics = 35.0 / fps;
        animdefs.Append($"texture \"{name(0)}\"\n");
        for (int f = 0; f < frames; f++) animdefs.Append(FormattableString.Invariant($"\tpic \"{name(f)}\" tics {tics:F4}\n"));
    }

    // Frame 0 of a model texture is already in the package. This adds the later frames and their animation.
    static void WriteModelTextureFrames(ZipArchive zip, StringBuilder animdefs, TextureFile file, int archive, int record)
    {
        if (record >= file.RecordCount) return;
        int frames = file.GetFrameCount(record);
        if (frames <= 1) return;
        for (int f = 1; f < frames; f++)
        {
            using var s = zip.CreateEntry(ModelTextureName(archive, record, f), CompressionLevel.Fastest).Open();
            WriteTexturePng(s, file.GetDFBitmap(record, f), file.Palette);
        }
        AppendAnimation(animdefs, f => ModelTextureName(archive, record, f), frames, ModelTextureFps(archive));
    }

    // Every frame of a billboard, anchored on its center as Daggerfall Unity's quad is.
    static void WriteFlatTexture(ZipArchive zip, StringBuilder animdefs, TextureFile file, int archive, int record)
    {
        int frames = Math.Max(1, file.GetFrameCount(record));
        for (int f = 0; f < frames; f++)
        {
            var image = file.GetDFBitmap(record, f);
            using var s = zip.CreateEntry(FlatTextureName(archive, record, f), CompressionLevel.Fastest).Open();
            WriteTexturePng(s, image, file.Palette, true, (image.Width / 2, image.Height / 2));
        }
        if (frames > 1) AppendAnimation(animdefs, f => FlatTextureName(archive, record, f), frames, BillboardFps(archive));
    }

    // Flats without an action. Flats with one are drawn through their action record so they can move.
    static void CollectDungeonFlats(ActionPackage package, BlocksFile blocks, DFLocation location, Func<int, TextureFile> archive)
    {
        var hidden = new SortedDictionary<int, int>();
        foreach (var dungeonBlock in location.Dungeon.Blocks)
        {
            var block = blocks.GetBlock(dungeonBlock.BlockName);
            if (block.RdbBlock.ObjectRootList == null) continue;
            var offset = new V3(dungeonBlock.X * BlockSide, 0, dungeonBlock.Z * BlockSide);
            foreach (var group in block.RdbBlock.ObjectRootList)
            {
                if (group.RdbObjects == null) continue;
                foreach (var obj in group.RdbObjects)
                {
                    // RDBLayout.AddLight: a point light whose Unity range is the record's radius times 3.
                    if (obj.Type == DFBlock.RdbResourceTypes.Light)
                    {
                        package.Lights.Add((ToDoom(new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset), obj.Resources.LightResource.Radius * 3 * PlayerScale.DoomUnitsPerDaggerfallUnit));
                        continue;
                    }
                    if (obj.Type != DFBlock.RdbResourceTypes.Flat) continue;
                    var flat = obj.Resources.FlatResource;
                    // RDBLayout.AddFlat makes a StaticNPC of every flat in these archives.
                    if (NpcFlatArchives.Contains(flat.TextureArchive))
                    {
                        var npcFile = archive(flat.TextureArchive);
                        if (flat.TextureRecord >= npcFile.RecordCount) { Console.WriteLine($"missing NPC flat {flat.TextureArchive}:{flat.TextureRecord}"); continue; }
                        package.Ordinary.Add((flat.TextureArchive, flat.TextureRecord, ToDoom(new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset),
                            NpcIdentity.Make(location.MapTableData.MapId, NpcIdentity.Dungeon, dungeonBlock.X, dungeonBlock.Z, 0, flat.Position)));
                        continue;
                    }
                    if (!IsOrdinaryFlat(flat.TextureArchive))
                    {
                        hidden.TryGetValue(flat.TextureArchive, out int n);
                        hidden[flat.TextureArchive] = n + 1;
                        continue;
                    }
                    if (flat.Action != 0) continue;
                    var file = archive(flat.TextureArchive);
                    if (flat.TextureRecord >= file.RecordCount) { Console.WriteLine($"missing flat {flat.TextureArchive}:{flat.TextureRecord}"); continue; }
                    package.Ordinary.Add((flat.TextureArchive, flat.TextureRecord, ToDoom(new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset), 0));
                }
            }
        }
        var kinds = package.Ordinary.GroupBy(f => f.archive).OrderBy(g => g.Key).Select(g => $"{g.Key}:{g.Count()}");
        if (package.Lights.Count > 0)
        {
            var ranges = package.Lights.Select(l => l.range).OrderBy(r => r).ToList();
            Console.WriteLine(FormattableString.Invariant($"lights: {ranges.Count}, Doom range min {ranges[0]:F0} median {ranges[ranges.Count / 2]:F0} max {ranges[^1]:F0}"));
        }
        Console.WriteLine($"flats: {package.Ordinary.Count} ordinary,{package.Ordinary.Select(f => (f.archive, f.record)).Distinct().Count()} distinct, by archive {string.Join(" ", kinds)}; not drawn by archive {string.Join(" ", hidden.Select(p => $"{p.Key}:{p.Value}"))}");
    }

    // --list-flats: the dungeons with the most ordinary billboards, to choose a worst case for frame cost.
    static int ListFlats(string arena2)
    {
        var maps = new MapsFile(Path.Combine(arena2, "MAPS.BSA"), FileUsage.UseMemory, true);
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var perBlock = new Dictionary<string, int>();
        var totals = new List<(int flats, int id, string name)>();
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var location = maps.GetLocation(r, l);
                if (!location.HasDungeon) continue;
                int total = 0;
                foreach (var dungeonBlock in location.Dungeon.Blocks)
                {
                    if (!perBlock.TryGetValue(dungeonBlock.BlockName, out int count))
                    {
                        var roots = blocks.GetBlock(dungeonBlock.BlockName).RdbBlock.ObjectRootList;
                        count = roots == null ? 0 : roots.Where(g => g.RdbObjects != null).SelectMany(g => g.RdbObjects)
                            .Count(o => o.Type == DFBlock.RdbResourceTypes.Flat && o.Resources.FlatResource.Action == 0 && IsOrdinaryFlat(o.Resources.FlatResource.TextureArchive));
                        perBlock[dungeonBlock.BlockName] = count;
                    }
                    total += count;
                }
                totals.Add((total, location.MapTableData.MapId, $"{region.Name}/{region.MapNames[l]}"));
            }
        }
        foreach (var t in totals.OrderByDescending(t => t.flats).Take(5)) Console.WriteLine($"FLATS {t.flats} #{t.id} {t.name}");
        Console.WriteLine($"dungeons {totals.Count}, median {totals.Select(t => t.flats).OrderBy(n => n).ElementAt(totals.Count / 2)} ordinary flats");
        return 0;
    }

    // DFDLIGHTS: one "x y z range" line per RDB light record, in Doom units. The range is Daggerfall Unity's light range.
    static string DungeonLightLump(ActionPackage package) =>
        string.Concat(package.Lights.Select(l => FormattableString.Invariant($"{l.at.X:F1} {l.at.Y:F1} {l.at.Z:F1} {l.range:F1}\n")));

    // DFDFLATS: one "texture x y z scaleX scaleY [npc id]" line per billboard.
    static string DungeonFlatLump(ActionPackage package, Func<int, TextureFile> archive)
    {
        var text = new StringBuilder();
        foreach (var f in package.Ordinary)
        {
            var (sx, sy) = BillboardScale(archive(f.archive), f.record);
            text.Append(FormattableString.Invariant($"{FlatTextureName(f.archive, f.record)} {f.at.X:F3} {f.at.Y:F3} {f.at.Z:F3} {sx:F4} {sy:F4}{(f.npc != 0 ? $" {f.npc:x16}" : "")}\n"));
        }
        return text.ToString();
    }
}
