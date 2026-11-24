"""Runs the existing door, save, load, and stock suites against the dungeon-reentry build, without changing them."""
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeon-reentry")
COPY = REVIEW / "suite-tools"
COPY.mkdir(parents=True, exist_ok=True)
(REVIEW / "run").mkdir(exist_ok=True)

doors = (TOOLS / "connected_transitions" / "run_doors.py").read_text()
doors = doors.replace(r"review\connected-transitions", r"review\dungeon-reentry")
doors = doors.replace('HERE = Path(__file__).parent', f'HERE = Path(r"{TOOLS / "connected_transitions"}")')
doors = doors.replace('SOURCE_CACHE = REVIEW.parent / "combined-bridge" / "data" / "cache"', 'SOURCE_CACHE = REVIEW / "town-cache"')
(COPY / "run_doors.py").write_text(doors)
suite = (TOOLS / "connected_transitions" / "run_all.py").read_text().replace(r"review\connected-transitions", r"review\dungeon-reentry")
(COPY / "run_all.py").write_text(suite)
stock = (TOOLS / "fast_travel_arrival" / "check_stock.py").read_text()
stock = stock.replace(r"review\fast-travel-arrival", r"review\dungeon-reentry").replace(r"review\fast-travel-menu\uzdoom", r"review\position-sync-10hz\uzdoom")
(COPY / "check_stock.py").write_text(stock)
travel = (TOOLS / "fast_travel_arrival" / "run_travel.py").read_text().replace(r"review\fast-travel-arrival", r"review\dungeon-reentry")
travel = travel.replace("Path(__file__).parent", f'Path(r"{TOOLS / "fast_travel_arrival"}")')
(COPY / "run_travel.py").write_text(travel)

which = sys.argv[1] if len(sys.argv) > 1 else "all"
code = 0
if which in ("all", "doors"):
    code |= subprocess.call([sys.executable, str(COPY / "run_all.py")])
if which in ("all", "stock"):
    code |= subprocess.call([sys.executable, str(COPY / "check_stock.py")])
sys.exit(code)
