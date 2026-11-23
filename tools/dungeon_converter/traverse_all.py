"""Convert dungeons, run the in-engine check, and classify what the player can reach.

Usage: python traverse_all.py --out <dir outside the repo> [--timeout 600] [--only name_or_id ...] <"#mapid" or "name"> ...
Writes <out>/<slug>/<slug>.wad etc. and <out>/<slug>/traverse.txt, then prints one summary line per dungeon.
The traversal numbers come from check_map.py's engine run (edges the engine refused are removed) plus the
converter's own graph. Unreached areas are grouped and labelled by a geometric rule only; see the notes file.
"""
import argparse
import collections
import math
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = 24  # the converter's player step height; a bigger gap to a neighbour needs climbing, a lift, or a jump


def load_points(path):
    nodes, edges, blocks, start = {}, [], {}, 0
    for line in open(path):
        p = line.split()
        if p[0] == "S":
            start = int(p[1])
        elif p[0] == "B":
            blocks[int(p[1])] = p[2]
        elif p[0] == "N":
            nodes[int(p[1])] = tuple(map(int, p[2:9]))  # x y floor ceil block door
        elif p[0] == "E":
            edges.append((int(p[1]), int(p[2]), int(p[3])))
    return nodes, edges, blocks, start


def bfs(start, adj):
    seen, queue = {start}, collections.deque([start])
    while queue:
        for n in adj[queue.popleft()]:
            if n not in seen:
                seen.add(n)
                queue.append(n)
    return seen


