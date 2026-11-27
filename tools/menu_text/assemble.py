"""Assembles the menu text demo in review/menu-text from the hud-messages demo's data and this lane's fresh builds.

usage: assemble.py
"""
import shutil
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
SRC = Path(r"D:\dev\DoomDaggerfall-loop\review\hud-messages")  # Unchanged converter data and mod pk3s.
OUT = Path(r"D:\dev\DoomDaggerfall-loop\review\menu-text")
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
DFU = WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("data", "uzdoom"):
        if not (OUT / name).exists():
            shutil.copytree(SRC / name, OUT / name)
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-drla.pk3"):
        shutil.copy2(SRC / name, OUT / name)
    shutil.copy2(BUILD / "uzdoom-quiet" / "Release" / "uzdoom.exe", OUT / "uzdoom" / "uzdoom.exe")
    shutil.copy2(BUILD / "launcher-quiet" / "Release" / "doomerfall-launcher.exe", OUT / "doomerfall-launcher.exe")
    if (OUT / "dfu").exists():
        shutil.rmtree(OUT / "dfu")
    shutil.copytree(DFU, OUT / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.log"))
    # Portable and renamed, as tools/inventory_menu does, so it never touches the owner's Daggerfall Unity settings or saves.
    (OUT / "dfu" / "Portable.txt").touch()
    shutil.copytree(SRC / "dfu" / "PortableAppdata", OUT / "dfu" / "PortableAppdata", ignore=shutil.ignore_patterns("*.log"), dirs_exist_ok=True)
    manager = OUT / "dfu" / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if b"Daggerfall Unity" in data:
        manager.write_bytes(data.replace(b"Daggerfall Unity", b"Doomerfall Local"))
    elif b"Doomerfall Local" not in data:
        raise SystemExit("product name not found; refusing to assemble an unisolated Daggerfall copy")
    shutil.copy2(BUILD / "bridge-quiet" / "Release" / "doomerfall_bridge.dll",
                 OUT / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll")
    print("assembled", OUT)


if __name__ == "__main__":
    main()
