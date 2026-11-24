"""Builds this worktree's bridge, launcher, and UZDoom into the existing *-doomitems build trees. Logs go to the review folder."""
import subprocess
from pathlib import Path

BUILD = Path(r"D:\dev\DoomDaggerfall-build")
LOGS = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo")
LOGS.mkdir(parents=True, exist_ok=True)
for name in ("bridge", "launcher", "uzdoom"):
    with open(LOGS / f"{name}-build.log", "w") as log:
        code = subprocess.call(["cmake", "--build", str(BUILD / f"{name}-doomitems"), "--config", "Release", "--parallel", "6"], stdout=log, stderr=subprocess.STDOUT)
    print(name, "exit", code, flush=True)
    if code:
        break
