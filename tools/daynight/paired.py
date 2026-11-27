"""Paired check of Daggerfall's time and weather drawn by Doom (dd_weather.cpp, DoomerfallWorldLook.cs).

usage: paired.py stage | run NAME [--steps "6:0 12:4 ..."] [--hold SECONDS] [--weather 0|1] [--draw] [--doom-args ...]

stage  copies this worktree's Builds/Windows64 to the review folder, with the bridge DLL built from this worktree.
run    starts both games through the launcher, minimized, in Gothway Garden (the Doom items demo's data, read only).
       Daggerfall steps its clock and weather (-dfworldlooktest); Doom screenshots every 4 s and logs what it drew.
       Prints Daggerfall's "world look" lines next to Doom's DDWEATHER lines, and the frame times Doom measured.
       --draw keeps Daggerfall's 3D world drawn and saves its camera at the end of each step, with Doom's HUD and
       weapon hidden, then compares their brightness (brightness.py).
Builds: ../DoomDaggerfall-build/{uzdoom,bridge,launcher}-daynight. Game data and screenshots stay in the review folder.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

BUILD = Path(r"D:\dev\DoomDaggerfall-build")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\daynight")
DEMO = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # Doom side data. Not modified.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
STEPS = "6:0 8:0 12:0 17:4 19:5 23:0 12:6 12:3"
# Other checks (windows.py) point these at their own build and data. --review, --uzdoom-build, --cache and --converter set them too.
UZDOOM_BUILD = "uzdoom-daynight"
RUNTIME = DEMO / "data" / "ddruntime.pk3"
CACHE = DEMO / "data" / "cache"
CONVERTER = DEMO / "data" / "converter" / "DungeonConverter.exe"


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def stage():
    dfu = REVIEW / "dfu"
    if dfu.exists():
        shutil.rmtree(dfu)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, ignore=shutil.ignore_patterns("*.pdb"))
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge-daynight" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    (dfu / "PortableAppdata").mkdir()
    for name in ("settings.ini", "KeyBinds.txt"):
        shutil.copy2(DEMO / "dfu" / "PortableAppdata" / name, dfu / "PortableAppdata" / name)
    print("staged", dfu)


def run(name, steps, hold, weather, draw, doom_args):
    runs = REVIEW / "run"
    shots = runs / f"{name}-shots"
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir(parents=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    count = int((len(steps.split()) * hold + 30) / 4)
    (runs / f"{name}.cfg").write_text("".join(f'alias dnshot{i} "screenshot; wait 140; dnshot{i + 1}"\n' for i in range(count))
                                      + f'alias dnshot{count} ""\nwait 105; dnshot0\n')
    timeout = int(len(steps.split()) * hold + 40)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3", "-nomonsters",
          "-ddtowncache", str(CACHE), "-ddconverter", str(CONVERTER),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0",
          "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+screenshot_type", "png", "+screenshot_dir", str(shots),
          "+vid_maxfps", "0", "+vid_vsync", "0", "+dd_weather", str(weather), "+map", "DDT07154", "+exec", f"{name}.cfg"]
    if draw:
        uz += ["+screenblocks", "12", "+r_drawplayersprites", "0", "+crosshair", "0"]
    uz += doom_args
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360",
          "-dfworldlooktest", steps, str(hold)]
    df_shots = runs / f"{name}-dfshots"
    shutil.rmtree(df_shots, ignore_errors=True)
    if draw:
        df += ["-dfworldlookshots", str(df_shots)]
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(BUILD / "launcher-daynight" / "Release" / "doomerfall-launcher.exe"),
               "--minimized"] + ([] if draw else ["--nodraw"]) + ["--uzdoom", str(BUILD / UZDOOM_BUILD / "Release" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [RUNTIME, DEMO / "data" / "overworld.pk3", DEMO / "dfitems.pk3", DEMO / "doomerfall.pk3"]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, last = "timeout", time.time() + timeout + 3, len(steps.split())
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
        if (f"worldlooktest: shot step {last} " if draw else f"worldlooktest: step {last} ") in read(df_log) and not hasattr(run, "done"):
            run.done = time.time()
        if getattr(run, "done", 0) and time.time() > run.done + (1 if draw else hold):
            reason = "steps finished"
            break
        if any(k in read(console) for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(df_log).splitlines():
        if "worldlooktest" in line or "world look" in line:
            print("df", line[:200])
    for line in read(console).splitlines():
        if line.startswith("DDWEATHER") or any(k in line for k in FATAL):
            print("uz", line[:200])
    print("screenshots:", len(list(shots.glob("*.png"))), "in", shots)
    if draw:
        import brightness
        brightness.compare(df_shots, shots, df_log, hold)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["stage", "run"])
    ap.add_argument("name", nargs="?", default="daynight")
    ap.add_argument("--steps", default=STEPS)
    ap.add_argument("--hold", type=float, default=5)
    ap.add_argument("--weather", type=int, default=1)
    ap.add_argument("--draw", action="store_true")
    ap.add_argument("--review", help="output folder (default the day/night one)")
    ap.add_argument("--uzdoom-build", help="build folder name under DoomDaggerfall-build")
    ap.add_argument("--cache", help="town cache folder (default the Doom items demo's)")
    ap.add_argument("--converter", help="DungeonConverter.exe for uncached places")
    ap.add_argument("--doom-args", nargs=argparse.REMAINDER, default=[])
    a = ap.parse_args()
    if a.review:
        REVIEW = Path(a.review)
    if a.cache:
        CACHE = Path(a.cache)
    if a.converter:
        CONVERTER = Path(a.converter)
    if a.uzdoom_build:
        UZDOOM_BUILD = a.uzdoom_build
    stage() if a.command == "stage" else run(a.name, a.steps, a.hold, a.weather, a.draw, a.doom_args)
