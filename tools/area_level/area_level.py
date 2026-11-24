"""Proposed area level (1 to 30) for every Daggerfall location.

Approved formula (work/notes/20261123-225515-area-level-proposal.md). The game computes the same
levels in daggerfall-unity-master/Assets/Scripts/Doomerfall/DoomerfallAreaLevels.cs. Change both
together, then run compare_runtime.py (via runtime_check.py dump) to prove they still match.

    python tools/area_level/area_level.py [--arena2 DIR] [--csv OUT.csv] [--png OUT.png]

The CSV and PNG are derived from game data. Write them outside the repo.

Formula, per location:

    raw = REGION_W * region_lean          (hand table, -2..+2)
        + GEO_W    * geo_field(x, y)      (smooth fixed-seed noise over the map)
        + TYPE_W   * type_lean            (hand table per dungeon type, -2..+2)
        + NOISE_W  * location_noise(id)   (fixed-seed noise per location)

    level = 1 + floor(30 * rank(raw) / count), ranked within the location's class.

Dungeons are ranked within their size class (labyrinth, keep, ruin, graveyard), so
every size class, and therefore all dungeons together, has each level 1 to 30
equally often. Places without a dungeon (towns, homes, temples, taverns) and the
open wilderness take the "terrain level": region lean plus geo field only, ranked
over every land map pixel, so the wilderness and the towns in it agree.

Every random value comes from a 32-bit integer hash of fixed seeds and the
location's MapId or map pixel, so a place has the same level in every game and
the hash ports to C# exactly.
"""
import argparse
import collections
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dfdata  # noqa: E402

DEFAULT_ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"

# ---- Tunables -------------------------------------------------------------

REGION_W = 0.85
GEO_W = 0.9
TYPE_W = 0.8
NOISE_W = 1.0
# Exceptions: a few places ignore their surroundings, so a starting region still
# has the odd level 30 lair and a mountain range the odd easy cave.
EXCEPTION_CHANCE = 0.07
EXCEPTION_MIN = 2.5   # added or subtracted, in the same units as the leans
EXCEPTION_MAX = 5.0

SEED_GEO_A = 0xA17E0001
SEED_GEO_B = 0xA17E0002
SEED_LOC = 0xA17E0003
GEO_CELL_A = 48   # map pixels per lattice cell, broad clusters
GEO_CELL_B = 16   # finer clusters

# Region lean: -2 gentlest .. +2 hardest. Early game is the western High Rock
# around Daggerfall city, where the game starts. The main quest then pulls the
# player to Sentinel, Wayrest, and Orsinium. Mountains, the desert, and the
# remote isles lean hardest.
REGION_LEAN = {
    # -2: starting area
    "Daggerfall": -2, "Glenpoint": -2, "Tulune": -2, "Glenumbra Moors": -2,
    "Betony": -2, "Northmoor": -2,
    # -1: one step out
    "Ilessan Hills": -1, "Shalgora": -1, "Anticlere": -1, "Ykalon": -1,
    "Daenia": -1, "Abibon-Gora": -1, "Kairou": -1, "Myrkwasa": -1, "Pothago": -1,
    # 0: the middle of the Bay
    "Sentinel": 0, "Urvaius": 0, "Phrygias": 0, "Bhoriane": 0, "Kambria": 0,
    "Dwynnen": 0, "Ayasofya": 0, "Tigonus": 0, "Antiphyllos": 0, "Bergama": 0,
    "Cybiades": 0,
    # +1: the far east and south
    "Wayrest": 1, "Lainlyn": 1, "Koegria": 1, "Alcaire": 1, "Menevia": 1,
    "Kozanset": 1, "Satakalaam": 1, "Totambu": 1, "Mournoth": 1, "Santaki": 1,
    "Gavaudon": 1, "Dak'fron": 1, "Ephesus": 1,
    # +2: wild and remote
    "Alik'r Desert": 2, "Dragontail Mountains": 2, "Wrothgarian Mountains": 2,
    "Orsinium Area": 2, "Isle of Balfiera": 2, "High Rock sea coast": 2,
}

