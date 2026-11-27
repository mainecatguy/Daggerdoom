"""Screenshots of the character sheet's attribute popups with Doomerfall's rules.

Stages this worktree's Daggerfall Unity build (Builds/Windows64) into a private portable folder, with the same
isolated settings as tools/travel_hint/run_shots.py, then runs it on a private desktop with -dfattrhelptest. The
screenshots show Daggerfall's art, so they stay in the review folder, outside the repo.

    python tools/attribute_help/run_shots.py [--nostage]
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\attribute-help")
DEMO = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-pile")  # source of the private settings.ini. Not modified.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")

# What the report must say for the test's fixed character (level 5; STR 62, WIL 70, AGI 33, END 55, SPD 80,
# Luck 120 or Daggerfall's cap), computed here from the formulas independently of the game code.
EXPECT = [
    "Yours (62): +62% melee damage.",                      # 1 + 62/100
    "Yours (70): -8% damage taken.",                       # (300-70)/250 = 0.92
    "Yours (33): +13.2% handling, 4.95% dodge.",           # 0.4*33, 0.15*33
    "Yours (55): " + str(round(50 + 55 + 4 * 55 / 15)) + " max HP at level 5.",  # 119.67 -> 120
    "Yours (80): +15% move speed.",                        # 0.75 + 80/200 = 1.15
    "100% chance of a second drop.",                       # Luck above 100 counts as 100 (or capped at 100)
    "in combat and from the environment:",                 # Willpower scales only Doom's damage, as manual.md says
]


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
    text = re.sub(r"(?m)^MyDaggerfallPath = .*$", lambda m: "MyDaggerfallPath = " + str(GAME / "DAGGER"), ini.read_text())
    # Daggerfall Unity applies these over -screen-width/-height, so the capture size is set here.
    for key, value in (("ResolutionWidth", "1280"), ("ResolutionHeight", "800"), ("Fullscreen", "False")):
        text = re.sub(rf"(?m)^{key} = .*$", f"{key} = {value}", text)
    ini.write_text(text)
    print("staged", dfu)


def main():
    dfu = REVIEW / "shots-dfu"
    if "--nostage" not in sys.argv:
        stage(dfu)
    out = REVIEW / "shots"
    shutil.rmtree(out, ignore_errors=True)
    start = time.time()
    code = subprocess.call([sys.executable, QUIET, "--timeout", "120", "--", str(dfu / "DaggerfallUnity.exe"),
                            "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
                            "-dfattrhelptest", str(out)], stdin=subprocess.DEVNULL)
    print(f"daggerfall exit {code} after {time.time() - start:.1f} s")
    report = out / "report.txt"
    text = report.read_text() if report.exists() else ""
    print(text or "no report")
    missing = [e for e in EXPECT if e not in text]
    for e in missing:
        print("MISSING:", e)
    boxes = text.count("top DaggerfallMessageBox")
    print(f"popups shown: {boxes} of 8")
    ok = code == 0 and "done" in text and "error" not in text and not missing and boxes == 8
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
