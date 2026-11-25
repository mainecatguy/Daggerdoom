"""Tests that Doom's own Use key does all of Doomerfall's interaction, with both real games, minimized.

usage: usekey.py assemble | run MODE [NAME] [--stock-mods] [--old-bind] | wad
MODE shop:    Use enters a store by its town door, opens a shelf, opens the shop menu, talks, and steals while crouching.
MODE dungeon: Use enters Privateer's Hold, takes a Doom drop, opens a Daggerfall pile, swings a door, presses a lever.
Every press is Doom's Use button in the player's command (harness.zs); nothing sends netevent df_interact.
Each run uses a fresh private config, so Doom's default binds apply. --old-bind adds the old play folder's
'+bind e "netevent df_interact"' to check that a bridge session turns that key back into Use.
wad: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set: Use opens a door and presses the exit switch.
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
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\usekey")
DATA_SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # Dungeon data, converter, and item sprites.
TOWN_SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\stationary-npcs\data\cache")  # A DDT3 town the current UZDoom reads.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
# This checkout's converter, so interiors converted on demand match the current UZDoom:
# dotnet build tools/dungeon_converter/DungeonConverter.csproj -c Release -o <this> -p:DungeonConverterBuildRoot=<obj>/
CONVERTER = BUILD / "usekey-converter"
UZ_BUILD = BUILD / "uzdoom-npckill" / "Release"  # This lane's UZDoom tree.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-npckill" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-npckill" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
DUNGEON_DOOR = "1 187853213"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
OLD_BIND = ["+bind", "e", "netevent df_interact"]


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


class QaPresses:
    """Answers each UKUSE line the harness prints with one press of Doom's Use through the QA channel."""

    def __init__(self, folder):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        self.inbox, self.sent = folder / "inbox.txt", 0
        self.inbox.write_text("")

    def feed(self, body):
        wanted = len(re.findall(r"(?m)^UKUSE\s*$", body))
        while self.sent < wanted:
            self.sent += 1
            with open(self.inbox, "a") as f:
                f.write(f"u{self.sent} use\n")


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", UZ_BUILD), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if not (REVIEW / "data").exists():
        shutil.copytree(DATA_SOURCE / "data", REVIEW / "data")
    shutil.rmtree(REVIEW / "data" / "converter", ignore_errors=True)
    shutil.copytree(CONVERTER, REVIEW / "data" / "converter")
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(DATA_SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    print("assembled", REVIEW)


def fresh_town():
    # UZDoom trims its town cache oldest first; copy the test town and its converted interiors in, freshly dated.
    cache = REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt"
    for other in cache.parent.glob("T*.ddt"):
        other.unlink()
    for source in TOWN_SOURCE.glob("T*.ddt"):
        shutil.copy(source, cache.parent / source.name)
    return cache


def door_row(mode, cache):
    rows = [l.split() for l in lumps(cache)["DDDOORS"].decode().splitlines()]
    if mode == "dungeon":
        return next(r for r in rows if " ".join(r[:2]) == DUNGEON_DOOR)
    data = REVIEW / "data"
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    return next(r for r in rows if r[0] == "0" and types.get(int(r[1])) == "GeneralStore")


def run(mode, name, stock_mods, old_bind):
    data, runs = REVIEW / "data", REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    ini = runs / f"{name}.ini"
    for path in (uz_log, df_log, console, launcher, ini):
        path.unlink(missing_ok=True)
    door = door_row(mode, fresh_town())
    text = (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@MODE@", mode)
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "UKHarness" }\n')
    qa = QaPresses(runs / f"qa-{name}")
    uz = ["-ddqa", str(qa.inbox.parent), "-config", str(ini), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+map", f"DDT{GROUP:05d}"] + (OLD_BIND if old_bind else [])
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfshoptest", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 100
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [data / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness]
    for mod in mods:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = read(console)
        qa.feed(body)
        if "UKDONE" in body:
            reason = "route finished"
            time.sleep(2)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if re.match(r"UK[A-Z]+( |$)", line) or any(k in line for k in FATAL):
            print(line[:200])
    for line in read(uz_log).splitlines():
        if re.search(r"binds: |ui: |error", line):
            print("uz", line[:200])
    for line in read(df_log).splitlines():
        if re.search(r"talk:|shoptest:|items: |doomitems|ui: (menu|top|world|inventory|loot)|error", line):
            print("df", line[:240])
    stored = re.findall(r"(?m)^e=(.*)$", read(ini))
    print("saved config binds e to:", stored or "(nothing written)")


def wad():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    harness = runs / "wad_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "wad_harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "UKWadHarness" }\n')
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log, ini = runs / f"log-wad-{label}.txt", runs / f"wad-{label}.ini"
        qa = QaPresses(runs / f"qa-wad-{label}")
        log.unlink(missing_ok=True)
        ini.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "40", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(ini), "-ddqa", str(qa.inbox.parent), "-noautoload", "-skill", "3", "-file", *mods, str(harness), "+logfile", f"wad-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1"]
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.time() + 43
        while time.time() < end and proc.poll() is None and "UKDONE" not in read(log) and not any(k in read(log) for k in FATAL):
            qa.feed(read(log))
            time.sleep(0.1)
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
        body = read(log)
        print(label, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()), "| fatal", any(k in body for k in FATAL))
        for line in body.splitlines():
            if re.match(r"UK[A-Z]+( |$)", line) or "Script error" in line or any(k in line for k in FATAL):
                print("  ", line[:200])


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "wad"))
ap.add_argument("mode", nargs="?", choices=("shop", "dungeon"), default="shop")
ap.add_argument("name", nargs="?", default="")
ap.add_argument("--stock-mods", action="store_true")
ap.add_argument("--old-bind", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "run":
    run(args.mode, args.name or args.mode, args.stock_mods, args.old_bind)
else:
    wad()
