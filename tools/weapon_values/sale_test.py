"""Paired test: a Doom gun has a price and sells at a weaponsmith and a pawn shop (goal 20261127-095003).

usage: sale_test.py assemble | run NAME --building TYPE [--group N] | check

assemble  builds review/weaponvalues-02 from the staged integration build (review/batch10-stage: UZDoom, launcher,
          bridge, town data) plus this checkout's Daggerfall Unity build and Doomerfall PK3s, and writes play.bat.
run       walks into the first building of TYPE (WeaponSmith, PawnShop, GeneralStore...) in town group N (default the
          city 9183, which has a weaponsmith and pawn shops; 7154 has only a general store) with both
          real games on a private desktop, using tools/shop_menu/harness.zs. Daggerfall's -dfshoptest -dfshopdoomgun
          hook gives the player Doom guns at the shopkeeper's menu, logs their value, weight and price, then sells one.
check     E1M1 of DOOM.WAD with no bridge, stock and with DRLA (nothing in UZDoom changed; this proves it still runs).
"""
import argparse
import re
import struct
import shutil
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\weaponvalues-02")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\batch10-stage")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 9183  # a city with a weaponsmith and six pawn shops
CITY_CACHE = Path(r"D:\dev\DoomDaggerfall-loop\review\arrival-pause\data\cache")  # where an earlier run converted it
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    bridge_dll = Path("DaggerfallUnity_Data") / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
    # Once the staged build is gone, keep this folder's UZDoom, bridge, launcher and data and refresh only Daggerfall.
    staged = (SOURCE / "uzdoom").exists()
    kept_bridge = REVIEW / "doomerfall_bridge.dll.keep"
    if not staged:
        shutil.copy2(REVIEW / "dfu" / bridge_dll, kept_bridge)
    for name in ("uzdoom", "dfu") if staged else ("dfu",):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
    if staged:
        shutil.copytree(SOURCE / "uzdoom", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.ini"))
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    (REVIEW / "dfu" / bridge_dll).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / "dfu" / bridge_dll if staged else kept_bridge, REVIEW / "dfu" / bridge_dll)
    kept_bridge.unlink(missing_ok=True)
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if not (REVIEW / "data").exists():
        shutil.copytree(SOURCE / "data", REVIEW / "data")
    town_cache(GROUP)
    for name in ("doomerfall-launcher.exe", "dfitems.pk3") if staged else ():
        shutil.copy2(SOURCE / name, REVIEW / name)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def town_cache(group):
    """The converted town (local game-derived data, never committed); copied from an earlier run, or converted by UZDoom."""
    path = REVIEW / "data" / "cache" / f"T{group:05d}.ddt"
    if not path.exists() and (CITY_CACHE / path.name).exists():
        shutil.copy2(CITY_CACHE / path.name, path)
    return path


def building_door(kind, group=GROUP):
    """The first door of a building of this Daggerfall type in the town (as tools/shop_menu does it)."""
    data = REVIEW / "data"
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(group), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    rows = [l.split() for l in lumps(town_cache(group))["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    found = next((r for r in rows if types.get(int(r[1])) == kind), None)
    if not found:
        raise SystemExit(f"no {kind} in town {group}; types here: {sorted(set(types.values()))}")
    return found


def mods():
    return [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / n for n in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-drla.pk3")]


def write_demo():
    door = building_door("WeaponSmith")
    start = f"""version "4.14"
// Demo only: starts the player a few steps from a weaponsmith's door, facing it.
class WVDemoStart : StaticEventHandler
{{
	bool done;
	override void WorldLoaded(WorldEvent e) {{ if (e.IsSaveGame) done = true; }}
	override void WorldTick()
	{{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		let p = players[0].mo;
		p.SetOrigin(({door[3]} + {door[6]} * 160, {door[4]} + {door[7]} * 160, {door[5]}), false);
		p.angle = atan2(-({door[7]}), -({door[6]}));
	}}
}}
"""
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", start)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "WVDemoStart" }\n')
    modargs = " ".join(f'--mod "{m}"' for m in mods()).replace(str(REVIEW) + "\\", "%HERE%")
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem weaponvalues 02: Doom gun prices are a fifth of before (a legendary costs 2x its Daggerfall base weapon), and a gun's weight follows its\r\n"
        "rem material as a Daggerfall weapon's does (Steel and Daedric x1.25, Dwarven x0.75, Ebony x0.5). You start in a city facing its weaponsmith, with DRLA.\r\n"
        "rem Pick up a Doom gun (or use the one you have), go in with Use, Use the shopkeeper and choose Sell: Doom guns are listed with their price.\r\n"
        "rem Info (Q) on a gun in the inventory shows its weight. Pawn shops, armorers and general stores buy them too. The gun you are holding is not offered.\r\n"
        "rem E is Interact, Q is Info, I opens the inventory, K opens fast travel.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg q --uzdoom-arg \"netevent df_info\" --uzdoom-arg +bind --uzdoom-arg e --uzdoom-arg \"netevent df_interact\" "
        "--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {modargs} "
        "--mod \"%HERE%demo_start.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


def run(name, building, group):
    data, runs = REVIEW / "data", REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    door = building_door(building, group)
    print("door", door[:3], "building", door[1])
    text = (REPO / "tools" / "shop_menu" / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8]))
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SMHarness" }\n')
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{group:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfshoptest", "-dfshopdoomgun", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 150  # a city interior may be converted on first entry
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in mods() + [harness]:
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
        if "NDDONE" in body:
            reason = "route finished"
            time.sleep(1)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if re.match(r"ND[A-Z]+ ", line) or any(k in line for k in FATAL):
            print(line[:190])
    for line in read(df_log).splitlines():
        if re.search(r"shoptest:|doomitems: take|error", line):
            print("df", line[:320])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l or "WeaponValues" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, extra in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *extra, "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", any(k in body for k in FATAL),
              "| E1M1 entered", "E1M1" in body)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--building", default="WeaponSmith")
ap.add_argument("--group", type=int, default=GROUP)
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "run":
    run(args.name, args.building, args.group)
else:
    check()
