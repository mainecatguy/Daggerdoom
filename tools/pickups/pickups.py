"""Health and cheap ammo pickups in generated Daggerfall maps. Based on tools/hotkeys/hotkeys.py.

usage: pickups.py build | survey NAME... | interiors GROUP | assemble | first | load | check
build: publishes this worktree's converter into the review folder.
survey: converts dungeons (outside the repo) and prints the per-room pickup counts, twice, to prove the seed is fixed.
interiors: converts every building of one location and prints its pickup lines.
assemble: makes the demo folder from the weapon hotkeys demo, with Privateer's Hold and the town reconverted.
first: both real games with DRLA. Enters Privateer's Hold, counts pickups, takes one by touch, leaves, comes back,
       checks it stays taken, then autosaves.
load: loads that autosave in fresh copies of both games and checks the taken pickup is still gone.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, with the Doomerfall mod loaded.
"""
import argparse
import os
import random
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\pickups")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\weapon-hotkeys")  # Engine, Daggerfall Unity, launcher, and data. No engine change here.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
CONVERTER = REVIEW / "data" / "converter" / "DungeonConverter.exe"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def wad_lumps(path):
    with open(path, "rb") as f:
        data = f.read()
    count, offset = struct.unpack_from("<ii", data, 4)
    out = {}
    for n in range(count):
        at, size = struct.unpack_from("<ii", data, offset + 16 * n)
        out[data[offset + 16 * n + 8:offset + 16 * n + 16].rstrip(b"\0").decode()] = data[at:at + size]
    return out


