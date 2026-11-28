"""Exterior collision test set: finite-height check and fidelity metric for towns and dungeon exteriors.

Usage:
  python tools/dungeon_converter/exterior_fidelity.py --out <dir outside the repo> [--legacy-void] [--raster 8]
  python tools/dungeon_converter/exterior_fidelity.py --find <name>

Converts each test location the way the running game does (--group), with --fidelity, and prints one table row per
location plus the totals. Exits 1 if any location fails the finite-height check. Output is derived from game data, so
keep it outside the repo.
"""
import argparse
import os
import re
import subprocess
import sys

CONVERTER = os.path.normpath(os.path.join(os.path.dirname(__file__), r"..\..\..\DoomDaggerfall-build\dungeon_converter\bin\Release\net9.0\DungeonConverter.exe"))

# (label, group id). Group ids come from --find; they are stable while WorldTerrain's grouping is unchanged.
GROUPS = [
    ("capital Daggerfall + village Ripwych Commons + manor", "9183"),
    ("city Ykalon", "1131"),
    ("village Gothworth Commons", "2154"),
    ("hamlet Midbrugh Hollow", "3246"),
    ("dungeon Privateer's Hold + hamlet Gothway Garden", "7154"),
    ("dungeon keep Castle Mastering", "18"),
    ("dungeon ruin Kinghart Court", "3"),
    ("graveyard Wickhart", "47"),
    ("countryside Yeomhart Farmstead", "7"),
]


def find(name):
    out = subprocess.run([CONVERTER, "--find-group", name], capture_output=True, text=True).stdout
    return out


def run(group, out_dir, extra):
    work = os.path.join(out_dir, str(group))
    os.makedirs(work, exist_ok=True)
    ddt = os.path.join(work, "group.ddt")
    args = [CONVERTER, "--group", str(group), "--ddt", ddt, "--out", work, "--fidelity"] + extra
    proc = subprocess.run(args, capture_output=True, text=True)
    text = proc.stdout + proc.stderr
    with open(os.path.join(work, "log.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    def grab(pattern, cast=float):
        m = re.search(pattern, text)
        return cast(m.group(1)) if m else None
    return {
        "pass": "finite height check PASS" in text,
        "sky": grab(r"(\d+) open to the sky", int),
        "tall": grab(r"open to the sky, (\d+) more than", int),
        "error": grab(r"weighted mean \|error\| ([\d.]+)"),
        "excess": grab(r"excess ([\d.]+)"),
        "missing": grab(r"missing ([\d.]+)"),
        "phantom": grab(r"phantom walls (\d+)", int),
        "toolow": grab(r"too low (\d+)", int),
        "fine": grab(r"(\d+) fine cells", int),
        "ms": grab(r"convert time (\d+) ms", int),
        "sectors": grab(r"sectors (\d+)", int),
        "lines": grab(r"lines (\d+)", int),
        "rc": proc.returncode,
    }


def main():
    lines = []
    def emit(text):
        print(text)
        lines.append(text)

    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--find")
    ap.add_argument("--groups", default="", help="label=id,label=id overrides the built-in set")
    ap.add_argument("--legacy-void", action="store_true")
    ap.add_argument("--raster", default="8")
    a = ap.parse_args()
    if a.find:
        print(find(a.find))
        return 0
    groups = [tuple(x.split("=")) for x in a.groups.split(",") if x] or GROUPS
    extra = (["--legacy-void"] if a.legacy_void else []) + ["--raster", a.raster]
    failed = False
    totals = {"error": 0.0, "fine": 0, "ms": 0, "phantom": 0, "sky": 0, "tall": 0, "toolow": 0}
    emit("| Location | Group | Height check | Open to sky | Too tall (raster) | Mean abs error | Excess | Missing | Phantom (fine) | Too low (fine) | Sectors | Lines | Convert ms |")
    emit("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for label, gid in groups:
        r = run(int(gid), a.out, extra)
        failed |= not r["pass"]
        emit(f"| {label} | {gid} | {'PASS' if r['pass'] else 'FAIL'} | {r['sky']} | {r['tall']} | {r['error']} | {r['excess']} | {r['missing']} | {r['phantom']} | {r['toolow']} | {r['sectors']} | {r['lines']} | {r['ms']} |")
        if r["error"] is not None:
            totals["error"] += r["error"] * r["fine"]
            totals["fine"] += r["fine"]
        for k in ("ms", "phantom", "sky", "tall", "toolow"):
            totals[k] += r[k] or 0
    if totals["fine"]:
        emit(f"\nOverall (fine-cell weighted) mean abs error {totals['error'] / totals['fine']:.2f} units; open to sky {totals['sky']}; too tall {totals['tall']}; phantom {totals['phantom']}; too low {totals['toolow']}; convert {totals['ms']} ms total")
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
