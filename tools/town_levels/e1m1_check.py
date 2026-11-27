"""Stock DOOM.WAD E1M1 with this branch's UZDoom, plain and with the DRLA set from play_drlax.bat, 30 seconds each on a
private desktop. Prints the map line, any fatal lines and any Doomerfall (dd/doomitems/DDTOWN) lines from each log.

usage: e1m1_check.py
"""
import subprocess
import sys
from pathlib import Path

UZ = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-towndanger\Release\uzdoom.exe")
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [str(MODS / n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
OUT = Path(r"D:\dev\DoomDaggerfall-loop\review\town-levels\e1m1")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
KEYS = ("E1M1", "fatal", "FATAL", "aborted", "Script error", "doomitems", "DDTOWN", "dd_", "treadmill")

OUT.mkdir(parents=True, exist_ok=True)
for name, files in (("stock", []), ("drla", DRLA)):
    log = OUT / f"{name}.log"
    if log.exists():
        log.unlink()
    args = [str(UZ), "-iwad", IWAD] + (["-file"] + files if files else []) + [
        "-config", str(OUT / f"{name}.ini"), "-skill", "3", "+logfile", log.name, "+i_pauseinbackground", "0",
        "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "E1M1"]
    subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(OUT), "--"] + args,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lines = log.read_text(errors="replace").splitlines() if log.exists() else []
    print(f"== {name}: {len(lines)} log lines")
    for line in lines:
        if any(k in line for k in KEYS):
            print("  ", line[:200])
