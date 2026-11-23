"""Regression checks with no bridge session: stock Doom, Doom with DRLA, and plain private Daggerfall."""
import subprocess
import sys
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-arrival")
BASELINE = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-menu\uzdoom\uzdoom.exe")  # The build before this work.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
RUN = REVIEW / "run"
FATAL = ("Fatal error", "FATAL", "VM execution aborted", "Script error")


def doom(name, files, exe=REVIEW / "uzdoom" / "uzdoom.exe"):
    log = RUN / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    args = [str(exe), "-iwad", IWAD, "-config", str(RUN / f"{name}.ini"), "-nosound", "-noautoload",
            "-noactivate", "-skill", "3", "+logfile", name, "+vid_fullscreen", "0", "+i_pauseinbackground", "0",
            "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "E1M1", "+wait 175;quit"]
    if files:
        args[3:3] = ["-file"] + [str(MODS / f) for f in files]
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(RUN), "--"] + args,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = log.read_text(errors="replace") if log.exists() else ""
    fatal = [line for line in text.splitlines() if any(k in line for k in FATAL)]
    print(f"{name}: exit {code}, E1M1 entered {'E1M1' in text}, bridge lines {text.count('[bridge]')}, error lines {len(fatal)}, unknown-class lines {text.count('Unknown class name')}")
    for line in fatal[:3]:
        print("  ", line[:160])


def daggerfall():
    exe = REVIEW / "dfu" / "DaggerfallUnity.exe"
    player = REVIEW / "dfu" / "PortableAppdata" / "Player.log"
    code = subprocess.call([sys.executable, QUIET, "--timeout", "12", "--", str(exe), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = player.read_text(errors="replace") if player.exists() else ""
    print(f"plain Daggerfall: exit {code}, log lines {len(text.splitlines())}, bridge mentions {text.lower().count('doomerfall_bridge')}, "
          f"DoomerfallUi mentions {text.count('DoomerfallUi')}, exceptions {text.count('Exception')}")


doom("stock", [])
doom("drla", DRLA)
doom("drla-before", DRLA, BASELINE)
daggerfall()
