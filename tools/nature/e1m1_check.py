"""Checks that the nature flats change nothing outside Daggerfall maps: stock DOOM.WAD startup (-norun, exit 1337),
then E1M1 stock and with the DRLA set from play_drlax.bat, ~10 s each with a screenshot, on a private desktop.

    python tools/nature/e1m1_check.py [--exe uzdoom.exe] [--out dir]
"""
import argparse
import subprocess
from pathlib import Path

IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-nature\Release\uzdoom.exe")
    ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-build\nature-tests\e1m1")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([a.exe, "-iwad", IWAD, "-norun", "-nosound", "-stdout", "-config", str(out / "norun.ini")],
                       capture_output=True, text=True, errors="replace")
    print("norun exit", r.returncode, "(1337 = pass)")
    (out / "run.cfg").write_text("wait 350; screenshot; wait 35; quit\n")
    bg = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+screenshot_dir", str(out)]
    for name, files in (("stock", []), ("drla", [str(Path(MODS) / f) for f in DRLA])):
        log = out / f"{name}.log"
        if log.exists():
            log.unlink()
        cmd = [a.exe, "-iwad", IWAD] + (["-file"] + files if files else []) + ["-config", str(out / f"{name}.ini"), "-skill", "3",
               "+logfile", log.name] + bg + ["+map", "E1M1", "+exec", str(out / "run.cfg")]
        r = subprocess.run(["python", QUIET, "--cwd", str(out), "--timeout", "60", "--", *cmd], capture_output=True)
        text = r.stdout.decode(errors="replace")	# quiet_run passes the game's console output through
        bad = [l for l in text.splitlines() if any(k in l.lower() for k in ("fatal", "error", "ddnature", "ddtm"))]
        print(name, "exit", r.returncode, "log lines", len(text.splitlines()), "suspicious:", bad[:5], "screenshot" if "Captured" in text else "NO screenshot")


if __name__ == "__main__":
    main()
