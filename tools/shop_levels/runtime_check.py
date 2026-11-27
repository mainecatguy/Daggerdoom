"""Checks Daggerfall Unity's runtime shop levels against shop_level.py.

    python tools/shop_levels/runtime_check.py STAGE_DIR [--settings PATH]

Copies this worktree's Builds/Windows64 into STAGE_DIR (outside the repo) with private settings and a private
registry key, starts it on a private desktop with -dfshopleveldump, prints sample.txt and compares the dump with
shop_level.py. --settings is any Doomerfall portable settings.ini; only its MyDaggerfallPath line is changed.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
DAGGER = Path(r"D:\dev\DoomDaggerfall\GameResources\DAGGER")
SETTINGS = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-pile\dfu\PortableAppdata\settings.ini")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage")
    ap.add_argument("--settings", default=str(SETTINGS))
    a = ap.parse_args()
    stage = Path(a.stage)
    dfu, out = stage / "dfu", stage / "dump"
    shutil.rmtree(dfu, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, ignore=shutil.ignore_patterns("*.pdb"))
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    (dfu / "PortableAppdata").mkdir()
    ini = Path(a.settings).read_text()
    ini = re.sub(r"(?m)^MyDaggerfallPath = .*$", lambda m: "MyDaggerfallPath = " + str(DAGGER), ini)
    (dfu / "PortableAppdata" / "settings.ini").write_text(ini)
    start = time.time()
    code = subprocess.call([sys.executable, QUIET, "--timeout", "150", "--", str(dfu / "DaggerfallUnity.exe"),
                            "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360",
                            "-dfshopleveldump", str(out)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print(f"daggerfall exit {code} after {time.time() - start:.1f} s")
    sample = out / "sample.txt"
    print(sample.read_text(errors="replace") if sample.exists() else "no sample.txt")
    sys.exit(subprocess.call([sys.executable, str(HERE / "shop_level.py"), "--arena2", str(DAGGER / "ARENA2"), "--runtime", str(out)]))


if __name__ == "__main__":
    main()
