"""Summarizes the worldcost lines of Daggerfall bridge logs (see DoomerfallWorldCost.cs) as markdown tables.

usage: analyze.py <df.log> [...]
One row per segment (a place Daggerfall was in), from its last frames line, with its settled census and ready time.
"""
import re
import sys
from pathlib import Path


def fields(text):
    return dict(re.findall(r"(\w+)=([^\s|]+)", text))


def segments(path):
    rows = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        m = re.search(r"worldcost (begin|frames|census|ready) (\d+) (\S+)(.*)", line)
        if not m:
            continue
        kind, index, place, rest = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        row = rows.setdefault(index, {"place": place})
        if kind == "begin":
            row["begin"] = fields(rest)
        elif kind == "frames":
            row["frames"] = fields(rest)
            row["hitches"] = re.search(r"hitches=(\S+)", rest).group(1)
        elif kind == "census" and "census" not in row:
            row["census"] = fields(rest)
        elif kind == "ready":
            row["ready"] = re.search(r"after (\d+) ms", rest).group(1)
    return [rows[i] for i in sorted(rows)]


def main():
    for path in sys.argv[1:]:
        print(f"\n### {Path(path).name}\n")
        print("| # | place | s | frames | mean ms | p95 | p99 | max ms | >33 ms | hitches >50 ms | private MB | Unity MB | terrains | renderers | colliders | DF enemies (motors on) | census ms |")
        print("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---:|")
        for i, row in enumerate(segments(path), 1):
            f, c = row.get("frames", {}), row.get("census", {})
            hitches = row.get("hitches", "")
            if len(hitches) > 60:
                hitches = hitches[:57] + "..."
            print("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                i, row["place"], f.get("seconds", ""), f.get("frames", ""), f.get("mean_ms", ""), f.get("p95_ms", ""), f.get("p99_ms", ""),
                f.get("max_ms", ""), f.get("over33", ""), hitches, f.get("private_mb", ""), f.get("unity_alloc_mb", ""),
                c.get("terrains", ""), c.get("renderers", ""), c.get("colliders", ""),
                f"{c['enemies']} ({c['enemy_motors_on']})" if c else "", c.get("census_ms", "")))


if __name__ == "__main__":
    main()
