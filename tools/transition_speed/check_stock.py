"""No-bridge regression checks for this build: stock E1M1, E1M1 with DRLA on this and the previous build, and plain Daggerfall."""
from pathlib import Path

NEW = r"D:\dev\DoomDaggerfall-build\uzdoom-transition\Release\uzdoom.exe"
source = (Path(__file__).parent.parent / "fast_travel_arrival" / "check_stock.py").read_text()
source = source.replace('exe=REVIEW / "uzdoom" / "uzdoom.exe"', f'exe=Path(r"{NEW}")')
source = source.replace(r"review\fast-travel-menu\uzdoom", r"review\bridge-codegen\uzdoom").replace(r"review\fast-travel-arrival", r"review\bridge-codegen")
source = source.replace('RUN = REVIEW / "run"', r'RUN = Path(r"D:\dev\DoomDaggerfall-loop\review\transition-speed\stock")')
Path(r"D:\dev\DoomDaggerfall-loop\review\transition-speed\stock").mkdir(parents=True, exist_ok=True)
exec(compile(source, "check_stock", "exec"))
