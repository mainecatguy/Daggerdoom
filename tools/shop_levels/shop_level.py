"""Shop levels (1 to 30) of every classic shop, by proposal C (band-locked rank).

    python tools/shop_levels/shop_level.py [--arena2 DIR] [--csv OUT] [--runtime DUMP_DIR]

The owner chose proposal C on 2026-11-26 (work/notes/20261124-124736-shop-levels.md). This script is the reference
for DoomerfallShopLevels.cs in Daggerfall Unity: same tables, same seed, same order, so both give the same level for
every shop. Keep the two in step.

Inputs:  classic MAPS.BSA only (each location's building list, map table and names).
Outputs: per-level counts and the band contract check on stdout; with --csv, one row per shop; with --runtime, a
         comparison against what DaggerfallUnity.exe -dfshopleveldump DUMP_DIR wrote.

The rule:
- A shop is a building of a shop type (RMBLayout.IsShop) in a location's MAPS.BSA building list.
- Its quality band picks a fixed level range: 1-3 -> 1-4, 4-7 -> 5-10, 8-13 -> 11-18, 14-17 -> 19-24, 18-20 -> 25-30.
- Inside a band, shops are sorted by (quality, town class, seed) and spread evenly over the range:
  level = lo + rank * width // shops in band. Sorting is the same as counting the shops per (band, quality, town
  class) cell, adding the cells below, and placing the shop inside its cell by its seed.
- Town class: 0 village (and the alchemists in castles), 1 hamlet, 2 city, 3 capital (the city named after its
  region, with the aliases below).
- Seed: lowbias32 chain of (SEED_SHOP, MapId, building type << 16 | NameSeed). Within one location, (building type,
  NameSeed) is unique for all 14,790 classic shops, and both are on the runtime BuildingSummary, so the seed needs
  no BLOCKS.BSA and no building key. Ties on the seed fall back to (MapId, type, NameSeed).
- A shop that is not in the classic list (a mod-added location, or a building a mod replaced) is placed among the
  classic keys of its band without being counted, so classic levels never move.
"""
import argparse
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "area_level"))
import dfdata  # noqa: E402

DEFAULT_ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
SHOP_TYPES = {0: "Alchemist", 2: "Armorer", 5: "Bookseller", 6: "ClothingStore", 7: "FurnitureStore", 8: "GemStore",
              9: "GeneralStore", 12: "PawnShop", 13: "WeaponSmith"}
BAND_RANGE = [(1, 4), (5, 10), (11, 18), (19, 24), (25, 30)]
BAND_NAMES = ["1-3", "4-7", "8-13", "14-17", "18-20"]
CAPITAL_ALIAS = {"Glenumbra Moors": "Glenumbra", "Dragontail Mountains": "Dragontail",
                 "Wrothgarian Mountains": "Wrothgaria", "Antiphyllos": "Antyphyllos", "Orsinium Area": "Orsinium",
                 "Alik'r Desert": "Alik'ra"}
SEED_SHOP = 0x5B0F0001
TOWN_CITY, TOWN_HAMLET, TOWN_VILLAGE = 0, 1, 2


def band(quality):
    return 0 if quality <= 3 else 1 if quality <= 7 else 2 if quality <= 13 else 3 if quality <= 17 else 4


def is_capital(region_name, location_name, ltype):
    want = CAPITAL_ALIAS.get(region_name, region_name)
    return ltype == TOWN_CITY and location_name.strip().lower() == want.strip().lower()


def town_class(ltype, capital):
    if capital:
        return 3
    return {TOWN_CITY: 2, TOWN_HAMLET: 1, TOWN_VILLAGE: 0}.get(ltype, 0)


def hash32(x):
    # lowbias32 by Chris Wellons, as area_level.py and DoomerfallAreaLevels.cs.
    x &= 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return x


def seed(map_id, btype, name_seed):
    h = hash32(SEED_SHOP)
    h = hash32(h ^ (map_id & 0xFFFFFFFF))
    return hash32(h ^ ((btype << 16) | name_seed))


def sort_key(s):
    return (s["quality"], s["tclass"], s["seed"], s["map_id"] & 0xFFFFFFFF, s["type"], s["name_seed"])


