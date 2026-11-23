"""Runs the whole transition suite and keeps the key lines. Full output goes to the review folder."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
TEST = Path(r"D:\dev\DoomDaggerfall-loop\review\connected-transitions\test")
KEEP = ("stopped:", "summary:", "Daggerfall exceptions:", "owner registry", "load 1: both games", "DTFAIL", "FATAL", "error:")
B, D = ["--targets", "10403728"], ["--group", "7154", "--targets", "dungeon"]
RUNS = [("types", ["--pick", "16", "--timeout", "60"]), ("dungeon", [*D, "--timeout", "35"]), ("saveout", [*B, "--mode", "saveout"]),
        ("save-b", [*B, "--mode", "save"]), ("save-d", [*D, "--mode", "save"])]
for n in range(1, 4):
    RUNS += [(f"load-b{n}", [*B, "--resume", str(TEST / "save-b" / "saves" / "auto00.zds")]), (f"load-d{n}", [*D, "--resume", str(TEST / "save-d" / "saves" / "auto00.zds")])]

TEST.mkdir(parents=True, exist_ok=True)
with (TEST / "suite.txt").open("w", encoding="utf-8") as full:
    for name, extra in RUNS:
        if "--timeout" not in extra:
            extra = [*extra, "--timeout", "30"]
        out = subprocess.run([sys.executable, str(HERE / "run_doors.py"), name, "--brief", *extra], capture_output=True, text=True, errors="replace").stdout
        full.write(f"=== {name}\n{out}\n")
        print("==", name)
        for line in out.splitlines():
            if any(k in line for k in KEEP):
                print(line[:260])
