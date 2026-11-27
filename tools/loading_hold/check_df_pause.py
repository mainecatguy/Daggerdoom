"""Checks that Daggerfall stayed paused through every Doom loading hold in one paired run.

Usage: check_df_pause.py DF_LOG [UZ_LOG]
Reads Daggerfall's bridge log for DoomerfallLoadingPause's lines ("loading: Daggerfall held ..." and
"loading: Daggerfall released after N ms, clock C (changed S s), hp H (changed D), resumed R").
Passes when there is at least one hold, every hold was released, and neither the clock nor HP changed during any.
With UZ_LOG it also prints Doom's own hold lines (dd_loading.cpp) for comparison. Exit code 0 means pass.
"""
import re
import sys
from pathlib import Path

# Changes are counted from Daggerfall's first paused frame. The frame that first saw the hold had its time step fixed
# before the pause took effect, so it moves the clock by one Daggerfall frame (the lead-in, printed, not checked).
RELEASED = re.compile(r"loading: Daggerfall released after (\d+) ms, clock (\d+) \(changed (-?\d+) s\), hp (-?\d+) \(changed (-?\d+)\), resumed (\w+), lead-in (-?\d+) s")


def main():
    df = Path(sys.argv[1]).read_text(errors="replace").splitlines()
    held = [l for l in df if "loading: Daggerfall held" in l]
    released = [RELEASED.search(l) for l in df if "loading: Daggerfall released" in l]
    for l in held:
        print("DF ", l.strip()[-160:])
    bad = 0
    for m in released:
        ms, clock, dclock, hp, dhp, resumed, lead = m.groups()
        ok = dclock == "0" and dhp == "0"
        bad += not ok
        print(f"DF  {'ok ' if ok else 'BAD'} hold {ms} ms: clock {clock} changed {dclock} s, hp {hp} changed {dhp}, resumed {resumed}, lead-in {lead} s")
    if len(sys.argv) > 2:
        for l in Path(sys.argv[2]).read_text(errors="replace").splitlines():
            if "loading:" in l:
                print("UZ ", l.strip()[-160:])
    ok = bool(held) and len(held) == len(released) and not bad
    print(f"{'PASS' if ok else 'FAIL'}: {len(held)} holds, {len(released)} released, {bad} with a clock or HP change")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
