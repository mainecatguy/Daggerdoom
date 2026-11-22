"""Two-way Daggerfall/Doom movement parity and bullet check for one converted dungeon.

Usage: python tools/dungeon_compare/parity.py "Privateer's Hold" --out <dir outside the repo>
           [--unity-flood <df_flood_walk.txt>] [--world-scale 1.0] [--uzdoom <exe>] [--timeout 180]

Writes parity.csv, bullets.txt, worst_views.txt, and unity_validation.txt under <out>/parity.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PROJECT = os.path.join(REPO, "tools", "dungeon_converter", "DungeonConverter.csproj")
SW_SHOWMINNOACTIVE = 7
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"


def convert(name, out, parity, scale, extra):
    command = ["dotnet", "run", "-c", "Release", "-v", "q", "--project", PROJECT, "--", name, "--out", out,
               "--parity", parity, "--world-scale", str(scale)] + extra
    result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    keep = [l for l in result.stdout.splitlines() if not l.startswith(("  ", "LINE", "MAP "))]
    print("\n".join(keep[-60:]))
    if result.returncode:
        sys.exit("converter failed:\n" + result.stderr[-2000:])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dungeon")
    parser.add_argument("--out", required=True)
    parser.add_argument("--unity-flood")
    parser.add_argument("--world-scale", type=float, default=1.0)
    parser.add_argument("--uzdoom", default=UZDOOM)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cell", type=int, help="converter collision cell size")
    parser.add_argument("--baseline", action="store_true", help="measure the converter without the ceiling relief fix")
    args = parser.parse_args()
    extra = ["--cell", str(args.cell)] if args.cell else []
    if args.baseline:
        extra.append("--no-ceiling-relief")

    out = os.path.abspath(args.out)
    if (os.path.normcase(out) + os.sep).startswith(os.path.normcase(REPO) + os.sep):
        sys.exit("--out must be outside the repository: results are derived from game data")
    parity = os.path.join(out, "parity")
    os.makedirs(parity, exist_ok=True)
    flood = os.path.join(parity, "doom_flood.txt")
    if os.path.exists(flood):
        os.remove(flood)
    if args.unity_flood:
        shutil.copyfile(args.unity_flood, os.path.join(parity, "df_flood_walk.txt"))

    started = time.time()
    convert(args.dungeon, out, parity, args.world_scale, extra)
    slug = re.sub(r"[^a-z0-9]", "", args.dungeon.lower())
    log = os.path.join(parity, "log-parity.txt")
    if os.path.exists(log):
        os.remove(log)
    doom_started = time.time()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWMINNOACTIVE
    # ZScript cannot quit the engine, so this stops the one process it started once the log reports completion.
    process = subprocess.Popen([args.uzdoom,
                                "-iwad", IWAD, "-file", os.path.join(out, slug + ".wad"), os.path.join(out, slug + "_player.pk3"),
                                os.path.join(HERE, "parity_doom"), os.path.join(parity, "lumps"),
                                "-config", os.path.join(parity, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
                                "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                "+logfile", "parity", "+map", "MAP01"],
                               cwd=parity, startupinfo=startup, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finished = False
    try:
        while time.time() - doom_started < args.timeout and process.poll() is None:
            time.sleep(1)
            if os.path.exists(log) and "DFPARITYDONE" in open(log, errors="replace").read():
                finished = True
                break
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
    print(f"UZDoom finished={finished} ({time.time() - doom_started:.0f} s)")
    if not os.path.exists(log):
        sys.exit("UZDoom wrote no log")
    lines = [l for l in open(log, errors="replace") if l.startswith(("DFF ", "DFB ", "DFSEEDFAIL", "DFPARITYDONE"))]
    if not finished:
        sys.exit("UZDoom did not finish the test; see " + log)
    with open(flood, "w") as f:
        f.writelines(lines)
    convert(args.dungeon, out, parity, args.world_scale, extra)
    print(f"Total {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
