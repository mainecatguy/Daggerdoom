"""Configures (once) and builds this worktree's bridge, launcher, and UZDoom into their own *-ammosize build trees, so no
other lane's tree is used or disturbed. Logs go to the review folder."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
LOGS = Path(r"D:\dev\DoomDaggerfall-loop\review\ammosize")
LOGS.mkdir(parents=True, exist_ok=True)
for name, source in (("bridge", "bridge"), ("launcher", "launcher"), ("uzdoom", "UZDoom")):
    tree = BUILD / f"{name}-ammosize"
    with open(LOGS / f"{name}-build.log", "w") as log:
        code = 0
        if not (tree / "CMakeCache.txt").exists():
            code = subprocess.call(["cmake", "-S", str(REPO / source), "-B", str(tree), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=log, stderr=subprocess.STDOUT)
        if not code:
            code = subprocess.call(["cmake", "--build", str(tree), "--config", "Release", "--parallel", "6"], stdout=log, stderr=subprocess.STDOUT)
    print(name, "exit", code, flush=True)
    if code:
        break
