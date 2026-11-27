"""Builds this worktree's UZDoom into the distant-LOD build folder and prints errors and the result.

Usage: python tools/distant_lod/build.py [build_dir]
"""
import subprocess
import sys

build = sys.argv[1] if len(sys.argv) > 1 else r"D:\dev\DoomDaggerfall-build\uzdoom-carbine"
log = build + "-build.log"
with open(log, "w", encoding="utf-8", errors="replace") as out:
    code = subprocess.call(["cmake", "--build", build, "--config", "Release", "--parallel", "6"],
                           stdout=out, stderr=subprocess.STDOUT)
with open(log, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
errors = [l.rstrip() for l in lines if " error " in l or "error C" in l or "error LNK" in l]
for l in errors[:20]:
    print(l)
print("".join(lines[-3:]).rstrip())
print("exit", code, "log", log)
