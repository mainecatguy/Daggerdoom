"""Converts sample dungeons of every Daggerfall dungeon type with the runtime path (--group), as the game's town cache
does, and checks each cache file. Output names game content, so it stays in the work folder, outside the repository.

Usage: python runtime_dungeon_check.py <converter exe> <work dir> [--per-type N] [--arena2 DIR] [--only NAME...]
"""
import argparse
import os
import struct
import subprocess
import sys
import time
import zlib

DUNGEON_GROUP = 30000000
TYPES = ["Crypt", "OrcStronghold", "HumanStronghold", "Prison", "DesecratedTemple", "Mine", "NaturalCave", "Coven",
         "VampireHaunt", "Laboratory", "HarpyNest", "RuinedCastle", "SpiderNest", "GiantStronghold", "DragonsDen",
         "BarbarianStronghold", "VolcanicCaves", "ScorpionNest", "Cemetery"]


def read_ddt(path):
    data = open(path, "rb").read()
    magic, count = data[:4], struct.unpack("<i", data[4:8])[0]
    assert magic == b"DDT3", magic
    heads, at = [], 8
    for _ in range(count):
        name, raw, packed = data[at:at + 8].rstrip(b"\0").decode(), *struct.unpack("<II", data[at + 8:at + 16])
        heads.append((name, raw, packed))
        at += 16
    lumps = {}
    for name, raw, packed in heads:
        body = zlib.decompress(data[at:at + packed]) if packed else b""
        assert len(body) == raw, name
        lumps[name] = body
        at += packed
    return lumps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("work")
    ap.add_argument("--per-type", type=int, default=1)
    ap.add_argument("--arena2", default=r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    listing = subprocess.run([args.exe, "--list-dungeon-types", "--arena2", args.arena2], capture_output=True, text=True, errors="replace").stdout
    by_type = {}
    for line in listing.splitlines():
        f = line.split("\t")
        if len(f) == 5 and f[0] == "DUNGEON":
            by_type.setdefault(f[2], []).append((int(f[1]), f[3], int(f[4])))
    picks = []
    for t in TYPES:
        rows = sorted(by_type.get(t, []), key=lambda r: r[2])  # smallest first: quick, and still the type's own blocks
        if args.only:
            rows = [r for r in rows if any(o.lower() in r[1].lower() for o in args.only)]
        step = max(1, len(rows) // max(1, args.per_type))
        picks += [(t, r) for r in rows[::step][:args.per_type]]
    failures = 0
    for t, (map_id, name, blocks) in picks:
        group = DUNGEON_GROUP + (map_id & 0xFFFFF)
        ddt = os.path.join(args.work, f"T{group:05d}.ddt")
        if os.path.exists(ddt):
            os.remove(ddt)
        start = time.time()
        p = subprocess.run([args.exe, "--group", str(group), "--ddt", ddt, "--out", os.path.join(args.work, f"work{group}"), "--arena2", args.arena2],
                           capture_output=True, text=True, errors="replace")
        ms = (time.time() - start) * 1000
        ok = p.returncode == 0 and os.path.exists(ddt)
        detail = ""
        if ok:
            lumps = read_ddt(ddt)
            need = ["MAPWAD", "DFMESH", "DDDUNGN", "DFDOORS", "DFACTION"]  # cache names hold 8 characters
            missing = [n for n in need if n not in lumps]
            info = lumps.get("DDDUNGN", b"").decode()
            exits = sum(1 for l in info.splitlines() if l.startswith("exit "))
            wad = lumps.get("MAPWAD", b"")
            mapname = wad[struct.unpack("<i", wad[8:12])[0] + 8:][:8].rstrip(b"\0").decode() if len(wad) > 12 else "?"
            ok = not missing and exits > 0 and f"mapid {map_id}" in info
            detail = f"map {mapname} exits {exits} lumps {','.join(sorted(lumps))}{' MISSING ' + ','.join(missing) if missing else ''}"
        else:
            detail = (p.stdout + p.stderr).strip().splitlines()[-1:] or ["no output"]
            detail = detail[0]
        failures += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {t:20} {name:40} blocks {blocks:3} {ms:7.0f} ms {detail}", flush=True)
    print(f"{len(picks) - failures}/{len(picks)} converted")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
