"""Clusters the converter links that the engine walker refused (reached node -> unreached node), to see what they have in common.

Usage: python refused.py <dungeon folder> <slug>
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
refused = [(a, b, d) for a, b, d in edges if stage.get(a) and not stage.get(b)]
clusters = collections.defaultdict(list)
for a, b, d in refused:
    clusters[(nodes[a][0] // 96, nodes[a][1] // 96, nodes[a][2])].append((nodes[a][:4], nodes[b][:4], d))
print(len(refused), "refused links in", len(clusters), "clusters")
for k, v in sorted(clusters.items(), key=lambda kv: -len(kv[1]))[:8]:
    print(k, len(v), v[0])
print("height change across the link:", collections.Counter(nodes[b][2] - nodes[a][2] for a, b, d in refused).most_common(6))
print("ceiling at the target node (height of the opening):", collections.Counter(nodes[b][3] - nodes[b][2] for a, b, d in refused).most_common(6))
