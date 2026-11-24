// Builds a UZDoom package that shows every Daggerfall item as a DaggerfallItem actor.
// Sprites come from the player's own game data at generation time and are never committed.
// Usage: ItemGallery <arena2> <ItemTemplates.txt> <mod source dir> <output.pk3> <manifest.tsv>
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Text.Json;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Items;

static class ItemGallery
{
    // Copied from ItemHelper so the mapping matches Daggerfall Unity.
    static readonly int[] ArtifactRecords = { 12, 13, 10, 8, 19, 16, 25, 18, 21, 2, 24, 26, 0, 15, 3, 9, 23, 17, 7, 1, 22, 20, 5 };
    const int ArtifactMaleArchive = 432;
    const int Spacing = 128, Columns = 36, Margin = 192; // The largest item is 169 pixels, 127 world units at 75%, so the grid never overlaps.
    const string Placeholder = "DINOSPR";
    static readonly int[] LootArchives = { 204, 205, 207, 209, 211, 216 }; // DaggerfallLootDataTables: every pile and dropped-item icon.

    static readonly (ItemGroups group, Type type)[] Groups =
    {
        (ItemGroups.Drugs, typeof(Drugs)), (ItemGroups.UselessItems1, typeof(UselessItems1)), (ItemGroups.Armor, typeof(Armor)),
        (ItemGroups.Weapons, typeof(Weapons)), (ItemGroups.MensClothing, typeof(MensClothing)), (ItemGroups.Books, typeof(Books)),
        (ItemGroups.Furniture, typeof(Furniture)), (ItemGroups.UselessItems2, typeof(UselessItems2)), (ItemGroups.ReligiousItems, typeof(ReligiousItems)),
        (ItemGroups.Maps, typeof(Maps)), (ItemGroups.WomensClothing, typeof(WomensClothing)), (ItemGroups.Paintings, typeof(Paintings)),
        (ItemGroups.Gems, typeof(Gems)), (ItemGroups.PlantIngredients1, typeof(PlantIngredients1)), (ItemGroups.PlantIngredients2, typeof(PlantIngredients2)),
        (ItemGroups.CreatureIngredients1, typeof(CreatureIngredients1)), (ItemGroups.CreatureIngredients2, typeof(CreatureIngredients2)),
        (ItemGroups.CreatureIngredients3, typeof(CreatureIngredients3)), (ItemGroups.MiscellaneousIngredients1, typeof(MiscellaneousIngredients1)),
        (ItemGroups.MetalIngredients, typeof(MetalIngredients)), (ItemGroups.MiscellaneousIngredients2, typeof(MiscellaneousIngredients2)),
        (ItemGroups.Transportation, typeof(Transportation)), (ItemGroups.Deeds, typeof(Deeds)), (ItemGroups.Jewellery, typeof(Jewellery)),
        (ItemGroups.QuestItems, typeof(QuestItems)), (ItemGroups.MiscItems, typeof(MiscItems)), (ItemGroups.Currency, typeof(Currency)),
    };

    class Entry
    {
        public int Template, Variant, Artifact = -1, Archive, Record, X, Y, W, H;
        public ItemGroups Group;
        public string Name, Texture, Status;
        public double ScaleX = 1, ScaleY = 1;
    }

    // MeshReader.GetBillboardMesh's size at the converted world's scale. Only the actor's display scale changes, never the image.
    static (double x, double y) WorldSpriteScale(TextureFile file, int record)
    {
        var size = file.GetSize(record);
        var scale = file.GetScale(record);
        int xChange = (int)(size.Width * (scale.Width / (double)BlocksFile.ScaleDivisor)), yChange = (int)(size.Height * (scale.Height / (double)BlocksFile.ScaleDivisor));
        double s = PlayerScale.DoomUnitsPerDaggerfallUnit;
        return (s * (size.Width + xChange) / size.Width, s * (size.Height + yChange) / size.Height);
    }

