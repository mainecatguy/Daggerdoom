"""Both real games through real doors with the new engine: building types, the dungeon, autosaves, and saves made indoors.

Usage: suite.py EXE
Uses the launcher, Daggerfall build, and data of the bridge-codegen demo, the newest with this branch's bridge. Logs stay in review\\transition-speed\\suite.
"""
import os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = Path(r"D:\dev\DoomDaggerfall-loop\review\transition-speed\suite")
KEEP = ("stopped:", "summary:", "Daggerfall exceptions:", "owner registry", "load 1: both games", "DTFAIL", "FATAL", "error:")
B, D = ["--targets", "10403728"], ["--group", "7154", "--targets", "dungeon"]
RUNS = [("types", ["--pick", "6"]), ("dungeon", D), ("saveout", [*B, "--mode", "saveout"]), ("save-b", [*B, "--mode", "save"]), ("save-d", [*D, "--mode", "save"])]
for n in (1, 2):
    RUNS += [(f"load-b{n}", [*B, "--resume", str(ROOT / "save-b" / "saves" / "auto00.zds")]), (f"load-d{n}", [*D, "--resume", str(ROOT / "save-d" / "saves" / "auto00.zds")])]

env = dict(os.environ, DD_REVIEW=r"D:\dev\DoomDaggerfall-loop\review\bridge-codegen", DD_TEST_ROOT=str(ROOT))
ROOT.mkdir(parents=True, exist_ok=True)
with (ROOT / "suite.txt").open("w", encoding="utf-8") as full:
    for name, extra in RUNS:
        out = subprocess.run([sys.executable, str(HERE.parent / "connected_transitions" / "run_doors.py"), name, "--brief", "--exe", sys.argv[1], "--timeout", "30", *extra],
                             capture_output=True, text=True, errors="replace", env=env).stdout
        full.write(f"=== {name}\n{out}\n")
        full.flush()
        print("==", name, flush=True)
        for line in out.splitlines():
            if any(k in line for k in KEEP):
                print(line[:240], flush=True)
