"""Counts the dungeons whose blocks hold a door model with a roll or pitch (the converter's --list-tilted-doors).

Usage: tilted_doors.py --converter EXE [--out FILE]
Prints the tilted door placements by block and model, and how many dungeons, and of which types, use those blocks.
"""
import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"


def run(exe, *args):
    r = subprocess.run([exe, *args, "--arena2", ARENA2], capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL)
    return r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--converter", required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    text = run(a.converter, "--list-tilted-doors")
    if a.out:
        a.out.write_text(text)
    lines = text.splitlines()
    doors = [l for l in lines if " door " in l and " rot " in l]
    rots = collections.Counter(re.sub(r"^\S+ ", "", l) for l in doors)
    print("\n".join(l for l in lines if "door objects" in l))
    print(f"{len(doors)} tilted door placements in {len({l.split()[0] for l in doors})} blocks; by model and rotation:")
    for k, n in rots.most_common():
        print(f"  {n:4d}  {k}")
    used = [l for l in lines if l.startswith("TILTEDIN")]
    types = {}
    for l in run(a.converter, "--list-dungeon-types").splitlines():
        f = l.split("\t")
        if len(f) >= 3 and f[0] == "DUNGEON":
            types[f[1]] = f[2]
    by_type = collections.Counter(types.get(re.match(r"TILTEDIN #(\d+)", l).group(1), "?") for l in used)
    print(f"{len(used)} dungeons use those blocks; by type: {dict(by_type.most_common())}")
    for l in used[:20]:
        print("  ", l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
