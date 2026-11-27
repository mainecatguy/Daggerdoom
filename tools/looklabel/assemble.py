"""Review folder for the look label fix (test and demo only): a copy of a staged play folder with this worktree's
UZDoom build and Doomerfall mod.

usage: assemble.py <staged play folder> <UZDoom Release folder> <new folder>
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
stage, engine, dest = map(Path, sys.argv[1:4])
shutil.copytree(stage, dest, ignore=shutil.ignore_patterns("run"), dirs_exist_ok=True)
for name in ("uzdoom.exe", "uzdoom.pk3"):
    shutil.copy2(engine / name, dest / "uzdoom" / name)
build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
subprocess.check_call([sys.executable, str(build), str(dest / "doomerfall.pk3")])
subprocess.check_call([sys.executable, str(build), "--drla", str(dest / "doomerfall-drla.pk3")])
print("assembled", dest)
