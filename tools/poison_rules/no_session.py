"""Stock check: UZDoom on DOOM.WAD E1M1 with no bridge session, stock and with the DRLA set from play_drlax.bat.

usage: no_session.py <review dir>
Each launch runs about 15 seconds on a private desktop (quiet_run.py) with a private config; the console log must show
E1M1 and no fatal error.
"""
import subprocess
import sys
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3"]
FATAL = ("Fatal error", "FATAL", "VM execution aborted", "Unhandled exception")


def launch(review, name, files):
    run = review / "run"
    run.mkdir(exist_ok=True)
    log = run / f"log-{name}.txt"  # +logfile <name> is written as log-<name>.txt
    log.unlink(missing_ok=True)
    args = [str(review / "uzdoom" / "uzdoom.exe"), "-iwad", IWAD]
    if files:
        args += ["-file"] + [str(f) for f in files]
    args += ["-config", str(run / f"{name}.ini"), "-skill", "3", "+logfile", name, "+map", "E1M1",
             "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    subprocess.call([sys.executable, QUIET, "--timeout", "15", "--cwd", str(run), "--"] + args,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = log.read_text(errors="replace") if log.exists() else ""
    ok = "E1M1" in text and not any(k in text for k in FATAL)
    print(("PASS " if ok else "FAIL ") + f"{name}: E1M1 loaded={'E1M1' in text}, fatal={any(k in text for k in FATAL)}")
    return ok


def main():
    review = Path(sys.argv[1])
    ok = launch(review, "nosession-stock", []) & launch(review, "nosession-drla", DRLA)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
