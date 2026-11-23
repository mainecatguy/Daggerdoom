"""Builds the bridge DLL, launcher, and UZDoom into the existing private build folders (Release)."""
import subprocess
import sys
from pathlib import Path

BUILD = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-menu\build")
log = BUILD / "hp-build.log"
with open(log, "w") as out:
    for target in sys.argv[1:] or ["bridge", "launcher", "uzdoom"]:
        out.write("== %s\n" % target)
        out.flush()
        rc = subprocess.call(["cmake", "--build", str(BUILD / target), "--config", "Release", "--parallel", "6"],
                             stdout=out, stderr=subprocess.STDOUT)
        out.write("== %s exit %d\n" % (target, rc))
        out.flush()
        if rc:
            break
    out.write("DONE\n")
