"""Shop and town level study: distributions and proposals.

Reads buildings.csv and locations.csv from ShopLevels (Program.cs) and area.csv from tools/area_level/area_level.py
--csv, all written outside the repository. Prints Markdown tables for work/notes/20261124-124736-shop-levels.md.

usage: python analyze.py <data dir>
"""
import collections
import csv
import math
import os
import sys

D = sys.argv[1]
BT = {0: "Alchemist", 1: "HouseForSale", 2: "Armorer", 3: "Bank", 4: "Town4", 5: "Bookseller", 6: "ClothingStore",
      7: "FurnitureStore", 8: "GemStore", 9: "GeneralStore", 10: "Library", 11: "GuildHall", 12: "PawnShop",
      13: "WeaponSmith", 14: "Temple", 15: "Tavern", 16: "Palace", 17: "House1", 18: "House2", 19: "House3",
      20: "House4", 21: "House5", 22: "House6", 23: "Town23", 24: "Ship"}
LT = {0: "TownCity", 1: "TownHamlet", 2: "TownVillage", 3: "HomeFarms", 4: "DungeonLabyrinth", 5: "ReligionTemple",
      6: "Tavern", 7: "DungeonKeep", 8: "HomeWealthy", 9: "ReligionCult", 10: "DungeonRuin", 11: "HomePoor",
      12: "Graveyard", 13: "Coven", 14: "HomeYourShips"}
SHOPS = {0, 2, 5, 6, 7, 8, 9, 12, 13}


def band(q):
    return 1 if q <= 3 else 2 if q <= 7 else 3 if q <= 13 else 4 if q <= 17 else 5


BAND_TEXT = {1: "1-3", 2: "4-7", 3: "8-13", 4: "14-17", 5: "18-20"}

rows = list(csv.DictReader(open(os.path.join(D, "buildings.csv"), encoding="utf-8")))
locs = {(int(r["region"]), int(r["locIndex"])): r for r in csv.DictReader(open(os.path.join(D, "locations.csv"), encoding="utf-8"))}
area = {int(r["map_id"]): r for r in csv.DictReader(open(os.path.join(D, "area.csv"), encoding="utf-8"))}
for r in rows:
    for k in ("region", "locIndex", "mapId", "locType", "buildingType", "quality", "nameSeed", "shelves", "interiorObjects",
              "houseContainers", "sizeX", "sizeZ", "sizeY", "modelId"):
        r[k] = int(float(r[k]))
    r["foot"] = r["sizeX"] * r["sizeZ"]
    r["band"] = band(r["quality"])
    loc = locs[(r["region"], r["locIndex"])]
    r["blocks"] = int(loc["width"]) * int(loc["height"])
    r["terrain"] = int(area[r["mapId"]]["terrain_level"])


def out(s=""):
    print(s)


def table(header, body):
    out("| " + " | ".join(header) + " |")
    out("|" + "---|" * len(header))
    for b in body:
        out("| " + " | ".join(str(x) for x in b) + " |")
    out()


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2
            i = j + 1
        return rk
    a, b = ranks(xs), ranks(ys)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


shops = [r for r in rows if r["buildingType"] in SHOPS]

# ---- 1. Shop data -------------------------------------------------------------------------------------------------
out("## Shops by type and location type")
bylt = collections.Counter((BT[r["buildingType"]], LT[r["locType"]]) for r in shops)
lts = sorted({LT[r["locType"]] for r in shops})
types = sorted({BT[r["buildingType"]] for r in shops})
table(["Shop"] + lts + ["Total"], [[t] + [bylt[(t, l)] for l in lts] + [sum(bylt[(t, l)] for l in lts)] for t in types]
      + [["Total"] + [sum(bylt[(t, l)] for t in types) for l in lts] + [len(shops)]])

out("## Shop quality (1-20)")
qc = collections.Counter(r["quality"] for r in shops)
table(["Quality"] + [str(q) for q in range(1, 21)], [["Shops"] + [qc[q] for q in range(1, 21)]])
out("## Shop quality band by location type")
bc = collections.Counter((LT[r["locType"]], r["band"]) for r in shops)
table(["Location type"] + [BAND_TEXT[b] for b in range(1, 6)] + ["mean quality"],
      [[l] + [bc[(l, b)] for b in range(1, 6)] + ["%.1f" % (sum(r["quality"] for r in shops if LT[r["locType"]] == l) / max(1, sum(1 for r in shops if LT[r["locType"]] == l)))] for l in lts])
