"""Stock check for the fixed drops engine change: DOOM.WAD E1M1, stock and with the DRLA set, 10 s each, no errors.

usage: e1m1_check.py
"""
import os
import subprocess
import sys
from pathlib import Path

UZ = r"D:\dev\DoomDaggerfall-build\uzdoom-items\Release\uzdoom.exe"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
OUT = Path(r"D:\dev\DoomDaggerfall-loop\review\fixed-drops\e1m1")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"

OUT.mkdir(parents=True, exist_ok=True)
for name, files in (("stock", []), ("drla", [str(MODS / f) for f in DRLA])):
    log = OUT / f"log-{name}.txt"   # UZDoom names a relative +logfile log-<name>.txt
    log.unlink(missing_ok=True)
    args = [UZ, "-iwad", r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"] + (["-file", *files] if files else []) + \
        ["-noautoload", "-config", str(OUT / "e1m1.ini"), "-skill", "3", "+logfile", name, "+vid_fullscreen", "0",
         "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "E1M1", "+wait 350;quit"]
    code = subprocess.call([sys.executable, QUIET, "--timeout", "40", "--cwd", str(OUT), "--", *args],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    bad = [k for k in ("VM execution aborted", "Unhandled exception", "FATAL", "Execution could not continue") if k in body]
    print(f"{name}: exit {code}, log {len(body)} bytes, E1M1 loaded {'E1M1' in body}, errors {bad or 'none'}")