def analyse(points, log, out_path, name, seconds):
    nodes, edges, blocks, start = load_points(points)
    bad_nodes, bad_edges = set(), set()
    for line in open(log, errors="replace"):
        p = line.split()
        if len(p) > 3 and p[0] == "DFCHK":
            if p[1] == "N":
                if p[3] == "0":  # the log is "N node fits floor ceil"; a node whose floor is off but where the body fits is a slope, not a wall
                    bad_nodes.add(int(p[2]))
            elif p[1] == "E":
                dz = int(p[4]) if len(p) > 4 else 9999  # 9999 = blocked; otherwise the height error, and a step above 24 cannot be walked
                if abs(dz) > STEP:
                    bad_edges.add((int(p[2]), int(p[3])))
    full, good, undirected = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    door_edge = {}
    for a, b, d in edges:
        full[a].append(b)
        undirected[a].append(b)
        undirected[b].append(a)
        if d:
            door_edge[(a, b)] = True
        if (a, b) not in bad_edges and a not in bad_nodes and b not in bad_nodes:
            good[a].append(b)
    model = bfs(start, full)
    engine = bfs(start, good)
    # Areas the player cannot reach, grouped by the converter's own undirected connectivity (so one-way drops stay together).
    left = set(nodes) - engine
    groups, seen = [], set()
    for n in sorted(left):
        if n in seen:
            continue
        comp = bfs(n, {k: [m for m in undirected[k] if m in left] for k in left})
        seen |= comp
        groups.append(comp)
    groups.sort(key=len, reverse=True)
    lines = [f"dungeon: {name}", f"nodes {len(nodes)}  reachable-model {len(model)} ({100*len(model)/len(nodes):.1f}%)  reachable-engine {len(engine)} ({100*len(engine)/len(nodes):.1f}%)",
             f"engine-bad nodes {len(bad_nodes)}  bad edges {len(bad_edges)}  doors on {sum(1 for n in nodes.values() if n[5])} nodes  check-seconds {seconds:.0f}",
             f"unreached groups: {len(groups)}"]
    reached_nodes = [nodes[n] for n in engine]
    grid = collections.defaultdict(list)
    for x, y, f, c, b, d, *_ in reached_nodes:
        grid[(x // 64, y // 64)].append((x, y, f, c))
    kinds = collections.Counter()
    detail = []
    for comp in groups:
        xs = [nodes[n][0] for n in comp]
        ys = [nodes[n][1] for n in comp]
        fs = [nodes[n][2] for n in comp]
        blk = collections.Counter(blocks.get(nodes[n][4], "?") for n in comp).most_common(1)[0][0]
        # Closest reached node in plan, sampled over every member (members are 16 units apart).
        best = None
        for n in comp if len(comp) < 400 else list(comp)[:: max(1, len(comp) // 400)]:
            x, y, f, c, *_ = nodes[n]
            for gx in range(x // 64 - 1, x // 64 + 2):
                for gy in range(y // 64 - 1, y // 64 + 2):
                    for rx, ry, rf, rc in grid.get((gx, gy), ()):
                        d = math.hypot(rx - x, ry - y)
                        if d <= 40 and rc > f + 40 and f + 40 < rc:  # overlapping the player's body height
                            dz = f - rf
                            if best is None or (abs(dz), d) < (abs(best[0]), best[1]):
                                best = (dz, d)
        if best is None:
            kind = "no-neighbour (sealed in the converted data, or behind an action/teleporter)"
        elif abs(best[0]) > STEP:
            kind = f"height-gap ({best[0]:+d} units to the nearest reached floor: climb, lift, jump or levitate)"
        else:
            kind = "step-ok-but-unlinked (converter edge missing or engine refused it: suspect Broken)"
        kinds[kind.split(" ")[0]] += len(comp)
        detail.append(f"  group {len(comp):6d} nodes  x {min(xs)}..{max(xs)}  y {min(ys)}..{max(ys)}  floor {min(fs)}..{max(fs)}  block {blk}  -> {kind}")
    lines += detail[:25]
    if len(detail) > 25:
        lines.append(f"  ... {len(detail) - 25} smaller groups, {sum(len(g) for g in groups[25:])} nodes")
    lines.append("unreached nodes by label: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
    lines.append("per block (name nodes reached): " + "; ".join(
        f"{blocks[i]} {sum(1 for n in nodes if nodes[n][4] == i)}/{sum(1 for n in engine if nodes[n][4] == i)}" for i in sorted(blocks)))
    open(out_path, "w").write("\n".join(lines) + "\n")
    return lines[:4] + ["unreached by label: " + lines[-2]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dungeons", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    repo = os.path.normcase(os.path.dirname(os.path.dirname(HERE)))
    if (os.path.normcase(out) + os.sep).startswith(repo + os.sep):
        sys.exit("--out must be outside the repository")
    for name in args.dungeons:
        slug = "".join(c for c in name if c.isalnum()).lower()
        folder = os.path.join(out, slug)
        os.makedirs(folder, exist_ok=True)
        began = time.time()
        convert = subprocess.run(["dotnet", "run", "-c", "Release", "-v", "q", "--no-build", "--project", os.path.join(HERE, "DungeonConverter.csproj"),
                                  "--", name, "--out", folder], capture_output=True, text=True, errors="replace")
        convert_seconds = time.time() - began
        open(os.path.join(folder, "convert.log"), "w").write(convert.stdout + convert.stderr)
        if convert.returncode:
            print(f"{name}: CONVERT FAILED ({convert.returncode}): {(convert.stdout + convert.stderr).strip().splitlines()[-1][:200]}")
            continue
        base = os.path.join(folder, slug)
        check = subprocess.run([sys.executable, os.path.join(HERE, "check_map.py"), base + ".wad", base + ".points.txt", base + ".report.txt",
                                "--timeout", str(args.timeout)], capture_output=True, text=True, errors="replace")
        open(os.path.join(folder, "check.log"), "w").write(check.stdout + check.stderr)
        log = os.path.join(folder, "log-" + re.sub(r"[^A-Za-z0-9]", "", slug + "report") + ".txt")
        if not os.path.exists(log):
            print(f"{name}: no engine log; {check.stdout.strip()[-300:]}")
            continue
        m = re.search(r"engine run finished: \w+ in (\d+)s", open(base + ".report.txt").read()) if os.path.exists(base + ".report.txt") else None
        seconds = float(m.group(1)) if m else 0
        print(f"== {name}: convert {convert_seconds:.0f}s, wad {os.path.getsize(base + '.wad') / 1e6:.1f} MB, check exit {check.returncode}")
        print("\n".join(analyse(base + ".points.txt", log, os.path.join(folder, "traverse.txt"), name, seconds)))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
