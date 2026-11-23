"""Assemble the private fast travel demo. Game data and generated files stay outside the repo.

The Daggerfall copy is portable and patched to its own product name, so it has its own registry key
and never touches the owner's real Daggerfall Unity settings or saves.
"""
import shutil
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-arrival")
BUILD = REVIEW / "build"
MENU = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-menu")
SOUND = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
REAL_NAME = b"Daggerfall Unity"
PRIVATE_NAME = b"Doomerfall Local"

PLAY = r"""@echo off
rem Press K in Doom to open Daggerfall's travel map. Pick a place and press Begin. Esc or K cancels.
rem Daggerfall's window stays open behind Doom for now. Close either game and both close.
set "HERE=%~dp0"
if not exist "%HERE%run" mkdir "%HERE%run"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%HERE%ddruntime.pk3" --mod "%HERE%overworld.pk3" --mod "%HERE%doomerfall" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%HERE%town-cache" --uzdoom-arg -ddconverter --uzdoom-arg "%HERE%converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDOVER01 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_fast_travel" --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800
"""


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles"))


def main():
    (REVIEW / "run").mkdir(parents=True, exist_ok=True)
    dfu = REVIEW / "dfu"
    copy_tree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
    (dfu / "Portable.txt").touch()
    if not (dfu / "PortableAppdata").exists():
        shutil.copytree(MENU / "dfu" / "PortableAppdata", dfu / "PortableAppdata", ignore=shutil.ignore_patterns("*.log"))

    manager = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if REAL_NAME in data:
        manager.write_bytes(data.replace(REAL_NAME, PRIVATE_NAME))
    elif PRIVATE_NAME not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")

    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge" / "Release" / "doomerfall_bridge.dll", plugins)

    uz = REVIEW / "uzdoom"
    copy_tree(BUILD / "uzdoom" / "Release", uz)
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / name, uz)
    shutil.copy2(BUILD / "launcher" / "Release" / "doomerfall-launcher.exe", REVIEW)
    copy_tree(WORKTREE / "mods" / "doomerfall" / "src", REVIEW / "doomerfall")
    copy_tree(BUILD / "converter", REVIEW / "converter")
    shutil.copy2(BUILD / "ddruntime.pk3", REVIEW)
    shutil.copy2(MENU / "overworld.pk3", REVIEW)  # No placeholder monster packs, starts in Ephesus.
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
