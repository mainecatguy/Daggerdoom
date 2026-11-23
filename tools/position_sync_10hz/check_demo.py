"""Launches this demo's exact play.bat command, minimized and without focus."""
from pathlib import Path

source = (Path(__file__).parent.parent / "connected_transitions" / "check_demo.py").read_text()
exec(compile(source.replace(r"review\connected-transitions", r"review\position-sync-10hz"), "check_demo", "exec"))
