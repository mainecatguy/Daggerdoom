"""Configures (once) and builds this worktree's UZDoom, bridge DLL and launcher into private build folders (Release).

The Skill XP card changes the bridge schema (DFB_KIND_SKILL_XP, DFB_UI_SKILLS) and adds dd_skillxp.cpp.
usage: build_native.py [uzdoom] [bridge] [launcher]
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
# These folders are configured from this lane's worktree (lane-items).
TARGETS = {"uzdoom": ("UZDoom", "uzdoom-items"), "bridge": ("bridge", "bridge-ammopile"), "launcher": ("launcher", "launcher-ammopile")}
log = BUILD / "skillxp-native.log"
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
