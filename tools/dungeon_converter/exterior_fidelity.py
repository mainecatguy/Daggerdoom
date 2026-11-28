"""Exterior collision test set: finite-height check and the collision fidelity metric for towns and dungeon exteriors.

Usage:
  python tools/dungeon_converter/exterior_fidelity.py --out <dir outside the repo> [--cache <dir>] [--legacy-void] [--raster 8]
  python tools/dungeon_converter/exterior_fidelity.py --find <name>

Converts each test location the way the running game does (--group), with --fidelity, and prints one table row per
location plus the set headline (mean of the locations, as fidelity.py does for dungeons). The metric is Fidelity.cs's,
run on the emitted map. Exits 1 if any location fails the finite-height check or the metric. Output is derived from
game data, so keep it outside the repo.
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
CASES = ("walkable top missing", "phantom wall", "invisible ledge")


def find(name):
    return subprocess.run([CONVERTER, "--find-group", name], capture_output=True, text=True).stdout


def cases(report):
    """Each failure case's bad area and surface area, summed over the reached tiers (contact, climb, levitation)."""
    found = {}
    for line in open(report, encoding="utf-8"):
        m = re.match(r"\s+(walkable top missing|phantom wall|invisible ledge)\s+(.*)", line)
        if m:
            bad = [float(x) for x in re.findall(r"([\d.]+) /", m.group(2))]
            total = [float(x) for x in re.findall(r"/ ([\d.]+)", m.group(2))]
            found[m.group(1)] = (sum(bad[:3]), sum(total[:3]))
    return found


def reach(report):
    """'N of M' reachable legal positions, from the report (written whether or not the Daggerfall side was cached)."""
    m = re.search(r"reachable legal positions (\d+ of \d+)", open(report, encoding="utf-8").read())
    return m.group(1) if m else None


def run(group, out_dir, extra, converter):
    work = os.path.join(out_dir, str(group))
    os.makedirs(work, exist_ok=True)
    args = [converter, "--group", str(group), "--ddt", os.path.join(work, "group.ddt"), "--out", work, "--fidelity"] + extra
    proc = subprocess.run(args, capture_output=True, text=True)
    text = proc.stdout + proc.stderr
    with open(os.path.join(work, "log.txt"), "w", encoding="utf-8") as f:
        f.write(text)

    def grab(pattern, cast=float):
        m = re.search(pattern, text)
        return cast(m.group(1)) if m else None
    m = re.search(r"^FIDELITY (\S+) headline (\S+) seconds (\S+)", text, re.M)
    c = cases(os.path.join(work, m.group(1) + ".fidelity.txt")) if m else {}
    return {
        "pass": "finite height check PASS" in text,
        "sky": grab(r"(\d+) open to the sky", int),
        "tall": grab(r"open to the sky, (\d+) more than", int),
        "headline": float(m.group(2)) if m else None,
        "metric_s": float(m.group(3)) if m else None,
        "cases": c,
        "reach": reach(os.path.join(work, m.group(1) + ".fidelity.txt")) if m else None,
        "ms": grab(r"convert time (\d+) ms", int),
        "sectors": grab(r"sectors (\d+)", int),
        "lines": grab(r"lines (\d+)", int),
    }


def main():
    lines = []

    def emit(text):
        print(text, flush=True)
        lines.append(text)

    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--find")
    ap.add_argument("--groups", default="", help="label=id,label=id overrides the built-in set")
    ap.add_argument("--legacy-void", action="store_true")
    ap.add_argument("--raster", default="8")
    ap.add_argument("--cache", default=None, help="--fidelity-cache directory for the Daggerfall side (Fidelity.cs)")
    ap.add_argument("--converter", default=CONVERTER)
    a = ap.parse_args()
    if a.find:
        print(find(a.find))
        return 0
    groups = [tuple(x.split("=")) for x in a.groups.split(",") if x] or GROUPS
    extra = (["--legacy-void"] if a.legacy_void else []) + ["--raster", a.raster] + (["--fidelity-cache", a.cache] if a.cache else [])
    failed = False
    heads = []
    sums = dict.fromkeys(CASES, 0.0)
    ms = 0

    def area(c, name):
        bad, total = c.get(name, (None, None))
        return "-" if bad is None else f"{bad:.0f} ({100 * bad / max(1, total):.2f}%)"
    emit("Headline: tier-weighted mean error in map units, both directions, lower is better (Fidelity.cs on the emitted map).")
    emit("Case areas: map units^2 over the contact, climb and levitation tiers, with the share of that kind of surface.")
    emit("| Location | Group | Height check | Open to sky | Too tall (raster) | Headline | Walkable top missing | Phantom wall | Invisible ledge | Reachable legal | Sectors | Lines | Convert ms | Metric s |")
    emit("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for label, gid in groups:
        r = run(int(gid), a.out, extra, a.converter)
        failed |= not r["pass"] or r["headline"] is None
        c = r["cases"]
        emit(f"| {label} | {gid} | {'PASS' if r['pass'] else 'FAIL'} | {r['sky']} | {r['tall']} | {r['headline']} | {area(c, CASES[0])} | {area(c, CASES[1])} | {area(c, CASES[2])} | {r['reach']} | {r['sectors']} | {r['lines']} | {r['ms']} | {r['metric_s']} |")
        if r["headline"] is not None:
            heads.append(r["headline"])
        for k in CASES:
            sums[k] += c.get(k, (0, 0))[0]
        ms += r["ms"] or 0
    if heads:
        emit(f"\nSET headline {sum(heads) / len(heads):.4f} (mean of {len(heads)} locations); " + "; ".join(f"{k} {v:.0f}" for k, v in sums.items()) + f"; convert {ms} ms total")
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
