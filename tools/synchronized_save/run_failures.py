"""Fails a real save at each step and checks that the previous save survives. Needs a good save from run_save.py."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).with_name("run_save.py")
name = sys.argv[1] if len(sys.argv) > 1 else "real1"
extra = sys.argv[2:]
for step in ("df_write", "uz_zip", "uz_commit", "uz_crash"):
    print("===", step, flush=True)
    subprocess.call([sys.executable, str(RUN), name, "--keep-old", "--fail", step, *extra])
