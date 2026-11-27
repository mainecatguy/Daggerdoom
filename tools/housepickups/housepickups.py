"""No generated Doom pickups in any building interior: dungeons only (owner, 2026-11-26; houses since 2026-11-24).

usage: housepickups.py build | survey [GROUP] | assemble | run MODE [--stock-mods] | wad
build:    builds this worktree's converter into D:\\dev\\DoomDaggerfall-build\\housepickups-converter.
survey:   converts every building of one town with that converter and prints each building's type and pickup line.
assemble: makes the demo folder from the magicmenu-stage review folder (integration builds), with this converter and
          an empty interior cache, so every building is converted on demand by this converter.
run MODE: both real games, minimized, with DRLA. Counts generated pickups outdoors in town, then enters by a town door:
          house    a House* building: expects no pickups.
          shop     a general store: expects no pickups.
          dungeon  Privateer's Hold: expects pickups.
wad:      DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, with the Doomerfall mod loaded.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeonpickups")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\magicmenu-stage")  # Integration UZDoom, Daggerfall Unity, bridge, launcher, data.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
CONVERTER = BUILD / "housepickups-converter"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
DUNGEON_DOOR = "1 187853213"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def wad_textmap(path):
    data = path.read_bytes()
    count, offset = struct.unpack_from("<ii", data, 4)
    for n in range(count):
        at, size = struct.unpack_from("<ii", data, offset + 16 * n)
        if data[offset + 16 * n + 8:offset + 16 * n + 16].rstrip(b"\0") == b"TEXTMAP":
            return data[at:at + size]
    return b""


def converter(*args):
    return subprocess.run(["dotnet", str(CONVERTER / "DungeonConverter.dll"), *map(str, args)], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace")


def buildings(group):
    return {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", converter("--group", group, "--list-buildings", "--arena2", ARENA2).stdout)}


def build():
    subprocess.check_call(["dotnet", "build", str(REPO / "tools" / "dungeon_converter" / "DungeonConverter.csproj"), "-c", "Release", "-v", "q", "-o", str(CONVERTER),
                           f"-p:DungeonConverterBuildRoot={BUILD / 'housepickups-obj'}\\"], stdin=subprocess.DEVNULL)


def survey(group):
    work = BUILD / "housepickups-scan"
    work.mkdir(parents=True, exist_ok=True)
    ddt = work / "probe.ddt"
    totals = {}
    for space, kind in buildings(group).items():
        ddt.unlink(missing_ok=True)
        text = converter("--group", space, "--ddt", ddt, "--out", work, "--arena2", ARENA2)
        line = next((l for l in text.stdout.splitlines() if l.startswith("pickups:")), "no pickups line: " + (text.stderr.strip().splitlines() or [""])[-1])
        m = re.match(r"pickups: (\d+) placed", line)
        n = int(m.group(1)) if m else 0
        t = totals.setdefault(kind, [0, 0])
        t[0] += 1
        t[1] += n
        print(space, kind, line[:140])
    print("SUMMARY type: buildings, pickups")
    for kind, (count, n) in sorted(totals.items()):
        print(f"SUMMARY {kind}: {count} buildings, {n} pickups")


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "dfu"):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(SOURCE / name, REVIEW / name, ignore=shutil.ignore_patterns("*.ini", "PortableAppdata"))
    for name in ("doomerfall-launcher.exe", "dfitems.pk3"):
        shutil.copy2(SOURCE / name, REVIEW / name)
    data = REVIEW / "data"
    data.mkdir(exist_ok=True)
    for name in DATA + ["ddruntime.groups.tsv"]:
        shutil.copy2(SOURCE / "data" / name, data / name)
    shutil.rmtree(data / "converter", ignore_errors=True)
    shutil.copytree(CONVERTER, data / "converter")
    # Privateer's Hold from this converter. The wad, doors, and mesh come from one converter run.
    out = BUILD / "housepickups-scan" / "privateershold"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    text = converter("Privateer's Hold", "--out", out, "--arena2", ARENA2)
    print("Privateer's Hold:", next((l for l in text.stdout.splitlines() if l.startswith("pickups:")), "no pickups line " + text.stderr[-300:]))
    text = converter("Privateer's Hold", "--export-mesh", "--runtime-dungeon", "--out", out, "--arena2", ARENA2)
    if text.returncode:
        sys.exit("mesh export failed: " + text.stderr[-300:])
    for name in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        shutil.copy2(out / name, data / name)
    things = len(re.findall(rb"type = 316(?:4\d|50);", wad_textmap(data / "privateershold.wad")))
    print("privateershold.wad pickup things:", things)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    fresh_cache()
    write_demo()
    print("assembled", REVIEW)


def fresh_cache():
    """The test town from the usekey folder, and no interiors, so every building is converted by this converter."""
    cache = REVIEW / "data" / "cache"
    shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True)
    shutil.copy(SOURCE / "data" / "cache" / f"T{GROUP:05d}.ddt", cache / f"T{GROUP:05d}.ddt")
    return cache / f"T{GROUP:05d}.ddt"


def door_row(mode, town):
    rows = [l.split() for l in lumps(town)["DDDOORS"].decode().splitlines()]
    if mode == "dungeon":
        return next(r for r in rows if " ".join(r[:2]) == DUNGEON_DOOR)
    types = buildings(GROUP)
    want = (lambda k: k.startswith("House") and k != "HouseForSale") if mode == "house" else (lambda k: k == "GeneralStore")
    return next(r for r in rows if r[0] == "0" and want(types.get(int(r[1]), "")))


def write_demo():
    door = door_row("house", REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt")
    start = f"""version "4.14"
