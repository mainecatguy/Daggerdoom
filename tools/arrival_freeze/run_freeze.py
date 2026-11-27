"""The arrival freeze (goal 20261126-154857) with both real games, minimized.

usage: run_freeze.py normal | slow | lost | nosave | use | demo   [--root DIR]
normal: enters Privateer's Hold from its town; the map change waits for the place record as usual (too short for a frame since the door arm was removed: see work/notes/20261126-lockpick-rethink.md).
slow:   the same, with -dfsetuptest 2500: setup also waits 2.5 s for a fake answer (a slow Daggerfall).
lost:   -dfsetuptest lost: the fake answer never comes, so the setup gate's 5 s timeout ends the wait.
use:    -dfsetuptest 2500 -dffreezeuse: Use is pressed on every frozen frame (dd_tm_use). It must be dropped: the
        player stays inside (one arrival only, no exit or other map change).
nosave: autosaves off (+disableautosave 1) with -dfsetuptest 2500: the arrival still waits frozen, and makes no autosave.
Every run uses -dffreezetest: the bridge log says whether any monster, missile or the player changed while frozen,
and how often frames ran meanwhile (the window stays live). PASS needs: a freeze, changed=0, the player's health
unchanged, no frame gap over MAX_GAP_MS after the first frozen frame, play resuming (AFDONE after 6 s inside),
and the harness's WorldTick seeing level.time 0, 1, 2, ... inside with no gap (the freeze holds the clock).
demo: writes play.bat into --root (enters the dungeon with a slow 2.5 s setup, then hands over to the player).
--root is a folder made by scripts/play/install.py. Logs go to <root>/test.
"""
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lockpick" / "paired"))
import run_paired as rp  # noqa: E402  (shares the paired setup: data, mods, door lookup)

ROOT = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else Path(r"D:\dev\DoomDaggerfall-loop\review\arrival-pause")
SETUP = {"normal": None, "slow": "2500", "lost": "lost", "nosave": "2500", "use": "2500"}
# One tic of the setup spawns the dungeon's monsters and blocks the loop for ~150-250 ms here (it did before this goal);
# "responsive" here means no stall near Windows' 5 s "not responding" mark.
MAX_GAP_MS = 1000


