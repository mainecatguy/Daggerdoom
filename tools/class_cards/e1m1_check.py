"""Stock DOOM.WAD E1M1 check, plain and with the DRLA set from play_drlax.bat, through quiet_run.

usage: e1m1_check.py <uzdoom.exe> <doomerfall.pk3> <log folder>
"""
import subprocess, sys
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3"]
BG = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]


def run(uz, out, name, files):
    log = out / f"{name}.log"
    log.unlink(missing_ok=True)
    args = [uz, "-iwad", IWAD, "-config", str(out / f"{name}.ini")] + (["-file"] + [str(f) for f in files] if files else [])
    args += ["-stdout", "+map", "E1M1"] + BG  # the game is stopped at the timeout, so read its console output
    done = subprocess.run([sys.executable, QUIET, "--timeout", "30", "--"] + args, capture_output=True, text=True, errors="replace")
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    ok = "Hangar" in text and "Script error" not in text and "FATAL" not in text.upper().replace("NONFATAL", "")
    print(name, "PASS" if ok else "FAIL", "(E1M1 - Hangar reached)" if "Hangar" in text else "(no Hangar)")
    return ok


def main():
    uz, pk3, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    results = [run(uz, out, "plain", []), run(uz, out, "stock", [pk3]), run(uz, out, "drla", DRLA + [pk3])]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
