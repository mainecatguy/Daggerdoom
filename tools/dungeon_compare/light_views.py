"""Viewpoints that look at a converted dungeon's lights, for compare.py --lit.

Usage: python light_views.py <slug_doors.pk3> <slug.points.txt> <count> [--scale 0.75] > views.txt
Picks <count> light records spread through the DFDLIGHTS list, stands on the walkable node 150 to 350 map units away
from each (preferring 250), and looks at the light. Output is compare.py's viewpoint format, in Daggerfall units.
"""
import argparse
import math
import zipfile

ap = argparse.ArgumentParser()
ap.add_argument("doors")
ap.add_argument("points")
ap.add_argument("count", type=int)
ap.add_argument("--scale", type=float, default=0.75)
args = ap.parse_args()

lights = [tuple(map(float, l.split()[:3])) for l in zipfile.ZipFile(args.doors).read("DFDLIGHTS").decode().split("\n") if l.strip()]
nodes = []
for line in open(args.points):
    p = line.split()
    if p and p[0] == "N":
        nodes.append((float(p[2]), float(p[3]), float(p[4]), float(p[5])))
print("# id | kind | x y floor yaw pitch | note")
step = max(1, len(lights) // args.count)
made = 0
for i in range(0, len(lights), step):
    lx, ly, lz = lights[i]
    best = None
    for x, y, floor, ceiling in nodes:
        d = math.hypot(x - lx, y - ly)
        if not 150 <= d <= 350 or floor > lz or ceiling < lz:
            continue
        score = abs(d - 250) + abs(floor + 41 - lz) * 0.5
        if best is None or score < best[0]:
            best = (score, x, y, floor, d)
    if not best:
        continue
    _, x, y, floor, d = best
    yaw = math.degrees(math.atan2(ly - y, lx - x)) % 360
    pitch = -math.degrees(math.atan2(lz - (floor + 41), d)) * 0.5  # half way to the light: keep the floor in view
    s = args.scale
    print(f"light{i} | light | {x / s:.0f} {y / s:.0f} {floor / s:.0f} {yaw:.1f} {pitch:.1f} | light record {i} at {lx:.0f} {ly:.0f} {lz:.0f}")
    made += 1
    if made >= args.count:
        break