// Demo only: starts the player a few steps from a house door, facing it.
class HPDemoStart : StaticEventHandler
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
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "HPDemoStart" }\n')
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Doom pickups are in dungeons only. Starts in town facing a house door, with DRLA. Press Use (E) to enter: no pickups inside, nor in shops or other buildings.\r\n"
        "rem Privateer's Hold (the big door in town) has them: clips, shells, health, some rockets or cells, rarely a powerup. Q is Info, I the inventory, K fast travel.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg q --uzdoom-arg \"netevent df_info\" "
        "--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --mod \"%HERE%demo_start.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


def run(mode, stock_mods):
    data, runs = REVIEW / "data", REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    name = mode + ("-stock" if stock_mods else "")
    uz_log, df_log, console, launcher, ini = (runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log", runs / f"{name}.ini")
    for path in (uz_log, df_log, console, launcher, ini):
        path.unlink(missing_ok=True)
    door = door_row(mode, fresh_cache())
    print("door", " ".join(door[:3]))
    text = (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@WANT@", "1" if mode == "dungeon" else "0")
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "HPHarness" }\n')
    uz = ["-config", str(ini), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(ARENA2),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 100
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in ([] if stock_mods else [MODS / n for n in DRLA]) + [data / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"] + ([] if stock_mods else [REVIEW / "doomerfall-drla.pk3"]) + [harness]:
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
        if "HPDONE" in body:
            reason = "harness finished"
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
        if re.match(r"HP[A-Z]+ ", line) or "Script error" in line or any(k in line for k in FATAL):
            print(line[:240])
    for line in read(uz_log).splitlines():
        if re.search(r"DDTCONV|pickups:", line):
            print("uz", line[:240])


def wad():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log, ini = runs / f"log-wad-{label}.txt", runs / f"wad-{label}.ini"
        log.unlink(missing_ok=True)
        ini.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(ini), "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3"), "+logfile", f"wad-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lines = read(log).splitlines()
        print(label, "exit", code, "| E1M1 entered", any("E1M1" in l for l in lines), "| unknown things", sum("Unknown type" in l for l in lines),
              "| script errors", sum("Script error" in l for l in lines), "| fatal", sum(any(k in l for k in FATAL) for l in lines))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("build", "survey", "assemble", "run", "wad"))
ap.add_argument("arg", nargs="?", default="")
ap.add_argument("--stock-mods", action="store_true")
args = ap.parse_args()
if args.command == "build":
    build()
elif args.command == "survey":
    survey(int(args.arg) if args.arg else GROUP)
elif args.command == "assemble":
    assemble()
elif args.command == "run":
    run(args.arg or "house", args.stock_mods)
else:
    wad()
