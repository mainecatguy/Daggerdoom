"""Copies the built games into review/new-game and writes its one-click play.bat."""
import shutil
from pathlib import Path

WORK = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\new-game")

PLAY = r'''@echo off
rem Doomerfall New Game: choose New Game in Doom, make a character, watch the cinematics, pick a difficulty.
set "HERE=%~dp0"
set "DATA=%HERE%..\combined-bridge\data"
set "DF=D:\dev\DoomDaggerfall\GameResources\DAGGER"
if not exist "%HERE%run\saves" mkdir "%HERE%run\saves"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%DATA%\ddruntime.pk3" --mod "%DATA%\overworld.pk3" --mod "%DATA%\privateershold.wad" --mod "%DATA%\privateershold_mesh.pk3" --mod "%DATA%\privateershold_doors.pk3" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -dfflow --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%DATA%\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%DATA%\converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "%DF%\ARENA2" --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +wipetype --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfflow --dfu-arg "%DF%" --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 960 --dfu-arg -screen-height --dfu-arg 540
'''


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BUILD / "uzdoom-newgame" / "Release", REVIEW / "uzdoom", dirs_exist_ok=True)
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(BUILD / "uzdoom-launcher" / "Release" / dll, REVIEW / "uzdoom" / dll)
    shutil.copytree(WORK / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", dirs_exist_ok=True)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge-newgame" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / PORTABLE).write_text("")
    # Portable mode does not isolate Unity's registry values. The product name picks the key, so this copy gets its own.
    managers = REVIEW / "dfu" / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = managers.read_bytes()
    count = data.count(b"\x10\0\0\0Daggerfall Unity")  # Unity strings are length prefixed. Both names are 16 bytes.
    if count:
        managers.write_bytes(data.replace(b"\x10\0\0\0Daggerfall Unity", b"\x10\0\0\0Doomerfall Local"))
    elif b"\x10\0\0\0Doomerfall Local" not in data:
        raise SystemExit("could not isolate the Daggerfall registry key")
    print("product name occurrences patched:", count)
    shutil.copy2(BUILD / "launcher-newgame" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    (REVIEW / "play.bat").write_text(PLAY, newline="\r\n")
    print("staged", REVIEW)


PORTABLE = "Portable.txt"

if __name__ == "__main__":
    main()
