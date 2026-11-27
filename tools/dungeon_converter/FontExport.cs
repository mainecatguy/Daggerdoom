// Daggerfall's fonts as UZDoom folder fonts (fonts/<folder>/<hex code>.png plus font.inf), so Doom can draw text the way
// Daggerfall Unity draws it (Daggerfall's HUD messages in mods/doomerfall/src/zscript/Doomerfall.zs).
//
// Write: the classic pixel font from the player's ARENA2 (FONT0003.FNT -> fonts/dffont3), read as Daggerfall Unity reads
// it (API/FntFile.cs, DaggerfallFont.cs): 240 glyphs from ASCII 33, 16x16 bit rows, proportional widths, a space
// FixedWidth - 1 wide, and one pixel between glyphs. Game data: generated at install, never committed.
//
// WriteSdf: the smooth font Daggerfall Unity draws by default (SDFFontRendering=True), from its TextMeshPro asset
// (Assets/Resources/Fonts/FONT000N-SDF.asset, Kingthings Petrock for FONT0003), rasterized at SdfTexelsPerPixel texels
// per Daggerfall native pixel. Same glyph boxes, advances and baseline as DaggerfallFont.DrawSDFGlyph and
// TextLabel.DrawLabelSingleCallSDF, and the same edge as the Daggerfall/SDFFont shader (smoothstep around 0.5).
// UZDoom advances a folder font by each glyph's whole texture width plus one global kerning, so every glyph texture is
// its rounded advance plus a shared margin K wide, drawn at a shared left offset, with Kerning -K: the net advance is
// exactly the advance, and ink that overhangs the advance box is kept. Glyphs are white for Doom to tint.
// FontHeight is the classic glyph height times SdfTexelsPerPixel, so a script can find the texel scale as
// GetHeight() / classic height. Reusable for any FONT000N (the menu font card).

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;

static class FontExport
{
    const int GlyphCount = 240, FirstCode = 33, LastExported = 126; // Above '~' Daggerfall's codes are not Unicode.
    public const int SdfTexelsPerPixel = 8;

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

    // Classic glyph height of a Daggerfall font (the SDF glyphs are scaled to it), from the FNT header.
    public static int ClassicHeight(string arena2, string name)
    {
        string path = Path.Combine(arena2, name);
        return File.Exists(path) ? BitConverter.ToUInt16(File.ReadAllBytes(path), 2) : 0;
    }

    // Daggerfall Unity's SDF font assets: the --dfu-fonts folder, or Assets/Resources/Fonts of the daggerfall-unity-master
    // found above the working folder or the converter.
    public static string FindSdfFolder(string[] args)
    {
        int at = Array.IndexOf(args, "--dfu-fonts");
        if (at >= 0 && at + 1 < args.Length) return args[at + 1];
        foreach (string start in new[] { Directory.GetCurrentDirectory(), AppContext.BaseDirectory })
            for (var dir = new DirectoryInfo(start); dir != null; dir = dir.Parent)
            {
                string fonts = Path.Combine(dir.FullName, "daggerfall-unity-master", "Assets", "Resources", "Fonts");
                if (Directory.Exists(fonts)) return fonts;
            }
        return null;
    }

    struct SdfGlyph { public double W, H, Bx, By, Adv; public int Rx, Ry, Rw, Rh; }

