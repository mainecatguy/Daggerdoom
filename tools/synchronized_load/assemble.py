"""Assembles the private synchronized loading demo. Game data and generated files stay outside the repo.

The Daggerfall copy is portable and patched to its own product name, so it never touches the owner's
real Daggerfall Unity settings or saves.
"""
import shutil
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
LOOP = Path(r"D:\dev\DoomDaggerfall-loop\review")
REVIEW = LOOP / "synchronized-loading"
OLD = LOOP / "synchronized-saving"
BUILD = OLD / "build"
LAUNCHER_COPIES = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
REAL_NAME, PRIVATE_NAME = b"Daggerfall Unity", b"Doomerfall Local"
SKIP = shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles")

PLAY = r"""@echo off
rem Doom and a hidden Daggerfall together, starting in the City of Daggerfall.
rem Save and load from Doom's menu. Each save holds both games. After a death, choose Load Last Save, Load Game, or Main Menu.
rem Press K to take 15 damage from Daggerfall, which lets you test dying quickly. Close either game and both close.
set "HERE=%~dp0"
set "DATA=%HERE%..\combined-bridge\data"
if not exist "%HERE%run\saves" mkdir "%HERE%run\saves"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%DATA%\ddruntime.pk3" --mod "%DATA%\overworld.pk3" --mod "%DATA%\privateershold.wad" --mod "%DATA%\privateershold_mesh.pk3" --mod "%DATA%\privateershold_doors.pk3" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%DATA%\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%DATA%\converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT09183 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +wipetype --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_hp_damage" --dfu-arg -dfhptest --dfu-arg demo --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 960 --dfu-arg -screen-height --dfu-arg 540
"""


def main():
    (REVIEW / "run" / "saves").mkdir(parents=True, exist_ok=True)
    dfu = REVIEW / "dfu"
    shutil.copytree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, dirs_exist_ok=True, ignore=SKIP)
    (dfu / "Portable.txt").touch()
    if not (dfu / "PortableAppdata").exists():
        shutil.copytree(OLD / "dfu" / "PortableAppdata", dfu / "PortableAppdata", ignore=shutil.ignore_patterns("*.log", "SAVE*"))
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
    shutil.copytree(BUILD / "uzdoom" / "Release", uz, dirs_exist_ok=True, ignore=SKIP)
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(LAUNCHER_COPIES / name, uz)
    shutil.copy2(OLD / "doomerfall-launcher.exe", REVIEW)
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
