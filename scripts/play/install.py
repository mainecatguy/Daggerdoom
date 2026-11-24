"""Assembles the current playable Doomerfall from this checkout's builds. Saves and settings in its run folder are kept.

Usage: install.py [target folder]. UZDoom and Daggerfall Unity must already be built from this checkout.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO.parent / "DoomDaggerfall-build"
LOOP = Path(r"D:\dev\DoomDaggerfall-loop")
TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else LOOP / "play"
DATA = LOOP / "review" / "monster-deaths" / "data"  # Its dungeon map carries the monster IDs.
ITEM_SPRITES = LOOP / "review" / "item-pickup" / "dfitems.pk3"
SOUND_DLLS = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")

PLAY = r'''@echo off
rem Doomerfall: choose New Game in Doom's menu. Use picks up what you look at (crouch to Steal), and health and ammo pick up by touch. E is a second Interact key, I opens the inventory, K opens fast travel.
rem Rebind them in Options, Customize Controls, Doomerfall Controls.
set "HERE=%~dp0"
set "DATA=%HERE%data"
set "DF=@DAGGER@"
if not exist "%HERE%run\saves" mkdir "%HERE%run\saves"
set BINDS=
if not exist "%HERE%run\uzdoom.ini" set BINDS=--uzdoom-arg +bind --uzdoom-arg e --uzdoom-arg "netevent df_interact" --uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg "netevent df_inventory" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_fast_travel"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "@IWAD@" --mod "@MODS@\DoomRL_Arsenal_1.1.5.pk3" --mod "@MODS@\DoomRL_Monsters_Beta_7.3.pk3" --mod "@MODS@\drlax_1.2b.pk3" --mod "%DATA%\ddruntime.pk3" --mod "%DATA%\overworld.pk3" --mod "%DATA%\privateershold.wad" --mod "%DATA%\privateershold_mesh.pk3" --mod "%DATA%\privateershold_doors.pk3" --mod "%HERE%dfitems.pk3" --mod "%HERE%doomerfall.pk3" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -dfflow --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%DATA%\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%DATA%\converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "%DF%\ARENA2" --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +wipetype --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfflow --dfu-arg "%DF%" --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%
'''


def build(source, folder, target):
    out = BUILD / folder
    subprocess.check_call(["cmake", "-S", str(REPO / source), "-B", str(out), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=subprocess.DEVNULL)
    subprocess.check_call(["cmake", "--build", str(out), "--config", "Release", "--target", target, "--parallel", "6"], stdout=subprocess.DEVNULL)
    return out / "Release"


def replace_tree(source, name):
    destination = TARGET / name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def isolate_registry(dfu):
    # Unity picks its registry key from the product name, so this copy must not share the owner's Daggerfall settings.
    managers = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = managers.read_bytes()
    stock, private = b"\x10\0\0\0Daggerfall Unity", b"\x10\0\0\0Doomerfall Local"
    if stock in data:
        managers.write_bytes(data.replace(stock, private))
    elif private not in data:
        raise SystemExit("could not isolate the Daggerfall registry key")


def main():
    bridge = build("bridge", "bridge", "doomerfall_bridge")
    launcher = build("launcher", "launcher", "doomerfall-launcher")
    TARGET.mkdir(parents=True, exist_ok=True)

    uzdoom = replace_tree(BUILD / "uzdoom" / "Release", "uzdoom")
    (uzdoom / "check.ini").unlink(missing_ok=True)
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND_DLLS / dll, uzdoom / dll)

    dfu = replace_tree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", "dfu")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bridge / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    isolate_registry(dfu)

    if not (TARGET / "data").exists():
        shutil.copytree(DATA, TARGET / "data")
    for packaged in DATA.iterdir():  # The town cache and converter stay, so towns are not rebuilt on every install.
        if packaged.is_file():
            shutil.copy2(packaged, TARGET / "data" / packaged.name)
    shutil.copy2(ITEM_SPRITES, TARGET / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(TARGET / "doomerfall.pk3")])
    shutil.copy2(launcher / "doomerfall-launcher.exe", TARGET / "doomerfall-launcher.exe")

    play = PLAY.replace("@DAGGER@", str(GAME / "DAGGER")).replace("@IWAD@", str(GAME / "wads" / "DOOM2.WAD")).replace("@MODS@", str(GAME.parent / "GameMods"))
    (TARGET / "play.bat").write_text(play, newline="\r\n")
    print("installed", TARGET)


if __name__ == "__main__":
    main()
