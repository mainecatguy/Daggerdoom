"""Builds and assembles the private connected-transitions demo. Nothing generated lands in the repo.

Usage: make.py build [bridge launcher uzdoom converter] | make.py assemble
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "fast_travel_arrival"))
import assemble as base_assemble  # noqa: E402
import build as base_build  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\connected-transitions")
DATA = REVIEW.parent / "combined-bridge" / "data"
DUNGEON = ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
base_build.REVIEW = base_assemble.REVIEW = REVIEW
base_build.BUILD = base_assemble.BUILD = REVIEW / "build"

PLAY = r"""@echo off
rem Starts in Gothway Garden. Walk to a building door or Privateer's Hold and press Use.
rem Daggerfall's window stays open behind Doom and follows you through each door.
set "HERE=%~dp0"
if not exist "%HERE%run" mkdir "%HERE%run"
start "" "%HERE%doomerfall-launcher.exe" --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%HERE%ddruntime.pk3" --mod "%HERE%overworld.pk3" --mod "%HERE%privateershold.wad" --mod "%HERE%privateershold_mesh.pk3" --mod "%HERE%privateershold_doors.pk3" --mod "%HERE%doomerfall" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%HERE%town-cache" --uzdoom-arg -ddconverter --uzdoom-arg "%HERE%converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT07154 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800
"""


def main():
    if sys.argv[1] == "build":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        base_build.main()
        return
    base_assemble.main()
    for name in DUNGEON:
        shutil.copy2(DATA / name, REVIEW)
    shutil.copytree(DATA / "cache", REVIEW / "town-cache", dirs_exist_ok=True)  # The demo's first doors open without a conversion wait.
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")


if __name__ == "__main__":
    main()
