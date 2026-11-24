"""Runs the fixed door route with one UZDoom exe and prints the transition profile.

Usage: bench.py LABEL EXE [--runs 2]
Route: City of Daggerfall and Gothway Garden (two buildings each, the first twice), then Privateer's Hold twice.
Runs are minimized through quiet_run, so load times are meaningful but frame rates between loads are not.
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = r"D:\dev\DoomDaggerfall-loop\review\transition-speed\bench"
ROUTES = [("city", "9183", "10403392,10403394"), ("gothway", "7154", "8325696,8325698"), ("dungeon", "7154", "dungeon")]

ap = argparse.ArgumentParser()
ap.add_argument("label")
ap.add_argument("exe")
ap.add_argument("--runs", type=int, default=2)
args = ap.parse_args()

os.makedirs(os.path.join(BENCH, "profiles"), exist_ok=True)
for run in range(1, args.runs + 1):
    for name, group, targets in ROUTES:
        log = os.path.join(BENCH, "profiles", f"{args.label}-{name}-{run}.csv")
        print(f"=== {args.label} {name} run {run}", flush=True)
        cmd = [sys.executable, os.path.join(HERE, "..", "overworld", "door_test.py"), f"{args.label}_{name}", "--group", group, "--build", BENCH, "--targets", targets,
               "--exe", args.exe, "--dungeon-dir", BENCH, "--timeout", "30", "--translog", log]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=75)
        lines = result.stdout.splitlines()
        print("\n".join(l for l in lines if l.startswith(("result:", "DTFAIL", "DTDONE")) or "FATAL" in l or "error" in l.lower()))
        if result.returncode or not any(l.startswith("DTDONE") for l in lines):
            print(result.stdout[-1200:], result.stderr[-600:])
            sys.exit(f"route {name} did not finish")
        print(subprocess.run([sys.executable, os.path.join(HERE, "analyze.py"), log], capture_output=True, text=True).stdout, flush=True)
