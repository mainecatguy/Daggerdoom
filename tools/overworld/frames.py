"""Summarizes a run's frame log. Usage: frames.py NAME [NAME...]"""
import csv, os, sys

WORK = r"D:\dev\DoomDaggerfall-build\overworld-tests"


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p / 100 * (len(v) - 1) + 0.5))] if v else float("nan")


for name in sys.argv[1:]:
    rows = [{k: float(x) for k, x in r.items()} for r in csv.DictReader(open(os.path.join(WORK, name + ".csv"))) if r.get("shift") not in (None, "")][60:]
    shift = [i for i, r in enumerate(rows) if r["shift"] == 1]
    near = {j for i in shift for j in range(i, min(i + 3, len(rows)))}
    other = [r["frame_us"] / 1000 for i, r in enumerate(rows) if i not in near]
    hit = [rows[i]["frame_us"] / 1000 for i in shift]
    sim = [rows[i]["sim_us"] / 1000 for i in shift]
    moved = [int(r["moved"]) for r in csv.DictReader(open(os.path.join(WORK, name + ".csv.shifts.csv")))]
    print(f"{name}: frames={len(rows)} shifts={len(shift)} actorsMoved max={max(moved) if moved else 0}")
    print(f"  other frames ms: median {pct(other, 50):.2f}, p99 {pct(other, 99):.2f}, worst {max(other):.2f}")
    print(f"  shift frames ms: median {pct(hit, 50):.2f}, worst {max(hit) if hit else 0:.2f}; shift simulation ms: median {pct(sim, 50):.2f}, worst {max(sim) if sim else 0:.2f}")
