"""Summarizes a -ddtranslog profile: one row per transition, plus the slowest phases.

Usage: analyze.py LOG [--phases N]
wall is real time, cpu is main-thread CPU time, and wait is wall minus cpu (disk, GPU driver, other threads).
The worst frame is the longest frame from the transition's start until one second after arrival.
"""
import argparse
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument("log")
ap.add_argument("--phases", type=int, default=6)
args = ap.parse_args()

marks, frames = [], []
for line in open(args.log, errors="replace"):
    p = line.strip().split(",")
    if p[0] == "M" and len(p) == 8:
        marks.append((float(p[1]), p[2], float(p[3]), float(p[4]), float(p[5]), float(p[6]), float(p[7])))
    elif p[0] == "F" and len(p) == 3:
        frames.append((float(p[1]), float(p[2])))

starts = [i for i, m in enumerate(marks) if m[1].startswith("leave>")]
print("target    wall_ms  cpu_ms  wait_ms  read_MB  worst_frame_ms  private_MB  top phases (wall ms)")
for n, i in enumerate(starts):
    end = starts[n + 1] if n + 1 < len(starts) else len(marks)
    arrive = next((k for k in range(i + 1, end) if marks[k][1] == "arrive"), None)
    if arrive is None:
        continue
    # Work that lands in the first drawn frame, such as the mesh upload, belongs to this transition.
    last = arrive
    for k in range(arrive + 1, end):
        if marks[k][0] - marks[arrive][0] < 1000:
            last = k
    phases = defaultdict(float)
    wall = cpu = read = 0.0
    for m in marks[i + 1:last + 1]:
        if m[1].startswith("sechash_"):  # The check itself, which only runs when profiling.
            continue
        phases[m[1]] += m[2]
        wall += m[2]
        cpu += m[3]
        read += m[4]
    t0, t1 = marks[i][0], marks[arrive][0] + 1000
    worst = max((ms for t, ms in frames if t0 <= t <= t1), default=0)
    top = sorted(phases.items(), key=lambda kv: -kv[1])[:args.phases]
    print(f"{marks[i][1][6:]:9} {wall:7.1f} {cpu:7.1f} {wall - cpu:8.1f} {read / 1024:8.1f} {worst:15.1f} {marks[last][6]:11.0f}  " + " ".join(f"{k}={v:.0f}" for k, v in top))
