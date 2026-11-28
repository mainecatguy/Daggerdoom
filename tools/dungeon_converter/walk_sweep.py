"""Sweep of walk_replay.py runs around one spot on two maps: how often does a run stop dead, and where.

usage: walk_sweep.py <play folder> <old wad> <new wad> --spot x,y --headings a:b:step (in 16ths of a turn)
       [--offsets 8] [--box x0,x1,y0,y1]
Starts are the spot and the spot moved by +-offset in x and y. A run "stops dead" when its last 30 tics move under
1 unit in total; with --box, only stops inside the box are counted (for example one corridor wall). Prints, per map,
the count of dead stops, the summed net distance, and each run where the two maps differ by more than 10 units.
"""
import math, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def option(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def runs_of(text):
    runs, cur = [], None
    for line in text.splitlines():
        if line.startswith("WRRUN"):
            parts = line.split()
            cur = {"heading": float(parts[3]), "path": [(float(parts[5]), float(parts[6]))]}
            runs.append(cur)
        elif line.startswith("WRT") and cur:
            parts = line.split()
            cur["path"].append((float(parts[2]), float(parts[3])))
    return runs


play, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
sx, sy = map(float, option("--spot").split(","))
a, b, step = map(float, option("--headings").split(":"))
off = float(option("--offsets", "8"))
box = [float(v) for v in option("--box").split(",")] if option("--box") else None
starts = [(sx, sy), (sx + off, sy), (sx - off, sy), (sx, sy + off), (sx, sy - off)]
headings = [a + k * step for k in range(int(round((b - a) / step)) + 1)]
spec = ";".join(f"{x},{y},{h}" for (x, y) in starts for h in headings)
labels = [(x, y, h) for (x, y) in starts for h in headings]
result = {}
for name, wad in (("old", old), ("new", new)):
    out = subprocess.run([sys.executable, str(HERE / "walk_replay.py"), play, wad, spec], capture_output=True, text=True).stdout
    runs = runs_of(out)
    if len(runs) != len(labels):
        sys.exit(f"{name}: {len(runs)} runs, expected {len(labels)}")
    rows = []
    for r in runs:
        p = r["path"]
        tail = sum(math.dist(p[i], p[i + 1]) for i in range(len(p) - 31, len(p) - 1))
        end = p[-1]
        stuck = tail < 1 and (not box or (box[0] <= end[0] <= box[1] and box[2] <= end[1] <= box[3]))
        rows.append({"net": math.dist(p[0], end), "end": end, "stuck": stuck})
    result[name] = rows
print(f"# walk_sweep.py {' '.join(sys.argv[1:])}")
for name in ("old", "new"):
    rows = result[name]
    print(f"{name}: runs {len(rows)}, dead stops {sum(r['stuck'] for r in rows)}, net {sum(r['net'] for r in rows):.0f}")
for lab, o, n in zip(labels, result["old"], result["new"]):
    if abs(o["net"] - n["net"]) > 10 or o["stuck"] != n["stuck"]:
        print(f"start {lab[0]:.0f},{lab[1]:.0f} heading {lab[2] * 22.5:6.2f}: old net {o['net']:4.0f} end {o['end'][0]:.1f},{o['end'][1]:.1f}{' STOP' if o['stuck'] else ''}"
              f" | new net {n['net']:4.0f} end {n['end'][0]:.1f},{n['end'][1]:.1f}{' STOP' if n['stuck'] else ''}")
