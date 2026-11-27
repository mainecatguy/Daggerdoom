"""Visual parity, pass 2: the same Daggerfall windows, with the same character and items, in Daggerfall Unity and in
Doomerfall.

usage: python tools/visual_parity/menus.py [--seed N] [--out DIR] [--skip-df] [--skip-doom]

Both sides use the paired tests' blank character (-dfsynctest with -dfinventorytest: 100 HP, 5000 gold, an iron
longsword and a steel dagger) in the test town (map pixel 207, 213), and open the windows Doomerfall offers
(inventory, travel map, map, quest journal, rest) in a seeded random order.
- Daggerfall Unity: the capture player (DungeonCaptureTest's menu job) opens each window with Daggerfall Unity's own
  message, as its keys do, and saves its whole screen.
- Doomerfall: the real paired game opens each window with the real Doom command (the same netevent Doom's keys send)
  and takes Doom's screenshot, which shows Daggerfall's window composited in the Doom window.
Writes <id>.df.png, <id>.doom.png, <id>.side.png, menus.csv and index.html under --out, outside the repository.
"""
import argparse
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import common as c

# window name: (Doom console command that opens it in Doomerfall, Doom's bridge menu id)
WINDOWS = {
    "inventory": "netevent df_inventory",
    "travelmap": "netevent df_fast_travel",
    "automap": "togglemap",
    "journal": "netevent df_journal",
    "rest": "netevent df_rest",
}


UNMINIMIZED = False


