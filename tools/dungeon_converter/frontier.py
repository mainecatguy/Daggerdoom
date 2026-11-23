"""Shows why the engine-reached area of a checked dungeon stops where it does.

Usage: python frontier.py <slug folder> <slug>
Lists the walk edges that leave the engine-reached set, grouped by what the engine said about them.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traverse_all as t

folder, slug = sys.argv[1], sys.argv[2]
nodes, edges, blocks, start = t.load_points(os.path.join(folder, slug + ".points.txt"))
bad, badn = {}, set()
for l in open(os.path.join(folder, f"log-{slug}report.txt"), errors="replace"):
    p = l.split()
    if len(p) > 3 and p[0] == "DFCHK":
        if p[1] == "E": bad[(int(p[2]), int(p[3]))] = int(p[4])
        if p[1] == "N" and p[3] == "0": badn.add(int(p[2]))
adj = collections.defaultdict(list)
for a, b, d in edges:
    if abs(bad.get((a, b), 0)) <= t.STEP and a not in badn and b not in badn:
        adj[a].append(b)
seen = t.bfs(start, adj)
fr, ex = collections.Counter(), collections.defaultdict(list)
for a, b, d in edges:
    if a in seen and b not in seen:
        why = "to-badnode" if b in badn else ("blocked" if bad.get((a, b)) == 9999 else f"dz{bad.get((a, b))}")
        key = (why, "door" if d else "plain")
        fr[key] += 1
        if len(ex[key]) < 5: ex[key].append((nodes[a][:4], nodes[b][:4]))
print(len(seen), "reached")
for k, v in fr.most_common():
    print(k, v)
    for e in ex[k]: print("   ", e)
