"""Prints the nodes within 30 units of a vertical or horizontal line, to compare the two sides of a block seam.

Usage: python seam_nodes.py <dungeon folder> <slug> x|y <coordinate>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traverse_all as t

folder, slug, axis, at = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
nodes, edges, blocks, start = t.load_points(os.path.join(folder, slug + ".points.txt"))
i = 0 if axis == "x" else 1
rows = sorted((v[1 - i], v[i], v[2], v[3], blocks[v[4]][:9], n) for n, v in nodes.items() if abs(v[i] - at) <= 30)
for r in rows:
    print(f"{'y' if axis == 'x' else 'x'}={r[0]} {axis}={r[1]} floor {r[2]} ceil {r[3]} {r[4]} node {r[5]}")
