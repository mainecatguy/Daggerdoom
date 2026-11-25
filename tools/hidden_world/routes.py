"""Measures Daggerfall's hidden 3D world on the usual routes, with Daggerfall's own streaming radius and the session one.

usage: routes.py <play folder> [--radius N ...] [--out DIR] [route ...]
routes: walk (New Game start in Privateer's Hold, the exit, Gothway Garden, a townsperson, the travel map, a shop),
        save (New Game, then Doom's save and load test), travel (two fast travels from the overworld, the second from
        inside a town). Default: all three, at radius 3 (Daggerfall Unity's setting here) and 1 (the session's).
Each run sets DOOMERFALL_WORLDCOST=1 and DOOMERFALL_WORLDRADIUS=N for Daggerfall, through the environment, and reuses
the routes' own harnesses unchanged. Daggerfall's logs are copied to DIR/<route>-r<N>-df.log; analyze.py reads them.
Every program starts through quiet_run.py inside those harnesses.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
PY = sys.executable
QUIET_USER = HERE / "quiet_user.py"  # The drivers post window messages to Doom's window; see quiet_user.py.
TRAVEL_ROWS = ["3", "5"]  # Alphabetical rows in the test start's region, as run_travel.py takes them.


def link(path, target):
    if not path.exists():
        subprocess.check_call(["cmd", "/c", "mklink", "/J", str(path), str(target)], stdout=subprocess.DEVNULL)


def prepare_travel(play):
    """run_travel.py expects its own review layout. Gives the play folder's run-tests that layout."""
    tests = play / "run-tests"
    tests.mkdir(exist_ok=True)
    for name in ("ddruntime.pk3", "overworld.pk3"):
        if not (tests / name).exists():
            shutil.copy2(play / "data" / name, tests / name)
    shutil.copy2(play / "doomerfall-launcher.exe", tests / "doomerfall-launcher.exe")
    link(tests / "doomerfall", TOOLS.parent / "mods" / "doomerfall" / "src")
    link(tests / "town-cache", play / "data" / "cache")
    link(tests / "converter", play / "data" / "converter")


def run(route, play, radius, out):
    env = dict(os.environ, DOOMERFALL_WORLDCOST="1", DOOMERFALL_WORLDRADIUS=str(radius))
    retarget = [PY, str(TOOLS / "demo_combined" / "retarget.py"), str(play)]
    tests = play / "run-tests"
    quiet = f'QUIET=r"{QUIET_USER}"'
    if route == "walk":
        folder = out / f"walk-r{radius}"
        shim = (f"import sys; sys.path[:0] = [r'{TOOLS / 'demo_combined'}', r'{TOOLS / 'new_game'}']; import run_new_game; "
                f"run_new_game.QUIET = r'{QUIET_USER}'; import walk; sys.argv = ['walk.py', r'{play}', '--out', r'{folder}']; walk.main()")
        command = [PY, "-c", shim]
        df_log = folder / "df.log"
    elif route == "save":
        command = retarget + ["--play-mods", "--set", "TIMEOUT=180", "--set", quiet, str(TOOLS / "new_game" / "run_new_game.py"), "create", "save"]
        df_log = tests / "test-run" / "create-save-df.log"
    elif route == "travel":
        prepare_travel(play)
        command = retarget + ["--set", quiet, "--set", "TIMEOUT=70", str(TOOLS / "fast_travel_arrival" / "run_travel.py"), "hwtravel"] + TRAVEL_ROWS
        df_log = tests / "run" / "hwtravel-df.log"
    else:
        sys.exit("unknown route " + route)
    start = time.time()
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", env=env, timeout=900)
    text = result.stdout + result.stderr
    (out / f"{route}-r{radius}-harness.txt").write_text(text)
    if df_log.exists():
        shutil.copy2(df_log, out / f"{route}-r{radius}-df.log")
    verdict = next((l for l in text.splitlines() if l.startswith(("result:", "stopped:"))), "no result line")
    print(f"{route:6} radius {radius}  {int(time.time() - start):4}s  {verdict}", flush=True)


def main():
    args = sys.argv[1:]
    play = Path(args.pop(0)).resolve()
    radii, out, routes = [], play / "worldcost", []
    while args:
        a = args.pop(0)
        if a == "--radius":
            radii.append(int(args.pop(0)))
        elif a == "--out":
            out = Path(args.pop(0)).resolve()
        else:
            routes.append(a)
    out.mkdir(parents=True, exist_ok=True)
    for route in routes or ["walk", "save", "travel"]:
        for radius in radii or [3, 1]:
            run(route, play, radius, out)
            time.sleep(15)  # The last run's games may still hold its log files for a moment.


if __name__ == "__main__":
    main()
