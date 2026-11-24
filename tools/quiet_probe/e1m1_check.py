"""Runs DOOM.WAD E1M1 quietly, stock and with the DRLA set from play_drlax.bat, and reports problems.

Usage: python e1m1_check.py UZDOOM_EXE WORK_DIR
For each case: a -norun startup check (exit 1337 expected), then 15 seconds of E1M1 under quiet_probe
(timeout exit 124 expected), with the console log scanned for fatal errors.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("Script error", "Execution could not continue", "VM abort", "crashed")
QUIET_ARGS = ["-noactivate", "-nosound", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
              "+vid_lowerinbackground", "0"]


def main():
    exe, work = sys.argv[1], Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    failed = False
    for name, files in (("stock", []), ("drla", [str(MODS / f) for f in DRLA])):
        base = [exe, "-iwad", IWAD, "-config", str(work / f"{name}.ini")] + (["-file"] + files if files else [])
        start = subprocess.run([sys.executable, QUIET, "--timeout", "60", "--cwd", str(work), "--"] + base +
                               ["-norun", "-nosound", "-stdout", "-noactivate"], capture_output=True).returncode
        log = work / f"log-{name}.txt"  # UZDoom names +logfile NAME as log-NAME.txt
        log.unlink(missing_ok=True)
        report = work / f"{name}-probe.json"
        run = subprocess.run([sys.executable, str(HERE / "quiet_probe.py"), "--json", str(report), "--", sys.executable,
                              QUIET, "--timeout", "15", "--cwd", str(work), "--"] + base + QUIET_ARGS +
                             ["-skill", "3", "+logfile", name, "+map", "E1M1"], capture_output=True).returncode
        text = log.read_text(errors="replace") if log.exists() else ""
        # DRLA's own menus log non-fatal script errors on every engine, as the other tools allow for.
        keys = [k for k in FATAL if not (files and k == "Script error")]
        fatal = sorted({line.strip()[:120] for line in text.splitlines() if any(k in line for k in keys)})
        data = json.loads(report.read_text())
        disturb = len(data["events"]) + len(data["onscreen"]) + sum(a["max_peak"] > 0.0001 for a in data["audio"].values())
        ok = start == 1337 and run == 124 and "E1M1" in text and not fatal and not disturb
        failed |= not ok
        print(f"{name}: startup {start}, run {run}, log {len(text)} bytes, E1M1 {'E1M1' in text}, "
              f"fatal {fatal[:3]}, disturbances {disturb} -> {'OK' if ok else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
