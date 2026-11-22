"""Treadmill kill test generator. Writes heights.bin, treadmill.pk3, and route.json to --out.

Ports DefaultTerrainSampler outside Unity. Mathf.PerlinNoise is native Unity code, so the
small "extra noise" term uses a classic Perlin surrogate with the same frequencies and scale.
Output is derived from game data and must stay outside the repository.
"""
import argparse, io, json, math, os, random, struct, zipfile

BASE_SCALE, NOISE_SCALE, EXTRA_SCALE = 8.0, 4.0, 10.0
OCEAN = 3.4 * BASE_SCALE
MAX_HEIGHT = 1539.0
DIM = 129
UNITY_TO_DF = 40.0  # 1 Daggerfall unit = 0.025 Unity units
W, H = 1000, 500

ap = argparse.ArgumentParser()
ap.add_argument("--woods", default=r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2\WOODS.WLD")
ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-loop\review\terrain-treadmill")
ap.add_argument("--pixels", type=int, default=10, help="map pixels of height data along the run")
ap.add_argument("--unit", type=float, default=1.0, help="Doom units per Daggerfall unit (open owner question)")
ap.add_argument("--vscale", type=float, default=1.5, help="Daggerfall Unity terrain scale (open owner question)")
ap.add_argument("--route", help="mx,my to override route search")
args = ap.parse_args()

woods = open(args.woods, "rb").read()
hm_off = struct.unpack_from("<I", woods, 28)[0]
hm = woods[hm_off:hm_off + W * H]
data_offsets = struct.unpack_from(f"<{W*H}I", woods, 144)


def small(x, y):
    return hm[min(max(y, 0), H - 1) * W + min(max(x, 0), W - 1)]


def large_5x5(x, y):
    x, y = min(max(x, 0), W - 1), min(max(y, 0), H - 1)
    o = data_offsets[y * W + x] + 22
    return [[woods[o + b * 5 + a] for b in range(5)] for a in range(5)]  # [x][y]


def large_range(mx, my):
    out = [[0] * 9 for _ in range(9)]  # [x][y]
    for y in range(3):
        for x in range(3):
            src = large_5x5(mx + x, my - y)
            for iy in range(1, 4):
                for ix in range(1, 4):
                    out[x * 3 + ix - 1][y * 3 + iy - 1] = src[ix][4 - iy]
    return out


def cubic(v0, v1, v2, v3, t):
    a = (v3 - v2) - (v0 - v1)
    b = (v0 - v1) - a
    return a * t * t * t + b * t * t + (v2 - v0) * t + v1


_perm = list(range(256))
random.Random(0).shuffle(_perm)
_perm += _perm


def perlin(x, y):
    """Surrogate for Mathf.PerlinNoise, returning roughly 0..1."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    xi &= 255
    yi &= 255
    u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
    v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)

    def grad(h, dx, dy):
        h &= 3
        return (dx if h & 1 == 0 else -dx) + (dy if h & 2 == 0 else -dy)

    p = _perm
    n00 = grad(p[p[xi] + yi], xf, yf)
    n10 = grad(p[p[xi + 1] + yi], xf - 1, yf)
    n01 = grad(p[p[xi] + yi + 1], xf, yf - 1)
    n11 = grad(p[p[xi + 1] + yi + 1], xf - 1, yf - 1)
    a = n00 + u * (n10 - n00)
    b = n01 + u * (n11 - n01)
    return max(0.0, min(1.0, (a + v * (b - a)) * 0.5 + 0.5))


def sample_pixel(mx, my):
    """Returns heights[x][y] in scaled sampler units, matching GenerateSamplesJob."""
    shm = [[small(mx - 2 + x, my - 2 + y) for y in range(4)] for x in range(4)]
    lhm = large_range(mx - 1, my)
    div = (DIM - 1) / 3.0
    out = [[0.0] * DIM for _ in range(DIM)]
    for x in range(DIM):
        rx = x / div
        ix = math.floor(rx)
        sx = x / (DIM - 1)
        fx = (x - ix * div) / div
        rows = [cubic(shm[0][r], shm[1][r], shm[2][r], shm[3][r], sx) for r in (3, 2, 1, 0)]
        lrows = [cubic(lhm[ix][iy], lhm[ix + 1][iy], lhm[ix + 2][iy], lhm[ix + 3][iy], fx) if ix + 3 < 9 else 0.0
                 for iy in range(9)]
        for y in range(DIM):
            ry = y / div
            iy = math.floor(ry)
            sy = y / (DIM - 1)
            fy = (y - iy * div) / div
            h = cubic(rows[0], rows[1], rows[2], rows[3], sy) * BASE_SCALE
            h += cubic(lrows[iy], lrows[iy + 1], lrows[iy + 2], lrows[iy + 3], fy) * NOISE_SCALE
            nx = mx * (DIM - 1) + x
            ny = (H - 1 - my) * (DIM - 1) + y
            h += perlin(nx * 0.3, ny * 0.3) * 0.5 * perlin(nx * 0.9, ny * 0.9) * 0.5 * EXTRA_SCALE
            out[x][y] = min(max(h, OCEAN), MAX_HEIGHT)
    return out


def find_route(n):
    best, best_score = None, -1
    for my in range(8, H - 8):
        for mx in range(8, W - n - 8, 2):
            cells = [small(mx + i, my + j) for j in (-2, -1, 0, 1) for i in range(-2, n + 2)]
            if min(cells) <= 4 or (max(cells) - min(cells)) * 8 * UNITY_TO_DF * args.vscale > 56000:
                continue
            line = [small(mx + i, my) for i in range(n)]
            score = sum(abs(line[i + 1] - line[i]) for i in range(n - 1))
            if score > best_score:
                best, best_score = (mx, my), score
    return best, best_score


def build_map(cells, spacing):
    half = cells * spacing // 2
    o = ['namespace="zdoom";']
    for j in range(cells + 1):
        for i in range(cells + 1):
            o.append(f"vertex{{x={-half + i * spacing};y={-half + j * spacing};}}")
    vid = lambda i, j: j * (cells + 1) + i
    edges, tris = {}, 0

    def tri(a, b, c):
        nonlocal tris
        for u, v in ((a, b), (b, c), (c, a)):
            if (v, u) in edges:
                edges[(v, u)][1] = tris
            else:
                edges[(u, v)] = [tris, -1]
        tris += 1

    for j in range(cells):
        for i in range(cells):
            a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
            tri(a, c, b)
            tri(a, d, c)
    o += ['sector{heightfloor=0;heightceiling=32000;texturefloor="RROCK19";textureceiling="F_SKY1";lightlevel=192;}'] * tris
    sides, lines = [], []
    for (u, v), (f, b) in edges.items():
        sf = len(sides)
        sides.append(f)
        if b >= 0:
            sb = len(sides)
            sides.append(b)
            ui, uj, vi, vj = u % (cells + 1), u // (cells + 1), v % (cells + 1), v // (cells + 1)
            zone = (ui == vi and ui % 32 == 0) or (uj == vj and uj % 32 == 0)
            lines.append(f"linedef{{v1={u};v2={v};sidefront={sf};sideback={sb};twosided=true;{'zoneboundary=true;' if zone else ''}}}")
        else:
            lines.append(f"linedef{{v1={u};v2={v};sidefront={sf};blocking=true;}}")
    o += lines
    o += [f'sidedef{{sector={s};texturemiddle="-";}}' for s in sides]
    o.append("thing{x=-3968;y=8;type=1;angle=0;coop=true;dm=true;single=true;skill1=true;skill2=true;skill3=true;skill4=true;skill5=true;}")
    textmap = "\n".join(o).encode()
    lumps = [("TREADM01", b""), ("TEXTMAP", textmap), ("ENDMAP", b"")]
    body, dirs, pos = io.BytesIO(), [], 12
    for n, d in lumps:
        body.write(d)
        dirs.append((pos, len(d), n))
        pos += len(d)
    out = io.BytesIO()
    out.write(b"PWAD" + struct.pack("<ii", len(lumps), pos) + body.getvalue())
    for p, s, n in dirs:
        out.write(struct.pack("<ii", p, s) + n.encode().ljust(8, b"\0"))
    return out.getvalue()


ZSCRIPT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "treadmill_harness.zs")).read()
MAPINFO = 'gameinfo { addeventhandlers = "TMHarness" playerclasses = "TMPlayer" }\nmap TREADM01 "Treadmill" { sky1 = "SKY1" }\n'

os.makedirs(args.out, exist_ok=True)
if args.route:
    mx, my = map(int, args.route.split(","))
    score = -1
else:
    (mx, my), score = find_route(args.pixels)

columns = []
for p in range(args.pixels):
    px = sample_pixel(mx + p, my)
    columns += px if p == args.pixels - 1 else px[:-1]
width = len(columns)
scale = args.vscale * UNITY_TO_DF * args.unit
world = [[v * scale for v in col] for col in columns]
zmin, zmax = min(map(min, world)), max(map(max, world))
zbase = round((zmin + zmax) / 2)
spacing = round(256 * args.unit)

steep, worst = 0, 0.0
for x in range(width - 1):
    for y in range(DIM - 1):
        g = math.hypot(world[x + 1][y] - world[x][y], world[x][y + 1] - world[x][y]) / spacing
        deg = math.degrees(math.atan(g))
        worst = max(worst, deg)
        steep += deg > 45

with open(os.path.join(args.out, "heights.bin"), "wb") as f:
    f.write(struct.pack("<4s7i", b"DDTM", 1, 128, spacing, width, DIM, mx * 128, (H - 1 - my) * 128))
    for y in range(DIM):
        f.write(struct.pack(f"<{width}f", *[world[x][y] - zbase for x in range(width)]))
with zipfile.ZipFile(os.path.join(args.out, "treadmill.pk3"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("maps/TREADM01.wad", build_map(128, spacing))
    z.writestr("zscript.txt", ZSCRIPT)
    z.writestr("mapinfo.txt", MAPINFO)

info = dict(mapPixel=[mx, my], pixels=args.pixels, routeScore=score, width=width, height=DIM, cells=128, sectors=32768,
            spacing=spacing, unit=args.unit, vscale=args.vscale, zMin=zmin, zMax=zmax, zBase=zbase,
            reliefUnits=zmax - zmin, steepestDegrees=round(worst, 2), cellsOver45Degrees=steep,
            baseBytes=[small(mx + i, my) for i in range(args.pixels)],
            perlin="surrogate, not Unity Mathf.PerlinNoise")
json.dump(info, open(os.path.join(args.out, "route.json"), "w"), indent=1)
print(json.dumps(info))