# Dungeon type lean: -2 easier .. +2 harder. A lean only, so every type still
# spans the whole range.
TYPE_LEAN = {
    # Graveyards are ranked in their own class and are all cemeteries, so a
    # cemetery lean would have no effect.
    "Cemetery": 0, "NaturalCave": -1.5, "Mine": -1.5, "HarpyNest": -1,
    "SpiderNest": -1, "ScorpionNest": -0.5, "Crypt": -0.5, "Prison": -0.5,
    "HumanStronghold": 0, "BarbarianStronghold": 0, "OrcStronghold": 0,
    "RuinedCastle": 0, "DesecratedTemple": 0.5, "Laboratory": 1, "Coven": 1,
    "GiantStronghold": 1, "VampireHaunt": 1.5, "VolcanicCaves": 1.5,
    "DragonsDen": 2,
}

# Fixed levels for story places, applied after ranking. Privateer's Hold is where
# every new character wakes up with nothing.
OVERRIDES = {187853213: 1}  # Daggerfall/Privateer's Hold

MAX_LEVEL = 30

# ---- Fixed-seed hashing (ports to C# with uint arithmetic) -----------------

M32 = 0xFFFFFFFF


def hash32(x):
    """lowbias32 by Chris Wellons."""
    x &= M32
    x ^= x >> 16
    x = (x * 0x7FEB352D) & M32
    x ^= x >> 15
    x = (x * 0x846CA68B) & M32
    x ^= x >> 16
    return x


def unit(*keys):
    """Uniform [0, 1) from a sequence of 32-bit keys."""
    h = 0
    for k in keys:
        h = hash32(h ^ (k & M32))
    return h / 4294967296.0


def lattice(ix, iy, seed):
    return unit(seed, ix, iy) * 2.0 - 1.0


def value_noise(x, y, cell, seed):
    fx, fy = x / cell, y / cell
    ix, iy = math.floor(fx), math.floor(fy)
    tx, ty = fx - ix, fy - iy
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = lattice(ix, iy, seed)
    b = lattice(ix + 1, iy, seed)
    c = lattice(ix, iy + 1, seed)
    d = lattice(ix + 1, iy + 1, seed)
    return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty


def geo_field(x, y):
    # Roughly unit spread: value noise in [-1, 1] has std about 0.4 per octave.
    return (value_noise(x, y, GEO_CELL_A, SEED_GEO_A)
            + 0.5 * value_noise(x, y, GEO_CELL_B, SEED_GEO_B)) * 2.0


def location_noise(map_id):
    # Sum of three uniforms: bell shaped, std about 1.
    n = (unit(SEED_LOC, map_id, 1) + unit(SEED_LOC, map_id, 2)
         + unit(SEED_LOC, map_id, 3) - 1.5) * 2.0
    if unit(SEED_LOC, map_id, 4) < EXCEPTION_CHANCE:
        kick = EXCEPTION_MIN + (EXCEPTION_MAX - EXCEPTION_MIN) * unit(SEED_LOC, map_id, 5)
        n += kick if unit(SEED_LOC, map_id, 6) < 0.5 else -kick
    return n


# ---- Level assignment --------------------------------------------------------

def dungeon_class(loc):
    lt = loc["ltype_name"]
    if lt == "Graveyard":
        return "graveyard"
    if lt == "DungeonRuin":
        return "ruin"
    if lt == "DungeonKeep":
        return "keep"
    return "labyrinth"  # DungeonLabyrinth and the three cities with dungeons


def terrain_raw(region_name, x, y):
    return REGION_W * REGION_LEAN.get(region_name, 0) + GEO_W * geo_field(x, y)


def rank_levels(items, key):
    """items: list of (raw, tiebreak, obj). Assigns obj[key] by rank."""
    items.sort(key=lambda t: (t[0], t[1]))
    n = len(items)
    for i, (_, _, obj) in enumerate(items):
        obj[key] = 1 + (i * MAX_LEVEL) // n


