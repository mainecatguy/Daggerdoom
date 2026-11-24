"""Assembles and runs the NPC kill test with both real games, minimized, through the launcher.

usage: npckill.py assemble | run NAME [--hour H] [--home ORDINAL|-1] [--inside] [--save | --load]
run stands outside a building in Gothway (a lived-in house, or the tavern with --home -1), optionally goes in, and tries
to hurt the nearest NPC of each kind (see harness.zs). It prints Doom's NK lines and Daggerfall's town, guard and npc
lines. Reuses the townhomes package's converted data and its census of homes.
"""
import argparse
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
argv, sys.argv = sys.argv, sys.argv[:1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\npckill")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\townhomes")  # converted Gothway data, dfitems.pk3, and the census
BUILDS = Path(r"D:\dev\DoomDaggerfall-build")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", BUILDS / "uzdoom-npckill" / "Release"), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(BUILDS / "uzdoom-launcher" / "Release" / dll, REVIEW / "uzdoom" / dll)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILDS / "bridge-npckill" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if not (REVIEW / "data").exists():
        shutil.copytree(SOURCE / "data", REVIEW / "data")
    shutil.copy2(BUILDS / "launcher-npckill" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    print("assembled", REVIEW)


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def pick_door(home):
    """Door row for a census home ordinal (the fullest home by default), or the tavern for -1. As in townhomes.py."""
    data = REVIEW / "data"
    arena2 = str(GAME / "DAGGER" / "ARENA2")
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", arena2],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    order = [(int(m[0]), m[1]) for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)]
    rows = [l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    if home is None:
        census = [tuple(map(int, l.split()[1:4])) for l in read(SOURCE / "run" / "homes.txt").splitlines() if l.startswith("townhome ")]
        doors = {int(r[1]) for r in rows}
        census = [c for c in census if c[0] < len(order) and order[c[0]][0] in doors]
        home = max(census, key=lambda c: c[2])[0] if census else -1
    if home < 0:
        types = dict(order)
        return next(r for r in rows if types.get(int(r[1])) == "Tavern"), "tavern"
    space, kind = order[home]
    return next(r for r in rows if int(r[1]) == space), f"home ordinal {home} space {space} {kind}"


def run(name, hour, home, inside, save, load):
    data, runs = REVIEW / "data", REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    door, label = pick_door(home)
    print("door:", label, door[3:8])
    mode = ("inside " if inside else "") + ("save " if save else "") + ("load" if load else "")
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@MODE@", mode))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "NKHarness" }\n')
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    if load:
        newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
        if newest is None:
            sys.exit("no save to load")
        resume = saves / "resume.zds"
        shutil.copy2(newest, resume)
        uz += ["-dfloadtest", "resume:" + str(resume), "+dd_ui_test_hold", "1"]
    elif save:
        for old in saves.glob("*.zds"):
            old.unlink()
    if hour is not None:
        df += ["-dftownhour", str(hour)]
    timeout = 80
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [data / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness]:
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
        if "NKDONE" in body:
            reason = "route finished"
            time.sleep(1.5)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if line.startswith(("NK", "DDTOWNSFOLK", "DDGUARD", "DDNPC", "DDTRANSITION")) or any(k in line for k in FATAL):
            print(line[:200])
    for line in read(df_log).splitlines():
        if re.search(r"town: (death|murder|assault|ledger|repeat)|guards?:|crime|exception", line, re.I):
            print("DF", line[:260])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--hour", type=float)
ap.add_argument("--home", type=int, help="census ordinal of a home, or -1 for the tavern")
ap.add_argument("--inside", action="store_true", help="go in before the tests")
ap.add_argument("--save", action="store_true", help="autosave after the tests")
ap.add_argument("--load", action="store_true", help="start from the newest autosave and only list")
args = ap.parse_args()
if args.command == "assemble":
    assemble()
else:
    run(args.name, args.hour, args.home, args.inside, args.save, args.load)
