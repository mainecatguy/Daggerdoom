"""Builds this worktree's bridge DLL, launcher and UZDoom into its existing private build folders (Release).

The level-up card changes no native code; this only gives the test natives whose bridge schema matches this branch.
"""
import subprocess
import sys
from pathlib import Path

BUILD = Path(r"D:\dev\DoomDaggerfall-build")
TARGETS = {"bridge": "bridge-location", "launcher": "launcher-location", "uzdoom": "uzdoom-location"}
log = BUILD / "levelup-native.log"
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