def capture_doomerfall(order, out, work, timeout):
    session = out / "session"
    os.environ["DDQA_SESSION"] = str(session)
    sys.path.insert(0, str(c.REPO / "tools" / "qa"))
    import qa
    run = session / "run"
    c.fresh_run_folder(run)
    if qa.QA.exists():
        shutil.rmtree(qa.QA)
    qa.QA.mkdir(parents=True)
    qa.INBOX.write_text("")
    proc = subprocess.Popen(c.paired_command(work, run, timeout, uz_extra=["+screenblocks", "12"], df_extra=["-dfinventorytest"], qa=qa.QA,
                                              minimized=not UNMINIMIZED),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    uzlog = run / "uz.log"
    log = {"menus": []}
    try:
        if not qa.await_line(lambda o: o.get("event") == "level", 90):
            raise RuntimeError(f"no level event in 90 s (fatal: {c.fatal(run)})")
        t0 = time.time()
        while time.time() - t0 < 90:
            p = qa.command(["pos"])
            if p.get("df_phase") == 3:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Daggerfall never reached sync phase 3")
        time.sleep(4.0)  # the town settles, the harness removes the sync test's rat
        log["pos"] = qa.command(["pos"])
        log["df_place"] = paired_place(run / "df.log")
        for shot_id, window in order:
            shot = out / f"{shot_id}.doom.png"
            shot.unlink(missing_ok=True)
            opened = c.read(uzlog).count("Daggerfall opened menu")
            closed = c.read(uzlog).count("ui: closed")
            qa.command(["con", WINDOWS[window]])
            ok_open = c.wait_until(lambda: c.read(uzlog).count("Daggerfall opened menu") > opened, 10, run)
            time.sleep(1.5)  # the window's first frames reach Doom
            qa.command(["con", f'screenshot "{shot.as_posix()}"'])
            ok_shot = c.wait_until(shot.exists, 10, run)
            qa.command(["con", WINDOWS[window]])  # the same command closes it, as the bound key does
            ok_close = c.wait_until(lambda: c.read(uzlog).count("ui: closed") > closed, 6, run)
            if not ok_close:
                qa.command(["con", "menu_main; closemenu"])  # fall back to closing every menu
                ok_close = c.wait_until(lambda: c.read(uzlog).count("ui: closed") > closed, 6, run)
            time.sleep(1.0)
            log["menus"].append(dict(id=shot_id, window=window, opened=ok_open, shot=ok_shot, closed=ok_close))
            print(shot_id, window, "opened", ok_open, "shot", ok_shot, "closed", ok_close)
            if c.fatal(run):
                raise RuntimeError("fatal: " + c.fatal(run))
    finally:
        c.kill(proc)
        (out / "doomerfall_session.json").write_text(json.dumps(log, indent=1))
    return log


def paired_place(df_log):
    """The paired Daggerfall Unity's place and time once position sync engaged, from its bridge log: map pixel, world
    coordinates (gps) and classic game minutes."""
    place = {}
    for line in c.read(df_log).splitlines():
        m = re.search(r"sync engaged=True .*?gps=(-?\d+),(-?\d+) pixel=(\d+),(\d+)", line)
        if m:
            place.update(gps=[int(m[1]), int(m[2])], pixel=[int(m[3]), int(m[4])])
        m = re.search(r"game_minutes (\d+)", line)
        if m and "minutes" not in place:
            place["minutes"] = int(m[1])
    return place


def capture_df(order, out, timeout, session):
    """Daggerfall Unity's side, at the paired session's town spot, facing and time (from doomerfall_session.json)."""
    place, pos = session.get("df_place", {}), session.get("pos", {})
    px, py = place.get("pixel", [207, 213])
    lines = [f"out\t{out}", f"daggerfall\t{c.GAME / 'DAGGER'}", f"size\t{c.WIDTH}\t{c.HEIGHT}", f"exterior\t{px}\t{py}", "testcharacter"]
    if "gps" in place:
        lines.append(f"world\t{place['gps'][0]}\t{place['gps'][1]}")
    if "angle" in pos:
        lines.append(f"yaw\t{90 - pos['angle']}")  # Doom: counter-clockwise from east; Unity yaw: clockwise from north
    if "minutes" in place:
        lines.append(f"time\t{place['minutes']}")
    lines += [f"menu\t{i}\t{w}" for i, w in order]
    return c.capture_daggerfall(lines, out, timeout, "df_menus")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=c.OUT / "menus")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--skip-df", action="store_true")
    ap.add_argument("--skip-doom", action="store_true")
    ap.add_argument("--unminimized", action="store_true", help="launch the paired game unminimized (still on the private desktop)")
    ap.add_argument("--user-desktop", action="store_true", help="diagnosis only: run the capture player on the owner's desktop (2AM-7AM)")
    ap.add_argument("--minimized-capture", action="store_true", help="diagnosis only: run the capture player minimized, as quiet_run does by itself")
    args = ap.parse_args()
    global UNMINIMIZED
    UNMINIMIZED = args.unminimized
    out = args.out.resolve()
    c.ensure_outside_repo(out)
    out.mkdir(parents=True, exist_ok=True)
    names = list(WINDOWS)
    random.Random(args.seed).shuffle(names)
    order = [(f"m{args.seed}_{i}_{w}", w) for i, w in enumerate(names)]
    if not args.skip_doom:
        work = c.OUT / "work"
        c.prepare(work)
        capture_doomerfall(order, out, work, args.timeout)
    if not args.skip_df:
        session = out / "doomerfall_session.json"
        capture_df(order, out, 180, json.loads(session.read_text()) if session.exists() else {})
    cards, rows = [], []
    for shot_id, window in order:
        df, doom = out / f"{shot_id}.df.png", out / f"{shot_id}.doom.png"
        score = c.pair(df, doom, out / f"{shot_id}.side.png")
        rows.append([shot_id, window, score])
        cards.append(dict(title=f"{shot_id}: {window}", note=f"difference {score}", side=f"{shot_id}.side.png" if score is not None else None))
    with open(out / "menus.csv", "w", newline="") as f:
        csv.writer(f).writerows([["id", "window", "difference"]] + rows)
    c.write_index(out / "index.html", f"Visual parity: Daggerfall windows, seed {args.seed}", cards)
    made = sum(1 for r in rows if r[2] is not None)
    print(f"{made} of {len(order)} pairs written to {out}")
    return 0 if made == len(order) else 1


if __name__ == "__main__":
    sys.exit(main())
