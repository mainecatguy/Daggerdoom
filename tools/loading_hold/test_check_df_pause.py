"""Self-test of check_df_pause.py on made-up logs: a Daggerfall release during a Doom block (what the stale heartbeat
did before commit e7745537) must FAIL, a release after Doom's hold must PASS, and --dead-doom must accept only a release
60-65 s into a block. Usage: test_check_df_pause.py   (exit 0 = all as expected)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

CHECK = Path(__file__).resolve().parent / "check_df_pause.py"


def uz(hold_end, block=(100.5, 103.0)):
    lines = ["100.000 loading: dungeon spawn holds the game",
             f"{block[0]:.3f} loadingtest: blocking the main thread for 2500 ms, 500 ms into the hold"]
    if block[1] is not None:
        lines.append(f"{block[1]:.3f} loadingtest: block ended, hold active 1")
    if hold_end is not None:
        lines.append(f"{hold_end:.3f} loading: dungeon spawn released after 1.0 ms, game frozen 10 tics, message shown")
    return lines


def df(release, rehold=None):
    lines = ["100.010 loadingpausetest: poisoned with Moonseed, poisons 1",
             "100.010 loadingpausetest: hold seen, clock 1000, hp 100, frame 0.01 game s",
             f"{release:.3f} loadingpausetest: released after 1 ms, clock 1000 (changed 0 s), hp 100 (changed 0), lead-in 0 s, "
             "frame 0.01 game s, poison Waiting 1 (at the hold Waiting 1)"]
    if rehold:
        lines += [f"{rehold[0]:.3f} loadingpausetest: hold seen, clock 1700, hp 90, frame 0.01 game s",
                  f"{rehold[1]:.3f} loadingpausetest: released after 1 ms, clock 1700 (changed 0 s), hp 90 (changed 0), lead-in 0 s, "
                  "frame 0.01 game s, poison Active 1 (at the hold Active 1)"]
    return lines


CASES = [  # name, df lines, uz lines, extra args, expected exit
    ("release after the hold", df(104.02), uz(104.0), [], 0),
    ("release during the block", df(101.6), uz(104.0), [], 1),
    ("release after the block, before the hold ended", df(103.5), uz(104.0), [], 1),
    ("Doom's hold never ended", df(104.02), uz(None), [], 1),
    ("dead Doom released at 60.2 s", df(160.7), uz(None, (100.5, None)), ["--dead-doom"], 0),
    ("dead Doom woke later and held again", df(160.7, (175.6, 176.1)), uz(176.0, (100.5, 175.5)), ["--dead-doom"], 0),
    ("dead Doom never released", df(176.1), uz(176.0, (100.5, 175.5)), ["--dead-doom"], 1),
    ("dead Doom released too early", df(101.6), uz(None, (100.5, None)), ["--dead-doom"], 1),
]


def main():
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, d, u, extra, want in CASES:
            dp, up = Path(tmp) / "df.log", Path(tmp) / "uz.log"
            dp.write_text("\n".join(d) + "\n")
            up.write_text("\n".join(u) + "\n")
            got = subprocess.run([sys.executable, str(CHECK), str(dp), str(up)] + extra, capture_output=True, text=True).returncode
            ok = got == want
            failed += not ok
            print(f"{'ok ' if ok else 'BAD'} {name}: exit {got}, want {want}")
    print("PASS" if not failed else f"FAIL: {failed}")
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
