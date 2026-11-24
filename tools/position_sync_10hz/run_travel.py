"""Runs the real fast travel test against this demo. Usage is the same as fast_travel_arrival/run_travel.py."""
from pathlib import Path

source = (Path(__file__).parent.parent / "fast_travel_arrival" / "run_travel.py").read_text()
exec(compile(source.replace(r"review\fast-travel-arrival", r"review\position-sync-10hz"), "run_travel", "exec"))
