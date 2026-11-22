"""Run the automated map check in UZDoom and report reachability.

Usage: python check_map.py <map.wad> <points.txt> <report.txt> [--timeout 300]
"""
import argparse
import collections
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
ERROR_WORDS = ("VM execution aborted", "Script error", "Execution could not continue", "FATAL", "Unknown texture", "error, ", "Error:")


def run_engine(wad, log, timeout):
    if os.path.exists(log):
        os.remove(log)
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", UZDOOM, "-iwad", IWAD,
               "-file", wad, os.path.join(HERE, "check"), "-noactivate", "-nosound", "-skill", "3",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+set", "dfcheck", "1", "+logfile", os.path.basename(log)[4:-4], "+map", "MAP01"]  # the engine writes log-<name>.txt
    command[2:2] = ["--cwd", os.path.dirname(log)]
    command.insert(command.index("-noactivate"), "-stdout")
    console = open(log + ".console", "w")
    process = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT)
    began = time.time()
    done = False
    while process.poll() is None and time.time() - began < timeout:
        time.sleep(1)
        if os.path.exists(log):
            with open(log, errors="replace") as f:
                if "DFCHK DONE" in f.read():
                    done = True
                    break
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
    console.close()
    if not os.path.exists(log):
        # The engine stopped before opening its log, so use its console output.
        os.replace(log + ".console", log)
    return done, time.time() - began


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wad")
    parser.add_argument("points")
    parser.add_argument("report")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    report = os.path.abspath(args.report)
    stem = "".join(c for c in os.path.splitext(os.path.basename(report))[0] if c.isalnum())
    log = os.path.join(os.path.dirname(report), f"log-{stem}.txt")
    startup = subprocess.run([UZDOOM, "-iwad", IWAD, "-file", os.path.abspath(args.wad), os.path.join(HERE, "check"),
                              "-norun", "-nosound", "-stdout"], capture_output=True, text=True, errors="replace", timeout=90)
    if startup.returncode != 1337:
        lines = (startup.stdout + startup.stderr).splitlines()
        print(f"startup check failed, exit code {startup.returncode}")
        print("\n".join(l[:180] for l in lines if "rror" in l or "FATAL" in l or "zs" in l.lower())[:3000] or "\n".join(lines[-15:]))
        return 1
    done, seconds = run_engine(os.path.abspath(args.wad), log, args.timeout)
    if not done:
        # Without a finished run the log proves nothing about reachability.
        print(f"ENGINE CHECK DID NOT FINISH after {seconds:.0f}s. Log: {log}")
        if os.path.exists(log):
            print("\n".join(l.rstrip()[:180] for l in open(log, errors="replace").readlines()[-12:]))
        return 1

    nodes, edges, blocks, start = {}, [], {}, 0
    for line in open(args.points):
        p = line.split()
        if p[0] == "S":
            start = int(p[1])
        elif p[0] == "B":
            blocks[int(p[1])] = p[2]
        elif p[0] == "N":
            nodes[int(p[1])] = tuple(map(int, p[2:8]))
        elif p[0] == "E":
            edges.append((int(p[1]), int(p[2])))

    bad_nodes, bad_edges, summary, errors = {}, set(), [], []
    with open(log, errors="replace") as f:
        for line in f:
            text = line.strip()
            if any(word in text for word in ERROR_WORDS):
                errors.append(text)
            if not text.startswith("DFCHK"):
                continue
            p = text.split()
            if p[1] == "N":
                bad_nodes[int(p[2])] = p[3:]
            elif p[1] == "E":
                bad_edges.add((int(p[2]), int(p[3])))
            else:
                summary.append(text)

    def reach(usable):
        graph = collections.defaultdict(list)
        for a, b in usable:
            graph[a].append(b)
        seen, queue = {start}, collections.deque([start])
        while queue:
            for n in graph[queue.popleft()]:
                if n not in seen:
                    seen.add(n)
                    queue.append(n)
        return seen

    model = reach(edges)
    engine = reach([e for e in edges if e not in bad_edges and e[0] not in bad_nodes and e[1] not in bad_nodes])
    out = [f"engine run finished: {done} in {seconds:.0f}s", f"script/engine errors: {len(errors)}"]
    out += errors[:10] + summary
    out.append(f"nodes: {len(nodes)}, directed edges: {len(edges)}")
    out.append(f"bad nodes: {len(bad_nodes)}, bad edges: {len(bad_edges)}")
    out.append(f"reachable in source model: {len(model)} ({100 * len(model) / len(nodes):.1f}%)")
    out.append(f"reachable in engine: {len(engine)} ({100 * len(engine) / len(nodes):.1f}%)")
    out.append("per block: name nodes reachable bad_nodes")
    for index in sorted(blocks):
        ids = [n for n, v in nodes.items() if v[4] == index]
        out.append(f"  {blocks[index]} {len(ids)} {sum(n in engine for n in ids)} {sum(n in bad_nodes for n in ids)}")
    out.append("sample bad nodes (id x y floor ceil block | fits engine_floor engine_ceil):")
    for n in list(bad_nodes)[:12]:
        out.append(f"  {n} {nodes[n][:5]} | {' '.join(bad_nodes[n])}")
    out.append("sample bad edges (block, from -> to):")
    for a, b in list(bad_edges)[:12]:
        out.append(f"  {blocks.get(nodes[a][4], '?')} {nodes[a][:3]} -> {nodes[b][:3]}")
    text = "\n".join(out)
    with open(args.report, "w") as f:
        f.write(text + "\n")
    print(text)
    return 0 if done and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
