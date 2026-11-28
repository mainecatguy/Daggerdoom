"""Paired collision walk in Privateer's Hold: a real New Game in both games, then runs in 16 headings from each spot.

usage: quiet_run.py --timeout 480 -- python paired_walk.py <play folder> --out DIR --inside-quiet [--wad PATH] [--spots x,y;x,y]
       paired_walk.py <play folder> --out DIR --analyse   (report on an earlier run's logs only)
Uses the play folder's games and data (from scripts/play/install.py), minimized under quiet_run.py, with paired_walk.zs.
--wad swaps in another privateershold.wad (for example the old converter's) with the same mesh and doors.
Prints, per spot and heading, the distance run and the snags: tics where the player, still moving, covered less than
half of that run's typical tic, and floor steps: tics on the ground that rose or fell more than 6 units at once.
Then Daggerfall's position from the two synchronized autosaves next to Doom's.
"""
import math
import re
import shutil
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "new_game"))
import run_new_game as ng  # noqa: E402  (its window-message driver for Daggerfall's creation screens)

DRLA = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
# The diagonal corridor by the entrance (notes 20261126-225039); two 45-degree corridor-side bevels, which the old
# converter left as flat 8-unit steps and the new one writes as 44.4-degree planes; a visible 26.6-degree ramp. Chosen and
# checked against the visible mesh with floor_check.py (evidence in work/notes/20261126-231823.md). 840,-96 from the
# earlier notes is a 69-degree stair, which stays stepped by design.
SPOTS = "700,860;52,620;931,1490;690,-300"
TIMEOUT = 420


SUMMARY = []


def say(*parts):
    """Prints and keeps the line for summary.txt, since quiet_run.py may not pass this script's output through."""
    SUMMARY.append(" ".join(str(p) for p in parts))
    print(*parts)


def option(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def analyse(text):
    walks, current = [], None
    for line in text.splitlines():
        if line.startswith("PWWALK"):
            s, h, x, y, z = line.split()[1:6]
            current = {"spot": int(s), "heading": int(h), "path": [(float(x), float(y), float(z), 1)]}
            walks.append(current)
        elif line.startswith("PWT") and current:
            x, y, z, ground = line.split()[1:5]
            current["path"].append((float(x), float(y), float(z), int(ground)))
    rows = []
    for w in walks:
        p = w["path"]
        steps = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(p, p[1:])]
        moving = [d for d in steps if d > 0.5]
        typical = statistics.median(moving) if moving else 0
        # A snag: a tic between two moving tics that covers under half the typical tic. Stopping dead at a wall is not one.
        snags = sum(1 for i in range(1, len(steps) - 1) if typical > 2 and steps[i] < typical / 2
                    and steps[i - 1] > typical / 2 and max(steps[i + 1:i + 4] or [0]) > typical / 2)
        # A floor step: a tic on the ground whose rise or fall is over 6 units and over twice its neighbours'. A slope moves
        # the same amount every tic, so it has none; a stair tread gives one per riser.
        dz = [abs(b[2] - a[2]) if a[3] and b[3] else 0 for a, b in zip(p, p[1:])]
        floor_steps = sum(1 for i, d in enumerate(dz) if d > 6 and d > 2 * max(dz[i - 1] if i else 0, dz[i + 1] if i + 1 < len(dz) else 0))
        # Jitter: tics inside a 16-tic window whose path is over 12 units long while every position stays inside a box
        # 6 units across, so the player shakes in place (the path length then counts vibration, not progress). A clean stop
        # has no path; a real slide leaves the box.
        shaking = set()
        for i in range(len(p) - 16):
            xs, ys = [q[0] for q in p[i:i + 17]], [q[1] for q in p[i:i + 17]]
            if sum(steps[i:i + 16]) > 12 and math.hypot(max(xs) - min(xs), max(ys) - min(ys)) < 6:
                shaking.update(range(i, i + 16))
        rows.append({**w, "net": math.dist(p[0][:2], p[-1][:2]), "jitter": len(shaking), "end": p[-1][:2],
                     "distance": sum(steps), "typical": typical, "snags": snags,
                     "floor_steps": floor_steps, "rise": p[-1][2] - p[0][2], "max_dz": max(dz or [0])})
    return rows