def ddt_lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def convert(name, out):
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = dict(os.environ, DD_PICKUP_DUMP=str(out / "rooms.txt"))  # Every node's room, for render_rooms.py.
    text = subprocess.run([str(CONVERTER), name, "--out", str(out), "--arena2", str(ARENA2)], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", env=env)
    line = next((l for l in text.stdout.splitlines() if l.startswith("pickups:")), "no pickup line (exit %d) %s" % (text.returncode, text.stderr[-300:]))
    wad = next(out.glob("*.wad"), None)
    things = sorted(l for l in wad_lumps(wad)["TEXTMAP"].decode().splitlines() if re.search(r"type = 3164[0-2];", l)) if wad else []
    return line, things


def build():
    subprocess.check_call(["dotnet", "build", str(REPO / "tools" / "dungeon_converter" / "DungeonConverter.csproj"), "-c", "Release", "-v", "q", "-o", str(REVIEW / "data" / "converter"),
                           f"-p:BaseIntermediateOutputPath={REVIEW / 'converter-obj'}\\"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print("built", CONVERTER)


def survey(names):
    expanded = []
    for name in names:
        if not name.startswith("random:"):
            expanded.append(name)
            continue
        # A fixed sample of ordinary dungeons, the same every time: random:<count>
        listed = subprocess.run([str(CONVERTER), "--list-main", "--list-all"], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace").stdout
        found = re.findall(r"MAIN \d+ [^/\n]+/(.+?) hasDungeon=True blocks=(\d+)", listed)
        rng = random.Random(20261124)
        expanded += [n for n, _ in rng.sample(found, int(name[7:]))]
    for name in expanded:
        slug = re.sub(r"[^a-z0-9]", "", name.lower())
        line, things = convert(name, REVIEW / "scan" / slug)
        again, things2 = convert(name, REVIEW / "scan" / (slug + "-again"))
        same = things == things2 and line == again
        print(f"{name}: {line} | {len(things)} things, second conversion identical: {same}")


def interiors(group):
    listed = subprocess.run([str(CONVERTER), "--group", str(group), "--list-buildings", "--arena2", str(ARENA2)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    work = REVIEW / "scan" / f"interiors-{group}"
    work.mkdir(parents=True, exist_ok=True)
    ddt = work / "probe.ddt"
    for space, kind in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout):
        ddt.unlink(missing_ok=True)
        text = subprocess.run([str(CONVERTER), "--group", space, "--ddt", str(ddt), "--out", str(work), "--arena2", str(ARENA2)], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace")
        line = next((l for l in text.stdout.splitlines() if l.startswith("pickups:")), "no pickups line: " + (text.stderr.strip().splitlines() or [""])[-1])
        print(space, kind, line)


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "dfu"):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(SOURCE / name, REVIEW / name, ignore=shutil.ignore_patterns("*.ini", "PortableAppdata"))
    for name in ("doomerfall-launcher.exe", "dfitems.pk3"):
        shutil.copy2(SOURCE / name, REVIEW / name)
    for name in DATA:
        shutil.copy2(SOURCE / "data" / name, REVIEW / "data" / name)
    shutil.copy2(SOURCE / "data" / "ddruntime.groups.tsv", REVIEW / "data" / "ddruntime.groups.tsv")
    # Privateer's Hold with pickups. The wad, doors, and mesh come from one converter.
    out = REVIEW / "scan" / "privateershold-demo"
    line, things = convert("Privateer's Hold", out)
    print("Privateer's Hold:", line)
    subprocess.check_call([str(CONVERTER), "Privateer's Hold", "--export-mesh", "--runtime-dungeon", "--out", str(out), "--arena2", str(ARENA2)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    for name in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        shutil.copy2(out / name, REVIEW / "data" / name)
    # The town, freshly converted, so its interiors get pickups too.
    cache = REVIEW / "data" / "cache"
    shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True)
    subprocess.check_call([str(CONVERTER), "--group", str(GROUP), "--ddt", str(cache / f"T{GROUP:05d}.ddt"), "--out", str(REVIEW / "scan" / "town"), "--arena2", str(ARENA2)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Health and cheap ammo pickups. Starts at the Privateer's Hold door with DRLA. Press Use to enter.\r\n"
        "rem Rooms hold one or two stimpacks, clips, or shells, the same ones every time. Walk over one to take it.\r\n"
        "rem Leave and come back, or save and load: taken pickups stay taken. Town buildings have them too.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


def harness(load):
    cache = REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt"
    door = next(l.split() for l in ddt_lumps(cache)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    exits = [l.split() for l in wad_lumps(REVIEW / "data" / "privateershold.wad").get("DDDUNGN", b"").decode().splitlines() if l.startswith("exit ")]
    exit_spot = exits[0][1:6] if exits else ["0"] * 5
    text = (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@EXIT@", ", ".join(exit_spot)).replace("@LOADRUN@", "1" if load else "0")
    path = REVIEW / "run" / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PKHarness" }\n')
    return path


def run(name):
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    saves = runs / "saves"
    saves.mkdir(exist_ok=True)
    if name == "first":
        for old in saves.glob("*.zds"):
            old.unlink()
    autosaves = sorted(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime)
    if name == "load" and not autosaves:
        sys.exit("no autosave from the first run")
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(CONVERTER), "-ddarena2", str(ARENA2),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    if name == "load":
        uz += ["-dfloadtest", f"resume:{autosaves[-1]}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness(name == "load")]:
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
        if "PKDONE" in body:
            reason = "harness finished"
            time.sleep(2)
            break
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?, \d+ warnings? while compiling", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if re.match(r"PK[A-Z]+ ", line) or "Script error" in line or "DDTOWN active" in line or any(k in line for k in FATAL):
            print("uz", line[:260])
    for line in read(uz_log).splitlines():
        if re.search(r"save|load test", line, re.I):
            print("uz-bridge", line[:200])


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
        lines = body.splitlines()
        print(label, "exit", code, "| lines", len(lines), "| E1M1 entered", any("E1M1" in l for l in lines), "| unknown things", sum("Unknown type" in l for l in lines),
              "| script errors", sum("Script error" in l or "error" in l.lower() and "compil" in l.lower() for l in lines), "| fatal", sum(any(k in l for k in FATAL) for l in lines))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("build", "survey", "interiors", "assemble", "first", "load", "check"))
ap.add_argument("names", nargs="*")
args = ap.parse_args()
if args.command == "build":
    build()
elif args.command == "survey":
    survey(args.names)
elif args.command == "interiors":
    interiors(int(args.names[0]) if args.names else GROUP)
elif args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    run(args.command)
