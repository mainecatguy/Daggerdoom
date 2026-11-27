"""Stages the distant view demo (terrain and nature flats to the horizon) in the review folder: this build's engine, a
copy of a review folder's game data (read only source), the test screenshots, and play.bat. Game data stays outside
the repo.

usage: stage_demo.py [--out DIR] [--data DIR] [--build DIR] [--shots DIR]
"""
import argparse, os, shutil

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-loop\review\distant-lod-flats")
ap.add_argument("--data", default=r"D:\dev\DoomDaggerfall-loop\review\nature-flats\data")
ap.add_argument("--build", default=r"D:\dev\DoomDaggerfall-build\uzdoom-carbine\Release")
ap.add_argument("--shots", default=r"D:\dev\DoomDaggerfall-build\distantlod-tests")
args = ap.parse_args()

out = args.out
os.makedirs(os.path.join(out, "run"), exist_ok=True)
for src, name in ((args.build, "uzdoom"), (args.data, "data")):
    dst = os.path.join(out, name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
shots = os.path.join(out, "screenshots")
os.makedirs(shots, exist_ok=True)
for n in os.listdir(args.shots):
    if n.startswith("compare_") and n.endswith(".png"):
        shutil.copy(os.path.join(args.shots, n), shots)

common = (r'"%HERE%uzdoom\uzdoom.exe" -iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" -file "%HERE%data\ddruntime.pk3" "%HERE%data\overworld.pk3" '
          r'-config "%HERE%run\uzdoom.ini" -savedir "%HERE%run\saves" -ddtowncache "%HERE%run\cache" -ddconverter "%HERE%data\converter\DungeonConverter.exe" '
          r'-ddarena2 "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" -skill 3 -nomonsters +vid_fullscreen 0 +wipetype 0')
bat = (
    "@echo off\r\n"
    "rem Distant view: terrain AND wilderness trees, rocks and plants to the horizon (branch agent/distantlod-20261127-033005).\r\n"
    "rem Doom only, no Daggerfall Unity, monsters off.\r\n"
    "rem\r\n"
    "rem   play.bat            woodland on the overworld (map pixel 122,257). About 2 s after loading you are moved there.\r\n"
    "rem   play.bat dungeon    the Privateer's Hold / Gothway Garden exterior map.\r\n"
    "rem   play.bat city       the overworld 18 tiles west of the City of Daggerfall. Walk east into the town map, then turn\r\n"
    "rem                       around: the forest now continues past the town map's edge to the horizon.\r\n"
    "rem\r\n"
    "rem Look at the horizon, best from a hilltop: the trees beyond the loaded area are drawn by the distant view, from the\r\n"
    "rem same rule as the nearby ones, so they stand in the same spots on every map and every visit. Nothing is saved.\r\n"
    "rem In the console (~): dd_horizon 0 turns the distant view off, dd_horizon 1 back on.\r\n"
    "rem Screenshots are in the screenshots folder (compare_*.png: top distant view on, bottom off, unless labelled).\r\n"
    "set \"HERE=%~dp0\"\r\n"
    "if not exist \"%HERE%run\\saves\" mkdir \"%HERE%run\\saves\"\r\n"
    "if not exist \"%HERE%run\\cache\" mkdir \"%HERE%run\\cache\"\r\n"
    "set MAP=DDOVER01\r\n"
    "set \"SPOT=15632 31040\"\r\n"
    "if /i \"%1\"==\"dungeon\" set MAP=DDT07154\r\n"
    "if /i \"%1\"==\"city\" set \"SPOT=26489 36672\"\r\n"
    "> \"%HERE%run\\spot.cfg\" echo wait 70; dd_tm_warp \"%SPOT%\"\r\n"
    "if /i \"%MAP%\"==\"DDT07154\" > \"%HERE%run\\spot.cfg\" echo.\r\n"
    f"start \"\" {common} +map %MAP% +exec \"%HERE%run\\spot.cfg\"\r\n"
)
with open(os.path.join(out, "play.bat"), "w", newline="") as f:
    f.write(bat)
for mode in ("dungeon", "city"):
    with open(os.path.join(out, f"play-{mode}.bat"), "w", newline="") as f:
        f.write(f"@echo off\r\ncall \"%~dp0play.bat\" {mode}\r\n")
print("staged", out)
