"""Quest follower faces on Doom's HUD, with both real games through the launcher, minimized. Based on tools/ammo/ammo.py.

usage: faces.py assemble | uzdoom | run | check
assemble: builds the review folder from this worktree's builds (UZDoom, bridge, launcher, Daggerfall Unity).
uzdoom:   copies only a fresh UZDoom build into the review folder.
run:      paired session in Daggerfall's starting town with -dffacetest on both games. Daggerfall adds face A; Doom
          screenshots it and saves; Daggerfall adds face B after its half of the save; Doom screenshots both and loads;
          Doom screenshots A alone; Daggerfall drops A; Doom screenshots the empty row and quits.
check:    DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, plus the -norun startup check.
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\questfaces")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # Data, sprite package.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-location" / "Release"  # The *-location trees are configured from this worktree.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-location" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-location" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def copy_uzdoom():
    if (REVIEW / "uzdoom").exists():
        shutil.rmtree(REVIEW / "uzdoom")
    shutil.copytree(UZ_BUILD, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    copy_uzdoom()
    if (REVIEW / "dfu").exists():
        shutil.rmtree(REVIEW / "dfu")
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if (REVIEW / "data").exists():
        shutil.rmtree(REVIEW / "data")
    shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    print("assembled", REVIEW)


def run(name="run"):
    runs = REVIEW / "run"
    shots = runs / "shots"
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)
    cache = REVIEW / "data" / "cache"
    for other in cache.glob("T*.ddt"):
        if other.name != f"T{GROUP:05d}.ddt":
            other.unlink()
    shutil.copy(SOURCE / "data" / "cache" / f"T{GROUP:05d}.ddt", cache)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(shots), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(cache), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "-dffacetest", str(shots),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          # A minimized UZDoom renders at 320x200; a custom scale size gives full-size screenshots (work/notes/city-daggerfall.md).
          "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720", "+screenshot_type", "png",
          "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dffacetest", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 150
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if "DDFACES PASS" in body or "DDFACES FAIL" in body:
            reason = "test finished"
            time.sleep(3)
            break
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?, \d+ warnings? while compiling", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if line.startswith("DDFACES") or "Script error" in line or any(k in line for k in FATAL):
            print("uz", line[:220])
    for line in read(uz_log).splitlines():
        if re.search(r"faces|DDFACES|save|load", line, re.I):
            print("uz-bridge", line[:200])
    for line in read(df_log).splitlines():
        if re.search(r"face|\bsave\b|load", line, re.I):
            print("df", line[:300])
    print("screenshots:", sorted(p.name for p in shots.glob("*.png")))


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"  # UZDoom writes +logfile NAME to log-NAME.txt.
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3"), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()), "| E1M1 entered", "E1M1" in body)
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "uzdoom", "run", "check"))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "uzdoom":
    copy_uzdoom()
elif args.command == "check":
    check()
else:
    run()
