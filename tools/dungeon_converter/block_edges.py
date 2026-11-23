"""For each block: its node bounding box and how many of its nodes lie within 30 units of the block's outer rectangle edge,
split by whether that edge touches another block (a neighbour's nodes lie just across it).

Usage: python block_edges.py <dungeon folder> <slug>
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traverse_all as t

folder, slug = sys.argv[1], sys.argv[2]
nodes, edges, blocks, start = t.load_points(os.path.join(folder, slug + ".points.txt"))
SIDE = 1536  # 2048 Daggerfall units at the 0.75 scale
by = collections.defaultdict(list)
for n, v in nodes.items():
    by[v[4]].append(v)
occupied = {}
for b, vs in by.items():
    bx = min(v[0] for v in vs) // SIDE
    by_ = min(v[1] for v in vs) // SIDE
    occupied[(bx, by_)] = b
for b, vs in sorted(by.items()):
    cx, cy = min(v[0] for v in vs) // SIDE, min(v[1] for v in vs) // SIDE
    x0, y0 = cx * SIDE, cy * SIDE
    sides = {"west": lambda v: v[0] < x0 + 30, "east": lambda v: v[0] > x0 + SIDE - 30,
             "south": lambda v: v[1] < y0 + 30, "north": lambda v: v[1] > y0 + SIDE - 30}
    nb = {"west": (cx - 1, cy), "east": (cx + 1, cy), "south": (cx, cy - 1), "north": (cx, cy + 1)}
    text = []
    for s, f in sides.items():
        text.append(f"{s}:{sum(1 for v in vs if f(v))}{'->' + blocks[occupied[nb[s]]][:9] if nb[s] in occupied else '(void)'}")
    print(f"{blocks[b]} cell ({cx},{cy}) nodes {len(vs)}  " + "  ".join(text))
