"""No-bridge regression checks for this demo, baselined on the build before it."""
from pathlib import Path

source = (Path(__file__).parent.parent / "fast_travel_arrival" / "check_stock.py").read_text()
source = source.replace(r"review\fast-travel-arrival", r"review\position-sync-10hz").replace(r"review\fast-travel-menu\uzdoom", r"review\connected-transitions\uzdoom")
Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync-10hz\run").mkdir(parents=True, exist_ok=True)
exec(compile(source, "check_stock", "exec"))
