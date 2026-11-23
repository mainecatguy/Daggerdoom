"""Runs the connected-transition door, save, and load suite against this build, without changing that suite."""
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync-10hz")
COPY = REVIEW / "suite-tools"
COPY.mkdir(parents=True, exist_ok=True)

doors = (TOOLS / "connected_transitions" / "run_doors.py").read_text()
doors = doors.replace(r"review\connected-transitions", r"review\position-sync-10hz")
doors = doors.replace('HERE = Path(__file__).parent', f'HERE = Path(r"{TOOLS / "connected_transitions"}")')
doors = doors.replace('SOURCE_CACHE = REVIEW.parent / "combined-bridge" / "data" / "cache"', 'SOURCE_CACHE = REVIEW / "town-cache"')
(COPY / "run_doors.py").write_text(doors)

suite = (TOOLS / "connected_transitions" / "run_all.py").read_text().replace(r"review\connected-transitions", r"review\position-sync-10hz")
(COPY / "run_all.py").write_text(suite)
sys.exit(subprocess.call([sys.executable, str(COPY / "run_all.py")]))
