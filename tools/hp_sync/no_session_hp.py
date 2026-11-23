"""No bridge session: the HP-sync build must hurt and kill the player exactly like the stock baseline build.

Summons imps on E1M1 stock and with the DRLA set, in the baseline build and the HP-sync build, and compares
the obituary lines and the number of player damage messages. Private -config files only.
"""
import re
import subprocess
import sys
from pathlib import Path

RUN = Path(r"D:\dev\DoomDaggerfall-loop\review\hp-sync\run")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = [r"D:\dev\DoomDaggerfall\GameMods\DoomRL_Arsenal_1.1.5.pk3",
        r"D:\dev\DoomDaggerfall\GameMods\DoomRL_Monsters_Beta_7.3.pk3",
        r"D:\dev\DoomDaggerfall\GameMods\drlax_1.2b.pk3"]
BASELINE = r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release\uzdoom.exe"
NEW = r"D:\dev\DoomDaggerfall-loop\review\hp-sync\uzdoom\uzdoom.exe"
QUIET_ARGS = ["-noactivate", "-nosound", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]


def run(exe, label, mods):
    log = RUN / f"log-nohp-{label}.txt"
    log.unlink(missing_ok=True)
    args = [exe, "-iwad", IWAD]
    if mods:
        args += ["-file"] + mods
    args += ["-config", str(RUN / f"nohp-{label}.ini"), "-skill", "3", "+logfile", f"nohp-{label}", "+map", "E1M1"] + QUIET_ARGS
    for _ in range(5):
        args += ["+summon", "DoomImp"]
    subprocess.run([sys.executable, QUIET, "--timeout", "30", "--cwd", str(RUN), "--"] + args, capture_output=True, text=True)
    return log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""


def main():
    for name, mods in (("stock", []), ("drla", MODS)):
        for build, exe in (("baseline", BASELINE), ("new", NEW)):
            text = run(exe, f"{name}-{build}", mods)
            deaths = [l for l in text.splitlines() if l.startswith("Player was ")]
            print(f"{name} {build}: bridge text {'[bridge]' in text}; player-death lines: {len(deaths)}; first: {deaths[0][:90] if deaths else None}")


main()
