"""Collision fidelity battery: converts each dungeon of the fixed test set and scores its collision (Fidelity.cs).

Usage: python tools/dungeon_converter/fidelity.py --out <dir outside the repo> [--baseline <earlier summary.csv>]
           [--set <set file>] [--only <map id,...>] [--jobs 4] [--no-build] [-- <extra converter arguments>]

No window opens: this runs only the offline converter. Writes, under --out:
  summary.csv            one row per map: headline, timings, sample counts
  set.csv                every map's per-tier and per-orientation rows
  reports/<slug>.fidelity.txt, reports/<slug>.worst_views.txt (views for tools/dungeon_compare/compare.py)
The headline is the tier-weighted mean error in map units, lower is better. The set headline is the mean of the map
headlines, so each map counts the same. With --baseline, prints each map's change and whether the set improved.
Rule (owner, 2026-11-27): a collision change must improve the set headline without regressing the door, reach and
parity checks. A win on one map that loses overall does not pass.
"""
import argparse
import concurrent.futures
import csv
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BUILD = r"D:\dev\DoomDaggerfall-build\fidelity"


def read_set(path, only):
    maps = []
    for raw in open(path, encoding="utf-8"):
        if not raw.startswith("#") or not raw[1:2].isdigit():
            continue
        name, label = raw.rstrip("\n").split("\t", 1)
        if only and name[1:] not in only:
            continue
        maps.append((name, label))
    return maps


def run_one(exe, name, out, cache, extra):
    slug = "".join(c for c in name if c.isalnum()).lower()
    start = time.time()
    proc = subprocess.run([exe, name, "--out", os.path.join(out, "maps", slug), "--fidelity", os.path.join(out, "reports"),
                           "--fidelity-cache", cache] + extra, capture_output=True, text=True)
    seconds = time.time() - start
    match = re.search(r"^FIDELITY (\S+) headline (\S+) seconds (\S+) mesh (\d+) collision (\d+) df (\S+)", proc.stdout, re.M)
    if proc.returncode or not match:
        with open(os.path.join(out, slug + ".error.txt"), "w", encoding="utf-8") as f:
            f.write(proc.stdout + "\n" + proc.stderr)
        return dict(map=name, slug=slug, headline="", metric_seconds="", process_seconds=f"{seconds:.1f}", error=proc.returncode or "no result")
    return dict(map=name, slug=slug, headline=match.group(2), metric_seconds=match.group(3), process_seconds=f"{seconds:.1f}",
                mesh=match.group(4), collision=match.group(5), df=match.group(6), error="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--set", default=os.path.join(HERE, "fidelity_set.txt"))
    parser.add_argument("--only", default="", help="comma-separated map ids from the set")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--baseline")
    parser.add_argument("--cache", default=os.path.join(BUILD, "cache"), help="cached Daggerfall side, shared by all variants")
    parser.add_argument("--bin", default=os.path.join(BUILD, "bin"))
    parser.add_argument("--no-build", action="store_true")
    args, extra = parser.parse_known_args()
    extra = [a for a in extra if a != "--"]
    out = os.path.abspath(args.out)
    if (os.path.normcase(out) + os.sep).startswith(os.path.normcase(REPO) + os.sep):
        sys.exit("--out must be outside the repository: generated maps are derived from game data")
    os.makedirs(os.path.join(out, "reports"), exist_ok=True)
    if not args.no_build:
        build = subprocess.run(["dotnet", "build", os.path.join(HERE, "DungeonConverter.csproj"), "-c", "Release", "-v", "q", "-o", args.bin])
        if build.returncode:
            sys.exit(build.returncode)
    exe = os.path.join(args.bin, "DungeonConverter.exe")
    maps = read_set(args.set, set(filter(None, args.only.split(","))))
    if args.baseline:  # start the slowest maps first so one long map does not finish alone at the end
        took = {r["map"]: float(r["process_seconds"] or 0) for r in csv.DictReader(open(args.baseline, encoding="utf-8"))}
        maps.sort(key=lambda m: -took.get(m[0], 1e9))
    start = time.time()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for row in pool.map(lambda m: run_one(exe, m[0], out, args.cache, extra), maps):
            label = dict(maps)[row["map"]]
            row["label"] = label
            rows.append(row)
            print(f"{row['slug']:>11} {row['headline'] or 'FAILED':>8}  metric {row['metric_seconds'] or '-':>6} s  process {row['process_seconds']:>6} s  {label}", flush=True)
    wall = time.time() - start
    fields = ["map", "slug", "label", "headline", "metric_seconds", "process_seconds", "mesh", "collision", "df", "error"]
    with open(os.path.join(out, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out, "set.csv"), "w", encoding="utf-8") as f:
        f.write("map,direction,tier,area,samples,mean,p95,in1,in2,in4,front1,front2,front4,behind1,behind2,behind4\n")
        for row in rows:
            path = os.path.join(out, "reports", row["slug"] + ".fidelity.csv")
            if os.path.exists(path):
                f.writelines(open(path, encoding="utf-8").readlines()[1:])
    good = [r for r in rows if r["headline"]]
    failed = [r["slug"] for r in rows if not r["headline"]]
    set_headline = sum(float(r["headline"]) for r in good) / max(1, len(good))
    print(f"SET headline {set_headline:.4f} over {len(good)} maps ({len(failed)} failed{': ' + ', '.join(failed) if failed else ''}); wall {wall:.0f} s with {args.jobs} jobs")
    if args.baseline:
        base = {r["slug"]: r for r in csv.DictReader(open(args.baseline, encoding="utf-8")) if r["headline"]}
        both = [r for r in good if r["slug"] in base]
        if len(both) != len(good) or len(both) != len(base):
            print(f"warning: baseline has {len(base)} scored maps, this run {len(good)}; comparing the {len(both)} in both")
        old = sum(float(base[r["slug"]]["headline"]) for r in both) / max(1, len(both))
        new = sum(float(r["headline"]) for r in both) / max(1, len(both))
        worse = []
        for r in both:
            delta = float(r["headline"]) - float(base[r["slug"]]["headline"])
            if delta > 0:
                worse.append(r["slug"])
            print(f"  {r['slug']:>11} {float(base[r['slug']]['headline']):8.4f} -> {float(r['headline']):8.4f} ({delta:+.4f})")
        verdict = "IMPROVED" if new < old else "NOT IMPROVED"
        print(f"SET {old:.4f} -> {new:.4f} ({new - old:+.4f}): {verdict}; maps worse: {len(worse)} of {len(both)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
