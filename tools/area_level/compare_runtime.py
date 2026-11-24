"""Checks Daggerfall Unity's runtime area levels against area_level.py.

    python tools/area_level/compare_runtime.py DUMP_DIR [--arena2 DIR]

DUMP_DIR is what DaggerfallUnity.exe -dfarealeveldump DUMP_DIR wrote (levels.csv and terrain.bin).
Compares every classic location's dungeon and terrain level and every land map pixel's terrain level.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import area_level  # noqa: E402
import dfdata  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--arena2", default=area_level.DEFAULT_ARENA2)
    a = ap.parse_args()
    locs = dfdata.read_locations(a.arena2)
    region_at = dfdata.read_politic(a.arena2)
    terrain = area_level.assign(locs, region_at)

    runtime = {}
    with open(os.path.join(a.dump, "levels.csv"), encoding="utf-8") as f:
        next(f)
        for line in f:
            map_id, dungeon, ter = (int(v) for v in line.split(","))
            runtime[map_id] = (dungeon, ter)

    bad = 0
    for l in locs:
        want = (l["level"] if l["dtype_name"] else 0, l["terrain_level"])
        got = runtime.get(l["map_id"])
        if got != want:
            bad += 1
            if bad <= 10:
                print(f"location differs: {l['region_name']} / {l['name']} ({l['map_id']}) script {want} runtime {got}")
    extra = len(set(runtime) - {l["map_id"] for l in locs})
    print(f"locations: {len(locs)} in script, {len(runtime)} at runtime, {extra} only at runtime, {bad} differ")

    pixels = open(os.path.join(a.dump, "terrain.bin"), "rb").read()
    # The dump masks water with Daggerfall Unity's politic values. A few pixels have a politic value past the last
    # region: both sides leave them unranked, and the runtime reports an unranked pixel as level 1, which is the
    # default the script gives a location on one. Those are counted apart, not as matches or mismatches.
    bad_px = land = unranked = 0
    for y in range(500):
        for x in range(1000):
            want = terrain.get(y * 1000 + x, 0)
            land += want != 0
            if want == 0 and pixels[y * 1000 + x] == 1 and region_at(x, y) == -1:
                unranked += 1
            elif pixels[y * 1000 + x] != want:
                bad_px += 1
                if bad_px <= 10:
                    print(f"pixel ({x}, {y}) script {want} runtime {pixels[y * 1000 + x]} region {region_at(x, y)}")
    print(f"terrain pixels: {land} land, {bad_px} differ, {unranked} unranked on both sides (runtime reports 1)")

    names = ["Privateer's Hold", "Daggerfall", "Castle Necromoghan", "Sentinel", "Wayrest", "Orsinium",
             "Shedungent", "Mantellan Crux", "Jubithiva's Den", "The Fortress of Ashham"]
    print("script values for the named samples (dungeon / terrain):")
    for l in locs:
        if l["name"] in names and l["dtype_name"]:
            print(f"  {l['region_name']} / {l['name']} ({l['map_id']}): {l['level']} / {l['terrain_level']}")
    sys.exit(1 if bad or bad_px else 0)


if __name__ == "__main__":
    main()
