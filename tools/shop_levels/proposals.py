"""Shop level proposals, Daedric shelf odds, restocks, town classes and houses.

usage: python proposals.py <data dir>   (same CSVs as analyze.py)
"""
import collections
import csv
import hashlib
import os
import sys

D = sys.argv[1]
SHOPS = {0, 2, 5, 6, 7, 8, 9, 12, 13}
NAMES = {0: "Alchemist", 2: "Armorer", 5: "Bookseller", 6: "ClothingStore", 7: "FurnitureStore", 8: "GemStore",
         9: "GeneralStore", 12: "PawnShop", 13: "WeaponSmith"}

# ---- Approved material odds (work/notes/20261123-material-tier-proposal.md) ----------------------------------------


def p_daedric(level):
    level = max(1, min(30, level))
    if level <= 20:
        return 0.025 * ((level - 1) / 19) ** 3
    return 0.025 + 0.025 * (level - 20) / 10


# ---- Classic shelf rolls (DaggerfallLoot.StockShopShelf, DaggerfallLootDataTables) ----------------------------------
# Per item type: stock chance = chanceMod * 5 * (21 - rarity) / 100 (integer), rarity <= quality to be eligible.
# Weapons: 19 types (Dagger..Arrow), rarity 1. Armor: 7 body pieces rarity 3, 4 shields rarity 1.
# Armor material: Dice100 1-100, >= 90 is plate (11%), only plate uses the material tiers.
GROUP_MODS = {13: (70, 30), 2: (20, 80), 9: (20, 0), 12: (10, 10)}   # (weapons chanceMod, armor chanceMod)
PLATE = 0.11


