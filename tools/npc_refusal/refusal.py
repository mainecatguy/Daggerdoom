"""Paired test and demo for NPCs that will not talk: Daggerfall's own refusal message shows inside Doom.

usage: refusal.py assemble <source review folder> | run NAME [--building TYPE] [--stock-mods] | check
assemble copies the source folder's UZDoom, launcher, bridge DLL, data and pk3s (they must match this checkout) with
this checkout's Daggerfall Unity build into review\\npc-refusal, and writes play.bat.
run starts both games minimized with DRLA (unless --stock-mods), town start, -dftalktest -dftalkrefuse, goes into the
first building of TYPE (default Tavern) and presses Use on each NPC there twice. The first talk window opens normally;
after it closes Daggerfall's reputation drops, so later NPCs refuse with Daggerfall's message box.
check runs E1M1 with no bridge, stock and with DRLA.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\npc-refusal")
CONVERTER = Path(r"D:\dev\DoomDaggerfall-build\housepickups-converter")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
        shutil.copytree(source / name, REVIEW / name)
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(source / name, REVIEW / name)
    # Review folders carry an older converter whose interiors lack Daggerfall place keys, which current UZDoom treats
    # as unreadable, so building doors stall at "Opening...". Use a converter built from integration instead.
    if CONVERTER.exists():
        shutil.rmtree(REVIEW / "data" / "converter")
        shutil.copytree(CONVERTER, REVIEW / "data" / "converter")
        for old in (REVIEW / "data" / "cache").glob("T8*.ddt"):
            old.unlink()
    dfu = REVIEW / "dfu"
    shutil.rmtree(dfu, ignore_errors=True)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, ignore=shutil.ignore_patterns("*.pdb"))
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    # As scripts/play/install.py isolate_registry: this copy must not share the owner's Daggerfall settings.
    managers = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = managers.read_bytes()
    stock, private = b"\x10\0\0\0Daggerfall Unity", b"\x10\0\0\0Doomerfall Local"
    if stock in data:
        managers.write_bytes(data.replace(stock, private))
    elif private not in data:
        sys.exit("could not isolate the Daggerfall registry key")
    write_demo()
    print("assembled", REVIEW)


def building_door(kind):
    """The first door of a building of this Daggerfall type in the test town."""
    data = REVIEW / "data"
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    rows = [l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    return next(r for r in rows if types.get(int(r[1])) == kind)


def launch_args(runs, extra_mods, uz_extra, df_extra, minimized):
    """The launcher command line, as a list, for a run folder."""
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in extra_mods + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+vid_fullscreen", "0", "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0",
          "-screen-width", "1280", "-screen-height", "800"] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def write_demo():
    play = REVIEW / "play"
    door = building_door("Tavern")
    start = f"""version "4.14"
// Demo only: starts the player a few steps from a tavern door, facing it.
class NRDemoStart : StaticEventHandler
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
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "NRDemoStart" }\n')
    command = launch_args(play, [MODS / n for n in DRLA] + [REVIEW / "demo_start.pk3"], ["+i_pauseinbackground", "0"], ["-dfmute"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Town start with DRLA. Walk into a building, look at a person and press Use: a willing NPC opens Daggerfall's\r\n"
        "rem talk window. An NPC that dislikes you shows Daggerfall's own refusal instead, such as \"You get no response.\"\r\n"
        "rem So you meet refusals at once, after your first conversation every NPC dislikes you (test flag -dftalkrefuse).\r\n"
        "rem Go into the tavern ahead, talk to one person (Goodbye closes it), then press Use on anyone: \"You get no response.\"\r\n"
        "rem play.bat normal starts without the test flag.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set EXTRA=--dfu-arg -dftalkrefuse\r\n"
        "if /i \"%1\"==\"normal\" set EXTRA=\r\n"
        f"start \"\" {line} %EXTRA%\r\n", newline="")


def run(name, building, stock_mods):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    door = building_door(building)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "NRHarness" }\n')
    console = runs / "log-console.txt"  # UZDoom's +logfile NAME writes log-NAME.txt in its working folder
    uz = ["-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0", "+i_pauseinbackground", "0",
          "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfmute", "-dftalktest", "-dftalkrefuse"]
    timeout = 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, ([] if stock_mods else [MODS / n for n in DRLA]) + [harness], uz, df, True)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if "NRDONE" in body:
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
        if re.match(r"NR[A-Z]+ ", line) or any(k in line for k in FATAL):
            print(line[:190])
    for line in read(runs / "uz.log").splitlines():
        if re.search(r"ui: |error", line):
            print("uz", line[:200])
    talked = refused = 0
    for line in read(runs / "df.log").splitlines():
        if re.search(r"talk:|talktest:|ui: (menu|top)|error|mismatch", line):
            print("df", line[:300])
        talked += "talktest: talking to" in line
        refused += "talktest: message box" in line
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)
    print(f"RESULT talk windows {talked}, refusal message boxes {refused}:", "PASS" if talked and refused else "FAIL")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("arg", nargs="?", default="t", help="assemble: the source review folder; run: a run name")
ap.add_argument("--building", default="Tavern", help="Daggerfall building type to go into, as the converter lists it")
ap.add_argument("--stock-mods", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.arg))
elif args.command == "run":
    run(args.arg, args.building, args.stock_mods)
else:
    check()
