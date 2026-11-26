"""Builds this worktree's bridge DLL, launcher and UZDoom into its existing private build folders (Release).

The rest card changes the bridge schema (DFB_UI_REST, DFB_KIND_HUD_TEXT), dd_bridge.cpp and dd_info.cpp.
"""
import subprocess
import sys
from pathlib import Path

BUILD = Path(r"D:\dev\DoomDaggerfall-build")
TARGETS = {"bridge": "bridge-items", "launcher": "launcher-items", "uzdoom": "uzdoom-items"}
log = BUILD / "rest-native.log"
with open(log, "w") as out:
    for target in sys.argv[1:] or list(TARGETS):
        out.write("== %s\n" % target)
        out.flush()
        rc = subprocess.call(["cmake", "--build", str(BUILD / TARGETS[target]), "--config", "Release", "--parallel", "6"],
                             stdout=out, stderr=subprocess.STDOUT)
        out.write("== %s exit %d\n" % (target, rc))
        out.flush()
        print(target, "exit", rc)
        if rc:
            sys.exit(rc)
