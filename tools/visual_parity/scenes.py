"""Visual parity, pass 1: the same seeded random spots in Privateer's Hold, in Daggerfall Unity and in Doomerfall.

usage: python tools/visual_parity/scenes.py [--seed N] [--count N] [--out DIR] [--skip-df] [--skip-doom]

Spots are random standing places on the dungeon converter's walk graph (<slug>.points.txt, reachable from the
entrance, with room for a standing eye), with a random facing and level pitch.
- Daggerfall Unity: the capture player (DungeonCaptureTest, -dfcapture) loads the dungeon with no enemies and no NPC
  flats, keeps the game's own lights ("lit"), and renders each spot at Daggerfall Unity's standing eye height
  (1.71 m) and default field of view (65 degrees vertical).
- Doomerfall: the real paired game (launcher, UZDoom and Daggerfall Unity, -dfsynctest start, through the town door
  into the dungeon), with tools/visual_parity/doom removing every monster and NPC. At each spot it takes:
    <id>.doom.png        a camera at Daggerfall Unity's eye height and field of view (the parity shot), no HUD;
    <id>.doomnative.png  the player's own view as played (Doom's eye height and field of view, weapon and HUD).
Writes <id>.side.png (Daggerfall Unity left, Doomerfall right), <id>.native.side.png, scenes.csv and index.html.
Everything goes under --out, outside the repository (screenshots are derived from game data).
"""
import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import common as c

DUNGEON_NAME = "Privateer's Hold"
MIN_ROOM = 72  # Doom units between floor and ceiling: room for the 51.3-unit eye and a little above it


def walk_graph(points):
    nodes, links, start = {}, {}, None
    for line in open(points):
        f = line.split()
        if not f:
            continue
        if f[0] == "N":
            nodes[int(f[1])] = (int(f[2]), int(f[3]), int(f[4]), int(f[5]))
        elif f[0] == "E":
            links.setdefault(int(f[1]), []).append(int(f[2]))
        elif f[0] == "S":
            start = tuple(map(int, f[2:5]))
    return nodes, links, start


def open_run(grid, x, y, floor, angle, step=24, limit=40):
    """How many walk-graph cells in a row lie ahead in this direction, near this floor (a rough line of sight)."""
    dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for k in range(1, limit):
        px, py = x + dx * step * k, y + dy * step * k
        cell = (int(round((px - x) / step)) * step + x, int(round((py - y) / step)) * step + y)
        f = grid.get(cell)
        if f is None or abs(f - floor) > 48:
            return k
    return limit


def pick_spots(points, seed, count):
    nodes, links, start = walk_graph(points)
    first = min(nodes, key=lambda n: math.dist(nodes[n][:3], start)) if start else next(iter(nodes))
    seen, todo = {first}, deque([first])
    while todo:  # only places the player can reach from the entrance
        for m in links.get(todo.popleft(), ()):
            if m not in seen:
                seen.add(m)
                todo.append(m)
    good = sorted(n for n in seen if nodes[n][3] - nodes[n][2] >= MIN_ROOM)
    grid = {(nodes[n][0], nodes[n][1]): nodes[n][2] for n in seen}
    rng = random.Random(seed)
    spots = []
    for i, n in enumerate(rng.sample(good, min(count, len(good)))):
        x, y, floor, ceiling = nodes[n]
        # A random facing, then the most open of eight turns from it, so a spot rarely stares into a wall.
        base = rng.randrange(0, 45, 5)
        yaw = max((base + 45 * k for k in range(8)), key=lambda a: open_run(grid, x, y, floor, a))
        spots.append(dict(id=f"s{seed}_{i:02d}", node=n, x=x, y=y, floor=floor, ceiling=ceiling, yaw=yaw, pitch=0))
    print(f"{len(seen)} reachable walk-graph nodes, {len(good)} with room to stand; picked {len(spots)}")
    return spots


def ensure_points(work):
    points = work / "map" / "privateershold.points.txt"
    if not points.exists():
        (work / "map").mkdir(parents=True, exist_ok=True)
        subprocess.check_call([str(c.PLAY / "data" / "converter" / "DungeonConverter.exe"), DUNGEON_NAME, "--out", str(work / "map"),
                               "--arena2", str(c.GAME / "DAGGER" / "ARENA2")], stdout=subprocess.DEVNULL)
    return points


def capture_df(spots, out, timeout):
    lines = [f"dungeon\t{DUNGEON_NAME}", f"out\t{out}", f"daggerfall\t{c.GAME / 'DAGGER'}", f"size\t{c.WIDTH}\t{c.HEIGHT}",
             f"vfov\t{c.DF_VFOV}", "lit", "nonpcs"]
    for s in spots:  # the walk graph is in Doom units; the capture takes Daggerfall units
        x, y, floor = s["x"] / c.WORLD_SCALE, s["y"] / c.WORLD_SCALE, s["floor"] / c.WORLD_SCALE
        lines.append(f"view\t{s['id']}\t{x:.2f}\t{y:.2f}\t{floor + c.DF_EYE:.2f}\t{s['yaw']}\t{s['pitch']}")
    return c.capture_daggerfall(lines, out, timeout, "df_scenes")


