"""Two-way Daggerfall/Doom movement parity and bullet check for one converted dungeon.

Usage: python tools/dungeon_compare/parity.py "Privateer's Hold" --out <dir outside the repo>
           [--unity-flood <df_flood_walk.txt>] [--world-scale 0.75] [--daggerfall-player] [--uzdoom <exe>] [--timeout 180]

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
    parser.add_argument("--world-scale", type=float, default=0.75)
    parser.add_argument("--daggerfall-player", action="store_true", help="test the opt-in Daggerfall-size body instead of stock Doom")
    parser.add_argument("--uzdoom", default=UZDOOM)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cell", type=int, help="converter collision cell size")
    parser.add_argument("--ceiling-relief", type=int, help="largest collision ceiling raise, in map units")
    parser.add_argument("--baseline", action="store_true", help="measure the converter without the ceiling relief fix")
    args = parser.parse_args()
    extra = ["--cell", str(args.cell)] if args.cell else []
    if args.ceiling_relief is not None:
        extra += ["--ceiling-relief", str(args.ceiling_relief)]
    if args.baseline:
        extra.append("--no-ceiling-relief")
    if args.daggerfall_player:
        extra.append("--daggerfall-player")

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
    # The doors are separate objects in <slug>_doors.pk3, written by --export-mesh at the same scale.
    doors_dir = os.path.join(out, "doors")
    os.makedirs(doors_dir, exist_ok=True)
    doors_pk3 = os.path.join(doors_dir, slug + "_doors.pk3")
    if os.path.exists(doors_pk3):
        os.remove(doors_pk3)
    result = subprocess.run(["dotnet", "run", "-c", "Release", "-v", "q", "--project", PROJECT, "--", args.dungeon, "--out", doors_dir,
                             "--export-mesh", "--world-scale", str(args.world_scale)], capture_output=True, text=True, errors="replace")
    if result.returncode or not os.path.exists(doors_pk3):
        sys.exit("door package export failed:\n" +result.stdout[-1000:] + result.stderr[-1000:])
    doom_started = time.time()
    player = [os.path.join(out, slug + "_player.pk3")] if args.daggerfall_player else []
    # A private config keeps this launch windowed from the first frame, so it cannot interrupt the owner.
    with open(os.path.join(parity, "doom.ini"), "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWMINNOACTIVE
    # ZScript cannot quit the engine, so this stops the one process it started once the log reports completion.
    process = subprocess.Popen([args.uzdoom,
                                "-iwad", IWAD, "-file", os.path.join(out, slug + ".wad"), doors_pk3, *player,
                                os.path.join(HERE, "parity_doom"), os.path.join(parity, "lumps"),
                                "-config", os.path.join(parity, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
                                "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
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
    state = [l.strip() for l in open(log, errors="replace") if l.startswith(("DFDOORS", "DFDOORSTATE"))]
    print("\n".join(state))
    if not finished:
        sys.exit("UZDoom did not finish the test; see " + log)
    # Daggerfall's side models closed doors as solid boxes and open doors as absent, so Doom's doors must match.
    door_states = {m.group(1): tuple(map(int, m.groups()[1:])) for m in
                   (re.match(r"DFDOORSTATE (closed|opened) links (\d+) solid (\d+) moved (\d+)$", l) for l in state) if m}
    if "closed" not in door_states or "opened" not in door_states:
        sys.exit("the door state report is missing; the door stages would mean nothing")
    links, solid, moved = door_states["closed"]
    if not links or solid != links or moved:
        sys.exit(f"closed doors must be in place and solid: links {links} solid {solid} moved {moved}")
    links, solid, moved = door_states["opened"]
    if moved != links or solid:
        sys.exit(f"open doors must have swung and be non-solid: links {links} solid {solid} moved {moved}")
    with open(flood, "w") as f:
        f.writelines(lines)
    convert(args.dungeon, out, parity, args.world_scale, extra)
    print(f"Total {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
