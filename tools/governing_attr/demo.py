"""Builds the playable demo in review/governing-attributes: the integration demo's Doom side and data, with this
worktree's Daggerfall Unity build.

    python tools/governing_attr/demo.py
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

LOOP = Path(r"D:\dev\DoomDaggerfall-loop\review")
REVIEW = LOOP / "governing-attributes"
SOURCE = LOOP / "batch12-stage"  # The integration build this branch starts from. Not modified.


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data"):
        shutil.copytree(SOURCE / name, REVIEW / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.ini", "*.log"))
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-drla.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(SOURCE / name, REVIEW / name)
    dfu = REVIEW / "dfu"
    shutil.rmtree(dfu, ignore_errors=True)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu,
                    ignore=shutil.ignore_patterns("*.pdb", "PortableAppdata"))
    plugin = Path("DaggerfallUnity_Data", "Plugins", "x86_64", "doomerfall_bridge.dll")
    shutil.copy2(SOURCE / "dfu" / plugin, dfu / plugin)
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    bat = (SOURCE / "play.bat").read_text()
    note = ("rem Doomerfall: gun skill governing attributes. Choose New Game, press P for the character sheet, then click\n"
            "rem Primary, Major, Minor or Miscellaneous skills. The last column is the governing attribute:\n"
            "rem Explosives reads STR and Energy Weapons reads AGI (both read INT before).\n")
    (REVIEW / "play.bat").write_text("@echo off\n" + note + bat[bat.index('set "HERE='):], newline="\r\n")
    print("assembled", REVIEW)


if __name__ == "__main__":
    main()
