// Daggerfall's HUD font (ARENA2\FONT0003.FNT) as a UZDoom folder font, fonts/dffont3/<hex code>.png plus font.inf, so
// Doom can draw Daggerfall's HUD messages in Daggerfall Unity's classic font (mods/doomerfall/src/zscript/Doomerfall.zs).
// Read as Daggerfall Unity reads it (API/FntFile.cs, DaggerfallFont.cs): 240 glyphs from ASCII 33, 16x16 bit rows,
// proportional widths, a space FixedWidth - 1 wide, and one pixel between glyphs. Glyphs are white for Doom to tint.
// Generated from the player's game data at install, like the rest of ddruntime.pk3, and never committed.

using System;
using System.IO;
using System.IO.Compression;
using System.Text;

static class FontExport
{
    const int GlyphCount = 240, FirstCode = 33, LastExported = 126; // Above '~' Daggerfall's codes are not Unicode.

    public static int Write(ZipArchive zip, string arena2, string name = "FONT0003.FNT", string folder = "dffont3")
    {
        string path = Path.Combine(arena2, name);
        if (!File.Exists(path)) { Console.Error.WriteLine("font: " + path + " not found; Doom falls back to its own font"); return 0; }
        byte[] fnt = File.ReadAllBytes(path);
        int fixedWidth = BitConverter.ToUInt16(fnt, 0), height = BitConverter.ToUInt16(fnt, 2), written = 0;
        for (int i = 0; i < GlyphCount && FirstCode + i <= LastExported; i++)
        {
            int offset = BitConverter.ToUInt16(fnt, 4 + i * 4), width = BitConverter.ToUInt16(fnt, 6 + i * 4);
            if (width <= 0 || offset + 32 > fnt.Length) continue;
            var alpha = new byte[width * height];
            for (int y = 0; y < height && y < 16; y++)
            {
                int bits = fnt[offset + y * 2 + 1] << 8 | fnt[offset + y * 2]; // left byte second, most significant bit leftmost
                for (int x = 0; x < width && x < 16; x++)
                    if ((bits & (0x8000 >> x)) != 0) alpha[y * width + x] = 255;
            }
            using (var s = zip.CreateEntry($"fonts/{folder}/{FirstCode + i:x4}.png", CompressionLevel.Fastest).Open()) WritePng(s, width, height, alpha);
            written++;
        }
        using (var w = new StreamWriter(zip.CreateEntry($"fonts/{folder}/font.inf", CompressionLevel.Fastest).Open()))
            w.Write($"Kerning 1\nSpaceWidth {fixedWidth - 1}\nFontHeight {height}\n");
        return written;
    }

    // White RGBA with the given alpha.
    static void WritePng(Stream output, int w, int h, byte[] alpha)
    {
        var raw = new byte[(w * 4 + 1) * h];
        for (int y = 0, at = 0; y < h; y++)
        {
            raw[at++] = 0;
            for (int x = 0; x < w; x++) { raw[at++] = 255; raw[at++] = 255; raw[at++] = 255; raw[at++] = alpha[y * w + x]; }
        }
        var packed = new MemoryStream();
        using (var z = new ZLibStream(packed, CompressionLevel.Optimal, true)) z.Write(raw, 0, raw.Length);
        output.Write(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A });
        Chunk(output, "IHDR", new byte[] { (byte)(w >> 24), (byte)(w >> 16), (byte)(w >> 8), (byte)w, (byte)(h >> 24), (byte)(h >> 16), (byte)(h >> 8), (byte)h, 8, 6, 0, 0, 0 });
        Chunk(output, "IDAT", packed.ToArray());
        Chunk(output, "IEND", new byte[0]);
    }

    static void Chunk(Stream output, string kind, byte[] data)
    {
        byte[] name = Encoding.ASCII.GetBytes(kind);
        Big(output, (uint)data.Length);
        output.Write(name, 0, 4);
        output.Write(data, 0, data.Length);
        uint crc = 0xFFFFFFFF;
        foreach (byte[] part in new[] { name, data })
            foreach (byte b in part)
            {
                crc ^= b;
                for (int k = 0; k < 8; k++) crc = (crc & 1) != 0 ? 0xEDB88320 ^ (crc >> 1) : crc >> 1;
            }
        Big(output, ~crc);
    }

    static void Big(Stream output, uint v) { output.Write(new[] { (byte)(v >> 24), (byte)(v >> 16), (byte)(v >> 8), (byte)v }, 0, 4); }
}
