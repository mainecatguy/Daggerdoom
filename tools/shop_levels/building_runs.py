"""Shop levels 4: paired runs into several buildings of the test town, printing the level each interior was laid out at
(Daggerfall's "interior layout" line, the level its loot piles roll at) and the level inside (-dfbuildingleveltest).

    python tools/shop_levels/building_runs.py [--no-assemble] [--stock-mods]

Uses shelf_run.py with the demo folder D:\\dev\\DoomDaggerfall-loop\\review\\building-levels.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = r"D:\dev\DoomDaggerfall-loop\review\building-levels"
RUNS = [("h2", "House2", 0), ("h3", "House3", 0),("mg", "GuildHall", 1), ("tav", "Tavern", 0)]
shelf = [sys.executable, str(HERE / "shelf_run.py")]
if "--no-assemble" not in sys.argv:
    subprocess.check_call(shelf + ["assemble", "--review", REVIEW, "--demo-building", "GuildHall", "--nth", "1"], stdout=subprocess.DEVNULL)
extra = ["--stock-mods"] if "--stock-mods" in sys.argv else []
for name, kind, nth in RUNS:
    out = subprocess.run(shelf + ["run", name, "--building", kind, "--nth", str(nth), "--buildinglevels", "--review", REVIEW] + extra,
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace").stdout
    print("==", name, kind)
    for line in out.splitlines():
        if re.search(r"stopped|interior layout|df building|exception kinds|FATAL", line):
            print("  ", line[:260])
