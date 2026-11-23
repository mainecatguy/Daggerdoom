"""Converts dungeons and walks a player-sized body through each in UZDoom, then classifies what was reached.

Usage: python reach_all.py --out <dir outside the repo> [--timeout 300] [--reuse] "#<map id>" ...
Per dungeon it writes, under <out>/<id>/: <id>.wad, <id>.points.txt, actions.txt, log-reach.txt, reach.txt (the report).
The engine does the walking (reach/zscript.zs): 21 wide, 56 tall (28 crouched), step 24 (40 when jumping), any fall allowed.
Doors count as open because they are separate objects; locks, lifts, switches, spells and riddles are not modelled,
so areas that only those open stay unreached. Unreached areas are labelled by a geometric rule and by nearby action records.
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
sys.path.insert(0, HERE)
import traverse_all as t  # noqa: E402  (load_points, bfs)

UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
STAGES = {1: "walk", 2: "crouch", 3: "jump"}
# Action record types from DaggerfallAction.cs (the "flag" field). Seams wait on Daggerfall systems; the rest the action system runs.
FLAG_NAMES = {1: "move", 2: "move", 3: "move", 4: "move", 5: "move", 6: "move", 7: "move", 8: "rotate", 9: "spell", 11: "text", 12: "riddle",
              14: "teleport", 16: "lock", 17: "unlock", 18: "opendoor", 20: "closedoor", 21: "damage", 22: "damage", 23: "damage", 24: "damage", 25: "damage",
              26: "poison", 28: "magicka", 29: "dialogue", 30: "chain", 31: "questvar", 99: "doortext"}


def convert(name, folder, extra):
    r = subprocess.run(["dotnet", "run", "-c", "Release", "-v", "q", "--no-build", "--project", os.path.join(HERE, "DungeonConverter.csproj"),
                        "--", name, "--out", folder] + extra, capture_output=True, text=True, errors="replace")
    return r.returncode, r.stdout + r.stderr


def run_engine(wad, log, timeout):
    """Returns (finished, seconds until the map was loaded, total seconds)."""
    if os.path.exists(log):
        os.remove(log)
    stem = os.path.basename(log)[4:-4]
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--cwd", os.path.dirname(log), "--", UZDOOM, "-iwad", IWAD, "-stdout",
               "-file", wad, os.path.join(HERE, "reach"), "-noactivate", "-nosound", "-skill", "3",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+set", "dfreach", "1", "+logfile", stem, "+map", "MAP01"]
    console = open(log + ".console", "w")
    process = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT)
    began = time.time()
    loaded = None
    done = False
    while process.poll() is None and time.time() - began < timeout:
        time.sleep(1)
        if os.path.exists(log):
            text = open(log, errors="replace").read()
            if loaded is None and "DFREACH LOADED" in text:
                loaded = time.time() - began
            if "DFREACH DONE" in text:
                done = True
                break
            if loaded is None and time.time() - began > 45:
                break  # the engine sometimes stalls before the map starts; the caller retries once
            if "Script error" in text or "FATAL" in text or "VM execution aborted" in text:
                break  # a fatal error ends the launch at once
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    console.close()
    if not os.path.exists(log):
        os.replace(log + ".console", log)
    return done, loaded, time.time() - began


def read_actions(path):
    acts = []
    if not os.path.exists(path):
        return acts
    for line in open(path):
        m = re.match(r"ACT (\d+) (\S+) (\S+) (\S+) (.*?) flag=(\d+) .* at (-?\d+),(-?\d+),(-?\d+)", line)
        if m:
            acts.append(dict(id=int(m[1]), kind=m[3], desc=m[5], flag=int(m[6]), pos=(int(m[7]), int(m[8]), int(m[9]))))
    return acts


def analyse(folder, slug, name, load_seconds, total_seconds, done):
    nodes, edges, blocks, start = t.load_points(os.path.join(folder, slug + ".points.txt"))
    stage_of = {n: 0 for n in nodes}
    errors = []
    log = os.path.join(folder, "log-reach.txt")
    loaded_line = None
    for line in open(log, errors="replace"):
        p = line.split()
        if len(p) > 3 and p[0] == "DFREACH" and p[1] == "R":
            stage_of[int(p[2])] = int(p[3])
        elif "DFREACH LOADED" in line or "DFREACH STAGE" in line or "DFREACH DONE" in line or "DFREACH SCANNED" in line:
            loaded_line = (loaded_line or "") + line.strip() + "\n"
        elif any(w in line for w in ("Script error", "VM execution aborted", "FATAL")):
            errors.append(line.strip())
    counts = collections.Counter(stage_of.values())
    total = len(nodes)
    cum = {s: sum(counts[k] for k in range(1, s + 1)) for s in (1, 2, 3)}
    out = [f"dungeon: {name} ({slug})", f"blocks {len(blocks)}  nodes {total}  engine finished: {done}  load {load_seconds if load_seconds is None else round(load_seconds)}s  total {total_seconds:.0f}s (wall clock, minimized window)",
           "reached by: " + "  ".join(f"{STAGES[s]} {cum[s]} ({100 * cum[s] / total:.1f}%)" for s in (1, 2, 3)) + f"  unreached {counts[0]} ({100 * counts[0] / total:.1f}%)"]
    if errors:
        out.append("engine errors: " + " | ".join(errors[:3]))
    acts = read_actions(os.path.join(folder, "actions.txt"))
    kinds = collections.Counter(FLAG_NAMES.get(a["flag"], f"type{a['flag']}") for a in acts)
    out.append(f"action records {len(acts)} ({sum(1 for a in acts if a['kind'] == 'door')} on doors): " + (", ".join(f"{k} {v}" for k, v in kinds.most_common()) or "none"))

    # The converter's own link graph, for comparison: links from the engine-reached set into unreached nodes mean the engine
    # refused a move the converter expected (suspect Broken); none means the data has no walkable link there.
    full = collections.defaultdict(list)
    for a, b, _ in edges:
        full[a].append(b)
    model = t.bfs(start, full)
    refused = [(a, b, d) for a, b, d in edges if stage_of[a] and not stage_of[b]]
    out.append(f"converter link graph reaches {len(model)} ({100 * len(model) / total:.1f}%); links from engine-reached to unreached nodes: {len(refused)} ({sum(1 for r in refused if r[2])} through doors)")
    for a, b, d in refused[:3]:
        out.append(f"    e.g. {nodes[a][:4]} -> {nodes[b][:4]}{' door' if d else ''}")
    out.append(f"start node {nodes[start][:4]}")

    # Unreached groups, by the converter's own undirected connectivity.
    undirected = collections.defaultdict(list)
    for a, b, _ in edges:
        undirected[a].append(b)
        undirected[b].append(a)
    left = {n for n in nodes if stage_of[n] == 0}
    reached = [n for n in nodes if stage_of[n] != 0]
    grid = collections.defaultdict(list)
    for n in reached:
        x, y, f, c = nodes[n][:4]
        grid[(x // 64, y // 64)].append((x, y, f, c))
    agrid = collections.defaultdict(list)
    for a in acts:
        agrid[(a["pos"][0] // 128, a["pos"][1] // 128)].append(a)
    groups, seen = [], set()
    left_adj = {k: [m for m in undirected[k] if m in left] for k in left}
    for n in sorted(left):
        if n in seen:
            continue
        comp = t.bfs(n, left_adj)
        seen |= comp
        groups.append(comp)
    groups.sort(key=len, reverse=True)
    labels = collections.Counter()
    for comp in groups:
        xs = [nodes[n][0] for n in comp]
        ys = [nodes[n][1] for n in comp]
        fs = [nodes[n][2] for n in comp]
        sample = list(comp) if len(comp) < 300 else list(comp)[:: max(1, len(comp) // 300)]
        best = None
        near_act = collections.Counter()
        for n in sample:
            x, y, f, c = nodes[n][:4]
            for gx in range(x // 64 - 1, x // 64 + 2):
                for gy in range(y // 64 - 1, y // 64 + 2):
                    for rx, ry, rf, rc in grid.get((gx, gy), ()):
                        d = math.hypot(rx - x, ry - y)
                        if d <= 40 and rc > f + 28 and f + 28 < rc:
                            dz = f - rf
                            if best is None or (abs(dz), d) < (abs(best[0]), best[1]):
                                best = (dz, d)
            for gx in range(x // 128 - 1, x // 128 + 2):
                for gy in range(y // 128 - 1, y // 128 + 2):
                    for a in agrid.get((gx, gy), ()):
                        if math.hypot(a["pos"][0] - x, a["pos"][1] - y) <= 96 and abs(a["pos"][2] - f) <= 160:
                            near_act[FLAG_NAMES.get(a["flag"], f"type{a['flag']}")] += 1
        if best is None:
            kind = "sealed"  # no reached floor beside it in the converted data
        elif abs(best[0]) > 24:
            kind = f"height-gap {best[0]:+d}"
        else:
            kind = "step-ok-but-unreached"  # suspect Broken
        key = kind.split()[0]
        labels[key] += len(comp)
        if len(comp) >= 40:
            near = ", ".join(f"{k}x{v}" for k, v in near_act.most_common(3)) or "no action record within 96"
            out.append(f"  group {len(comp):6d} nodes  x {min(xs)}..{max(xs)} y {min(ys)}..{max(ys)} floor {min(fs)}..{max(fs)}  -> {kind}; actions nearby: {near}")
    big = sum(1 for g in groups if len(g) >= 40)
    if len(groups) > big:
        out.append(f"  ... {len(groups) - big} smaller groups, {sum(len(g) for g in groups if len(g) < 40)} nodes")
    out.append("unreached nodes by label: " + ", ".join(f"{k} {v}" for k, v in labels.items()))
    open(os.path.join(folder, "reach.txt"), "w").write("\n".join(out) + "\n")
    return out[:3] + ["unreached by label: " + out[-1]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dungeons", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--analyse-only", action="store_true", help="redo the report from an existing engine log")
    parser.add_argument("--reuse", action="store_true", help="skip conversion when the wad already exists")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    repo = os.path.normcase(os.path.dirname(os.path.dirname(HERE)))
    if (os.path.normcase(out) + os.sep).startswith(repo + os.sep):
        sys.exit("--out must be outside the repository")
    for name in args.dungeons:
        slug = "".join(c for c in name if c.isalnum()).lower()
        folder = os.path.join(out, slug)
        os.makedirs(folder, exist_ok=True)
        base = os.path.join(folder, slug)
        if args.analyse_only:
            print(f"== {name}")
            print("\n".join(analyse(folder, slug, name, None, 0, True)))
            continue
        began = time.time()
        if not (args.reuse and os.path.exists(base + ".wad")):
            code, text = convert(name, folder, [])
            open(os.path.join(folder, "convert.log"), "w").write(text)
            if code:
                print(f"{name}: CONVERT FAILED ({code}): {text.strip().splitlines()[-1][:200] if text.strip() else ''}")
                continue
        convert_seconds = time.time() - began
        convert(name, folder, ["--action-dump"])
        done, loaded, total = run_engine(base + ".wad", os.path.join(folder, "log-reach.txt"), args.timeout)
        if loaded is None:
            print(f"{name}: engine stalled before the map started; retrying once")
            done, loaded, total = run_engine(base + ".wad", os.path.join(folder, "log-reach.txt"), args.timeout)
        if loaded is None:
            print(f"{name}: UNKNOWN, the engine never reached the map twice (see log-reach.txt)")
            continue
        if not os.path.exists(base + ".points.txt"):
            print(f"{name}: no points file")
            continue
        print(f"== {name}: convert {convert_seconds:.0f}s, wad {os.path.getsize(base + '.wad') / 1e6:.1f} MB")
        print("\n".join(analyse(folder, slug, name, loaded, total, done)))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
