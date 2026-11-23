"""Estimates how much of Scourg Barrow the player can reach from the entrance, using the converter's walk graph.

Usage: python tools/dungeon_converter/action_reach.py <scourgbarrow.points.txt> <actions.txt>
Stages add: walking, falling off ledges, the two coffin shafts proven in game, and the three lifts.
All doors count as usable and moving objects as out of the way. It is an estimate, not a play-through.
"""
import collections
import re
import sys

nodes, adj = {}, collections.defaultdict(set)
for line in open(sys.argv[1]):
    f = line.split()
    if f and f[0] == "N":
        nodes[int(f[1])] = (int(f[2]), int(f[3]), int(f[4]), int(f[5]))
    elif f and f[0] == "E":
        adj[int(f[1])].add(int(f[2]))
cells = collections.defaultdict(list)
for n, (x, y, _, _) in nodes.items():
    cells[(x, y)].append(n)
start = min(nodes, key=lambda n: abs(nodes[n][0] - 672) + abs(nodes[n][1] - 439) + abs(nodes[n][2] - 1344))


def near(x, y, radius):
    return [n for n, v in nodes.items() if abs(v[0] - x) <= radius and abs(v[1] - y) <= radius]


def flood(edges):
    seen, stack = {start}, [start]
    while stack:
        for v in edges[stack.pop()]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def report(name, seen):
    print(f"{name}: {len(seen)} of {len(nodes)} positions ({100 * len(seen) / len(nodes):.1f}%)")


edges = collections.defaultdict(set, {k: set(v) for k, v in adj.items()})
report("walking", flood(edges))
for n, (x, y, fl, _) in nodes.items():  # step off a ledge into a neighboring column with room at this height
    for dx, dy in ((12, 0), (-12, 0), (0, 12), (0, -12), (24, 0), (-24, 0), (0, 24), (0, -24)):
        for m in cells.get((x + dx, y + dy), ()):
            if nodes[m][2] < fl - 24 and nodes[m][3] >= fl + 40:
                edges[n].add(m)
report("plus falling", flood(edges))
for x, y in ((480, 672), (672, 864)):  # coffins over shafts; see action_check
    tops = [n for n in near(x, y, 84) if abs(nodes[n][2] - 1344) <= 8]
    bottoms = [n for n in near(x, y, 30) if abs(nodes[n][2] - 1152) <= 8]
    for a in tops:
        edges[a].update(bottoms)
report("plus coffin shafts", flood(edges))
lifts, records = [], []
for line in open(sys.argv[2]):
    at = re.search(r" at (-?\d+),(-?\d+),(-?\d+)", line)
    if at:
        records.append((int(at[1]), int(at[2])))
    m = re.search(r"m72019 LXG .* mag=(\d+) .* at (-?\d+),(-?\d+),(-?\d+)", line)
    if m:
        lifts.append((int(m[2]), int(m[3]), int(m[4]), int(m[1]) * 0.75))
for x, y, z, travel in lifts:
    stops = [n for n in near(x, y, 72) if z - travel - 48 <= nodes[n][2] <= z + 48]
    for a in stops:
        edges[a].update(stops)
seen = flood(edges)
report(f"plus {len(lifts)} lifts", seen)
for a, targets in list(adj.items()):  # a walk link that only runs downhill can be climbed by a jump: 32 up plus a 24 step
    for b in targets:
        if nodes[a][2] - nodes[b][2] <= 56:
            edges[b].add(a)
seen = flood(edges)
report("plus jumping up ledges of at most 56", seen)

left, parts = set(nodes) - seen, []
undirected = collections.defaultdict(set)
for a, targets in adj.items():
    for b in targets:
        undirected[a].add(b)
        undirected[b].add(a)
while left:
    stack, part = [left.pop()], []
    while stack:
        u = stack.pop()
        part.append(u)
        for v in undirected[u]:
            if v in left:
                left.remove(v)
                stack.append(v)
    parts.append(part)
parts.sort(key=len, reverse=True)
print(f"unreached: {sum(map(len, parts))} positions in {len(parts)} areas; largest:")
for part in parts[:8]:
    v = nodes[part[0]]
    gap = min(max(abs(nodes[n][0] - a[0]), abs(nodes[n][1] - a[1])) for n in part[::4] for a in records)
    print(f"  {len(part)} positions near {v[0]},{v[1]} floor {min(nodes[n][2] for n in part)}..{max(nodes[n][2] for n in part)}, nearest action record {gap} units")
