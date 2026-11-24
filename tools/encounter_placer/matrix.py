"""Runs the placer test at area levels 1, 10 and 30, twice each, and compares the pairs.

usage: matrix.py [--drla] [levels...]
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
drla = "--drla" in sys.argv
levels = [a for a in sys.argv[1:] if a.isdigit()] or ["1", "10", "30"]
tag = "d" if drla else "s"
for level in levels:
    for run in "ab":
        name = f"{tag}{level}{run}"
        subprocess.call([sys.executable, str(HERE / "placer_test.py"), "run", level, name] + (["--drla"] if drla else []))
    subprocess.call([sys.executable, str(HERE / "placer_test.py"), "compare", f"{tag}{level}a", f"{tag}{level}b"])
