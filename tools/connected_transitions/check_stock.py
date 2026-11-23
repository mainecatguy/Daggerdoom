"""No-bridge regression checks for this demo: the fast travel checks, pointed at this build and baselined on the build before it."""
from pathlib import Path

source = (Path(__file__).parent.parent / "fast_travel_arrival" / "check_stock.py").read_text()
source = source.replace(r"review\fast-travel-arrival", r"review\connected-transitions").replace(r"review\fast-travel-menu\uzdoom", r"review\fast-travel-arrival\uzdoom")
Path(r"D:\dev\DoomDaggerfall-loop\review\connected-transitions\run").mkdir(parents=True, exist_ok=True)
exec(compile(source, "check_stock", "exec"))
