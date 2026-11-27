"""Configures (once) and builds this worktree's UZDoom, bridge DLL and launcher into private build folders (Release).

The spellbook card changes the bridge schema (DFB_UI_CHARACTER, DFB_UI_SPELLBOOK) and dd_bridge.cpp.
usage: build_native.py [uzdoom] [bridge] [launcher]
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
TARGETS = {"uzdoom": ("UZDoom", "uzdoom-quiet"), "bridge": ("bridge", "bridge-quiet"), "launcher": ("launcher", "launcher-quiet")}
log = BUILD / "spellbook-native.log"
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
