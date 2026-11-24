"""Ground loot review: builds the item gallery package, takes gallery screenshots, and stages the review folder.

Usage:
  python groundloot.py stage                 copy UZDoom into the review folder
  python groundloot.py package <name>        build the gallery package into <review>/<name>/daggerfall_items.pk3
  python groundloot.py shots <name>          run tools/item_gallery/check.py on <review>/<name>
  python groundloot.py demo                  write play.bat for the "after" package
"""
import pathlib
import shutil
import subprocess
import sys

WORKTREE = pathlib.Path(__file__).resolve().parents[2]
REVIEW = pathlib.Path(r"D:\dev\DoomDaggerfall-loop\review\groundloot")
ENGINE = pathlib.Path(r"D:\dev\DoomDaggerfall-loop\review\sprite-scale")
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
ENGINE_FILES = ("uzdoom.exe", "sndfile.dll", "soft_oal.dll", "brightmaps.pk3", "game_support.pk3", "game_widescreen_gfx.pk3", "lights.pk3", "uzdoom.pk3")


def templates():
    found = list((WORKTREE / "daggerfall-unity-master" / "Assets").rglob("ItemTemplates.txt"))
    if not found:
        sys.exit("ItemTemplates.txt not found")
    return found[0]


def stage(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name in ENGINE_FILES:
        if not (folder / name).exists():
            shutil.copy2(ENGINE / name, folder / name)


def main():
    command = sys.argv[1]
    if command == "stage":
        stage(REVIEW)
    elif command == "package":
        out = REVIEW / sys.argv[2]
        stage(out)
        code = subprocess.call(["dotnet", "run", "-c", "Release", "--project", str(WORKTREE / "tools" / "item_gallery" / "ItemGallery.csproj"), "--",
                                ARENA2, str(templates()), str(WORKTREE / "mods" / "daggerfall_items"), str(out / "daggerfall_items.pk3"), str(out / "items.tsv")],
                               stdin=subprocess.DEVNULL)
        sys.exit(code)
    elif command == "shots":
        folder = REVIEW / sys.argv[2]
        sys.exit(subprocess.call([sys.executable, str(WORKTREE / "tools" / "item_gallery" / "check.py"), str(folder), str(folder / "run")], stdin=subprocess.DEVNULL))
    elif command == "demo":
        stage(REVIEW)
        shutil.copy2(REVIEW / "after" / "daggerfall_items.pk3", REVIEW / "daggerfall_items.pk3")
        compare = REVIEW / "compare"
        compare.mkdir(exist_ok=True)
        for side in ("before", "after"):
            for shot in sorted((REVIEW / side / "run").glob("gallery*.png")):
                shutil.copy2(shot, compare / f"{side}_{shot.stem[len('gallery'):]}.png")
        (REVIEW / "play.bat").write_text(
            "@echo off\r\n"
            "rem Walk the Daggerfall item gallery. Every item now lies on the floor as a Daggerfall treasure pile, as a dropped item does in\r\n"
            "rem Daggerfall Unity. Stand near a pile to see which item it holds.\r\n"
            "set \"HERE=%~dp0\"\r\n"
            "set \"IWAD=D:\\dev\\DoomDaggerfall\\GameResources\\wads\\DOOM.WAD\"\r\n"
            "start \"\" /D \"%HERE%\" \"%HERE%uzdoom.exe\" -iwad \"%IWAD%\" -file \"%HERE%daggerfall_items.pk3\" -config \"%HERE%play.ini\" -noautoload -skill 3 +vid_fullscreen 0 +map DFGALLRY\r\n",
            encoding="ascii")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