out("## Shop quality by shop type")
table(["Shop", "n", "mean", "min", "max"] + [BAND_TEXT[b] for b in range(1, 6)],
      [[t, len(v), "%.1f" % (sum(v) / len(v)), min(v), max(v)] + [sum(1 for q in v if band(q) == b) for b in range(1, 6)]
       for t in types for v in [[r["quality"] for r in shops if BT[r["buildingType"]] == t]]])

out("## Size signals (Spearman rank correlation with quality, all shops)")
for key in ("foot", "shelves", "interiorObjects", "blocks", "terrain", "nameSeed"):
    out("- %s: %.3f" % (key, spearman([r[key] for r in shops], [r["quality"] for r in shops])))
out()
out("## Shelves per shop")
sc = collections.Counter(min(r["shelves"], 12) for r in shops)
table(["Shelves"] + [str(s) if s < 12 else "12+" for s in sorted(sc)], [["Shops"] + [sc[s] for s in sorted(sc)]])
out("## Mean shelves by quality band and shop type (weapon smith, armorer)")
for t in (13, 2):
    v = [r for r in shops if r["buildingType"] == t]
    table(["Band"] + [BAND_TEXT[b] for b in range(1, 6)],
          [[BT[t] + " mean shelves"] + ["%.2f" % (sum(r["shelves"] for r in v if r["band"] == b) / max(1, sum(1 for r in v if r["band"] == b))) for b in range(1, 6)]])
zero = [r for r in shops if r["shelves"] == 0]
out("Shops with no shelf model: %d" % len(zero))
out()
out("## Distinct exterior models used by shops: %d; distinct interiors (block, record): %d" % (
    len({r["modelId"] for r in shops}), len({(r["blockName"], r["record"]) for r in shops})))
# Is quality fixed per block record (interior) or per location?
per_interior = collections.defaultdict(set)
for r in shops:
    per_interior[(r["blockName"], r["record"])].add(r["quality"])
multi = sum(1 for v in per_interior.values() if len(v) > 1)
out("Interiors used with more than one quality: %d of %d" % (multi, len(per_interior)))
out()

# ---- Towns ----------------------------------------------------------------------------------------------------------
towns = [l for l in locs.values() if int(l["locType"]) in (0, 1, 2)]
out("## Towns by type and block count")
tb = collections.Counter((LT[int(l["locType"])], int(l["width"]) * int(l["height"])) for l in towns)
sizes = sorted({k[1] for k in tb})
table(["Type"] + [str(s) for s in sizes] + ["Total"], [[t] + [tb[(t, s)] for s in sizes] + [sum(tb[(t, s)] for s in sizes)]
                                                         for t in ("TownCity", "TownHamlet", "TownVillage")])
palace = collections.defaultdict(int)
for r in rows:
    if r["buildingType"] == 16:
        palace[(r["region"], r["locIndex"])] += 1
out("## Locations with a Palace building")
pl = []
for key in palace:
    l = locs[key]
    pl.append((l["regionName"], l["locName"], LT[int(l["locType"])], int(l["width"]) * int(l["height"]), int(area[int(l["mapId"])]["terrain_level"])))
table(["Region", "Location", "Type", "Blocks", "Terrain level"], sorted(pl))
out("## Largest TownCity per region")
best = {}
for l in towns:
    if int(l["locType"]) != 0:
        continue
    n = int(l["width"]) * int(l["height"])
    if l["regionName"] not in best or n > best[l["regionName"]][0]:
        best[l["regionName"]] = (n, l["locName"], int(area[int(l["mapId"])]["terrain_level"]), (int(l["region"]), int(l["locIndex"])) in palace)
table(["Region", "Largest city", "Blocks", "Terrain level", "Has palace", "Name = region"],
      [[k, v[1], v[0], v[2], "yes" if v[3] else "", "yes" if v[1] == k or v[1] == "City of " + k else ""] for k, v in sorted(best.items())])
