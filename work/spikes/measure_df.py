"""Throwaway: aggregate measurements of Daggerfall data. Prints numbers only."""
import struct, statistics as st, sys
A = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2\\"

def bsa(name):
    d = open(A + name, "rb").read()
    n, t = struct.unpack_from("<hH", d, 0)
    pos, out = 4, []
    if t == 0x0100:
        base = len(d) - 18 * n
        for i in range(n):
            e = base + 18 * i
            nm = d[e:e + 12].split(b"\0")[0].decode("latin1")
            sz = struct.unpack_from("<i", d, e + 14)[0]
            out.append((nm, pos, sz)); pos += sz
    else:
        base = len(d) - 8 * n
        for i in range(n):
            rid, sz = struct.unpack_from("<ii", d, base + 8 * i)
            out.append((rid, pos, sz)); pos += sz
    return d, out

def q(v):
    v = sorted(v)
    return dict(n=len(v), min=v[0], p50=v[len(v)//2], p95=v[int(len(v)*.95)], max=v[-1], mean=round(st.mean(v), 1))

# Elevation
w = open(A + "WOODS.WLD", "rb").read()
off = struct.unpack_from("<I", w, 28)[0]
hm = w[off:off + 500000]
print("woods dims", struct.unpack_from("<II", w, 4), "elev bytes", q(list(hm)))
land = [b for b in hm if b * 8 >= 3.4 * 8]
print("land pixels (base>=ocean)", len(land), "of 500000")
# base-only height in Doom/DF units: base*8 (scaled) *1.5 (TerrainScale) *40 (units/Unity)
U = 8 * 1.5 * 40
print("base unit per byte", U, "max base height units", max(hm) * U)
for lim in (32768, 65536):
    print("land pixels with base height >", lim, sum(b * U > lim for b in land))
dx = [abs(hm[y*1000+x] - hm[y*1000+x+1]) for y in range(500) for x in range(999)]
print("adjacent pixel byte delta", q(dx), "max slope units per 256-unit tile (base only)", round(max(dx) * U / 128, 1))

xs = [i % 1000 for i, b in enumerate(hm) if b >= 4]; ys = [i // 1000 for i, b in enumerate(hm) if b >= 4]
print("land bbox pixels x", min(xs), max(xs), "y", min(ys), max(ys))
print("share of adjacent pairs steeper than 45deg on base height alone (delta*480 > 8192/..):",
      round(sum(d * U > 32768 for d in dx) / len(dx) * 100, 4), "% exceed 1 unit/unit over a full pixel")
rel = []
for y in range(0, 499):
    for x in range(0, 999):
        c = (hm[y*1000+x], hm[y*1000+x+1], hm[(y+1)*1000+x], hm[(y+1)*1000+x+1])
        rel.append((max(c) - min(c)) * U)
print("2x2-pixel window base relief units", q(rel), "windows over 60000:", sum(r > 60000 for r in rel))

# Blocks
d, rec = bsa("BLOCKS.BSA")
rmb = [r for r in rec if r[0].upper().endswith(".RMB")]
rdb = [r for r in rec if r[0].upper().endswith(".RDB")]
print("blocks total", len(rec), "RMB", len(rmb), "RDB", len(rdb), "other", len(rec) - len(rmb) - len(rdb))
print("RMB bytes", q([r[2] for r in rmb if r[2] > 0]))
print("RMB building-record count (first header byte)", q([d[r[1]] for r in rmb if r[2] > 0]))

# Models
d, rec = bsa("ARCH3D.BSA")
pts, pls = [], []
for _, p, s in rec:
    if s >= 12:
        a, b = struct.unpack_from("<ii", d, p + 4)
        if 0 < a < 100000 and 0 < b < 100000:
            pts.append(a); pls.append(b)
print("ARCH3D records", len(rec), "parsed", len(pts), "points", q(pts), "planes", q(pls))

# Locations: 4 records per region; MapNames is the 4th, begins with int32 count
d, rec = bsa("MAPS.BSA")
total, used = 0, 0
for i in range(0, len(rec) - 3, 4):
    _, p, s = rec[i + 3]
    if s >= 4:
        c = struct.unpack_from("<i", d, p)[0]
        if 0 <= c < 20000:
            total += c; used += c > 0
print("MAPS records", len(rec), "regions with locations", used, "locations", total)

# Travel at Doom speeds
W, H = 32768000, 16384000
for name, u in (("walk~", float(sys.argv[1]) if len(sys.argv) > 1 else 0), ):
    if u:
        print("crossing hours at", u, "u/s: EW", round(W/u/3600, 2), "NS", round(H/u/3600, 2))
