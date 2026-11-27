"""Runs loading hold cases 2 (door press on an unconverted dungeon) and 3 (cleared level-30 re-entry) with both
games' loading tests, then check_df_pause.py on each. Also case 2 with a 2.5 s block of Doom's main thread inside the
hold (-ddloadingblock: Doom publishes nothing, as during a long dungeon spawn; Daggerfall must stay paused until Doom's
hold ends), and with a 75 s block, standing in for a dead Doom (Daggerfall must release on its own after 60 s).

Usage: run_cases_2_3.py KIT [CASE ...]   (KIT: a staged play folder such as review\\loading-pause, with uzdoom\\ and dfu\\;
CASE: any of case2-door case2-block case2-deaddoom case3-reentry, default all)
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRIES = HERE.parent / "runtime_dungeons" / "run_entries.py"
DATA = Path(r"D:\dev\DoomDaggerfall-build\dungeon-runtime")


def main():
    kit = Path(sys.argv[1])
    wanted = sys.argv[2:]
    out = kit / "test-run"
    base = [sys.executable, str(ENTRIES), "--uzdoom", str(kit / "uzdoom" / "uzdoom.exe"), "--kit", str(kit), "--data", str(DATA / "data"),
            "--converter", str(DATA / "converter" / "DungeonConverter.exe"), "--dfu-flag=-dfloadingpausetest"]
    door = ["--uz-flag=-ddloadingtest", "552:runtime"]
    cases = [  # name, run_entries arguments, run folder, checker flags
        ("case2-door", ["--timeout", "120"] + door, "run-552-runtime", []),
        ("case2-block", ["--timeout", "120", "--uz-flag=-ddloadingblock", "--uz-flag=2500"] + door, "run-552-runtime", []),
        ("case2-deaddoom", ["--timeout", "200", "--uz-flag=-ddloadingblock", "--uz-flag=75000"] + door, "run-552-runtime", ["--dead-doom"]),
        ("case3-reentry", ["--timeout", "150", "--dfu-flag=-dfarealevel", "--dfu-flag=30", "--mod", str(kit / "dfitems.pk3"),
                           "--mod", str(kit / "doomerfall.pk3"), "--clear", "7154"], "run-7154", []),
    ]
    ok = True
    for name, args, run, flags in cases:
        if wanted and name not in wanted:
            continue
        print(f"=== {name}", flush=True)
        entered = subprocess.run(base + ["--out", str(out / name)] + args).returncode == 0
        # A dead Doom's door test may not finish its in-out-in walk in time; only Daggerfall's release is judged there.
        ok &= entered or name == "case2-deaddoom"
        run_dir = out / name / run
        ok &= subprocess.run([sys.executable, str(HERE / "check_df_pause.py"), str(run_dir / "df.log"), str(run_dir / "uz.log")] + flags).returncode == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
