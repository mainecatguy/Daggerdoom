"""Runs tools/combined_bridge/no_session.py against this demo, with the uzdoom-launcher build as the stock baseline.

Usage: no_session_check.py doom | dfu | regkey
"""
from pathlib import Path

source = (Path(__file__).resolve().parents[1] / "combined_bridge" / "no_session.py").read_text()
source = source.replace(r'review\combined-bridge', r'review\new-game')
source = source.replace('REVIEW / "baseline" / "uzdoom" / "uzdoom.exe"', r'Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release\uzdoom.exe")')
exec(compile(source, "no_session.py", "exec"))
