"""Stages the distant terrain demo in the review folder: this build's engine, a copy of a review folder's game data
(read only source), the test screenshots, and play.bat. Game data stays outside the repo.

usage: stage_demo.py [--out DIR] [--data DIR] [--build DIR]
"""
import argparse, os, shutil

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-loop\review\distant-lod")
ap.add_argument("--data", default=r"D:\dev\DoomDaggerfall-loop\review\arrival-spawn\data")
ap.add_argument("--build", default=r"D:\dev\DoomDaggerfall-build\uzdoom-distantlod\Release")
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
for n in ("over3_a_0", "over3_off_0", "over3_a_1", "over3_off_1", "town1_a_0", "town1_off_0", "town1_a_2", "town1_off_2", "sheet2", "dfu_compare"):
    p = os.path.join(args.shots, n + ".png")
    if os.path.exists(p):
        shutil.copy(p, shots)

common = (r'"%HERE%uzdoom\uzdoom.exe" -iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" -file "%HERE%data\ddruntime.pk3" "%HERE%data\overworld.pk3" '
          r'-config "%HERE%run\uzdoom.ini" -savedir "%HERE%run\saves" -ddtowncache "%HERE%data\cache" -ddconverter "%HERE%data\converter\DungeonConverter.exe" '
          r'-ddarena2 "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" -skill 3 -nomonsters +vid_fullscreen 0 +wipetype 0')
bat = (
    "@echo off\r\n"
    "rem Distant terrain view (branch agent/distantlod-20261126-213115), Doom only, no Daggerfall Unity.\r\n"
    "rem Starts on the overworld near Privateer's Hold, with monsters off. Look at the horizon: the hills beyond the loaded\r\n"
    "rem window are the new distant terrain. In the console (~), dd_horizon 0 turns it off and dd_horizon 1 turns it back on.\r\n"
    "rem Run in one direction: the window shifts every 32 tiles, and the distant hills should not jump.\r\n"
    "rem play.bat dungeon starts on the Privateer's Hold / Gothway Garden exterior map instead.\r\n"
    "rem Screenshots from the tests are in the screenshots folder (on = a, off = off).\r\n"
    "set \"HERE=%~dp0\"\r\n"
    "if not exist \"%HERE%run\\saves\" mkdir \"%HERE%run\\saves\"\r\n"
    "set MAP=DDOVER01\r\n"
    "if /i \"%1\"==\"dungeon\" set MAP=DDT07154\r\n"
    f"start \"\" {common} +map %MAP%\r\n"
)
with open(os.path.join(out, "play.bat"), "w", newline="") as f:
    f.write(bat)
with open(os.path.join(out, "play-dungeon.bat"), "w", newline="") as f:
    f.write("@echo off\r\ncall \"%~dp0play.bat\" dungeon\r\n")
print("staged", out)
