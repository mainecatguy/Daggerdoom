"""Runs the three full treadmill measurements in sequence, in a visible window."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = "262144"  # 8 map pixels at 1 Daggerfall unit = 1 Doom unit
for name, flags in (("rewrite", []), ("baseline", ["-ddtmnorewrite"]), ("verify", ["-ddtmverify", "-ddtmshots"])):
    subprocess.run([sys.executable, os.path.join(HERE, "treadmill_run.py"), name, DIST] + flags)
