"""Compare the converter's connected areas with a flood fill over Daggerfall Unity's real collision.

Usage: python tools/dungeon_compare/flood_report.py <converted>.points.txt <compare output dir>
"""
import collections
import os
import sys

XY_MATCH, Z_MATCH = 16, 24


def load_points(path):
    nodes, links, start = {}, collections.defaultdict(set), None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "S":
            start = int(p[1])
        elif p[0] == "N":
            nodes[int(p[1])] = (int(p[2]), int(p[3]), int(p[4]), int(p[6]))
        elif p[0] == "E":
            links[int(p[1])].add(int(p[2]))
    return nodes, links, start


def areas(nodes, links, start):
    # Links are treated as undirected so that a one-way drop stays part of its area.
    both = collections.defaultdict(set)
    for a, targets in links.items():
        for b in targets:
            both[a].add(b)
            both[b].add(a)
    seen, result = set(), []
    for first in [start] + list(nodes):
        if first in seen:
            continue
        seen.add(first)
        part, stack = [], [first]
        while stack:
            at = stack.pop()
            part.append(at)
            for other in both[at]:
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        result.append(part)
    return [result[0]] + sorted(result[1:], key=len, reverse=True)


def main():
    nodes, links, start = load_points(sys.argv[1])
    parts = areas(nodes, links, start)
    for name in ("walk", "jump"):
        path = os.path.join(sys.argv[2], f"df_flood_{name}.txt")
        if not os.path.exists(path):
            print("missing", path)
            continue
        grid = collections.defaultdict(list)
        count = 0
        for line in open(path):
            x, y, z = (float(v) for v in line.split())
            grid[(int(x // XY_MATCH), int(y // XY_MATCH))].append(z)
            count += 1

        def reached(node):
            x, y, floor, _ = node
            cx, cy = x // XY_MATCH, y // XY_MATCH
            return any(abs(z - floor) <= Z_MATCH for i in (-1, 0, 1) for j in (-1, 0, 1) for z in grid.get((cx + i, cy + j), ()))

        hit = sum(reached(n) for n in nodes.values())
        print(f"\n{name}: {count} Daggerfall standing positions; {hit} of {len(nodes)} converter nodes ({100 * hit / len(nodes):.1f}%) are near one")
        print("area  nodes  reached_in_daggerfall  floors  sample")
        for index, part in enumerate(parts[:16]):
            got = sum(reached(nodes[i]) for i in part)
            floors = [nodes[i][2] for i in part]
            x, y, z, _ = nodes[part[len(part) // 2]]
            label = "entrance" if index == 0 else str(index)
            print(f"{label:>8} {len(part):6} {got:6} ({100 * got / len(part):5.1f}%)  {min(floors)}..{max(floors)}  {x},{y},{z}")


if __name__ == "__main__":
    main()