def capture_doomerfall(spots, out, work, timeout):
    session = out / "session"
    os.environ["DDQA_SESSION"] = str(session)
    sys.path.insert(0, str(c.REPO / "tools" / "qa"))
    import qa  # the QA bot's file channel (UZDoom -ddqa): commands run in the paired game's next tic, "con" at once
    run = session / "run"
    c.fresh_run_folder(run)
    if qa.QA.exists():
        import shutil
        shutil.rmtree(qa.QA)
    qa.QA.mkdir(parents=True)
    qa.INBOX.write_text("")
    proc = subprocess.Popen(c.paired_command(work, run, timeout, uz_extra=["+screenblocks", "12"], qa=qa.QA),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = {"spots": []}
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
        # Through Privateer's Hold's town door, as qa.py start --dungeon does.
        rows = [r.split() for r in qa.lumps(c.PLAY / "data" / "cache" / "T07154.ddt")["DDDOORS"].decode().splitlines() if r.strip()]
        door = next(r for r in rows if r[0] == "1")
        x, y, z, nx, ny = map(float, door[3:8])
        qa.command(["teleport", f"{x + nx * 48:.1f}", f"{y + ny * 48:.1f}", "nan", f"{math.degrees(math.atan2(-ny, -nx)):.1f}"])
        qa.command(["con", "dd_tm_use", "1"])
        inside = None
        for _ in range(80):
            time.sleep(0.5)
            p = qa.command(["pos"])
            if p.get("map") and not str(p["map"]).upper().startswith("DDT"):
                inside = p
                break
        if not inside:
            raise RuntimeError("did not get into the dungeon")
        log["inside"] = inside
        time.sleep(2.0)  # Daggerfall's dungeon load and the harness's first sweeps
        qa.command(["god", "on"])
        for s in spots:
            shot, native = out / f"{s['id']}.doom.png", out / f"{s['id']}.doomnative.png"
            for f in (shot, native):
                f.unlink(missing_ok=True)
            tp = qa.command(["teleport", str(s["x"]), str(s["y"]), str(s["floor"]), str(s["yaw"])])
            eye = s["floor"] + c.DOOM_EYE
            qa.command(["con", f"netevent vp_pos {round(s['x'] * 10)} {round(s['y'] * 10)} {round(eye * 10)}"])
            qa.command(["con", f"netevent vp_look {round(s['yaw'] * 100)} {round(s['pitch'] * 100)} {round(c.DOOM_FOV * 100)}"])
            time.sleep(0.6)
            qa.command(["con", f'screenshot "{shot.as_posix()}"'])
            ok = c.wait_until(shot.exists, 10, run)
            qa.command(["con", "netevent vp_player; screenblocks 10"])
            time.sleep(0.6)
            qa.command(["con", f'screenshot "{native.as_posix()}"'])
            ok_native = c.wait_until(native.exists, 10, run)
            qa.command(["con", "screenblocks 12"])
            log["spots"].append(dict(id=s["id"], teleport=tp, shot=ok, native=ok_native))
            print(s["id"], "teleport", tp.get("ok"), tp.get("error", ""), "shot", ok, "native", ok_native)
            if c.fatal(run):
                raise RuntimeError("fatal: " + c.fatal(run))
        log["actors"] = qa.command(["actors", "4096", "60"])
    finally:
        c.kill(proc)
        (out / "doomerfall_session.json").write_text(json.dumps(log, indent=1))
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--out", type=Path, default=c.OUT / "scenes")
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--skip-df", action="store_true")
    ap.add_argument("--skip-doom", action="store_true")
    args = ap.parse_args()
    out = args.out.resolve()
    c.ensure_outside_repo(out)
    out.mkdir(parents=True, exist_ok=True)
    work = c.OUT / "work"
    points = ensure_points(work)
    spots = pick_spots(points, args.seed, args.count)
    (out / "spots.json").write_text(json.dumps(spots, indent=1))
    if not args.skip_doom:
        c.prepare(work)
        capture_doomerfall(spots, out, work, args.timeout)
    if not args.skip_df:
        capture_df(spots, out, 300)
    cards, rows = [], []
    for s in spots:
        df, doom, native = (out / f"{s['id']}{e}" for e in (".df.png", ".doom.png", ".doomnative.png"))
        score = c.pair(df, doom, out / f"{s['id']}.side.png")
        c.pair(df, native, out / f"{s['id']}.native.side.png")
        bright = [c.mean_brightness(p) if p.exists() else "" for p in (df, doom)]
        rows.append([s["id"], s["x"], s["y"], s["floor"], s["yaw"], score, *bright])
        where = f"Doom {s['x']}, {s['y']}, floor {s['floor']} (Daggerfall {s['x'] / c.WORLD_SCALE:.0f}, {s['y'] / c.WORLD_SCALE:.0f}), facing {s['yaw']}"
        cards.append(dict(title=f"{s['id']}: {where}", note=f"difference {score}, brightness DFU {bright[0]} / Doomerfall {bright[1]}",
                          side=f"{s['id']}.side.png" if score is not None else None))
        cards.append(dict(title=f"{s['id']} as played (Doom's own eye height, field of view, weapon and HUD)",
                          side=f"{s['id']}.native.side.png" if native.exists() and df.exists() else None))
    with open(out / "scenes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "doom_x", "doom_y", "doom_floor", "angle", "difference", "brightness_dfu", "brightness_doomerfall"])
        w.writerows(rows)
    c.write_index(out / "index.html", f"Visual parity: {DUNGEON_NAME}, seed {args.seed}", cards)
    made = sum(1 for r in rows if r[5] is not None)
    print(f"{made} of {len(spots)} pairs written to {out}")
    return 0 if made == len(spots) else 1


if __name__ == "__main__":
    sys.exit(main())
