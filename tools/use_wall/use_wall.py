"""Paired test and demo: Doom's Use on a town building's wall does Daggerfall's Info on it (name + town map).

usage: use_wall.py assemble <source review folder> | run NAME [--stock-mods] | check
assemble copies the source folder's launcher, bridge DLL, data and dfitems.pk3 (they must match this checkout's bridge
header), this checkout's UZDoom build and Daggerfall Unity build, and a fresh doomerfall.pk3 into review\\use-wall.
run starts both games minimized with DRLA (unless --stock-mods), town start, and presses Doom's real Use button (QA
channel) on a general store's wall beside its door, then Info on the door, then Use on the door.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\use-wall")
UZ_BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-newgameesc\Release")  # This lane's UZDoom tree.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")


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
    for f in UZ_BUILD.glob("*"):
        if f.is_file() and f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, REVIEW / "uzdoom" / f.name)
    for name in ("dfitems.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(source / name, REVIEW / name)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
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
    door = building_door("GeneralStore")
    normal, along = (float(door[6]), float(door[7])), (-float(door[7]), float(door[6]))
    x, y = float(door[3]) + normal[0] * 72 + along[0] * 128, float(door[4]) + normal[1] * 72 + along[1] * 128
    start = f"""version "4.14"
// Demo only: starts the player beside a general store, facing its wall, away from the door.
class UWDemoStart : StaticEventHandler
{{
	bool done;
	override void WorldLoaded(WorldEvent e) {{ if (e.IsSaveGame) done = true; }}
	override void WorldTick()
	{{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		let p = players[0].mo;
		p.SetOrigin(({x:.1f}, {y:.1f}, {door[5]}), false);
		p.angle = atan2({-normal[1]:.6f}, {-normal[0]:.6f});
	}}
}}
"""
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", start)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "UWDemoStart" }\n')
    command = launch_args(play, [MODS / n for n in DRLA] + [REVIEW / "demo_start.pk3"], ["+i_pauseinbackground", "0"], ["-dfmute"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Town start with DRLA, facing a general store's wall a little to the side of its door.\r\n"
        "rem Press Use (E) on the wall: Daggerfall's name for the store shows at the top of the screen, as Daggerfall's Info does,\r\n"
        "rem and the store is now marked on the town map (open Daggerfall's map to see its name). Use on any other building's wall works too.\r\n"
        "rem Use on the store's door still goes in. Info (Q if you bind it) does the same as before.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


class QaPresses:
    """Answers each UWUSE line the harness prints with one press of Doom's Use through the QA channel (dd_qa.cpp)."""

    def __init__(self, folder):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        self.inbox, self.sent = folder / "inbox.txt", 0
        self.inbox.write_text("")

    def feed(self, body):
        wanted = len(re.findall(r"(?m)^UWUSE\s*$", body))
        while self.sent < wanted:
            self.sent += 1
            with open(self.inbox, "a") as f:
                f.write(f"u{self.sent} use\n")


def run(name, stock_mods):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    door = building_door("GeneralStore")
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "UWHarness" }\n')
    qa = QaPresses(runs / "qa")
    console = runs / "log-console.txt"  # UZDoom's +logfile NAME writes log-NAME.txt in its working folder
    uz = ["-ddqa", str(qa.inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    timeout = 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, ([] if stock_mods else [MODS / n for n in DRLA]) + [harness], uz, ["-dfmute"], True)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = read(console)
        qa.feed(body)
        if "UWDONE" in body:
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
    shown = False
    for line in read(console).splitlines():
        if re.match(r"UW[A-Z]+( |$)", line):
            if line.strip() not in ("UWUSE", "UWUSED"):
                print(line[:190])
            shown = line.startswith(("UWPRESS", "UWINFO")) or (shown and line.startswith(("UWUSE", "UWUSED")))
        elif any(k in line for k in FATAL):
            print(line[:190])
        elif shown and line.strip() and not line.startswith(("DD", "DF", "Doomerfall:", "[bridge]")):
            print("   doom shows:", line[:170])
    dflog = read(runs / "df.log")
    infos = [l for l in dflog.splitlines() if "info: request" in l]
    for line in infos:
        print("df", line[:300])
    # Daggerfall's answers in press order: the wall presses (Use) come first, then the door Info.
    buildings = [(m[0], m[1], m[2], int(m[3])) for m in re.findall(r"target 2 on building (\d+) .*?\(on the map before: (\w+), after: (\w+)\): (\d+) messages", dflog)]
    wall = next((b for b in buildings[:-1] if b[3] > 0), None) if len(buildings) > 1 else None
    door_key = buildings[-1][0] if buildings else None
    entered = "UWCASE pass Use on the door entered the store" in read(console)
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)
    checks = [("Use on the store's wall named a building", wall is not None),
              ("it was not on the map before and is after", wall is not None and wall[1] == "False" and wall[2] == "True"),
              ("the wall's building is the door's building", wall is not None and wall[0] == door_key),
              ("Use on the door entered the store", entered)]
    for what, ok in checks:
        print("UWCHECK", "pass" if ok else "FAIL", what)
    print("RESULT", "PASS" if all(ok for _, ok in checks) else "FAIL")


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
ap.add_argument("--stock-mods", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.arg))
elif args.command == "run":
    run(args.arg, args.stock_mods)
else:
    check()