    static int Main(string[] args)
    {
        if (args.Length != 5) { Console.Error.WriteLine("usage: ItemGallery <arena2> <ItemTemplates.txt> <mod dir> <output.pk3> <manifest.tsv>"); return 2; }
        string arena2 = args[0], modDir = args[2], output = args[3], manifest = args[4];

        var groupOf = new Dictionary<int, ItemGroups>();
        foreach (var (group, type) in Groups)
            foreach (var v in Enum.GetValues(type))
            {
                int index = Convert.ToInt32(v);
                // The Deeds enum holds 0-2 rather than template indices, so it is mapped explicitly below.
                if (index >= 0 && group != ItemGroups.Deeds && !groupOf.ContainsKey(index)) groupOf[index] = group;
            }
        // A few templates appear in two enums. None has an inventory image, so this only affects the group label.
        groupOf[(int)Currency.Gold_pieces] = ItemGroups.Currency;
        for (int deed = 99; deed <= 101; deed++) groupOf[deed] = ItemGroups.Deeds;

        using var doc = JsonDocument.Parse(File.ReadAllText(args[1]));
        var entries = new List<Entry>();
        int nominalVariants = 0, templates = 0;
        foreach (var t in doc.RootElement.EnumerateArray())
        {
            templates++;
            int index = t.GetProperty("index").GetInt32(), variants = t.GetProperty("variants").GetInt32();
            int worldA = t.GetProperty("worldTextureArchive").GetInt32(), worldR = t.GetProperty("worldTextureRecord").GetInt32();
            int playerA = t.GetProperty("playerTextureArchive").GetInt32(), playerR = t.GetProperty("playerTextureRecord").GetInt32();
            bool ingredient = t.GetProperty("isIngredient").GetBoolean();
            string name = t.GetProperty("name").GetString();
            if (!groupOf.TryGetValue(index, out var group)) group = ItemGroups.None;
            nominalVariants += Math.Max(1, variants);

            // Mirrors DaggerfallUnityItem.UseWorldTexture and GetInventoryTextureRecord.
            bool useWorld = group == ItemGroups.UselessItems1 || ingredient || index == (int)Weapons.Arrow
                || group == ItemGroups.ReligiousItems || group == ItemGroups.MiscItems;
            bool cloak = index == (int)MensClothing.Casual_cloak || index == (int)MensClothing.Formal_cloak
                || index == (int)WomensClothing.Casual_cloak || index == (int)WomensClothing.Formal_cloak;
            var seen = new HashSet<(int, int)>();
            for (int v = 0; v < Math.Max(1, variants); v++)
            {
                int a = useWorld ? worldA : playerA;
                int r = useWorld ? worldR : variants > 0 ? playerR + (cloak ? 1 : 0) + v : playerR;
                if (index == (int)Weapons.Katana) r += 1;
                // No inventory image. Daggerfall Unity falls back to the world sprite for variant 0 and has no image for
                // later variants of these decorations, so they all use the template's world sprite.
                if (a == 0) { a = worldA; r = worldR; }
                if (seen.Add((a, r)))
                    entries.Add(new Entry { Template = index, Variant = v, Group = group, Name = name, Archive = a, Record = r });
            }
        }
        for (int i = 0; i < ArtifactRecords.Length; i++)
            entries.Add(new Entry
            {
                Template = -1, Artifact = i, Group = ItemGroups.Artifacts, Archive = ArtifactMaleArchive, Record = ArtifactRecords[i],
                Name = ((ArtifactsSubTypes)i).ToString().Replace('_', ' '),
            });

        var files = new Dictionary<int, TextureFile>();
        TextureFile Open(int archive)
        {
            if (files.TryGetValue(archive, out var f)) return f;
            string path = Path.Combine(arena2, TextureFile.IndexToFileName(archive));
            f = archive > 0 && File.Exists(path) ? new TextureFile(path, FileUsage.UseMemory, true) : null;
            return files[archive] = f;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(output)));
        if (File.Exists(output)) File.Delete(output);
        using (var zip = ZipFile.Open(output, ZipArchiveMode.Create))
        {
            foreach (var path in Directory.GetFiles(modDir, "*", SearchOption.AllDirectories))
                zip.CreateEntryFromFile(path, Path.GetRelativePath(modDir, path).Replace('\\', '/'), CompressionLevel.Fastest);

            var written = new Dictionary<(int, int), (int w, int h)?>();
            foreach (var e in entries)
            {
                var key = (e.Archive, e.Record);
                if (!written.TryGetValue(key, out var size))
                {
                    size = null;
                    var file = Open(e.Archive);
                    var image = file != null && e.Record >= 0 && e.Record < file.RecordCount ? file.GetDFBitmap(e.Record, 0) : null;
                    if (image?.Data != null && image.Width > 0 && image.Height > 0 && image.Data.Any(p => p != 0 && p != 0xff))
                    {
                        using var s = zip.CreateEntry($"graphics/dfitems/{TextureName(e.Archive, e.Record)}.png", CompressionLevel.Fastest).Open();
                        WritePng(s, image.Width, image.Height, (x, y) =>
                        {
                            int p = image.Data[y * image.Width + x], c = p * 3 + file.Palette.HeaderLength;
                            var b = file.Palette.PaletteBuffer;
                            return (b[c], b[c + 1], b[c + 2], (byte)(p == 0 || p == 0xff ? 0 : 255));
                        });
                        size = (image.Width, image.Height);
                    }
                    written[key] = size;
                }
                if (size is (int w, int h))
                {
                    e.Texture = TextureName(e.Archive, e.Record); e.W = w; e.H = h; e.Status = "sprite";
                    (e.ScaleX, e.ScaleY) = WorldSpriteScale(Open(e.Archive), e.Record);
                }
                else { e.Texture = Placeholder; e.W = e.H = 32; e.Status = e.Archive == 0 ? "no-sprite-reference" : "bad-record"; }
            }
            using (var s = zip.CreateEntry($"graphics/dfitems/{Placeholder}.png", CompressionLevel.Fastest).Open())
                WritePng(s, 32, 32, (x, y) => x == y || x == 31 - y || x == 0 || y == 0 || x == 31 || y == 31
                    ? ((byte)255, (byte)0, (byte)255, (byte)255) : ((byte)0, (byte)0, (byte)0, (byte)0));

            // Loot pile icons, centered like Daggerfall's billboards. DoomerfallWorldItem draws these.
            var pileTextures = new StringBuilder($"graphic \"DPNOSPR\", 32, 32\n{{\n\tOffset 16, 16\n\tPatch \"{Placeholder}\", 0, 0\n}}\n");
            int pileIcons = 0;
            foreach (int archive in LootArchives)
            {
                var file = Open(archive);
                if (file == null) continue;
                for (int record = 0; record < file.RecordCount; record++)
                {
                    var key = (archive, record);
                    if (!written.TryGetValue(key, out var size))
                    {
                        size = null;
                        var image = file.GetDFBitmap(record, 0);
                        if (image?.Data != null && image.Width > 0 && image.Height > 0 && image.Data.Any(p => p != 0 && p != 0xff))
                        {
                            using var s = zip.CreateEntry($"graphics/dfitems/{TextureName(archive, record)}.png", CompressionLevel.Fastest).Open();
                            WritePng(s, image.Width, image.Height, (x, y) =>
                            {
                                int p = image.Data[y * image.Width + x], c = p * 3 + file.Palette.HeaderLength;
                                var b = file.Palette.PaletteBuffer;
                                return (b[c], b[c + 1], b[c + 2], (byte)(p == 0 || p == 0xff ? 0 : 255));
                            });
                            size = (image.Width, image.Height);
                        }
                        written[key] = size;
                    }
                    if (size is (int w, int h))
                    {
                        pileTextures.Append($"graphic \"DP{archive:D3}{record:D3}\", {w}, {h}\n{{\n\tOffset {w / 2}, {h / 2}\n\tPatch \"{TextureName(archive, record)}\", 0, 0\n}}\n");
                        pileIcons++;
                    }
                }
            }
            WriteText(zip, "textures.dfitems", pileTextures.ToString());
            Console.WriteLine($"ITEMS pileIcons={pileIcons}");

            int rows = (entries.Count + Columns - 1) / Columns;
            for (int i = 0; i < entries.Count; i++)
            {
                entries[i].X = Margin + (i % Columns) * Spacing;
                entries[i].Y = Margin + (i / Columns) * Spacing;
            }
            int width = Margin * 2 + (Columns - 1) * Spacing, height = Margin * 2 + (rows - 1) * Spacing;

            var table = new StringBuilder();
            foreach (var e in entries)
                table.Append(string.Join("\t", e.Template, e.Variant, e.Artifact, (int)e.Group, e.Archive, e.Record, e.X, e.Y,
                    e.ScaleX.ToString("0.####", CultureInfo.InvariantCulture), e.ScaleY.ToString("0.####", CultureInfo.InvariantCulture), e.Texture, e.Name.Replace('\t', ' '))).Append('\n');
            WriteText(zip, "dfitems.txt", table.ToString());
            WriteMap(zip, width, height);
        }

