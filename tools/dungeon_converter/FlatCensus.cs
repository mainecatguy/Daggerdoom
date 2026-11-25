// --flat-census <outdir>: every billboard picture placed in Daggerfall's blocks, counted by where it appears (dungeon
// blocks, building interiors, town exteriors), with its drawn size in Doom units and a PNG of its first frame.
// It is research for the flat collision card: Daggerfall's data has no solid flag, so the owner picks from this list.
// Counts are per block definition, not per location that uses the block. The PNGs come from game data: keep them out of git.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

static partial class Program
{
    static int FlatCensus(string arena2, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        // (archive, record) -> counts: dungeon, dungeon with action, interior, exterior, exterior NPC
        var counts = new SortedDictionary<(int a, int r), int[]>();
        void Bump(int a, int r, int column)
        {
            if (!counts.TryGetValue((a, r), out var c)) counts[(a, r)] = c = new int[5];
            c[column]++;
        }
        for (int b = 0; b < blocks.Count; b++)
        {
            var type = blocks.GetBlockType(b);
            if (type == DFBlock.BlockTypes.Rdb)
            {
                var roots = blocks.GetBlock(b).RdbBlock.ObjectRootList;
                if (roots == null) continue;
                foreach (var o in roots.Where(g => g.RdbObjects != null).SelectMany(g => g.RdbObjects))
                {
                    if (o.Type != DFBlock.RdbResourceTypes.Flat) continue;
                    var f = o.Resources.FlatResource;
                    Bump(f.TextureArchive, f.TextureRecord, f.Action != 0 ? 1 : 0);
                }
            }
            else if (type == DFBlock.BlockTypes.Rmb)
            {
                var rmb = blocks.GetBlock(b).RmbBlock;
                foreach (var sub in rmb.SubRecords ?? Array.Empty<DFBlock.RmbSubRecord>())
                {
                    foreach (var f in sub.Interior.BlockFlatObjectRecords ?? Array.Empty<DFBlock.RmbBlockFlatObjectRecord>()) Bump(f.TextureArchive, f.TextureRecord, 2);
                    foreach (var f in sub.Exterior.BlockFlatObjectRecords ?? Array.Empty<DFBlock.RmbBlockFlatObjectRecord>()) Bump(f.TextureArchive, f.TextureRecord, f.FactionID != 0 ? 4 : 3);
                }
                foreach (var f in rmb.MiscFlatObjectRecords ?? Array.Empty<DFBlock.RmbBlockFlatObjectRecord>()) Bump(f.TextureArchive, f.TextureRecord, f.FactionID != 0 ? 4 : 3);
            }
        }

        var files = new Dictionary<int, TextureFile>();
        TextureFile Archive(int a)
        {
            if (files.TryGetValue(a, out var f)) return f;
            string path = Path.Combine(arena2, TextureFile.IndexToFileName(a));
            return files[a] = File.Exists(path) ? new TextureFile(path, FileUsage.UseMemory, true) : null;
        }

        var text = new StringBuilder("archive:record dungeon dungeonAction interior exterior exteriorNpc widthDoom heightDoom\n");
        var html = new StringBuilder("<!doctype html><meta charset=utf-8><title>Daggerfall flat census</title><style>body{font:13px sans-serif;background:#222;color:#ddd}"
            + "div{display:inline-block;width:150px;margin:4px;vertical-align:top;text-align:center}img{max-width:140px;max-height:140px;image-rendering:pixelated;background:#444}</style>\n"
            + "<p>Counts are per block definition: dungeon / dungeon with action / interior / town exterior / town NPC. Size is Daggerfall Unity's drawn size in Doom units.</p>\n");
        int lastArchive = -1;
        foreach (var p in counts)
        {
            var file = Archive(p.Key.a);
            double w = 0, h = 0;
            bool ok = file != null && p.Key.r < file.RecordCount;
            if (ok)
            {
                var size = file.GetSize(p.Key.r);
                var (sx, sy) = BillboardScale(file, p.Key.r);
                w = size.Width * sx; h = size.Height * sy;
                string png = $"a{p.Key.a:D3}r{p.Key.r:D2}.png";
                using (var s = File.Create(Path.Combine(outDir, png))) WriteTexturePng(s, file.GetDFBitmap(p.Key.r, 0), file.Palette, true);
                if (p.Key.a != lastArchive) { html.Append($"<h2>TEXTURE.{p.Key.a:D3}</h2>\n"); lastArchive = p.Key.a; }
                var c = p.Value;
                html.Append(FormattableString.Invariant($"<div><img src=\"{png}\"><br>{p.Key.a}:{p.Key.r}<br>{c[0]}/{c[1]}/{c[2]}/{c[3]}/{c[4]}<br>{w:F0}×{h:F0}</div>\n"));
            }
            text.Append(FormattableString.Invariant($"{p.Key.a}:{p.Key.r} {string.Join(" ", p.Value)} {w:F1} {h:F1}{(ok ? "" : " missing")}\n"));
        }
        // One strip per archive, every placed record's first frame side by side, for quick viewing.
        foreach (var group in counts.Keys.GroupBy(k => k.a))
        {
            var file = Archive(group.Key);
            if (file == null) continue;
            var images = group.Where(k => k.r < file.RecordCount).Select(k => file.GetDFBitmap(k.r, 0)).ToList();
            if (images.Count == 0) continue;
            int width = images.Sum(i => i.Width + 2), height = images.Max(i => i.Height);
            var strip = new DFBitmap(width, height);
            int x0 = 0;
            foreach (var image in images)
            {
                for (int y = 0; y < image.Height; y++)
                    Array.Copy(image.Data, y * image.Width, strip.Data, y * width + x0, image.Width);
                x0 += image.Width + 2;
            }
            using var s = File.Create(Path.Combine(outDir, $"strip{group.Key:D3}.png"));
            WriteTexturePng(s, strip, file.Palette, true);
        }
        File.WriteAllText(Path.Combine(outDir, "census.txt"), text.ToString());
        File.WriteAllText(Path.Combine(outDir, "index.html"), html.ToString());
        Console.WriteLine($"FLATCENSUS {counts.Count} pictures in {counts.Keys.Select(k => k.a).Distinct().Count()} archives, written to {outDir}");
        return 0;
    }
}