def stock(mod, rarity):
    return (mod * 5 * (21 - rarity) // 100) / 100.0


def shelf_rolls(btype, quality):
    """List of (stock chance, chance the stocked item rolls on the Daedric check) per item type on one shelf."""
    wmod, amod = GROUP_MODS[btype]
    rolls = []
    if wmod:
        rolls += [(stock(wmod, 1), 1.0)] * 19
    if amod:
        if quality >= 3:
            rolls += [(stock(amod, 3), PLATE)] * 7
        rolls += [(stock(amod, 1), PLATE)] * 4
    return rolls


def p_shelf(btype, quality, level, shelves=1):
    pd = p_daedric(level)
    none = 1.0
    for c, share in shelf_rolls(btype, quality):
        none *= 1 - c * share * pd
    return 1 - none ** shelves


def mean_rolls(btype, quality):
    r = shelf_rolls(btype, quality)
    return sum(c for c, s in r if s == 1.0), sum(c * s for c, s in r if s != 1.0)


rows = list(csv.DictReader(open(os.path.join(D, "buildings.csv"), encoding="utf-8")))
locs = {(int(r["region"]), int(r["locIndex"])): r for r in csv.DictReader(open(os.path.join(D, "locations.csv"), encoding="utf-8"))}
area = {int(r["map_id"]): r for r in csv.DictReader(open(os.path.join(D, "area.csv"), encoding="utf-8"))}

# ---- Capitals: the city named after its region (hand aliases where the spelling differs) ---------------------------
ALIAS = {"Glenumbra Moors": "Glenumbra", "Dragontail Mountains": "Dragontail", "Wrothgarian Mountains": "Wrothgaria",
         "Antiphyllos": "Antyphyllos", "Orsinium Area": "Orsinium", "Alik'r Desert": "Alik'ra"}


def norm(s):
    return s.strip().lower()


capitals = {}
for key, l in locs.items():
    region = l["regionName"]
    if norm(l["locName"]) == norm(ALIAS.get(region, region)):
        capitals[key] = l
cap_keys = set(capitals)


def town_class(l, scheme):
    t = int(l["locType"])
    blocks = int(l["width"]) * int(l["height"])
    key = (int(l["region"]), int(l["locIndex"]))
    if t not in (0, 1, 2):
        return None
    if key in cap_keys and t == 0:
        return "capital"
    if scheme == "type":
        return {2: "small", 1: "medium", 0: "large"}[t]
    # "blocks": villages and hamlets of 4 blocks or fewer are small, other hamlets medium; cities below 42 blocks
    # medium, 42 and up large.
    if t == 2 or blocks <= 4:
        return "small"
    if t == 1 or blocks < 42:
        return "medium"
    return "large"


TOWN_LEVEL = {"small": 5, "medium": 10, "large": 15, "capital": 20}

for r in rows:
    for k in ("region", "locIndex", "mapId", "locType", "buildingType", "quality", "shelves"):
        r[k] = int(r[k])
    r["loc"] = locs[(r["region"], r["locIndex"])]
    r["terrain"] = int(area[r["mapId"]]["terrain_level"])
    r["tclass"] = town_class(r["loc"], "type")
shops = [r for r in rows if r["buildingType"] in SHOPS]


def out(s=""):
    print(s)


def table(header, body):
    out("| " + " | ".join(str(h) for h in header) + " |")
    out("|" + "---|" * len(header))
    for b in body:
        out("| " + " | ".join(str(x) for x in b) + " |")
    out()


def band(q):
    return 1 if q <= 3 else 2 if q <= 7 else 3 if q <= 13 else 4 if q <= 17 else 5


BANDS = {1: "1-3", 2: "4-7", 3: "8-13", 4: "14-17", 5: "18-20"}


def seeded(r):
    h = hashlib.sha256(f"shoplevel:{r['mapId']}:{r['blockX']}:{r['blockY']}:{r['record']}".encode()).digest()
    return int.from_bytes(h[:4], "little") / 2 ** 32


TOWN_BONUS = {"small": 0, "medium": 1, "large": 2, "capital": 3, None: 0}

# ---- Proposals ------------------------------------------------------------------------------------------------------


def p_linear(r):
    return 1 + round((r["quality"] - 1) * 29 / 19)


def p_town(r):
    # Quality plus town size: 1.25 per quality point plus 0/2/4/6 by town class.
    return max(1, min(30, round(r["quality"] * 1.25) + 2 * TOWN_BONUS[r["tclass"]]))


BAND_RANGE = {1: (1, 4), 2: (5, 10), 3: (11, 18), 4: (19, 24), 5: (25, 30)}


def make_band_rank():
    # Within each quality band, rank by (quality, town class, seeded tiebreak) onto the band's fixed level range.
    levels = {}
    for b, (lo, hi) in BAND_RANGE.items():
        members = [r for r in shops if band(r["quality"]) == b]
        members.sort(key=lambda r: (r["quality"], TOWN_BONUS[r["tclass"]], seeded(r)))
        n = len(members)
        for i, r in enumerate(members):
            levels[id(r)] = lo + i * (hi - lo + 1) // n
    return lambda r: levels[id(r)]


def make_global_rank():
    order = sorted(shops, key=lambda r: (r["quality"], TOWN_BONUS[r["tclass"]], seeded(r)))
    levels = {id(r): 1 + i * 30 // len(order) for i, r in enumerate(order)}
    return lambda r: levels[id(r)]


PROPOSALS = [
    ("A. Quality alone, linear", p_linear),
    ("B. Quality plus town size", p_town),
    ("C. Band-locked rank (quality band fixes the range; quality, town size and a fixed seed order inside it)", make_band_rank()),
    ("D. Global rank of all shops by (quality, town size, fixed seed)", make_global_rank()),
]

out("## Daedric odds on one shelf, by level (approved material odds; classic shelf rolls)")
ws_w, ws_a = mean_rolls(13, 10)
ar_w, ar_a = mean_rolls(2, 10)
out("Mean material rolls per shelf at quality 3 or more: weapon smith %.1f weapon rolls and %.2f plate armor rolls "
    "(%.1f armor pieces in all); armorer %.1f weapon rolls and %.2f plate rolls (%.1f armor pieces); general store "
    "%.1f weapon rolls; pawn shop %.1f weapon rolls and %.2f plate rolls." % (
        ws_w, ws_a, ws_a / PLATE, ar_w, ar_a, ar_a / PLATE, mean_rolls(9, 10)[0], mean_rolls(12, 10)[0], mean_rolls(12, 10)[1]))
out()
lv = [1, 5, 10, 12, 15, 18, 20, 22, 25, 28, 30]
table(["Level"] + lv,
      [["Daedric per material roll"] + ["1 in %d" % round(1 / p_daedric(l)) if p_daedric(l) else "0" for l in lv]]
      + [[f"{NAMES[t]} shelf"] + ["%.1f%%" % (100 * p_shelf(t, 10, l)) for l in lv] for t in (13, 2, 9, 12)]
      + [[f"{NAMES[t]}, whole shop (mean {s:.1f} shelves)"] + ["%.1f%%" % (100 * p_shelf(t, 10, l, s)) for l in lv]
         for t in (13, 2) for s in [sum(r["shelves"] for r in shops if r["buildingType"] == t) / sum(1 for r in shops if r["buildingType"] == t)]])

for title, f in PROPOSALS:
    out("## Proposal " + title)
    lev = [f(r) for r in shops]
    c = collections.Counter(lev)
    table(["Level"] + list(range(1, 31)), [["Shops"] + [c[l] for l in range(1, 31)]])
    # Band contract: a better described shop is never at a lower level.
    rng = {b: (min(l for l, r in zip(lev, shops) if band(r["quality"]) == b), max(l for l, r in zip(lev, shops) if band(r["quality"]) == b)) for b in BANDS}
    bad = sum(1 for l, r in zip(lev, shops) if band(r["quality"]) > 1 and l < rng[band(r["quality"]) - 1][1])
    table(["Quality band"] + [BANDS[b] for b in BANDS], [["Level range"] + ["%d-%d" % rng[b] for b in BANDS]])
    out("Shops below the top level of the band under theirs (description contradicted): %d" % bad)
    out()
    for t in (13, 2):
        sel = [(l, r) for l, r in zip(lev, shops) if r["buildingType"] == t]
        n = len(sel)
        hi20 = sum(1 for l, _ in sel if l >= 20)
        hi25 = sum(1 for l, _ in sel if l >= 25)
        top = sum(1 for l, _ in sel if l == 30)
        visit = sum(p_shelf(t, r["quality"], l, max(1, r["shelves"])) for l, r in sel) / n
        out("- %s (%d): level 20+ %d, level 25+ %d, level 30 %d. Mean chance that one visit (all shelves) shows a Daedric item: %.2f%%; best shop %.1f%%." % (
            NAMES[t], n, hi20, hi25, top, 100 * visit, 100 * max(p_shelf(t, r["quality"], l, max(1, r["shelves"])) for l, r in sel)))
    out()

# ---- Restocks -------------------------------------------------------------------------------------------------------
out("## Restocks")
out("A shelf restocks the first time it is opened on a new calendar day (stockedDate = year*1000 + day of year).")
out("Visits needed for an even chance of at least one Daedric item, whole shop at its mean shelf count:")
out()
table(["Level"] + lv[1:],
      [[f"{NAMES[t]}"] + ["%d" % max(1, round(0.693 / max(1e-9, -__import__('math').log(1 - p_shelf(t, 10, l, s))))) if p_shelf(t, 10, l, s) else "never" for l in lv[1:]]
       for t in (13, 2) for s in [sum(r["shelves"] for r in shops if r["buildingType"] == t) / sum(1 for r in shops if r["buildingType"] == t)]])

# ---- Towns ----------------------------------------------------------------------------------------------------------
out("## Capitals found (city named after its region)")
table(["Region", "Capital", "Type", "Blocks", "Terrain level"],
      sorted((l["regionName"], l["locName"], l["locType"], int(l["width"]) * int(l["height"]), area[int(l["mapId"])]["terrain_level"]) for l in capitals.values()))
regions = sorted({l["regionName"] for l in locs.values()})
out("Regions with no capital found: " + ", ".join(r for r in regions if r not in {l["regionName"] for l in capitals.values()}))
out()
towns = [l for l in locs.values() if int(l["locType"]) in (0, 1, 2)]
for scheme in ("type", "blocks"):
    out(f"## Town classes, scheme '{scheme}'")
    cnt = collections.Counter(town_class(l, scheme) for l in towns)
    shift = collections.defaultdict(list)
    for l in towns:
        cl = town_class(l, scheme)
        shift[cl].append(TOWN_LEVEL[cl] - int(area[int(l["mapId"])]["terrain_level"]))
    table(["Class", "Level", "Towns", "Mean terrain level today", "Towns that go up", "Towns that go down", "Largest rise", "Largest drop"],
          [[c, TOWN_LEVEL[c], cnt[c], "%.1f" % (TOWN_LEVEL[c] - sum(shift[c]) / len(shift[c])), sum(1 for s in shift[c] if s > 0),
            sum(1 for s in shift[c] if s < 0), max(shift[c]), min(shift[c])] for c in ("small", "medium", "large", "capital")])

out("## Towns in the Daggerfall region: terrain level today, by class under the 'type' scheme")
near = collections.Counter()
for l in towns:
    if l["regionName"] in ("Daggerfall",):
        near[(town_class(l, "type"), int(area[int(l["mapId"])]["terrain_level"]))] += 1
table(["Class", "Terrain levels today (count)"],
      [[c, ", ".join(f"{t}:{near[(c, t)]}" for t in sorted({k[1] for k in near if k[0] == c}))] for c in ("small", "medium", "large", "capital")])

# ---- Houses ---------------------------------------------------------------------------------------------------------
out("## House quality (House1-House6) by town class")
houses = [r for r in rows if 17 <= r["buildingType"] <= 22 and r["tclass"]]
hc = collections.Counter((r["tclass"], band(r["quality"])) for r in houses)
table(["Town class"] + [BANDS[b] for b in BANDS] + ["houses"],
      [[c] + [hc[(c, b)] for b in BANDS] + [sum(hc[(c, b)] for b in BANDS)] for c in ("small", "medium", "large", "capital")])
other = collections.Counter(NAMES.get(r["buildingType"], r["buildingType"]) for r in rows if r["tclass"] and r["buildingType"] not in SHOPS and not 17 <= r["buildingType"] <= 22)
out("Other buildings in towns by type: " + ", ".join(f"{k}: {v}" for k, v in sorted(other.items(), key=lambda kv: str(kv[0]))))
out()
qh = collections.Counter(r["quality"] for r in houses)
out("House quality values: " + ", ".join(f"{q}:{qh[q]}" for q in sorted(qh)))
