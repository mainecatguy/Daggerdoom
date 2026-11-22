"""Measures the real UZDoom player with the Daggerfall size package on a converted map, with it disabled, and on E1M1.

Usage: python tools/dungeon_compare/player_check.py --map <slug.wad> --player <slug_player.pk3> --out <dir outside the repo>
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
SW_SHOWMINNOACTIVE = 7
SCRIPT = ('alias dfrun "netevent dfcheck_stand; +crouch; wait 40; netevent dfcheck_crouched; -crouch; wait 40; '
          'netevent dfcheck_restood; wait 5; quit"\nwait 70; dfrun\n')


def run(name, iwad, files, level, extra, out):
    folder = os.path.join(out, name)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "check.cfg"), "w", newline="\n") as f:
        f.write(SCRIPT)
    log = os.path.join(folder, "log-check.txt")
    if os.path.exists(log):
        os.remove(log)
    # A private config keeps this launch windowed from the first frame, so it cannot interrupt the owner.
    with open(os.path.join(folder, "doom.ini"), "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWMINNOACTIVE
    process = subprocess.Popen([UZDOOM, "-iwad", os.path.join(WADS, iwad), "-file", *files, os.path.join(HERE, "player_check_doom"),
                                "-config", os.path.join(folder, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
                                "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                *extra, "+logfile", "check", "+map", level, "+exec", "check.cfg"],
                               cwd=folder, startupinfo=startup, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        code = process.wait(45)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        code = "timed out"
    print(f"{name}: exit {code}")
    if os.path.exists(log):
        for line in open(log, errors="replace"):
            if line.startswith("DFPLAYER"):
                print("  " + line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    run("daggerfall_on", "DOOM2.WAD", [args.map, args.player], "MAP01", [], out)
    run("daggerfall_off", "DOOM2.WAD", [args.map, args.player], "MAP01", ["+df_playersize", "0"], out)
    run("e1m1_package", "DOOM.WAD", [args.player], "E1M1", [], out)
    run("e1m1_plain", "DOOM.WAD", [], "E1M1", [], out)


if __name__ == "__main__":
    sys.exit(main())
