"""Assembles the current playable Doomerfall from this checkout. Saves and settings in its run folder are kept.

Usage: install.py [target folder] [--build-dir DIR] [--keep-data]
Builds UZDoom, the bridge, and the launcher, and copies this checkout's Daggerfall Unity build, which must already be
built. Then it builds the converter and item sprite tool from this checkout and makes every data file with them, so
the maps, the town cache, and the sprites always match the code. --keep-data skips the data step.
Everything generated stays outside the repository: tool builds and scratch maps go under the build folder.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOOP = Path(r"D:\dev\DoomDaggerfall-loop")
SOUND_DLLS = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"
DUNGEON = "Privateer's Hold"
TOWN_GROUPS = [7154]  # Converted ahead of time. Other places convert on first visit into the same cache.
OVERWORLD_START = ["--start-tile", "26592,36608", "--start-angle", "180"]  # As in the earlier play data.

PLAY = r'''@echo off
rem Doomerfall: choose New Game in Doom's menu. Use picks up what you look at (crouch to Steal), and health and ammo pick up by touch. E is a second Interact key, Q is Info (inspect what you look at), I opens the inventory, K opens fast travel.
rem Rebind them in Options, Customize Controls, Doomerfall Controls.
rem @TRY@
set "HERE=%~dp0"
set "DATA=%HERE%data"
set "DF=@DAGGER@"
if not exist "%HERE%run\saves" mkdir "%HERE%run\saves"
set BINDS=
if not exist "%HERE%run\uzdoom.ini" set BINDS=--uzdoom-arg +bind --uzdoom-arg e --uzdoom-arg "netevent df_interact" --uzdoom-arg +bind --uzdoom-arg q --uzdoom-arg "netevent df_info" --uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg "netevent df_inventory" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_fast_travel"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "@IWAD@" --mod "@MODS@\DoomRL_Arsenal_1.1.5.pk3" --mod "@MODS@\DoomRL_Monsters_Beta_7.3.pk3" --mod "@MODS@\drlax_1.2b.pk3" --mod "%DATA%\ddruntime.pk3" --mod "%DATA%\overworld.pk3" --mod "%DATA%\privateershold.wad" --mod "%DATA%\privateershold_mesh.pk3" --mod "%DATA%\privateershold_doors.pk3" --mod "%HERE%dfitems.pk3" --mod "%HERE%doomerfall.pk3" --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" --uzdoom-arg -dfflow --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%run\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%run\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%DATA%\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%DATA%\converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "%DF%\ARENA2" --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +wipetype --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfflow --dfu-arg "%DF%" --dfu-arg -dfbridgelog --dfu-arg "%HERE%run\df.log" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%
'''

# What to try, for the owner. One line each, written into play.bat as rem lines.
TRY = [
    "What to try (each was merged and tested on its own; this build has them all together):",
    " 1. New Game: make a character in Daggerfall's real creation screens. You wake in Privateer's Hold.",
    " 2. Privateer's Hold: rooms hold a stimpack, clip, or shells (walk over them). Kill a monster, look at its drop, press Use.",
    " 3. Pick up a Doom gun with Use. If nothing is on its number key yet it is drawn at once; otherwise put it on a hotkey from the inventory (I) and press that key to swap.",
    " 4. Look at a ground item or monster and press Q for Info, like Daggerfall's Info mode.",
    " 5. Climb a wall: walk into it and keep pressing forward. Back climbs down; holding still lets you shoot.",
    " 6. Leave the dungeon and walk into town. Townspeople walk the streets; at night they are inside their homes.",
    " 7. Use on a townsperson to talk. Use on a shopkeeper for Daggerfall's shop menu.",
    " 8. Crouch and Use on shop goods to steal. If you are seen, guards come and fight you, Doom style.",
    " 9. Press K for the travel map. Hover a place to see its danger hint. Places have fixed area levels.",
    "10. Save from Doom's menu, quit, start play.bat again, and load: both games come back together.",
]


def run(args, **kw):
    subprocess.check_call([str(a) for a in args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, **kw)


def build(source, out, target):
    run(["cmake", "-S", REPO / source, "-B", out, "-G", "Visual Studio 18 2026", "-A", "x64"])
    run(["cmake", "--build", out, "--config", "Release", "--target", target, "--parallel", "6"])
    return out / "Release"


def replace_tree(source, destination):
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


def make_data(build_dir, target):
    """Every data file from this checkout's converter. Built in a staging folder, then swapped in whole."""
    stage, scratch = build_dir / "play-data", build_dir / "play-scratch"
    for folder in (stage, scratch):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
    converter = stage / "converter"
    run(["dotnet", "build", REPO / "tools" / "dungeon_converter" / "DungeonConverter.csproj", "-c", "Release", "-v", "q", "-o", converter,
         f"-p:DungeonConverterBuildRoot={build_dir / 'play-converter'}\\"])
    exe = converter / "DungeonConverter.exe"
    arena2 = ["--arena2", ARENA2]
    print("data: shared runtime package")
    run([exe, "--runtime-assets", "--out", stage / "ddruntime.pk3", *arena2])
    print("data:", DUNGEON)
    dungeon = scratch / "dungeon"
    run([exe, DUNGEON, "--out", dungeon, *arena2])  # The map, its doors, and its pickups.
    run([exe, DUNGEON, "--export-mesh", "--runtime-dungeon", "--out", dungeon, *arena2])
    slug = "".join(c for c in DUNGEON if c.isalnum()).lower()
    for suffix in (".wad", "_mesh.pk3", "_doors.pk3"):
        shutil.copy2(dungeon / (slug + suffix), stage / (slug + suffix))
    print("data: overworld")
    world = scratch / "world"
    run([exe, "--world", "--out", world, *arena2])
    run([sys.executable, REPO / "tools" / "overworld" / "gen_overworld.py", "--out", stage / "overworld.pk3", "--world-dir", world,
         "--ground-from", stage / "ddruntime.pk3", *OVERWORLD_START])
    cache = stage / "cache"
    cache.mkdir()
    for group in TOWN_GROUPS:
        print("data: town", group)
        run([exe, "--group", group, "--ddt", cache / f"T{group:05d}.ddt", "--out", scratch / f"town{group}", *arena2])
    print("data: item sprites")
    templates = REPO / "daggerfall-unity-master" / "Assets" / "StreamingAssets" / "ItemTemplates.txt"
    if not templates.exists():
        templates = next((REPO / "daggerfall-unity-master" / "Assets").rglob("ItemTemplates.txt"))
    run(["dotnet", "run", "-c", "Release", "-v", "q", "--project", REPO / "tools" / "item_gallery" / "ItemGallery.csproj",
         f"-p:ItemGalleryBuildRoot={build_dir / 'play-item-gallery'}\\", "--",
         ARENA2, templates, REPO / "mods" / "daggerfall_items", stage / "dfitems.pk3", scratch / "dfitems-manifest.tsv"])
    shutil.move(str(stage / "dfitems.pk3"), str(target / "dfitems.pk3"))
    replace_tree(stage, target / "data")  # Cached towns must come from the same converter as the packaged data.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", type=Path, default=LOOP / "play")
    ap.add_argument("--build-dir", type=Path, default=REPO.parent / "DoomDaggerfall-build", help="native builds, tool builds, and scratch data")
    ap.add_argument("--keep-data", action="store_true", help="keep the target's data and sprites instead of rebuilding them")
    args = ap.parse_args()
    target, build_dir = args.target.resolve(), args.build_dir.resolve()

    bridge = build("bridge", build_dir / "bridge", "doomerfall_bridge")
    launcher = build("launcher", build_dir / "launcher", "doomerfall-launcher")
    target.mkdir(parents=True, exist_ok=True)

    uzdoom = replace_tree(build("UZDoom", build_dir / "uzdoom", "zdoom"), target / "uzdoom")  # Always rebuilt, so it matches this checkout's bridge.
    (uzdoom / "check.ini").unlink(missing_ok=True)
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND_DLLS / dll, uzdoom / dll)

    dfu = replace_tree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", target / "dfu")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bridge / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    isolate_registry(dfu)

    if not args.keep_data:
        make_data(build_dir, target)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(target / "doomerfall.pk3")])
    shutil.copy2(launcher / "doomerfall-launcher.exe", target / "doomerfall-launcher.exe")

    play = PLAY.replace("@DAGGER@", str(GAME / "DAGGER")).replace("@IWAD@", str(GAME / "wads" / "DOOM2.WAD")).replace("@MODS@", str(GAME.parent / "GameMods"))
    play = play.replace("@TRY@", "\nrem ".join(TRY))
    (target / "play.bat").write_text(play, newline="\r\n")
    print("installed", target)


if __name__ == "__main__":
    main()
