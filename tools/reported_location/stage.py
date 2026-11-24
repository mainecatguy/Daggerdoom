"""Stages the current game into review/reported-location and writes its one-click play.bat.

Uses the current UZDoom build, this checkout's Daggerfall build, and the same mods as the main game.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORK / "scripts" / "play"))
import install  # noqa: E402

BUILD = Path(r"D:\dev\DoomDaggerfall-build")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\monster-deaths")
ITEMS = Path(r"D:\dev\DoomDaggerfall-loop\review\item-pickup\dfitems.pk3")
TARGET = Path(r"D:\dev\DoomDaggerfall-loop\review\reported-location")
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    uzdoom = TARGET / "uzdoom"
    if uzdoom.exists():
        shutil.rmtree(uzdoom)
    shutil.copytree(BUILD / "uzdoom-location" / "Release", uzdoom)
    (uzdoom / "check.ini").unlink(missing_ok=True)
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(BUILD / "uzdoom-launcher" / "Release" / dll, uzdoom / dll)

    dfu = TARGET / "dfu"
    if dfu.exists():
        shutil.rmtree(dfu)
    shutil.copytree(WORK / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge-location" / "Release" / "doomerfall_bridge.dll", plugins)
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)

    if not (TARGET / "data").exists():
        shutil.copytree(SOURCE / "data", TARGET / "data")
    shutil.copy2(ITEMS, TARGET / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(WORK / "scripts" / "doomerfall" / "build_pk3.py"), str(TARGET / "doomerfall.pk3")])
    shutil.copy2(BUILD / "launcher-location" / "Release" / "doomerfall-launcher.exe", TARGET / "doomerfall-launcher.exe")

    play = install.PLAY.replace("@DAGGER@", str(GAME / "DAGGER")).replace("@IWAD@", str(GAME / "wads" / "DOOM2.WAD")).replace("@MODS@", str(GAME.parent / "GameMods"))
    (TARGET / "play.bat").write_text(play, newline="\r\n")

    with zipfile.ZipFile(TARGET / "data" / "privateershold_doors.pk3") as pk3:
        name = next(n for n in pk3.namelist() if n.upper().endswith("DDDUNGN"))
        row = next(l.split()[1:6] for l in pk3.read(name).decode().splitlines() if l.startswith("exit"))
    harness = TARGET / "test-harness"
    harness.mkdir(exist_ok=True)
    text = (Path(__file__).parent / "harness.zs").read_text().replace("@EXIT@", ", ".join(row))
    (harness / "zscript.txt").write_text(text)
    (harness / "mapinfo.txt").write_text('GameInfo\n{\n\tAddEventHandlers = "RLHarness"\n}\n')
    print("staged", TARGET, "exit", row)


if __name__ == "__main__":
    main()
