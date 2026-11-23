"""Assemble the private position sync demo. Game data and generated files stay outside the repo.

The Daggerfall copy is portable and patched to its own product name, so it has its own registry key
and never touches the owner's real Daggerfall Unity settings or saves.
"""
import shutil
import subprocess
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync")
APPDATA = WORKTREE / "daggerfall-unity-master" / "Builds" / "bridge-core" / "dfu" / "PortableAppdata"
REAL_NAME = b"Daggerfall Unity"
PRIVATE_NAME = b"Doomerfall Local"

PLAY = r"""@echo off
rem Doom drives; the Daggerfall window follows in the same area. Close either game and both close.
rem Add the word nodraw to hide Daggerfall's 3D world: play.bat nodraw
set "HERE=%~dp0"
set "DRAW="
if /i "%~1"=="nodraw" set "DRAW=--nodraw"
if not exist "%HERE%run" mkdir "%HERE%run"
start "" "%HERE%doomerfall-launcher.exe" %DRAW% --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%HERE%overworld.pk3" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDOVER01 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 960 --dfu-arg -screen-height --dfu-arg 540
"""


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles"))


def main():
    (REVIEW / "run").mkdir(parents=True, exist_ok=True)
    dfu = REVIEW / "dfu"
    copy_tree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
    (dfu / "Portable.txt").touch()
    if not (dfu / "PortableAppdata").exists():
        shutil.copytree(APPDATA, dfu / "PortableAppdata", ignore=shutil.ignore_patterns("*.log"))

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
    copy_tree(BUILD / "uzdoom-bridge" / "Release", uz)
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(BUILD / "uzdoom-launcher" / "Release" / name, uz)
    shutil.copy2(BUILD / "launcher-bridge" / "Release" / "doomerfall-launcher.exe", REVIEW)

    generator = WORKTREE / "tools" / "overworld" / "gen_overworld.py"
    subprocess.check_call([sys.executable, str(generator), "--out", str(REVIEW / "overworld.pk3"), "--packchance", "0"])
    subprocess.check_call([sys.executable, str(generator), "--out", str(REVIEW / "run" / "route.pk3"), "--packchance", "0",
                           "--harness", str(WORKTREE / "tools" / "position_sync" / "sync_harness.zs")])
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
