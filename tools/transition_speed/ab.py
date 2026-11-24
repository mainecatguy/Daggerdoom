"""Alternates the previous and new engine on the same door routes, so machine load affects both alike.

Usage: ab.py [rounds]
Reads the engine's own DDSTITCH arrival time, which both builds log. It runs from leaving one map to arriving in the next.
Runs are minimized. Load times are CPU work and remain meaningful, but frame rates between loads are not real performance.
"""
import os, re, statistics, subprocess, sys, time, zlib, struct

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = r"D:\dev\DoomDaggerfall-loop\review\transition-speed\bench"
OLD = r"D:\dev\DoomDaggerfall-loop\review\bridge-codegen\uzdoom\uzdoom.exe"
NEW = r"D:\dev\DoomDaggerfall-build\uzdoom-transition\Release\uzdoom.exe"
ROUTES = [("city", "9183", "10403392,10403394"), ("gothway", "7154", "8325696,8325698"), ("dungeon", "7154", "dungeon")]
rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
times = {}
for n in range(rounds):
    for route, group, targets in ROUTES:
        for label, exe in (("old", OLD), ("new", NEW)) if n % 2 == 0 else (("new", NEW), ("old", OLD)):  # Neither build always runs first.
            name = f"ab_{label}_{route}"
            out = subprocess.run([sys.executable, os.path.join(HERE, "..", "overworld", "door_test.py"), name, "--group", group, "--build", BENCH, "--targets", targets,
                                  "--exe", exe, "--dungeon-dir", BENCH, "--timeout", "30"], capture_output=True, text=True, timeout=75).stdout
            if "DTDONE legs" not in out:
                sys.exit(f"{name} did not finish:\n{out[-800:]}")
            body = open(os.path.join(BENCH, "tests", f"log-{name}.txt"), errors="replace").read()
            for target, ms in re.findall(r"DDSTITCH arrive (\S+) ms=([\d.]+)", body):
                kind = "out to town" if target.startswith("DDT") else "into dungeon" if target == "MAP01" else "into building"
                times.setdefault((route, kind, label), []).append(float(ms))
print("route    transition      n  old_median  old_worst  new_median  new_worst  change")
for route, kind in sorted({k[:2] for k in times}):
    a, b = times[(route, kind, "old")], times[(route, kind, "new")]
    print(f"{route:8} {kind:14} {len(b):2} {statistics.median(a):10.0f} {max(a):10.0f} {statistics.median(b):11.0f} {max(b):10.0f}  {100 * (statistics.median(b) / statistics.median(a) - 1):+.0f}%")

# What a cold read of the largest town costs on the CPU, for the slower-drive estimate.
path = os.path.join(BENCH, "testcache", "T09183.ddt")
size = os.path.getsize(path)
with open(path, "rb") as f:
    f.read(4)
    count = struct.unpack("<i", f.read(4))[0]
    heads = [(f.read(8), *struct.unpack("<II", f.read(8))) for _ in range(count)]
    blobs = [f.read(p) for _, _, p in heads]
start = time.perf_counter()
raw = sum(len(zlib.decompress(b)) for b in blobs if b)
print(f"city cache file {size / 1048576:.1f} MB, decompressed {raw / 1048576:.1f} MB, decompress {1000 * (time.perf_counter() - start):.0f} ms (Python zlib, one thread)")