def assign(locs, region_at):
    # Terrain level over every land pixel.
    pixels = []
    for y in range(500):
        for x in range(1000):
            r = region_at(x, y)
            if r >= 0:
                pixels.append((terrain_raw(dfdata.REGION_NAMES[r], x, y),
                               y * 1000 + x, {"x": x, "y": y}))
    rank_levels(pixels, "level")
    terrain = {p["y"] * 1000 + p["x"]: p["level"] for _, _, p in pixels}

    classes = collections.defaultdict(list)
    for loc in locs:
        t = terrain_raw(loc["region_name"], loc["x"], loc["y"])
        loc["terrain_level"] = terrain.get(loc["y"] * 1000 + loc["x"], 1)
        if loc["dtype_name"] is None:
            loc["class"] = "no dungeon"
            loc["level"] = loc["terrain_level"]
            continue
        loc["class"] = dungeon_class(loc)
        raw = (t + TYPE_W * TYPE_LEAN[loc["dtype_name"]]
               + NOISE_W * location_noise(loc["map_id"]))
        classes[loc["class"]].append((raw, loc["map_id"] & M32, loc))
    for items in classes.values():
        rank_levels(items, "level")
    for loc in locs:
        if loc["map_id"] in OVERRIDES:
            loc["level"] = OVERRIDES[loc["map_id"]]
    return terrain


# ---- Reporting ---------------------------------------------------------------

