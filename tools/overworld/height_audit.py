"""Compares the ground a town mesh draws with the overworld collision height at the same world tiles.

Usage: height_audit.py --cache DIR [--overworld PK3 ...] [--world-dir DIR] [--raw]
Each source is a set of height data the overworld could run with. The result is in Doom units.
Reads game data and prints only measurements.
"""
import argparse, glob, math, os, re, struct, zipfile, zlib

W, H, TILES = 1000, 500, 128
BASE, NOISE, EXTRA, MAX_H = 8.0, 4.0, 10.0, 1539.0
OCEAN = 3.4 * BASE
DOOM = 0.75
Z_BASE = 35240.0
WOODS = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2\WOODS.WLD"


def f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


F03, F09 = f32(0.3), f32(0.9)


def permutation():
    t = list(range(256))
    seed = 0x5DEECE6
    for i in range(255, 0, -1):
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        j = (seed >> 8) % (i + 1)
        t[i], t[j] = t[j], t[i]
    return t + t


PERM = permutation()


def perlin(x, y):
    fx, fy = math.floor(x), math.floor(y)
    xi, yi = int(fx) & 255, int(fy) & 255
    xf, yf = x - fx, y - fy
    u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
    v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
    grad = lambda h, dx, dy: (-dx if h & 1 else dx) + (-dy if h & 2 else dy)
    p = PERM
    n00, n10 = grad(p[p[xi] + yi], xf, yf), grad(p[p[xi + 1] + yi], xf - 1, yf)
    n01, n11 = grad(p[p[xi] + yi + 1], xf, yf - 1), grad(p[p[xi + 1] + yi + 1], xf - 1, yf - 1)
    a, b = n00 + u * (n10 - n00), n01 + u * (n11 - n01)
    return min(1.0, max(0.0, (a + v * (b - a)) * 0.5 + 0.5))


def cubic(v0, v1, v2, v3, t):
    a = (v3 - v2) - (v0 - v1)
    b = (v0 - v1) - a
    return a * t * t * t + b * t * t + (v2 - v0) * t + v1


