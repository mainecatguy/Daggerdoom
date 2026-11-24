"""Screenshots of the travel map danger hint.

Stages this worktree's Daggerfall Unity build (Builds/Windows64) into a private portable review folder, with the
same isolated settings as tools/area_level/runtime_check.py, then runs it on a private desktop with
-dftravelhintshots. The screenshots show Daggerfall's map art, so they stay in the review folder, outside the repo.

    python tools/travel_hint/run_shots.py [--nostage]
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\travel-hint")
DEMO = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # source of the private settings.ini. Not modified.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")


def stage(dfu):
    if dfu.exists():
        shutil.rmtree(dfu)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, ignore=shutil.ignore_patterns("*.pdb"))
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    (dfu / "PortableAppdata").mkdir()
    for name in ("settings.ini", "KeyBinds.txt"):
        shutil.copy2(DEMO / "dfu" / "PortableAppdata" / name, dfu / "PortableAppdata" / name)
    ini = dfu / "PortableAppdata" / "settings.ini"
    ini.write_text(re.sub(r"(?m)^MyDaggerfallPath = .*$", lambda m: "MyDaggerfallPath = " + str(GAME / "DAGGER"), ini.read_text()))
    print("staged", dfu)


def main():
    dfu = REVIEW / "dfu"
    if "--nostage" not in sys.argv:
        stage(dfu)
    out = REVIEW / "shots"
    shutil.rmtree(out, ignore_errors=True)
    start = time.time()
    code = subprocess.call([sys.executable, QUIET, "--desktop", "--timeout", "120", "--", str(dfu / "DaggerfallUnity.exe"),
                            "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
                            "-dftravelhintshots", str(out)], stdin=subprocess.DEVNULL)
    print(f"daggerfall exit {code} after {time.time() - start:.1f} s")
    report = out / "report.txt"
    print(report.read_text() if report.exists() else "no report")
    sys.exit(0 if code == 0 and report.exists() and "done" in report.read_text() and "error" not in report.read_text() else 1)


if __name__ == "__main__":
    main()
