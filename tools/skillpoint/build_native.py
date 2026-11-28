"""Builds this worktree's UZDoom, bridge DLL and launcher (Release), in build folders of its own (UZDoom reuses the tree
configured from this lane's worktree, so its build is incremental). The skill point card changes only dd_weather.cpp and
a comment in dd_bridge.cpp; the bridge and launcher are built from this worktree so their schema matches it.
usage: build_native.py [uzdoom] [bridge] [launcher]
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
TARGETS = {"uzdoom": ("UZDoom", "uzdoom-items"), "bridge": ("bridge", "bridge-skillpoint"), "launcher": ("launcher", "launcher-skillpoint")}
log = BUILD / "skillpoint-native.log"
with open(log, "a") as out:
    for target in sys.argv[1:] or list(TARGETS):
        source, folder = TARGETS[target]
        tree = BUILD / folder
        steps = []
        if not (tree / "CMakeCache.txt").exists():
            steps.append(["cmake", "-S", str(REPO / source), "-B", str(tree), "-G", "Visual Studio 18 2026", "-A", "x64"])
        steps.append(["cmake", "--build", str(tree), "--config", "Release", "--parallel", "6"])
        for step in steps:
            out.write("== %s: %s\n" % (target, " ".join(step)))
            out.flush()
            rc = subprocess.call(step, stdout=out, stderr=subprocess.STDOUT)
            out.write("== %s exit %d\n" % (target, rc))
            out.flush()
            print(target, "exit", rc)
            if rc:
                sys.exit(rc)
