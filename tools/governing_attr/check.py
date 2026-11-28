"""Checks the governing attribute the character sheet draws for each weapon skill, in the real Daggerfall Unity build.

Stages this worktree's build (as tools/attribute_help/run_shots.py does) outside the repo and runs it on a private
desktop with -dfgovstattest.

    python tools/governing_attr/check.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "attribute_help"))
import run_shots as base  # noqa: E402  (staging and paths)

OUT = Path(r"D:\dev\DoomDaggerfall-build\governingattr-check")
# The owner's governing attributes (2026-11-27). Every weapon skill keeps advancement multiplier 2.
EXPECT = (("Shotguns", "STR"), ("Automatics", "AGI"), ("Explosives", "STR"), ("Pistols", "AGI"), ("Rifles", "AGI"),
          ("Energy Weapons", "AGI"), ("Melee", "STR"))


def main():
    dfu, report = OUT / "dfu", OUT / "report.txt"
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(base.REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu,
                    ignore=shutil.ignore_patterns("*.pdb", "PortableAppdata"))
    (dfu / "Portable.txt").write_text("")
    base.install.isolate_registry(dfu)
    (dfu / "PortableAppdata").mkdir()
    for name in ("settings.ini", "KeyBinds.txt"):
        shutil.copy2(base.DEMO / "dfu" / "PortableAppdata" / name, dfu / "PortableAppdata" / name)
    ini = dfu / "PortableAppdata" / "settings.ini"
    ini.write_text(re.sub(r"(?m)^MyDaggerfallPath = .*$", lambda m: "MyDaggerfallPath = " + str(base.GAME / "DAGGER"),
                          ini.read_text()))
    code = subprocess.call([sys.executable, base.QUIET, "--timeout", "90", "--", str(dfu / "DaggerfallUnity.exe"),
                            "-screen-fullscreen", "0", "-dfgovstattest", str(report)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    text = report.read_text() if report.exists() else ""
    print(text or "no report")
    missing = [n for n, stat in EXPECT if not re.search(rf"(?m)^{n} \| \d+% \| {stat} \| advancement 2$", text)]
    for name in missing:
        print("WRONG OR MISSING:", name)
    ok = code == 0 and "done" in text and not missing
    print("PASS" if ok else f"FAIL (exit {code})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
