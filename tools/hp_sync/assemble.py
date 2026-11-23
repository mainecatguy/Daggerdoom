"""Assemble the private HP sync demo. Game data and generated files stay outside the repo.

The Daggerfall copy is portable and patched to its own product name, so it has its own registry key
and never touches the owner's real Daggerfall Unity settings or saves.
"""
import shutil
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\hp-sync")
BUILD = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-menu\build")
SEED = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync")
LAUNCHER_COPIES = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
REAL_NAME = b"Daggerfall Unity"
PRIVATE_NAME = b"Doomerfall Local"

PLAY = r"""@echo off
rem Doom's health is Daggerfall's health. DOOM.WAD E1M1 with the DRLA set, a hidden Daggerfall game behind it.
rem Monster hits and health pickups go to Daggerfall; the health you see is what Daggerfall confirms.
rem Press G in Doom to make Daggerfall itself hurt you for 15 (a stand-in for a Daggerfall attacker).
rem At 0 Daggerfall reports death and Doom kills you. Close either game and both close.
rem Add the word stock to play DOOM.WAD without the DRLA set: play.bat stock
set "HERE=%~dp0"
set "MODS=D:\dev\DoomDaggerfall\GameMods"
set "DRLA=--mod %MODS%\DoomRL_Arsenal_1.1.5.pk3 --mod %MODS%\DoomRL_Monsters_Beta_7.3.pk3 --mod %MODS%\drlax_1.2b.pk3"
if /i "%~1"=="stock" set "DRLA="
if not exist "%HERE%run" mkdir "%HERE%run"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD" %DRLA% --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg E1M1 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --uzdoom-arg +bind --uzdoom-arg g --uzdoom-arg "netevent df_hp_damage" --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -dfhptest --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800
"""


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles"))


def main():
    (REVIEW / "run").mkdir(parents=True, exist_ok=True)
    dfu = REVIEW / "dfu"
    copy_tree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
    (dfu / "Portable.txt").touch()
    if not (dfu / "PortableAppdata").exists():
        shutil.copytree(SEED / "dfu" / "PortableAppdata", dfu / "PortableAppdata", ignore=shutil.ignore_patterns("*.log"))

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
        shutil.copy2(LAUNCHER_COPIES / name, uz)
    shutil.copy2(BUILD / "launcher" / "Release" / "doomerfall-launcher.exe", REVIEW)
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
