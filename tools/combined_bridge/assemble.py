"""Assembles the private combined bridge and door demo. Game data and generated files stay outside the repo.

Usage: assemble.py baseline   copies the current native build and the HP lane's Daggerfall as the "before" build
       assemble.py            copies the current native build and this worktree's Daggerfall build

The Daggerfall copy is portable and patched to its own product name, so it has its own registry key
and never touches the owner's real Daggerfall Unity settings or saves.
"""
import shutil
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
LOOP = Path(r"D:\dev\DoomDaggerfall-loop\review")
REVIEW = LOOP / "combined-bridge"
BUILD = LOOP / "fast-travel-menu" / "build"
ENTRY = LOOP / "building-entry"
SEED = LOOP / "hp-sync" / "dfu"
LAUNCHER_COPIES = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
REAL_NAME = b"Daggerfall Unity"
PRIVATE_NAME = b"Doomerfall Local"

PLAY = r"""@echo off
rem Doom and a hidden Daggerfall together, starting in the City of Daggerfall.
rem Press Use on a building door to go in, and on the door inside to come back out.
rem K opens Daggerfall's travel map, indoors too. Choosing a destination does not move you yet.
rem Close either game and both close. Add the word show to keep Daggerfall's 3D view: play.bat show
set "HERE=%~dp0"
set "DRAW=--nodraw"
if /i "%~1"=="show" set "DRAW="
if not exist "%HERE%run" mkdir "%HERE%run"
start "" "%HERE%doomerfall-launcher.exe" %DRAW% --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%HERE%data\ddruntime.pk3" --mod "%HERE%data\overworld.pk3" --mod "%HERE%data\privateershold.wad" --mod "%HERE%data\privateershold_mesh.pk3" --mod "%HERE%data\privateershold_doors.pk3" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%HERE%data\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%HERE%data\converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT09183 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +wipetype --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_fast_travel" --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 960 --dfu-arg -screen-height --dfu-arg 540
"""

SKIP = shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles")


def isolate(dfu):
    (dfu / "Portable.txt").touch()
    if not (dfu / "PortableAppdata").exists():
        shutil.copytree(SEED / "PortableAppdata", dfu / "PortableAppdata", ignore=shutil.ignore_patterns("*.log"))
    manager = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if REAL_NAME in data:
        manager.write_bytes(data.replace(REAL_NAME, PRIVATE_NAME))
    elif PRIVATE_NAME not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge" / "Release" / "doomerfall_bridge.dll", plugins)


def main():
    baseline = sys.argv[1:] == ["baseline"]
    root = REVIEW / "baseline" if baseline else REVIEW
    (root / "run" / "saves").mkdir(parents=True, exist_ok=True)

    data = REVIEW / "data"
    if not data.exists():
        (data / "converter").mkdir(parents=True)
        for name in ("ddruntime.pk3", "overworld.pk3"):
            shutil.copy2(ENTRY / name, data)
        for name in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
            shutil.copy2(ENTRY / "dungeon" / name, data)
        shutil.copytree(ENTRY / "converter", data / "converter", dirs_exist_ok=True)
        shutil.copytree(ENTRY / "testcache", data / "cache", ignore=shutil.ignore_patterns("work"))

    dfu = root / "dfu"
    source = SEED if baseline else WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64"
    shutil.copytree(source, dfu, dirs_exist_ok=True, ignore=SKIP)
    isolate(dfu)

    uz = root / "uzdoom"
    shutil.copytree(BUILD / "uzdoom" / "Release", uz, dirs_exist_ok=True, ignore=SKIP)
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(LAUNCHER_COPIES / name, uz)
    shutil.copy2(BUILD / "launcher" / "Release" / "doomerfall-launcher.exe", root)
    if not baseline:
        (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
    print("assembled", root)


if __name__ == "__main__":
    main()
