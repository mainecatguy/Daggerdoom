"""Assembles review\\town-lookback: a paired build of this checkout for the town look-back (nature flats beyond a town
map's edge), used by town_lookback_paired.py and by the owner's play.bat.

    python tools/nature/stage_lookback_demo.py --exe <uzdoom Release folder> [--data <make_data.py output>]

Takes this checkout's UZDoom (--exe folder), launcher and bridge (built here into D:\\dev\\DoomDaggerfall-build),
Daggerfall Unity build (daggerfall-unity-master\\Builds\\Windows64), doomerfall.pk3, the nature data, and the portable
Daggerfall Unity settings and dfitems.pk3 from review\\town-corpses (generated data, not in the repository).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\town-lookback")
DONOR = Path(r"D:\dev\DoomDaggerfall-loop\review\town-corpses")

PLAY = r"""@echo off
rem Town look-back demo: starts paired in the City of Daggerfall at noon. Walk west out of the city (past the walls)
rem and turn around, or stand at the town map's west edge and look out: the forest beyond the town map's own ground is
rem the distant view's render-only flats, standing on its terrain. "dd_horizon 0" in the console hides the distant view.
set HERE=%~dp0
set GAME=D:\dev\DoomDaggerfall\GameResources
if not exist "%HERE%run" mkdir "%HERE%run"
"%HERE%doomerfall-launcher.exe" --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "%GAME%\wads\DOOM2.WAD" ^
 --uzdoom-cwd "%HERE%run" --log "%HERE%run\launcher.log" ^
 --mod "%HERE%data\ddruntime.pk3" --mod "%HERE%data\overworld.pk3" --mod "%HERE%dfitems.pk3" --mod "%HERE%doomerfall.pk3" ^
 --uzdoom-arg -config --uzdoom-arg "%HERE%run\uzdoom.ini" --uzdoom-arg -skill --uzdoom-arg 3 ^
 --uzdoom-arg -ddtowncache --uzdoom-arg "%HERE%run\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%HERE%data\converter\DungeonConverter.exe" ^
 --uzdoom-arg -ddarena2 --uzdoom-arg "%GAME%\DAGGER\ARENA2" --uzdoom-arg +map --uzdoom-arg DDT09183 ^
 --dfu-arg -dfsynctest --dfu-arg "%GAME%\DAGGER" --dfu-arg -dftownhour --dfu-arg 12
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, help="UZDoom Release folder")
    ap.add_argument("--data", default=str(BUILD / "nature-data"))
    a = ap.parse_args()
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "dfu", "data"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(a.exe, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.lib", "*.exp", "*.ini", "*.log"))
    data = Path(a.data)
    (REVIEW / "data").mkdir()
    for name in ("ddruntime.pk3", "overworld.pk3"):
        shutil.copy2(data / name, REVIEW / "data" / name)
    shutil.copytree(data / "converter", REVIEW / "data" / "converter")
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    for name in ("launcher", "bridge"):
        out = BUILD / f"townlookback-{name}"
        subprocess.check_call(["cmake", "-S", str(REPO / name), "-B", str(out), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=subprocess.DEVNULL)
        subprocess.check_call(["cmake", "--build", str(out), "--config", "Release", "--parallel", "6"], stdout=subprocess.DEVNULL)
    shutil.copy2(BUILD / "townlookback-launcher" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(BUILD / "townlookback-bridge" / "Release" / "doomerfall_bridge.dll", REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64")
    shutil.copy2(DONOR / "dfu" / "Portable.txt", REVIEW / "dfu")
    shutil.copytree(DONOR / "dfu" / "PortableAppdata", REVIEW / "dfu" / "PortableAppdata", dirs_exist_ok=True)
    shutil.copy2(DONOR / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"))
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