def read_shops(arena2):
    """Every shop in every classic location's MAPS.BSA building list."""
    records = dfdata._bsa_records(os.path.join(arena2, "MAPS.BSA"))
    shops = []
    for region, rname in enumerate(dfdata.REGION_NAMES):
        names = records[region * 4 + 3]
        table = records[region * 4 + 2]
        pitem = records[region * 4 + 0]
        if not names or not table or not pitem:
            continue
        n = struct.unpack_from("<I", names, 0)[0]
        for i in range(n):
            lname = names[4 + i * 32:4 + i * 32 + 32].split(b"\0", 1)[0].decode("latin-1")
            map_id, bits = struct.unpack_from("<iI", table, i * 17)
            ltype = ((4 * bits) & 0xFFFFFFFF) >> 27
            pos = n * 4 + struct.unpack_from("<I", pitem, i * 4)[0]
            doors = struct.unpack_from("<I", pitem, pos)[0]
            p = pos + 4 + doors * 6 + 112          # door list, then the 112-byte record header
            count = struct.unpack_from("<H", pitem, p)[0]
            p += 7                                  # building count and 5 unknown bytes
            tclass = town_class(ltype, is_capital(rname, lname, ltype))
            for b in range(count):
                o = p + b * 26
                name_seed = struct.unpack_from("<H", pitem, o)[0]
                btype, quality = pitem[o + 24], pitem[o + 25]
                if btype not in SHOP_TYPES:
                    continue
                shops.append({"region": region, "region_name": rname, "name": lname, "map_id": map_id,
                              "ltype": ltype, "tclass": tclass, "type": btype, "name_seed": name_seed,
                              "quality": quality, "seed": seed(map_id, btype, name_seed)})
    return shops


def assign(shops):
    """Sets s['level'] on every shop. Returns the sorted keys per band, for placing shops that are not classic."""
    keys = []
    for b, (lo, hi) in enumerate(BAND_RANGE):
        members = sorted((s for s in shops if band(s["quality"]) == b), key=sort_key)
        n = len(members)
        for i, s in enumerate(members):
            s["level"] = lo + i * (hi - lo + 1) // n
        keys.append([(s["quality"], s["tclass"], s["seed"]) for s in members])
    return keys


def place_among_classic(keys, quality, tclass, shop_seed):
    """Level of a shop that is not classic: its rank among the classic keys of its band, not counting itself."""
    import bisect
    b = band(quality)
    lo, hi = BAND_RANGE[b]
    k = keys[b]
    below = bisect.bisect_left(k, (quality, tclass, shop_seed))
    return min(hi, lo + below * (hi - lo + 1) // max(1, len(k)))


def contract_violations(shops):
    top = [max(s["level"] for s in shops if band(s["quality"]) == b) for b in range(5)]
    return sum(1 for s in shops if band(s["quality"]) > 0 and s["level"] < top[band(s["quality"]) - 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena2", default=DEFAULT_ARENA2)
    ap.add_argument("--csv")
    ap.add_argument("--runtime", help="dump dir from DaggerfallUnity.exe -dfshopleveldump")
    a = ap.parse_args()
    shops = read_shops(a.arena2)
    keys = assign(shops)
    print(f"shops: {len(shops)} in {len({s['map_id'] for s in shops})} locations")
    counts = collections.Counter(s["level"] for s in shops)
    print("counts: " + " ".join(f"{lv}:{counts[lv]}" for lv in range(1, 31)))
    for b, (lo, hi) in enumerate(BAND_RANGE):
        lv = [s["level"] for s in shops if band(s["quality"]) == b]
        print(f"band {BAND_NAMES[b]}: {len(lv)} shops, levels {min(lv)}-{max(lv)} (range {lo}-{hi})")
    print(f"contract violations (below the top level of the band beneath): {contract_violations(shops)}")
    same = sum(1 for s in shops if place_among_classic(keys, s["quality"], s["tclass"], s["seed"]) == s["level"])
    print(f"fallback placement on every classic shop: {same} of {len(shops)} land on their own level")
    caps = sorted({(s["region_name"], s["name"]) for s in shops if s["tclass"] == 3})
    print(f"capitals with shops: {len(caps)}")

    if a.csv:
        with open(a.csv, "w", encoding="utf-8", newline="") as f:
            f.write("map_id,type,name_seed,quality,town_class,level,region,location\n")
            for s in shops:
                f.write(f"{s['map_id']},{s['type']},{s['name_seed']},{s['quality']},{s['tclass']},{s['level']},"
                        f"\"{s['region_name']}\",\"{s['name']}\"\n")
        print("wrote " + a.csv)

    if a.runtime:
        # classic.csv is the runtime table; shops.csv is every shop Daggerfall Unity builds, read through ForShop.
        want = {(s["map_id"], s["type"], s["name_seed"], s["quality"]): s["level"] for s in shops}
        failed = False
        for name in ("classic.csv", "shops.csv"):
            got, rows = {}, 0
            with open(os.path.join(a.runtime, name), encoding="utf-8") as f:
                next(f)
                for line in f:
                    m, t, ns, q, lv = (int(v) for v in line.split(",")[:5])
                    got[(m, t, ns, q)] = lv
                    rows += 1
            bad = [k for k in want if got.get(k) != want[k]]
            extra = [k for k in got if k not in want]
            for k in bad[:10]:
                print(f"{name} differs: {k} script {want[k]} runtime {got.get(k)}")
            rc = collections.Counter(got.values())
            same_counts = all(rc[lv] == counts[lv] for lv in range(1, 31))
            print(f"{name}: {rows} rows, {len(want) - len(bad)} of {len(want)} match the script, {len(bad)} differ, "
                  f"{len(extra)} unknown, per-level counts match: {same_counts}")
            failed |= bool(bad or extra or rows != len(want) or not same_counts)
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
