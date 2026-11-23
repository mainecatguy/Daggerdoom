"""Measures every Daggerfall sprite in generated packages against Daggerfall Unity's billboard size.

Usage: python sprite_scale_check.py <arena2> <package.pk3> [more packages]
Expected world size is MeshReader.GetBillboardMesh's size in Daggerfall units times the 75% world scale.
It is read from TEXTURE.xxx headers, independently of the converter. Exits 1 if a sprite is off by more than 0.5%.
"""
import collections
import pathlib
import re
import struct
import sys
import zipfile

WORLD_SCALE, SCALE_DIVISOR, TOLERANCE = 0.75, 256, 0.005
headers = {}


def texture_header(arena2, archive, record):
    if archive not in headers:
        data = (pathlib.Path(arena2) / f"TEXTURE.{archive:03d}").read_bytes()
        rows = []
        for r in range(struct.unpack_from("<h", data, 0)[0]):
            at = struct.unpack_from("<i", data, 26 + r * 20 + 2)[0]
            w, h = struct.unpack_from("<hh", data, at + 4)
            sx, sy = struct.unpack_from("<hh", data, at + 24)
            rows.append((w, h, sx, sy))
        headers[archive] = rows
    return headers[archive][record]


def expected(arena2, archive, record):
    w, h, sx, sy = texture_header(arena2, archive, record)
    return (w + int(w * (sx / SCALE_DIVISOR))) * WORLD_SCALE, (h + int(h * (sy / SCALE_DIVISOR))) * WORLD_SCALE, w, h


def png_size(z, name):
    with z.open(name) as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def rows(z):
    """Yields (path, png name, archive, record, scale x, scale y)."""
    names = {n.lower(): n for n in z.namelist()}
    stems = {n.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower(): n for n in z.namelist() if n.lower().endswith(".png")}
    def row(path, texture, sx, sy):
        m = re.search(r"a(\d{3})r(\d{2})|F(\d{3})R(\d{2})", texture)
        if not m: return None
        a, r = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        png = names.get(texture.lower()) or stems.get(texture.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower())
        return path, png, int(a), int(r), float(sx), float(sy)
    for lump, path in (("DFDFLATS", "dungeon flat"), ("DFFLATS", "town flat")):
        if lump in z.namelist():
            for line in z.read(lump).decode().splitlines():
                f = line.split()
                if len(f) >= 6: yield row(path, f[0], f[4], f[5])
    for name in z.namelist():
        if name.lower().endswith((".zs", ".zsc")) or name.lower() == "zscript":
            text = z.read(name).decode("utf-8", "replace")
            for m in re.finditer(r'class DFActionFlat\d+.*?CheckForTexture\("([^"]+)".*?scale = \(([\d.]+), ([\d.]+)\)', text):
                yield row("action flat", m.group(1), m.group(2), m.group(3))
    if "dfitems.txt" in z.namelist():
        for line in z.read("dfitems.txt").decode().splitlines():
            f = line.split("\t")
            texture, sx, sy = (f[10], f[8], f[9]) if len(f) >= 12 else (f[9], f[8], f[8])  # older packages had one scale column
            if texture != "DINOSPR":
                yield "item", f"graphics/dfitems/{texture}.png", int(f[4]), int(f[5]), float(sx), float(sy)


def main():
    arena2, failed = sys.argv[1], False
    for package in sys.argv[2:]:
        z = zipfile.ZipFile(package)
        stats = collections.defaultdict(lambda: [0, 0, 9.0, 0.0, 0])
        for item in rows(z):
            if item is None or item[1] is None: continue
            path, png, archive, record, sx, sy = item
            width, height = png_size(z, png)
            ex, ey, w, h = expected(arena2, archive, record)
            s = stats[path]
            s[0] += 1
            s[4] += (width, height) != (w, h)
            for ratio in (width * sx / ex, height * sy / ey):
                s[2], s[3] = min(s[2], ratio), max(s[3], ratio)
                if abs(ratio - 1) > TOLERANCE: s[1] += 1
        print(pathlib.Path(package).name)
        for path, (n, off, low, high, resized) in sorted(stats.items()):
            print(f"  {path}: {n} sprites, shown/expected {low:.4f} to {high:.4f}, off-size axes {off}, images differing from source {resized}")
            failed |= off > 0 or resized > 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