    public static int WriteSdf(ZipArchive zip, string asset, int classicHeight, string folder)
    {
        if (asset == null || !File.Exists(asset) || classicHeight <= 0)
        {
            Console.Error.WriteLine("font: SDF asset " + (asset ?? "(none)") + " or classic height missing; Doom uses the classic font");
            return 0;
        }
        double pointSize = 0;
        var glyphs = new Dictionary<int, SdfGlyph>();
        var chars = new SortedDictionary<int, int>();
        int atlasW = 0, atlasH = 0;
        byte[] atlas = null;
        string section = "";
        int index = -1, unicode = -1;
        bool inRect = false;
        var g = new SdfGlyph();
        double F(string line) => double.Parse(line.Substring(line.IndexOf(':') + 1), CultureInfo.InvariantCulture);
        foreach (string raw in File.ReadLines(asset))
        {
            string line = raw.TrimStart();
            if (raw.StartsWith("--- !u!28")) { section = "texture"; continue; }
            if (raw.StartsWith("  m_GlyphTable:")) { section = "glyphs"; continue; }
            if (raw.StartsWith("  m_CharacterTable:")) { if (index >= 0) glyphs[index] = g; section = "chars"; continue; }
            if (raw.StartsWith("  m_") && (section == "glyphs" || section == "chars")) { if (section == "glyphs" && index >= 0) glyphs[index] = g; section = ""; } // the table ended
            if (pointSize == 0 && line.StartsWith("m_PointSize:")) pointSize = F(line);
            if (section == "glyphs")
            {
                if (line.StartsWith("- m_Index:")) { if (index >= 0) glyphs[index] = g; index = (int)F(line); g = new SdfGlyph(); inRect = false; }
                else if (line.StartsWith("m_GlyphRect:")) inRect = true;
                else if (line.StartsWith("m_Width:")) { if (inRect) g.Rw = (int)F(line); else g.W = F(line); }
                else if (line.StartsWith("m_Height:")) { if (inRect) g.Rh = (int)F(line); else g.H = F(line); }
                else if (line.StartsWith("m_X:")) g.Rx = (int)F(line);
                else if (line.StartsWith("m_Y:")) g.Ry = (int)F(line);
                else if (line.StartsWith("m_HorizontalBearingX:")) g.Bx = F(line);
                else if (line.StartsWith("m_HorizontalBearingY:")) g.By = F(line);
                else if (line.StartsWith("m_HorizontalAdvance:")) g.Adv = F(line);
            }
            else if (section == "chars")
            {
                if (line.StartsWith("m_Unicode:")) unicode = (int)F(line);
                else if (line.StartsWith("m_GlyphIndex:") && unicode >= 0) { chars[unicode] = (int)F(line); unicode = -1; }
            }
            else if (section == "texture")
            {
                if (raw.StartsWith("  m_Width:")) atlasW = (int)F(line);
                else if (raw.StartsWith("  m_Height:")) atlasH = (int)F(line);
                else if (line.StartsWith("_typelessdata:")) atlas = Convert.FromHexString(line.Substring(14).Trim());
            }
        }
        if (pointSize <= 0 || atlas == null || atlas.Length < atlasW * atlasH || !chars.ContainsKey(32))
        {
            Console.Error.WriteLine("font: could not read " + asset + "; Doom uses the classic font");
            return 0;
        }

        // Hi-res texels per font unit, and the row's baseline in texels below the row top: DrawSDFGlyph puts it at
        // position.y - 2 + GlyphHeight native pixels (plus faceInfo.baseline, which is 0 in these assets).
        double s = (double)classicHeight / pointSize * SdfTexelsPerPixel, baseline = (classicHeight - 2) * SdfTexelsPerPixel;
        var shown = chars.Where(c => c.Key > 32 && c.Key < 0xFFFF && glyphs.ContainsKey(c.Value) && glyphs[c.Value].W > 0 && glyphs[c.Value].Rw > 0)
                         .ToDictionary(c => c.Key, c => glyphs[c.Value]);
        int Adv(SdfGlyph q) => (int)Math.Round(q.Adv * s);
        int left = 1 + (int)Math.Ceiling(Math.Max(0, -shown.Values.Min(q => q.Bx * s)));
        int margin = left + 1 + (int)Math.Ceiling(Math.Max(0, shown.Values.Max(q => (q.Bx + q.W) * s - Adv(q))));
        int yMin = (int)Math.Floor(shown.Values.Min(q => baseline - q.By * s)) - 1;
        int yMax = (int)Math.Ceiling(shown.Values.Max(q => baseline - q.By * s + q.H * s)) + 1;
        int ch = yMax - yMin;
        foreach (var (code, q) in shown)
        {
            int cw = Adv(q) + margin;
            double gx = q.Bx * s, gy = baseline - q.By * s, gw = q.W * s, gh = q.H * s;
            var dist = new float[cw * ch];
            for (int py = 0; py < ch; py++)
                for (int px = 0; px < cw; px++)
                {
                    double u = (px - left + 0.5 - gx) / gw, v = (py + yMin + 0.5 - gy) / gh;
                    if (u < 0 || u > 1 || v < 0 || v > 1) continue; // outside the glyph quad Daggerfall Unity draws
                    // Atlas rows run bottom-up; the quad's top samples the rect's top (TextLabel: v0 = yMax).
                    dist[py * cw + px] = Sample(atlas, atlasW, atlasH, q.Rx + u * q.Rw - 0.5, q.Ry + q.Rh - v * q.Rh - 0.5);
                }
            var alpha = new byte[cw * ch];
            for (int py = 0; py < ch; py++)
                for (int px = 0; px < cw; px++)
                {
                    float d = dist[py * cw + px];
                    float dx = Math.Abs(dist[py * cw + Math.Min(px + 1, cw - 1)] - dist[py * cw + Math.Max(px - 1, 0)]) / 2;
                    float dy = Math.Abs(dist[Math.Min(py + 1, ch - 1) * cw + px] - dist[Math.Max(py - 1, 0) * cw + px]) / 2;
                    float fw = Math.Max(dx + dy, 1e-4f); // the shader's fwidth, per texel
                    float t = Math.Clamp((d - (0.5f - fw)) / (2 * fw), 0, 1);
                    alpha[py * cw + px] = (byte)Math.Round(t * t * (3 - 2 * t) * 255);
                }
            using (var st = zip.CreateEntry($"fonts/{folder}/{code:x4}.png", CompressionLevel.Fastest).Open()) WritePng(st, cw, ch, alpha, left, -yMin);
        }
        int space = Adv(glyphs[chars[32]]);
        using (var w = new StreamWriter(zip.CreateEntry($"fonts/{folder}/font.inf", CompressionLevel.Fastest).Open()))
            w.Write($"Kerning {-margin}\nSpaceWidth {space + margin}\nFontHeight {classicHeight * SdfTexelsPerPixel}\n");
        return shown.Count;
    }

    static float Sample(byte[] a, int w, int h, double x, double y)
    {
        int x0 = (int)Math.Floor(x), y0 = (int)Math.Floor(y);
        double fx = x - x0, fy = y - y0;
        float P(int px, int py) => a[Math.Clamp(py, 0, h - 1) * w + Math.Clamp(px, 0, w - 1)] / 255f;
        return (float)((P(x0, y0) * (1 - fx) + P(x0 + 1, y0) * fx) * (1 - fy) + (P(x0, y0 + 1) * (1 - fx) + P(x0 + 1, y0 + 1) * fx) * fy);
    }

    // White RGBA with the given alpha, and a grAb offset chunk when the glyph is drawn shifted.
    static void WritePng(Stream output, int w, int h, byte[] alpha, int leftOffset = 0, int topOffset = 0)
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
        if (leftOffset != 0 || topOffset != 0)
            Chunk(output, "grAb", new[] { (byte)(leftOffset >> 24), (byte)(leftOffset >> 16), (byte)(leftOffset >> 8), (byte)leftOffset,
                                          (byte)(topOffset >> 24), (byte)(topOffset >> 16), (byte)(topOffset >> 8), (byte)topOffset });
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
