"""Checks that Daggerfall stayed paused through every Doom loading hold in one paired run.

Usage: check_df_pause.py DF_LOG [UZ_LOG]
Daggerfall must run with -dfloadingpausetest (DoomerfallLoadingPauseTest.cs), which poisons the player with Moonseed
at the first hold and logs the clock and HP across each hold.
Passes when there is at least one hold, every hold was released, neither the clock nor HP changed from the first
paused frame to the release, and the lead-in (the clock change in the frame that first saw the hold, whose time step
was fixed before the pause) is at most one Daggerfall frame of game time, rounded up, plus 1 s for whole-second
rounding. If the run lasted long enough for the after-release line, HP must have dropped by then, which shows the
poison was live and only the pause kept it from acting. With UZ_LOG it also prints Doom's hold lines. Exit 0 = pass.
"""
import math
import re
import sys
from pathlib import Path

SEEN = "loadingpausetest: hold seen"
RELEASED = re.compile(r"loadingpausetest: released after (\d+) ms, clock (\d+) \(changed (-?\d+) s\), hp (-?\d+) \(changed (-?\d+)\), "
                      r"lead-in (-?\d+) s, frame ([\d.]+) game s, poison (.+) \(at the hold (.+)\)")
AFTER = re.compile(r"loadingpausetest: poison after the release: (.+) -> (.+) after ([\d.]+) s, hp (-?\d+) -> (-?\d+) in that frame \(changed (-?\d+)\)")


def main():
    df = Path(sys.argv[1]).read_text(errors="replace").splitlines()
    seen = [l for l in df if SEEN in l]
    released = [RELEASED.search(l) for l in df if "loadingpausetest: released" in l]
    for l in df:
        if "loadingpausetest: poisoned" in l or "clock moved during the hold" in l or SEEN in l:
            print("DF ", l.strip()[-160:])
    bad = 0
    for m in released:
        ms, clock, dclock, hp, dhp, lead, frame, poison, poison_hold = m.groups()
        bound = math.ceil(float(frame)) + 1
        ok = dclock == "0" and dhp == "0" and int(lead) <= bound and poison == poison_hold
        bad += not ok
        print(f"DF  {'ok ' if ok else 'BAD'} hold {ms} ms: clock changed {dclock} s, hp {hp} changed {dhp}, poison {poison_hold} -> {poison}, "
              f"lead-in {lead} s (bound {bound} s for a {frame} game s frame)")
    after = [AFTER.search(l) for l in df if "poison after the release" in l]
    for m in after:
        before, state, secs, hp0, hp1, dhp = m.groups()
        good = state != before and int(dhp) < 0
        bad += not good
        print(f"DF  {'ok ' if good else 'BAD'} poison ticked {secs} s after the release: {before} -> {state}, hp {hp0} -> {hp1} in that frame")
    if len(sys.argv) > 2:
        for l in Path(sys.argv[2]).read_text(errors="replace").splitlines():
            if "loading:" in l:
                print("UZ ", l.strip()[-160:])
    ok = bool(seen) and len(seen) == len(released) and not bad
    print(f"{'PASS' if ok else 'FAIL'}: {len(seen)} holds, {len(released)} released, {len(after)} after-release checks, {bad} failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
