"""Assemble the private bridge demo folder. Game data stays outside the repo.

The Daggerfall copy is patched to its own product name, so it has its own registry key and never
touches the owner's real Daggerfall Unity settings.
"""
import shutil
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
REVIEW = WORKTREE / "daggerfall-unity-master" / "Builds" / "bridge-core"  # git-ignored
OLD_REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\launcher")
REAL_NAME = b"Daggerfall Unity"
PRIVATE_NAME = b"Doomerfall Local"

PLAY_BAT = r"""@echo off
rem Starts both real games through the launcher and shows the bridge traffic in a log window.
rem Daggerfall uses the private copy in this folder. Close either game and the other closes too.
set "HERE=%~dp0"
set "IWAD=D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
if not exist "%HERE%run" mkdir "%HERE%run"
del /q "%HERE%run\uz-bridge.log" "%HERE%run\df-bridge.log" 2>nul
type nul > "%HERE%run\uz-bridge.log"
type nul > "%HERE%run\df-bridge.log"
start "Bridge log: Daggerfall side" powershell -NoProfile -Command "Get-Content -Wait -Tail 30 -LiteralPath '%HERE%run\df-bridge.log'"
start "Bridge log: UZDoom side" powershell -NoProfile -Command "Get-Content -Wait -Tail 30 -LiteralPath '%HERE%run\uz-bridge.log'"
start "" "%HERE%doomerfall-launcher.exe" --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "%IWAD%" --mod-list "%HERE%mods.txt" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz-bridge.log" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg E1M1 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df-bridge.log" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 960 --dfu-arg -screen-height --dfu-arg 540
"""


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles"))


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    (REVIEW / "run").mkdir(exist_ok=True)

    dfu = REVIEW / "dfu"
    copy_tree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
    (dfu / "Portable.txt").touch()
    appdata = dfu / "PortableAppdata"
    if not appdata.exists():
        shutil.copytree(OLD_REVIEW / "dfu" / "PortableAppdata", appdata)

    manager = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    count = data.count(REAL_NAME)
    if count:
        manager.write_bytes(data.replace(REAL_NAME, PRIVATE_NAME))
    elif PRIVATE_NAME not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")
    print(f"patched {count} product name occurrence(s)")

    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge" / "Release" / "doomerfall_bridge.dll", plugins)

    uz = REVIEW / "uzdoom"
    copy_tree(BUILD / "uzdoom-bridge" / "Release", uz)
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(BUILD / "uzdoom-launcher" / "Release" / name, uz)

    shutil.copy2(BUILD / "launcher-bridge" / "Release" / "doomerfall-launcher.exe", REVIEW)
    shutil.copy2(OLD_REVIEW / "mods.txt", REVIEW / "mods.txt")
    (REVIEW / "play.bat").write_text(PLAY_BAT.replace("\n", "\r\n"), newline="")
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
