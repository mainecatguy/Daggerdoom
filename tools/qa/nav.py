"""A* over the dungeon converter's walk graph (<slug>.points.txt), for the QA bot prototype.

The converter already writes, for every converted dungeon, the nodes it walks (a 24-unit lattice of standing spots with
floor and ceiling heights, in Doom map units) and the directed links between them (steps, one-way drops, door crossings).
That graph is what its connectivity and leak checks use, so the bot plans over the same truth the converter checked.

  nav.py <points.txt> <x0> <y0> <z0> <x1> <y1> <z1>     Plan and print the path as JSON with timings.
  nav.py <points.txt> --bench [pairs]                  Plan between random reachable node pairs and print timings.
"""
import heapq
import json
import math
import random
import sys
import time
from collections import defaultdict

STEP = 24  # Doom's step height: a smoothed segment may not climb more than this between samples.


class Graph:
    def __init__(self, path):
        t = time.perf_counter()
        self.nodes = {}  # id -> (x, y, floor, ceiling, door)
        self.links = defaultdict(list)  # id -> [(id, door)]
        self.start = None
        self.lev = set()  # (from, to) links that need levitation
        for line in open(path):
            f = line.split()
            if not f:
                continue
            if f[0] == "N":
                self.nodes[int(f[1])] = (int(f[2]), int(f[3]), int(f[4]), int(f[5]), f[7] == "1")
            elif f[0] == "E":
                self.links[int(f[1])].append((int(f[2]), f[3] == "1"))
            elif f[0] == "S":
                self.start = tuple(map(int, f[2:5]))
        self.cells = defaultdict(list)  # 48-unit buckets for nearest-node lookups
        for n, (x, y, *_rest) in self.nodes.items():
            self.cells[(x // 48, y // 48)].append(n)
        self.load_ms = (time.perf_counter() - t) * 1000

    def near(self, x, y, z, reach=64):
        """The closest node whose floor is at or a little below z (standing spots under the actor first)."""
        best, score = None, 1e18
        cx, cy = int(x) // 48, int(y) // 48
        for i in range(cx - 2, cx + 3):
            for j in range(cy - 2, cy + 3):
                for n in self.cells.get((i, j), ()):
                    nx, ny, fl, _c, _d = self.nodes[n]
                    if fl > z + STEP or fl < z - 256:
                        continue
                    d = math.hypot(nx - x, ny - y) + abs(z - fl) * 2
                    if d < score:
                        best, score = n, d
        return best if score <= reach + 512 else None

    def add_levitation(self, body=56):
        """Adds flight links: up from a node to a ledge beside it (one lattice step away) whose floor is more than a step
        higher and still under this node's ceiling with room for the body. Drops down are already one-way links."""
        added = 0
        by_xy = defaultdict(list)
        for n, (x, y, *_r) in self.nodes.items():
            by_xy[(x, y)].append(n)
        for n, (x, y, f, c, _d) in self.nodes.items():
            for dx in (-24, 0, 24):
                for dy in (-24, 0, 24):
                    if not dx and not dy:
                        continue
                    for m in by_xy.get((x + dx, y + dy), ()):
                        mx, my, mf, mc, _md = self.nodes[m]
                        if mf > f + STEP and mf + body <= c and mf + body <= mc and (m, False) not in self.links[n]:
                            self.links[n].append((m, False))
                            self.lev.add((n, m))
                            added += 1
        return added

    def astar(self, a, b):
        ax, ay, af, *_ = self.nodes[b]
        def h(n):
            x, y, f, *_ = self.nodes[n]
            return math.hypot(x - ax, y - ay)
        frontier = [(h(a), 0.0, a)]
        came, cost = {a: None}, {a: 0.0}
        expanded = 0
        while frontier:
            _, g, n = heapq.heappop(frontier)
            if g > cost[n]:
                continue
            expanded += 1
            if n == b:
                break
            x, y, f, *_ = self.nodes[n]
            for m, _door in self.links[n]:
                mx, my, mf, *_ = self.nodes[m]
                ng = g + math.hypot(mx - x, my - y) + abs(mf - f) * 0.5
                if ng < cost.get(m, 1e18):
                    cost[m], came[m] = ng, n
                    heapq.heappush(frontier, (ng + h(m), ng, m))
        if b not in came:
            return None, expanded
        path = [b]
        while came[path[-1]] is not None:
            path.append(came[path[-1]])
        return path[::-1], expanded

    def reachable(self, s):
        seen, queue = {s}, [s]
        while queue:
            for m, _ in self.links[queue.pop()]:
                if m not in seen:
                    seen.add(m)
                    queue.append(m)
        return seen

    def straight(self, a, b):
        """True when a straight walk from node a to node b stays on graph nodes with no climb over a step."""
        ax, ay, af, *_ = self.nodes[a]
        bx, by, bf, *_ = self.nodes[b]
        steps = max(1, int(math.hypot(bx - ax, by - ay) // 12))
        last = af
        for k in range(1, steps + 1):
            t = k / steps
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            n = self.near(x, y, last, reach=17)
            if n is None:
                return False
            nx, ny, fl, *_ = self.nodes[n]
            if math.hypot(nx - x, ny - y) > 17 or fl - last > STEP or self.nodes[n][4]:
                return False
            last = fl
        return True

    def smooth(self, path):
        """Greedy string pulling: keeps a waypoint only where a straight walk would leave the graph. Door nodes stay."""
        if not path:
            return []
        out, i = [path[0]], 0
        while i < len(path) - 1:
            j = i + 1
            while j + 1 < len(path) and not self.nodes[path[j]][4] and self.straight(path[i], path[j + 1]):
                j += 1
            out.append(path[j])
            i = j
        return out

    def plan(self, x0, y0, z0, x1, y1, z1):
        t = time.perf_counter()
        a, b = self.near(x0, y0, z0), self.near(x1, y1, z1)
        if a is None or b is None:
            return {"ok": False, "error": "no graph node near " + ("start" if a is None else "goal")}
        path, expanded = self.astar(a, b)
        t_astar = time.perf_counter()
        if path is None:
            return {"ok": False, "error": "no walking route (needs levitation, a key, or is cut off)", "expanded": expanded,
                    "ms": round((t_astar - t) * 1000, 1)}
        way = self.smooth(path)
        t_end = time.perf_counter()
        length = sum(math.hypot(self.nodes[p][0] - self.nodes[q][0], self.nodes[p][1] - self.nodes[q][1]) for p, q in zip(path, path[1:]))
        return {"ok": True, "levitate": sum((p, q) in self.lev for p, q in zip(path, path[1:])), "nodes": len(path), "expanded": expanded, "length": round(length), "doors": sum(self.nodes[p][4] for p in path),
                "astar_ms": round((t_astar - t) * 1000, 1), "smooth_ms": round((t_end - t_astar) * 1000, 1),
                "waypoints": [[self.nodes[p][0], self.nodes[p][1], self.nodes[p][2]] for p in way[1:]]}


def bench(g, pairs):
    rng = random.Random(1)
    # Pairs inside the area reachable from the entrance.
    s = g.near(*g.start)
    seen = g.reachable(s)
    pool = sorted(seen)
    times, smooth, lengths, wps = [], [], [], []
    for _ in range(pairs):
        a, b = rng.choice(pool), rng.choice(pool)
        r = g.plan(*(g.nodes[a][:3]), *(g.nodes[b][:3]))
        if r["ok"]:
            times.append(r["astar_ms"]); smooth.append(r["smooth_ms"]); lengths.append(r["length"]); wps.append(len(r["waypoints"]))
    times.sort(); smooth.sort()
    return {"nodes": len(g.nodes), "links": sum(len(v) for v in g.links.values()), "reachable_from_start": len(seen), "load_ms": round(g.load_ms),
            "pairs": len(times), "astar_ms_median": times[len(times) // 2], "astar_ms_max": times[-1], "smooth_ms_median": smooth[len(smooth) // 2],
            "smooth_ms_max": smooth[-1], "length_median": sorted(lengths)[len(lengths) // 2], "waypoints_median": sorted(wps)[len(wps) // 2]}


if __name__ == "__main__":
    g = Graph(sys.argv[1])
    if "--levitate" in sys.argv:
        sys.argv.remove("--levitate")
        walk = len(g.reachable(g.near(*g.start)))
        t = time.perf_counter()
        added = g.add_levitation()
        print(json.dumps({"levitation_links": added, "build_ms": round((time.perf_counter() - t) * 1000), "reachable_walking": walk,
                          "reachable_with_levitation": len(g.reachable(g.near(*g.start))), "nodes": len(g.nodes)}))
    if sys.argv[2:3] == ["--bench"]:
        print(json.dumps(bench(g, int(sys.argv[3]) if len(sys.argv) > 3 else 50)))
    else:
        print(json.dumps(g.plan(*map(float, sys.argv[2:8]))))
