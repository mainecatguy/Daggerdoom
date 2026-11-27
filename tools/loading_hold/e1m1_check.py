"""Stock check: DOOM.WAD E1M1, stock and with the DRLA set from play_drlax.bat, 30 s each on a private desktop.

Usage: e1m1_check.py UZDOOM_EXE OUT_DIR
Passes when both runs reach "E1M1 - Hangar" with no fatal error and no loading hold line ("loading:").
"""
import subprocess
import sys
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [str(MODS / n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
# Not "Script error": DRLA's own load warnings contain it in every launch (drlax special.zscript translation).
FATAL = ("FATAL", "VM execution aborted", "Execution could not continue")


def main():
    exe, out = sys.argv[1], Path(sys.argv[2])
    ok = True
    for name, files in (("e1m1-stock", []), ("e1m1-drla", DRLA)):
        run = out / name
        run.mkdir(parents=True, exist_ok=True)
        args = [exe, "-iwad", IWAD] + (["-file"] + files if files else []) + ["-config", str(run / "uz.ini"), "-skill", "3",
                "+logfile", "log.txt", "+map", "E1M1", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
        subprocess.run([sys.executable, QUIET, "--timeout", "30", "--cwd", str(run), "--"] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logs = sorted(run.glob("log*.txt"), key=lambda p: p.stat().st_mtime)  # +logfile log.txt is written as log-log-txt.txt
        log = logs[-1].read_text(errors="replace") if logs else ""
        good = "E1M1 - Hangar" in log and not any(k in log for k in FATAL) and "loading:" not in log
        ok &= good
        print(f"{'PASS' if good else 'FAIL'} {name}: hangar {'E1M1 - Hangar' in log}, fatal {any(k in log for k in FATAL)}, loading lines {log.count('loading:')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
