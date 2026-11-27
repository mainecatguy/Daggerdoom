"""Checks that Daggerfall stayed paused through every Doom loading hold in one paired run.

Usage: check_df_pause.py DF_LOG [UZ_LOG]
Daggerfall must run with -dfloadingpausetest (DoomerfallLoadingPauseTest.cs), which poisons the player with Moonseed
at the first hold and logs the clock and HP across each hold.
Passes when there is at least one hold, every hold was released, neither the clock nor HP changed from the first
paused frame to the release, and the lead-in (the clock change in the frame that first saw the hold, whose time step
was fixed before the pause) is at most one Daggerfall frame of game time, rounded up, plus 1 s for whole-second
rounding. If the run lasted long enough for the after-release line, HP must have dropped by then, which shows the
poison was live and only the pause kept it from acting. With UZ_LOG it also prints Doom's hold lines. Exit 0 = pass.

With UZ_LOG it also matches the two logs on their shared clock (both stamp lines with dfb_now_ns seconds): every
Daggerfall release must come at or after the end of the Doom hold it belongs to, so Daggerfall's clock cannot have
moved while Doom still held the game, including through a block where Doom published nothing (-ddloadingblock).
--dead-doom instead checks a block longer than 60 s, standing in for a dead Doom: Daggerfall must release on its own,
between 60 and 65 s after the block began, while Doom is still blocked.
"""
import math
import re
import sys
from pathlib import Path

SEEN = "loadingpausetest: hold seen"
RELEASED = re.compile(r"loadingpausetest: released after (\d+) ms, clock (\d+) \(changed (-?\d+) s\), hp (-?\d+) \(changed (-?\d+)\), "
                      r"lead-in (-?\d+) s, frame ([\d.]+) game s, poison (.+) \(at the hold (.+)\)")
AFTER = re.compile(r"loadingpausetest: poison after the release: (.+) -> (.+) after ([\d.]+) s, hp (-?\d+) -> (-?\d+) in that frame \(changed (-?\d+)\)")


STAMP = re.compile(r"^\s*(\d+\.\d+) ")
DEAD_MIN_S, DEAD_MAX_S = 60.0, 65.0


def stamp(line):
    m = STAMP.match(line)
    return float(m.group(1)) if m else None


def doom_holds(uz):
    """Doom's runs of holds as (start, end) on the shared clock; end is None if the log stops inside one. Also the
    injected blocks as (start, end)."""
    runs, start, blocks, bstart = [], None, [], None
    for l in uz:
        t = stamp(l)
        if t is None:
            continue
        if "loading: " in l and " holds the game" in l and start is None:
            start = t
        elif "loading: " in l and "game frozen" in l and start is not None:  # the last hold of the run released
            runs.append((start, t))
            start = None
        elif "loadingtest: blocking the main thread" in l:
            bstart = t
        elif "loadingtest: block ended" in l and bstart is not None:
            blocks.append((bstart, t))
            bstart = None
    if start is not None:
        runs.append((start, None))
    if bstart is not None:
        blocks.append((bstart, None))
    return runs, blocks


def check_against_doom(df, uz, dead):
    """Returns the number of failures."""
    runs, blocks = doom_holds(uz)
    releases = [stamp(l) for l in df if "loadingpausetest: released" in l]
    bad = 0
    for b0, b1 in blocks:
        stale = [l.strip()[-90:] for l in df if "heartbeat stale" in l and stamp(l) and b0 <= stamp(l) <= (b1 or 1e18)]
        print(f"UZ  block {b0:.3f} -> {'still blocked at the end of the log' if b1 is None else f'{b1:.3f} ({b1 - b0:.1f} s)'}; "
              f"Daggerfall saw the heartbeat go stale {len(stale)} time(s) during it")
    if dead:
        if not blocks:
            print("BAD --dead-doom but Doom logged no block")
            return 1
        b0, b1 = blocks[0]
        after = [t for t in releases if t is not None and t > b0]
        gap = after[0] - b0 if after else None
        ok = gap is not None and DEAD_MIN_S <= gap <= DEAD_MAX_S and (b1 is None or after[0] < b1)
        print(f"DF  {'ok ' if ok else 'BAD'} dead Doom: Daggerfall released "
              f"{'never' if gap is None else f'{gap:.1f} s after the block began'} (want {DEAD_MIN_S:.0f}-{DEAD_MAX_S:.0f} s, before Doom woke)")
        return int(not ok)
    for t in releases:
        inside = [(s, e) for s, e in runs if t is not None and s < t and (e is None or t < e)]
        ok = t is not None and not inside
        bad += not ok
        where = "no stamp" if t is None else (f"{inside[0][1] - t:.3f} s before Doom's hold ended" if inside and inside[0][1] else
                                             "while Doom's hold never ended" if inside else "after Doom's hold ended")
        print(f"DF  {'ok ' if ok else 'BAD'} released at {t}: {where}")
    for s, e in runs:
        if e is None:
            print(f"BAD Doom's hold from {s:.3f} never ended")
            bad += 1
    return bad


def main():
    dead = "--dead-doom" in sys.argv
    if dead:
        sys.argv.remove("--dead-doom")
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
        uz = Path(sys.argv[2]).read_text(errors="replace").splitlines()
        for l in uz:
            if "loading:" in l or "loadingtest: block" in l:
                print("UZ ", l.strip()[-160:])
        bad += check_against_doom(df, uz, dead)
    elif dead:
        print("BAD --dead-doom needs UZ_LOG")
        bad += 1
    # A dead Doom's run ends with Daggerfall released and, if Doom then woke, held again and released at the end.
    ok = bool(seen) and len(seen) == len(released) and not bad
    print(f"{'PASS' if ok else 'FAIL'}: {len(seen)} holds, {len(released)} released, {len(after)} after-release checks, {bad} failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
