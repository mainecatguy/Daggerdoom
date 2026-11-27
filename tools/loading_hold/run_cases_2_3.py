"""Runs loading hold cases 2 (door press on an unconverted dungeon) and 3 (cleared level-30 re-entry) with both
games' loading tests, then check_df_pause.py on each.

Usage: run_cases_2_3.py KIT   (KIT: a staged play folder such as review\\loading-pause, with uzdoom\\ and dfu\\)
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRIES = HERE.parent / "runtime_dungeons" / "run_entries.py"
DATA = Path(r"D:\dev\DoomDaggerfall-build\dungeon-runtime")


def main():
    kit = Path(sys.argv[1])
    base = [sys.executable, str(ENTRIES), "--uzdoom", str(kit / "uzdoom" / "uzdoom.exe"), "--kit", str(kit), "--data", str(DATA / "data"),
            "--converter", str(DATA / "converter" / "DungeonConverter.exe"), "--dfu-flag=-dfloadingpausetest"]
    cases = [
        (base + ["--out", str(kit / "test-run" / "case2-door"), "--timeout", "120", "--uz-flag=-ddloadingtest", "552:runtime"],
         kit / "test-run" / "case2-door" / "run-552-runtime"),
        (base + ["--out", str(kit / "test-run" / "case3-reentry"), "--timeout", "150", "--dfu-flag=-dfarealevel", "--dfu-flag=30",
                 "--mod", str(kit / "dfitems.pk3"), "--mod", str(kit / "doomerfall.pk3"), "--clear", "7154"],
         kit / "test-run" / "case3-reentry" / "run-7154"),
    ]
    ok = True
    for command, run in cases:
        ok &= subprocess.run(command).returncode == 0
        ok &= subprocess.run([sys.executable, str(HERE / "check_df_pause.py"), str(run / "df.log"), str(run / "uz.log")]).returncode == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