def harness(path, demo, use=False):
    cache = ROOT / "data" / "cache" / f"T{rp.GROUP:05d}.ddt"
    door = next(l.split() for l in rp.lumps(cache)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    text = (HERE / "freeze.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@DEMO@", "1" if demo else "0").replace("@USE@", "1" if use else "0")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AFHarness" }\n')
    return path


def run(mode):
    runs = ROOT / "test"
    saves = runs / f"saves-{mode}"
    saves.mkdir(parents=True, exist_ok=True)
    for old in saves.glob("*.zds"):
        old.unlink()
    uz_log, df_log, console, launcher = runs / f"freeze-{mode}-uz.log", runs / f"freeze-{mode}-df.log", runs / f"log-freeze-{mode}.txt", runs / f"freeze-{mode}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"freeze-{mode}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(ROOT / "data" / "cache"), "-ddconverter", str(ROOT / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(rp.GAME / "DAGGER" / "ARENA2"),
          "-dffreezetest", "+logfile", f"freeze-{mode}", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
          "+vid_lowerinbackground", "0", "+map", f"DDT{rp.GROUP:05d}"]
    if mode == "nosave":
        uz += ["+disableautosave", "1"]
    if mode == "use":
        uz += ["-dffreezeuse"]
    if SETUP[mode]:
        uz += ["-dfsetuptest", SETUP[mode]]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(rp.GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 75
    command = [sys.executable, rp.QUIET, "--timeout", str(timeout), "--", str(ROOT / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(ROOT / "uzdoom" / "uzdoom.exe"), "--dfu", str(ROOT / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(rp.GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [rp.MODS / n for n in rp.DRLA] + [ROOT / "data" / n for n in rp.DATA] + [ROOT / "dfitems.pk3", ROOT / "doomerfall.pk3", harness(runs / "freeze.pk3", False, mode == "use")]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = rp.read(console)
        if "AFDONE" in body:
            reason = "harness finished"
            time.sleep(1)
            break
        if any(k in body for k in rp.FATAL) or re.search(r"[1-9]\d* errors?(, \d+ warnings?)? while (compiling|parsing)", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    bridge = rp.read(uz_log)
    for line in bridge.splitlines():
        if any(k in line for k in ("arrival", "setup:", "save:", "autosave committed")):
            print("uz-bridge", line[:220])
    done = re.search(r"AFDONE health (\d+) first_time (-?\d+) time_gaps (\d+)", rp.read(console))
    print("uz", done.group(0) if done else "no AFDONE")
    # The dungeon's arrival: the last freeze result of the run (the town start has no stitched arrival).
    results = re.findall(r"arrivaltest: result changed=(\d+) monsters=(\d+) newcomers=(\d+) spawned=(\d+) player_health=(-?\d+)->(-?\d+) frames=(\d+) max_frame_gap_ms=([\d.]+) frozen_ms=([\d.]+)", bridge)
    ok = bool(results) and done is not None and reason == "harness finished" and done.group(2) == "0" and done.group(3) == "0"
    for changed, monsters, newcomers, spawned, before, after, frames, gap, frozen in results:
        ok = ok and changed == "0" and before == after and float(gap) <= MAX_GAP_MS
    if mode == "nosave":
        ok = ok and "autosave committed" not in bridge and "save: autosave for a map change" not in bridge
    if mode == "use":
        presses = re.findall(r"arrivaltest: use presses=(\d+)", bridge)
        print("use presses during the freeze:", presses)
        ok = ok and len(results) == 1 and bool(presses) and int(presses[0]) > 0
    if mode in ("slow", "lost", "nosave", "use"):
        ok = ok and any(float(r[8]) >= (4500 if mode == "lost" else 2000) for r in results)
    print(f"{mode} {'PASS' if ok else 'FAIL'} | stopped: {reason} | freezes {len(results)}")
    return ok


def demo():
    harness(ROOT / "demo_freeze.pk3", True)
    if (ROOT / "play.bat").exists() and not (ROOT / "play-newgame.bat").exists():
        (ROOT / "play.bat").rename(ROOT / "play-newgame.bat")  # install.py's normal game
    mods = " ".join(f'--mod "{rp.MODS / n}"' for n in rp.DRLA) + " " + " ".join(f'--mod "%HERE%data\\{n}"' for n in rp.DATA)
    dagger = rp.GAME / "DAGGER"
    (ROOT / "play.bat").write_text(
        "@echo off\r\n"
        "rem Arrival pause demo: both games start in Privateer's Hold's town, and you are walked through the dungeon door.\r\n"
        "rem The map change waits for its setup, made 2.5 s slow on purpose (-dfsetuptest 2500): the screen says \"Loading...\"\r\n"
        "rem and nothing in the dungeon moves until it is done. Then play resumes and you are in control.\r\n"
        "rem play-newgame.bat in this folder is the normal game, with no slowdown.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play-freeze\\saves\" mkdir \"%HERE%play-freeze\\saves\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{rp.GAME / 'wads' / 'DOOM2.WAD'}\" {mods} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%demo_freeze.pk3\" --uzdoom-cwd \"%HERE%play-freeze\" --log \"%HERE%play-freeze\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play-freeze\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play-freeze\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play-freeze\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{rp.GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        "--uzdoom-arg -dfsetuptest --uzdoom-arg 2500 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play-freeze\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800\r\n",
        newline="")
    print("wrote", ROOT / "play.bat")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "demo":
        demo()
    elif command in SETUP:
        sys.exit(0 if run(command) else 1)
    else:
        sys.exit(__doc__)
