"""Runs skillxp.py unity, assemble and run in order and prints the key lines of each (one call for the whole check)."""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEEP = re.compile(r"unity exit|error CS|SXHIT|SXRAISED|SXTOWN|sent .* XP|SXEARNED |SXLOADED|SXLEVEL|SXBUTTONMENU|SXKEYMENU|opened menu 15|harness")
for step in ("unity", "assemble", "run"):
    out = subprocess.run([sys.executable, str(HERE / "skillxp.py"), step], capture_output=True, text=True, errors="replace")
    for line in (out.stdout + out.stderr).splitlines():
        if KEEP.search(line):
            print(step, line[:200])
    if out.returncode:
        print(step, "exit", out.returncode)
        break
