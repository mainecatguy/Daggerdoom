"""Counts the converter's links between different blocks, and how many of those the engine walker used.

Usage: python seams.py <dungeon folder> <slug>
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traverse_all as t

folder, slug = sys.argv[1], sys.argv[2]
nodes, edges, blocks, start = t.load_points(os.path.join(folder, slug + ".points.txt"))
stage = {}
for line in open(os.path.join(folder, "log-reach.txt"), errors="replace"):
    p = line.split()
    if len(p) > 3 and p[0] == "DFREACH" and p[1] == "R":
        stage[int(p[2])] = int(p[3])
pairs = collections.Counter()
for a, b, d in edges:
    if nodes[a][4] != nodes[b][4] and a < b:
        pairs[(blocks[nodes[a][4]], blocks[nodes[b][4]], bool(stage.get(a)), bool(stage.get(b)))] += 1
print("block of the start node:", blocks[nodes[start][4]], "of", len(blocks), "blocks")
print("links between blocks (block, block, a reached, b reached): count")
for k, v in sorted(pairs.items()):
    print(" ", k, v)
reached_by_block = collections.Counter(blocks[nodes[n][4]] for n in nodes if stage.get(n))
total_by_block = collections.Counter(blocks[nodes[n][4]] for n in nodes)
print("reached per block:", {b: f"{reached_by_block[b]}/{total_by_block[b]}" for b in sorted(total_by_block)})
