"""Daggerfall's building greeting in Doom: the message Daggerfall Unity shows on walking into a shop or an open home.

usage: building_greeting.py assemble | run MODE | wad
assemble: makes D:\\dev\\DoomDaggerfall-loop\\review\\building-greeting from the dungeonpickups-stage review folder
          (integration UZDoom, launcher, bridge, data) with this worktree's Daggerfall Unity build, and writes play.bat.
run MODE: both real games on quiet_run's private desktop, with DRLA, in the test town. Enters one town door:
          shop    a general store: expects Daggerfall's shop quality text (a message box shown in Doom).
          house   a House1-4 building: expects the home greeting (a message box) when Daggerfall holds it unlocked.
          tavern  a tavern: expects no greeting.
          Prints Daggerfall's greeting and window lines, Doom's menu lines, and saves Doom's screen (MODE-N.png) 1, 3 and 6 s
          after Doom is inside.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\building-greeting")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeonpickups-stage")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
DOOM_BORDER = (28, 79)  # As in tools/hud_messages: Doom's window size includes its frame.
SHOTS = (1, 3, 6)
WANT = {"shop": lambda k: k == "GeneralStore", "house": lambda k: re.fullmatch(r"House[1-4]", k) is not None, "tavern": lambda k: k == "Tavern"}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def buildings():
    out = subprocess.run(["dotnet", str(REVIEW / "data" / "converter" / "DungeonConverter.dll"), "--group", str(GROUP), "--list-buildings", "--arena2", str(ARENA2)],
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace").stdout
    return {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", out)}


def door_row(mode):
    rows = [l.split() for l in lumps(REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines()]
    types = buildings()
    row = next(r for r in rows if r[0] == "0" and WANT[mode](types.get(int(r[1]), "")))
    return row, types[int(row[1])]


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "dfu", "data"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(SOURCE / "uzdoom", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.ini", "PortableAppdata"))
    bridge = SOURCE / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    shutil.copy2(bridge, REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll")
    # -dfsynctest needs a portable install: the marker and the stage's settings, without its logs and saves.
    shutil.copy2(SOURCE / "dfu" / "Portable.txt", REVIEW / "dfu" / "Portable.txt")
    (REVIEW / "dfu" / "PortableAppdata").mkdir()
    for name in ("settings.ini", "KeyBinds.txt"):
        shutil.copy2(SOURCE / "dfu" / "PortableAppdata" / name, REVIEW / "dfu" / "PortableAppdata" / name)
    for name in ("doomerfall-launcher.exe", "dfitems.pk3", "doomerfall.pk3", "doomerfall-drla.pk3"):
        shutil.copy2(SOURCE / name, REVIEW / name)
    shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("S*.ddt", "S*.wad"))
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    door, kind = door_row("shop")
    start = f"""version "4.14"
// Demo only: starts the player a few steps from a general store door, facing it.
class BGDemoStart : StaticEventHandler
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
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "BGDemoStart" }\n')
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Building greetings. Starts in town facing a general store door, with DRLA. Press Use (E) to enter: Daggerfall's shop quality text appears\r\n"
        "rem (click or press a key to close it). Open homes greet you in daytime; other buildings show nothing, as in Daggerfall Unity. Q is Info, I the inventory.\r\n"
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


def run(mode):
    runs = REVIEW / "run" / mode
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    door, kind = door_row(mode)
    print("door", " ".join(door[:3]), kind)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "BGHarness" }\n')
    console, uz_log, df_log = runs / "log-console.txt", runs / "uz.log", runs / "df.log"
    w, h = 1280, 800
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(uz_log), "-noautoload", "-skill", "3", "-ddqa", str(runs / "qa"),
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(ARENA2),
          "+logfile", "console", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "-width", str(w + DOOM_BORDER[0]), "-height", str(h + DOOM_BORDER[1]), "+vid_fullscreen", "0", "+win_w", str(w + DOOM_BORDER[0]), "+win_h", str(h + DOOM_BORDER[1]),
          "+vid_scalemode", "0", "+vid_scalefactor", "1", "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", str(w), "-screen-height", str(h)]
    timeout = 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, inside, shot = "timeout", time.time() + timeout + 3, None, 0
    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = read(console)
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
        if "BGDONE timeout" in body:
            reason = "harness timed out"
            break
        if inside is None and "BGINSIDE" in body:
            inside = time.time()
        if inside is not None:
            if shot < len(SHOTS) and time.time() - inside >= SHOTS[shot]:
                with open(inbox, "a") as f:
                    f.write(f"s{shot} con screenshot \"{runs / f'{mode}-{shot}.png'}\"\n")
                shot += 1
            if shot >= len(SHOTS) and time.time() - inside > SHOTS[-1] + 2:
                reason = "screens taken"
                break
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if line.startswith("BG") or "Script error" in line or any(k in line for k in FATAL):
            print("doom:", line[:240])
    for line in read(df_log).splitlines():
        if re.search(r"transition \d+:|^.*hud: |ui: ", line):
            print("df:", line[:300])
    for line in read(uz_log).splitlines():
        if "heartbeat=" not in line and re.search(r"(?i)ui|menu|transition", line):
            print("uz:", line[:240])
    print("screens:", ", ".join(p.name for p in sorted(runs.glob(f"{mode}-*.png"))) or "none")


def wad():
    runs = REVIEW / "run" / "wad"
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
        print(label, "exit", code, "| E1M1 entered", any("E1M1" in l for l in lines), "| script errors", sum("Script error" in l for l in lines),
              "| fatal", sum(any(k in l for k in FATAL) for l in lines))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "wad"))
ap.add_argument("mode", nargs="?", default="shop", choices=tuple(WANT))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "run":
    run(args.mode)
else:
    wad()