class World:
    """The engine's SampleVertex for one DDWORLD and DDLOCS pair."""

    def __init__(self, ddworld, ddlocs=None):
        self.small = ddworld[8:8 + W * H]
        self.large = ddworld[8 + W * H:]
        self.rects, self.cache = {}, {}
        if ddlocs and ddlocs[:4] == b"DDL1":
            count = struct.unpack_from("<i", ddlocs, 4)[0]
            for i in range(count):
                x, y, x0, x1, y0, y1 = struct.unpack_from("<6h", ddlocs, 8 + i * 12)
                self.rects[(H - 1 - y) * W + x] = (x0, x1, y0, y1)

    def s(self, x, y):
        return self.small[min(max(y, 0), H - 1) * W + min(max(x, 0), W - 1)]

    def l(self, mx, my, a, b):
        px, py = min(max(mx - 1 + a // 3, 0), W - 1), min(max(my - b // 3, 0), H - 1)
        return self.large[(py * W + px) * 9 + (b % 3) * 3 + a % 3]

    def raw(self, px, north, x, y):
        my = H - 1 - north
        div = TILES / 3
        ix, iy = math.floor(x / div), math.floor(y / div)
        sx, sy = x / TILES, y / TILES
        fx, fy = (x - ix * div) / div, (y - iy * div) / div
        row = [cubic(*[self.s(px - 2 + c, my + 1 - r) for c in range(4)], sx) for r in range(4)]
        h = cubic(*row, sy) * BASE
        row = [cubic(*[self.l(px, my, ix + c, iy + r) for c in range(4)], fx) for r in range(4)]
        h += cubic(*row, fy) * NOISE
        nx, ny = px * TILES + x, (H - my) * TILES + y
        h += perlin(f32(nx * F03), f32(ny * F03)) * 0.5 * perlin(f32(nx * F09), f32(ny * F09)) * 0.5 * EXTRA
        return min(1.0, max(0.0, max(h, OCEAN) / MAX_H))

    def blended(self, px, north, rect):
        key = north * W + px
        if key in self.cache:
            return self.cache[key]
        dim = TILES + 1
        h = [[self.raw(px, north, x, y) for y in range(dim)] for x in range(dim)]
        target = sum(map(sum, h)) / (dim * dim)
        x0, x1, y0, y1 = (v / TILES for v in rect)
        left, right, top, bottom = 1 / x0, 1 / (1 - x1), 1 / y0, 1 / (1 - y1)
        for y in range(dim):
            v = y / (dim - 1)
            in_y = y0 <= v <= y1
            for x in range(dim):
                u = x / (dim - 1)
                in_x = x0 <= u <= x1
                if in_x and in_y:
                    h[x][y] = target
                    continue
                ex = u * left if u <= x0 else (1 - u) * right
                ey = v * top if v <= y0 else (1 - v) * bottom
                strength = ex if in_y else ey if in_x else ex * ey
                h[x][y] += (target - h[x][y]) * min(1.0, max(0.0, strength))
        self.cache[key] = h
        return h

    def doom_z(self, gx, gy):
        px, north = min(gx // TILES, W - 1), min(gy // TILES, H - 1)
        x, y = gx - px * TILES, gy - north * TILES
        rect = self.rects.get(north * W + px)
        h = self.blended(px, north, rect)[x][y] if rect else self.raw(px, north, x, y)
        return h * MAX_H * 60 * DOOM - Z_BASE


def read_ddt(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"DDT2":
        raise ValueError("not a town cache file")
    count = struct.unpack_from("<i", data, 4)[0]
    pos, heads = 8, []
    for _ in range(count):
        heads.append((data[pos:pos + 8].rstrip(b"\0").decode(), *struct.unpack_from("<II", data, pos + 8)))
        pos += 16
    lumps = {}
    for name, raw, packed in heads:
        lumps[name] = zlib.decompress(data[pos:pos + packed]) if raw else b""
        pos += packed
    return lumps


def ground_vertices(lumps):
    """World tile and Doom height of every terrain vertex the town mesh draws."""
    town = {}
    for line in lumps["DDTOWN"].decode().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("origin", "ground"):
            town.setdefault(parts[0], [float(v) for v in parts[1:]])
    ox, oy = town["origin"][:2]
    ground = town["ground"][0] * DOOM - Z_BASE
    mesh = lumps["DFMESH"]
    textures, batches, vertices = struct.unpack_from("<iii", mesh, 12)
    table = 24 + textures * 32
    source = table + batches * 12
    out = {}
    for b in range(batches):
        name_index, first, n = struct.unpack_from("<iii", mesh, table + b * 12)
        name = mesh[24 + name_index * 32:24 + (name_index + 1) * 32].split(b"\0")[0].decode(errors="replace").lower()
        match = re.search(r"a(\d{3})r", name)  # Ground archives are 002, 102, 302, and 402.
        if not match or int(match.group(1)) % 100 != 2:
            continue
        for i in range(first, first + n):
            x, z, y, tu, tv, nx, ny, nz = struct.unpack_from("<8f", mesh, source + i * 32)
            if (nx, ny, nz) != (0.0, 1.0, 0.0) or tu not in (0.0, 1.0) or tv not in (0.0, 1.0):
                continue
            tx, ty = (x / DOOM + ox) / 256, (y / DOOM + oy) / 256
            if abs(tx - round(tx)) > 1e-3 or abs(ty - round(ty)) > 1e-3:
                continue
            out[(round(tx), round(ty))] = z + ground
    return out


def audit(label, world, towns):
    errors, worst, where, sunk, sunk_at = [], 0.0, None, 0.0, None
    for name, verts in towns.items():
        for (gx, gy), z in verts.items():
            e = world.doom_z(gx, gy) - z  # Negative: the player's floor is under the drawn ground.
            errors.append(abs(e))
            if abs(e) > worst:
                worst, where = abs(e), (name, gx, gy, round(e, 2))
            if -e > sunk:
                sunk, sunk_at = -e, (name, gx, gy)
    errors.sort()
    n = len(errors)
    print(f"{label}: vertices={n} mean={sum(errors) / n:.3f} p95={errors[int(n * .95)]:.3f} max={worst:.3f} at {where} deepestUnderDrawnGround={sunk:.3f} at {sunk_at} over4={sum(e > 4 for e in errors)} over16={sum(e > 16 for e in errors)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--overworld", action="append", default=[])
    ap.add_argument("--world-dir")
    ap.add_argument("--raw", action="store_true", help="also audit unsmoothed WOODS.WLD heights with no location flattening")
    args = ap.parse_args()
    towns = {os.path.basename(p): ground_vertices(read_ddt(p)) for p in sorted(glob.glob(os.path.join(args.cache, "*.ddt")))}
    print("towns:", {k: len(v) for k, v in towns.items()})
    if args.raw:
        from gen_overworld import world_lump
        audit("raw WOODS", World(world_lump(open(WOODS, "rb").read())), towns)
    for pk3 in args.overworld:
        z = zipfile.ZipFile(pk3)
        audit(os.path.basename(os.path.dirname(pk3)) + "/" + os.path.basename(pk3), World(z.read("DDWORLD"), z.read("DDLOCS") if "DDLOCS" in z.namelist() else None), towns)
    if args.world_dir:
        audit("world-dir", World(open(os.path.join(args.world_dir, "DDWORLD"), "rb").read(), open(os.path.join(args.world_dir, "DDLOCS"), "rb").read()), towns)


if __name__ == "__main__":
    main()
