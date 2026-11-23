"""Builds and assembles the Daggerfall map demo in its private review folder.

usage: build_map.py build | unity | assemble | check | registry save|compare
Reuses the inventory menu tool's steps with this demo's folders. Game data stays out of the repo.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "inventory_menu"))
import inventory_menu as base  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\daggerfall-map")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\connected-transitions")  # Town, door, and dungeon data.
base.REVIEW, base.BUILD, base.RUN, base.PREVIOUS = REVIEW, REVIEW / "build", REVIEW / "run", SOURCE

PLAY = r"""@echo off
rem Starts in Gothway Garden, beside houses and the Privateer's Hold entrance. Tab is Doom's map command.
rem Tab opens Daggerfall's map here. Tab, Esc, or Exit closes it. K opens fast travel and I the inventory.
rem Rebind the map under Options, Customize Controls. Daggerfall's window stays open behind Doom.
set "HERE=%~dp0"
if not exist "%HERE%play" mkdir "%HERE%play"
set BINDS=
if not exist "%HERE%play\uzdoom.ini" set BINDS=--uzdoom-arg +bind --uzdoom-arg tab --uzdoom-arg togglemap --uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg "netevent df_inventory" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_fast_travel"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%HERE%ddruntime.pk3" --mod "%HERE%overworld.pk3" --mod "%HERE%privateershold.wad" --mod "%HERE%privateershold_mesh.pk3" --mod "%HERE%privateershold_doors.pk3" --mod "%HERE%doomerfall" --uzdoom-cwd "%HERE%play" --log "%HERE%play\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%play\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%play\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%play\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%HERE%test-cache" --uzdoom-arg -ddconverter --uzdoom-arg "%HERE%converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT07154 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 %BINDS% --dfu-arg -dfbridgelog --dfu-arg "%HERE%play\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800
"""

command = sys.argv[1] if len(sys.argv) > 1 else ""
if command == "build":
    base.build()
elif command == "unity":
    base.unity()
elif command == "assemble":
    REVIEW.mkdir(parents=True, exist_ok=True)
    base.assemble()
    for name in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        shutil.copy2(SOURCE / name, REVIEW)
    if not (REVIEW / "test-cache").exists():
        shutil.copytree(SOURCE / "test-cache", REVIEW / "test-cache")
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
elif command == "check":
    base.check()
elif command == "registry":
    base.registry(sys.argv[2])
else:
    sys.exit(__doc__)