def quartiles(v):
    v = sorted(v)
    n = len(v)
    return v[n // 4], v[n // 2], v[(3 * n) // 4]


def histogram(levels, title):
    c = collections.Counter(levels)
    n = len(levels)
    print(f"\n{title} (n={n})")
    peak = max(c.values())
    for lv in range(1, MAX_LEVEL + 1):
        bar = "#" * round(40 * c[lv] / peak)
        print(f"  {lv:2d} {c[lv]:5d} {bar}")


def report(locs):
    dun = [l for l in locs if l["dtype_name"]]
    histogram([l["level"] for l in dun], "Dungeon levels, all classes")
    for cls in ("labyrinth", "keep", "ruin", "graveyard"):
        lv = [l["level"] for l in dun if l["class"] == cls]
        c = collections.Counter(lv)
        print(f"  {cls:10s} n={len(lv):4d}  per level min {min(c.values())} max {max(c.values())}")

    print("\nDungeons by region lean (q1 / median / q3, share at 1-5, share at 26-30)")
    by = collections.defaultdict(list)
    for l in dun:
        by[REGION_LEAN.get(l["region_name"], 0)].append(l["level"])
    for k in sorted(by):
        v = by[k]
        lo = sum(1 for x in v if x <= 5) / len(v)
        hi = sum(1 for x in v if x >= 26) / len(v)
        print(f"  lean {k:+d}: n={len(v):4d}  {quartiles(v)}  1-5 {lo:5.1%}  26-30 {hi:5.1%}")

    print("\nDungeons by region (lean, n, q1/median/q3, min-max)")
    byr = collections.defaultdict(list)
    for l in dun:
        byr[l["region_name"]].append(l["level"])
    for r in sorted(byr, key=lambda r: (REGION_LEAN.get(r, 0), sorted(byr[r])[len(byr[r]) // 2])):
        v = byr[r]
        print(f"  {r:26s} {REGION_LEAN.get(r, 0):+d} {len(v):4d}  {quartiles(v)}  {min(v)}-{max(v)}")

    print("\nDungeons by type (lean, n, q1/median/q3, min-max)")
    byt = collections.defaultdict(list)
    for l in dun:
        byt[l["dtype_name"]].append(l["level"])
    for t in sorted(byt, key=lambda t: TYPE_LEAN[t]):
        v = byt[t]
        print(f"  {t:20s} {TYPE_LEAN[t]:+.1f} {len(v):4d}  {quartiles(v)}  {min(v)}-{max(v)}")

    print("\nType effect with region removed: mean level minus the mean of its region")
    rmean = {r: sum(v) / len(v) for r, v in byr.items()}
    for t in sorted(byt, key=lambda t: TYPE_LEAN[t]):
        d = [l["level"] - rmean[l["region_name"]] for l in dun if l["dtype_name"] == t]
        print(f"  {t:20s} {TYPE_LEAN[t]:+.1f}  {sum(d) / len(d):+5.1f}")

    print("\nThemed variety: dungeon types present at each level band")
    for lo in range(1, 31, 5):
        types = {l["dtype_name"] for l in dun if lo <= l["level"] < lo + 5}
        print(f"  {lo:2d}-{lo + 4:2d}: {len(types)} of 19 types")

    # Clustering: nearest other dungeon vs random pairs.
    rng = random.Random(1)
    cells = collections.defaultdict(list)
    for l in dun:
        cells[(l["x"] // 10, l["y"] // 10)].append(l)
    near, dists = [], []
    for l in dun:
        best, bd = None, 1e9
        cx, cy = l["x"] // 10, l["y"] // 10
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for o in cells[(cx + dx, cy + dy)]:
                    if o is l:
                        continue
                    d = (o["x"] - l["x"]) ** 2 + (o["y"] - l["y"]) ** 2
                    if d < bd:
                        best, bd = o, d
        if best:
            near.append(abs(best["level"] - l["level"]))
            dists.append(math.sqrt(bd))
    rnd = [abs(rng.choice(dun)["level"] - rng.choice(dun)["level"]) for _ in range(20000)]
    print("\nGeographic clustering (mean |level difference|)")
    print(f"  nearest other dungeon (median {sorted(dists)[len(dists) // 2]:.0f} map pixels away): "
          f"{sum(near) / len(near):.1f} over {len(near)} dungeons")
    print(f"  random pair of dungeons: {sum(rnd) / len(rnd):.1f}")

    names = ["Privateer's Hold", "Daggerfall", "Wayrest", "Sentinel", "Orsinium",
             "Direnni Tower", "Shedungent", "Scourg Barrow", "Lysandus' Tomb",
             "Castle Necromoghan", "Tristore Laboratory", "Castle Llugwych",
             "Woodborne Hall", "Mantellan Crux", "Gothway Garden"]
    print("\nNamed examples (dungeon level / terrain level)")
    for nm in names:
        for l in locs:
            if l["name"] == nm:
                print(f"  {nm:22s} {l['region_name']:22s} {l['ltype_name']:16s} "
                      f"{str(l['dtype_name']):18s} level {l['level']:2d}  terrain {l['terrain_level']:2d}")

    print("\nRandom sample of dungeons in Daggerfall region")
    dr = sorted((l for l in dun if l["region_name"] == "Daggerfall"), key=lambda l: l["map_id"])
    for l in random.Random(7).sample(dr, 12):
        print(f"  {l['name']:28s} {l['class']:9s} {l['dtype_name']:18s} level {l['level']:2d}")

    print("\nDragon's dens, lowest five and highest five")
    dd = sorted((l for l in dun if l["dtype_name"] == "DragonsDen"), key=lambda l: l["level"])
    for l in dd[:5] + dd[-5:]:
        print(f"  {l['name']:28s} {l['region_name']:22s} level {l['level']:2d}")


def write_png(path, locs, terrain, region_at):
    try:
        from PIL import Image
    except ImportError:
        print("PIL not installed, skipping PNG")
        return
    img = Image.new("RGB", (1000, 500), (20, 30, 60))
    px = img.load()

    def color(lv):
        t = (lv - 1) / 29
        return (int(40 + 215 * t), int(200 - 150 * t), int(60 + 20 * (1 - t)))

    for key, lv in terrain.items():
        c = color(lv)
        px[key % 1000, key // 1000] = tuple(v // 2 for v in c)
    for l in locs:
        if l["dtype_name"] and 0 <= l["x"] < 1000 and 0 <= l["y"] < 500:
            px[l["x"], l["y"]] = color(l["level"])
    img = img.resize((2000, 1000), Image.NEAREST)
    img.save(path)
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena2", default=DEFAULT_ARENA2)
    ap.add_argument("--csv")
    ap.add_argument("--png")
    a = ap.parse_args()
    locs = dfdata.read_locations(a.arena2)
    region_at = dfdata.read_politic(a.arena2)
    missing = {l["region_name"] for l in locs} - set(REGION_LEAN)
    if missing:
        print("regions without a lean (using 0):", sorted(missing))
    terrain = assign(locs, region_at)
    report(locs)
    if a.csv:
        with open(a.csv, "w", encoding="utf-8") as f:
            f.write("map_id,region,name,location_type,dungeon_type,class,level,terrain_level\n")
            for l in locs:
                f.write(f"{l['map_id']},\"{l['region_name']}\",\"{l['name']}\",{l['ltype_name']},"
                        f"{l['dtype_name'] or ''},{l['class']},{l['level']},{l['terrain_level']}\n")
        print(f"wrote {a.csv}")
    if a.png:
        write_png(a.png, locs, terrain, region_at)


if __name__ == "__main__":
    main()