        using (var w = new StreamWriter(manifest, false, new UTF8Encoding(false)))
        {
            w.WriteLine("template\tvariant\tartifact\tgroup\tarchive\trecord\twidth\theight\ttexture\tstatus\tname");
            foreach (var e in entries)
                w.WriteLine(string.Join("\t", e.Template, e.Variant, e.Artifact, e.Group, e.Archive, e.Record, e.W, e.H, e.Texture, e.Status, e.Name));
        }

        var coveredTemplates = entries.Where(e => e.Template >= 0).Select(e => e.Template).Distinct().Count();
        Console.WriteLine($"ITEMS templates={templates} covered={coveredTemplates} artifacts={ArtifactRecords.Length} nominalVariants={nominalVariants} shownEntries={entries.Count}");
        Console.WriteLine($"ITEMS sprite={entries.Count(e => e.Status == "sprite")} noReference={entries.Count(e => e.Status == "no-sprite-reference")} badRecord={entries.Count(e => e.Status == "bad-record")} ungrouped={entries.Count(e => e.Group == ItemGroups.None)} uniqueSprites={entries.Where(e => e.Status == "sprite").Select(e => e.Texture).Distinct().Count()}");
        foreach (var e in entries.Where(e => e.Status == "bad-record"))
            Console.WriteLine($"BAD template={e.Template} variant={e.Variant} artifact={e.Artifact} {e.Name} archive={e.Archive} record={e.Record} recordsInFile={Open(e.Archive)?.RecordCount}");
        return 0;
    }

    static string TextureName(int archive, int record) => $"DI{archive:D3}{record:D3}";

    static void WriteText(ZipArchive zip, string name, string text)
    {
        using var s = zip.CreateEntry(name, CompressionLevel.Fastest).Open();
        var bytes = Encoding.UTF8.GetBytes(text);
        s.Write(bytes, 0, bytes.Length);
    }

    // One UDMF room holding the whole grid. UZDoom builds the nodes on load.
    static void WriteMap(ZipArchive zip, int w, int h)
    {
        var m = new StringBuilder("namespace = \"zdoom\";\n");
        foreach (var (x, y) in new[] { (0, 0), (0, h), (w, h), (w, 0) })
            m.Append($"vertex {{ x = {x}; y = {y}; }}\n");
        for (int i = 0; i < 4; i++)
            m.Append($"linedef {{ v1 = {i}; v2 = {(i + 1) % 4}; sidefront = {i}; blocking = true; }}\nsidedef {{ sector = 0; texturemiddle = \"STARTAN3\"; }}\n");
        m.Append("sector { heightfloor = 0; heightceiling = 320; texturefloor = \"FLOOR4_8\"; textureceiling = \"CEIL3_5\"; lightlevel = 255; }\n");
        m.Append("thing { x = 64.0; y = 64.0; angle = 45; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }\n");
        byte[] text = Encoding.ASCII.GetBytes(m.ToString());

        // A WAD holding DFGALLRY, TEXTMAP, ENDMAP.
        var wad = new MemoryStream();
        var o = new BinaryWriter(wad);
        o.Write(Encoding.ASCII.GetBytes("PWAD")); o.Write(3); o.Write(12 + text.Length);
        o.Write(text);
        void Dir(int offset, int size, string name) { o.Write(offset); o.Write(size); o.Write(Encoding.ASCII.GetBytes(name.PadRight(8, '\0'))); }
        Dir(12, 0, "DFGALLRY"); Dir(12, text.Length, "TEXTMAP"); Dir(12 + text.Length, 0, "ENDMAP");
        o.Flush();
        using var s = zip.CreateEntry("maps/DFGALLRY.wad", CompressionLevel.Fastest).Open();
        wad.Position = 0;
        wad.CopyTo(s);
    }

    static void WritePng(Stream output, int w, int h, Func<int, int, (byte r, byte g, byte b, byte a)> pixel)
    {
        var raw = new byte[(w * 4 + 1) * h];
        for (int y = 0, at = 0; y < h; y++)
        {
            raw[at++] = 0;
            for (int x = 0; x < w; x++)
            {
                var c = pixel(x, y);
                raw[at++] = c.r; raw[at++] = c.g; raw[at++] = c.b; raw[at++] = c.a;
            }
        }
        var packed = new MemoryStream();
        using (var z = new ZLibStream(packed, CompressionLevel.Fastest, true)) z.Write(raw, 0, raw.Length);
        byte[] Big(params int[] values) => values.SelectMany(v => new[] { (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v }).ToArray();
        void Chunk(string kind, byte[] data)
        {
            var name = Encoding.ASCII.GetBytes(kind);
            output.Write(Big(data.Length));
            output.Write(name); output.Write(data);
            output.Write(Big((int)Crc(name.Concat(data))));
        }
        output.Write(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A });
        Chunk("IHDR", Big(w, h).Concat(new byte[] { 8, 6, 0, 0, 0 }).ToArray());
        Chunk("grAb", Big(w / 2, h));   // Stand on the bottom center, as Daggerfall billboards do.
        Chunk("IDAT", packed.ToArray());
        Chunk("IEND", new byte[0]);
    }

    static uint Crc(IEnumerable<byte> data)
    {
        uint c = 0xFFFFFFFF;
        foreach (byte b in data)
        {
            c ^= b;
            for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320 ^ (c >> 1) : c >> 1;
        }
        return ~c;
    }
}
