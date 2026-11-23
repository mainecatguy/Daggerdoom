"""One line per dungeon: blocks, blocks with any link to another block, blocks the walker entered, and links between blocks.

Usage: python seam_summary.py <out dir> <slug> ...
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traverse_all as t

for slug in sys.argv[2:]:
    folder = os.path.join(sys.argv[1], slug)
    nodes, edges, blocks, start = t.load_points(os.path.join(folder, slug + ".points.txt"))
    stage = set()
    for line in open(os.path.join(folder, "log-reach.txt"), errors="replace"):
        p = line.split()
        if len(p) > 3 and p[0] == "DFREACH" and p[1] == "R":
            stage.add(int(p[2]))
    linked = set()
    links = 0
    for a, b, d in edges:
        if nodes[a][4] != nodes[b][4]:
            linked |= {nodes[a][4], nodes[b][4]}
            links += 1
    entered = {nodes[n][4] for n in stage}
    # blocks the walker entered that hold at least 20% of their nodes reached
    per = collections.Counter(nodes[n][4] for n in nodes)
    mostly = [b for b in blocks if sum(1 for n in stage if nodes[n][4] == b) >= 0.2 * per[b]]
    print(f"{slug}: blocks {len(blocks)}, blocks with a link to another block {len(linked)}, directed inter-block links {links}, "
          f"blocks entered {len(entered)}, blocks >=20% reached {len(mostly)}")
