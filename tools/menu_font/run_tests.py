"""Runs the menu font popup check on a demo: a stock paired run and one with the sample texture pack, then the sheet.

usage: run_tests.py <demo folder> <font.ttf>
Writes <demo>/test-stock, <demo>/test-pack and <demo>/popups-stock-vs-pack.png; removes the sample pack afterwards.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MENU_TEXT = HERE.parent / "menu_text" / "menu_text.py"


def run(demo, name):
    out = demo / name
    shutil.rmtree(out, ignore_errors=True)
    subprocess.call([sys.executable, str(MENU_TEXT), str(demo), str(out), "--menutext", "--timeout", "80", "--hover"])
    steps = out / "dfu-steps.txt"
    print(name, "steps:", steps.read_text() if steps.exists() else "none")


def main():
    demo, font = Path(sys.argv[1]).resolve(), sys.argv[2]
    pack = [sys.executable, str(HERE / "texture_pack.py")]
    subprocess.check_call(pack + ["remove", str(demo)])
    run(demo, "test-stock")
    subprocess.check_call(pack + ["install", str(demo), font])
    try:
        run(demo, "test-pack")
    finally:
        subprocess.check_call(pack + ["remove", str(demo)])
    subprocess.check_call([sys.executable, str(HERE / "popup_sheet.py"), str(demo / "test-stock"), str(demo / "test-pack"),
                           str(demo / "popups-stock-vs-pack.png")])


if __name__ == "__main__":
    main()