def main():
    play = Path(sys.argv[1]).resolve()
    out = Path(option("--out")).resolve()
    if "--analyse" in sys.argv:  # Only report on an earlier run's logs in --out.
        return report(out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "saves").mkdir(parents=True)
    (out / "shots").mkdir()
    spots = [s.split(",") for s in option("--spots", SPOTS).split(";")]
    harness = out / "walk.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "paired_walk.zs").read_text().replace("@SPOTS@", ", ".join(c for s in spots for c in s)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PWHarness" }\n')
    data = play / "data"
    mods = DRLA + [Path(option("--wad")) if n == "privateershold.wad" and option("--wad") else data / n for n in DATA]
    mods += [play / "dfitems.pk3", play / "doomerfall.pk3", play / "doomerfall-drla.pk3", harness]
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-walk.txt", out / "launcher.log"
    uz = ["-config", str(out / "walk.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log), "-dfflow",
          "-dfnewgametest", "once", "-dfuitest", "0", "-ddtowncache", str(data / "cache"),
          "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "walk", "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(out / "shots"), "+autosavecount", "4",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfflow", ng.DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    # Run the whole script under quiet_run.py with --inside-quiet: the creation driver must see Doom's window, which only
    # a process on the same private desktop can.
    # run_new_game takes --inside-quiet out of sys.argv when it is imported, so ask it.
    quiet = [] if ng.INSIDE_QUIET else [sys.executable, ng.QUIET, "--timeout", str(TIMEOUT), "--"]
    command = quiet + [str(play / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD,
               "--uzdoom-cwd", str(out), "--log", str(launcher)]
    for mod in mods:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline, result, hwnd, tries, last, answered = time.time() + TIMEOUT, "timeout", None, 0, "", 0
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.1)
            text, uzt, dft = ng.read(console), ng.read(uz_log), ng.read(df_log)
            if any(k in text for k in ("DIED WITH FATAL", "VM execution aborted")):
                result = "fatal"
                break
            if "PWDONE" in text:
                result = "walked"
                time.sleep(1)
                break
            hwnd = hwnd or ng.doom_window(launcher)
            if not hwnd:
                continue
            if "both games running" not in uzt:  # Character creation.
                size = re.search(r"opened menu 4 at (\d+)x(\d+)", uzt)
                if not size or "ui: closed" in uzt[uzt.rfind("opened menu 4"):]:
                    continue
                ng.SURFACE[:] = [int(size.group(1)), int(size.group(2))]
                top = ng.top_window(df_log)
                tries = tries + 1 if top == last else 0
                last = top
                ng.act(hwnd, top, tries)
                time.sleep(0.15)
                continue
            own = dft.count("ui: menu 7 opened") - dft.count("ui: menu 7 closed")  # The tutorial question: No, then Esc.
            if own > 0 and answered < 12:
                time.sleep(1.5)
                ng.key(hwnd, 0x4E if answered % 2 == 0 else 0x1B)
                answered += 1
                time.sleep(0.5)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    say("result:", result)
    report(out)


def report(out):
    console, df_log, uz_log = out / "log-walk.txt", out / "df.log", out / "uz.log"
    text = ng.read(console)
    for line in text.splitlines():
        if line.startswith(("PWARRIVED", "PWSAVE", "PWDONE")) or "Script error" in line and "DoomRL" not in line:
            say(line[:200])
    rows = analyse(text)
    for r in rows:
        say(f"spot {r['spot']} heading {r['heading'] * 22.5:5.1f}: net {r['net']:5.0f} to {r['end'][0]:.1f},{r['end'][1]:.1f}, "
            f"jitter tics {r['jitter']:2d}, path {r['distance']:6.0f}, tic {r['typical']:4.1f}, "
              f"snags {r['snags']}, floor steps {r['floor_steps']} (max {r['max_dz']:4.1f}), rise {r['rise']:+6.1f}")
    for s in sorted({r["spot"] for r in rows}):
        mine = [r for r in rows if r["spot"] == s]
        say(f"spot {s} total: net {sum(r['net'] for r in mine):.0f}, jitter tics {sum(r['jitter'] for r in mine)} "
            f"(headings {[r['heading'] * 22.5 for r in mine if r['jitter']]}), path {sum(r['distance'] for r in mine):.0f}, snags {sum(r['snags'] for r in mine)}, "
            f"floor steps {sum(r['floor_steps'] for r in mine)}")
    for line in ng.read(df_log).splitlines():
        if re.search(r"new game:|save \d|error", line):
            say("df", line[:220])
    for line in ng.read(uz_log).splitlines():
        if re.search(r"[Ss]ave", line):
            say("uz", line[:220])
    (out / "summary.txt").write_text("\n".join(SUMMARY) + "\n")


if __name__ == "__main__":
    main()
