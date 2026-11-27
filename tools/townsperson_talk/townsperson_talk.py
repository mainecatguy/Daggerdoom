"""Assembles and tests Use on townspeople (Daggerfall's talk window for a wandering townsperson, inside Doom), and on a
merchant afterwards, with both real games on quiet_run's private desktop.

usage: townsperson_talk.py assemble <source review folder> | run NAME [--stock-mods] [--reload] | check
assemble builds review\\townsperson-talk from a paired review folder (UZDoom, launcher, data, dfitems.pk3, the bridge
DLL and the portable Daggerfall Unity settings) with this checkout's Daggerfall Unity build and doomerfall.pk3, and
writes the demo play.bat. run starts in the test town, presses Use on the three nearest townspeople from close by, once
from too far, then goes into the first general store and presses Use on the nearest NPC. Daggerfall Unity's
-dftalktest reports each window and closes it.
--reload autosaves after the townspeople, loads that save in the same session, and talks to a townsperson again. check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\townsperson-talk")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")
PLUGIN = Path("DaggerfallUnity_Data") / "Plugins" / "x86_64" / "doomerfall_bridge.dll"


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
    for name in ("uzdoom", "data", "dfu"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(source / "data", REVIEW / "data")
    shutil.copytree(source / "uzdoom", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.ini", "*.log"))
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    (REVIEW / "dfu" / PLUGIN).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "dfu" / PLUGIN, REVIEW / "dfu" / PLUGIN)
    shutil.copy2(source / "dfu" / "Portable.txt", REVIEW / "dfu")  # -dfsynctest needs a portable install
    if (source / "dfu" / "PortableAppdata").exists():  # an install.py folder makes it on first run
        shutil.copytree(source / "dfu" / "PortableAppdata", REVIEW / "dfu" / "PortableAppdata", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("Player*.log", "Saves"))
    for name in ("doomerfall-launcher.exe", "dfitems.pk3"):
        shutil.copy2(source / name, REVIEW / name)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def store_door():
    """The first general store door in the test town: building, then x y z and the outward normal."""
    data = REVIEW / "data"
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    rows = [l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    return next(r for r in rows if types.get(int(r[1])) == "GeneralStore")


def launch_args(runs, harness, uz_extra, df_extra, stock_mods=False, minimized=True):
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]
    mods += [] if stock_mods else [REVIEW / "doomerfall-drla.pk3"]
    mods += [harness] if harness else []
    for mod in mods:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+vid_fullscreen", "0", "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0"] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def write_demo():
    play = REVIEW / "play"
    binds = ["+bind", "q", "netevent df_info", "+bind", "i", "netevent df_inventory", "+bind", "k", "netevent df_fast_travel"]
    command = launch_args(play, None, ["+i_pauseinbackground", "0"], ["-screen-width", "1280", "-screen-height", "800"], minimized=False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    bind_args = " ".join(f'--uzdoom-arg "{a}"' for a in binds)
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Talking to townspeople. Starts in a town with DRLA, during the day. Walk up to any person walking about the\r\n"
        "rem streets, look at them and press Use (E): Daggerfall's talk window opens with their name and portrait, as in\r\n"
        "rem Daggerfall Unity. Goodbye or Escape closes it. Crouching Use pickpockets instead, as Daggerfall's Steal does.\r\n"
        "rem From too far away you get Daggerfall's 'You are too far away'. Merchants inside shops still open their menu.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\\saves\" mkdir \"%HERE%play\\saves\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={bind_args}\r\n"
        f"start \"\" {line} %BINDS%\r\n", newline="")


def run(name, stock_mods, reload=False):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    door = store_door()
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@RELOAD@", "true" if reload else "false"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "TTHarness" }\n')
    console = runs / "log-console.txt"
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    timeout = 150 if reload else 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, harness, uz,
               ["-dfmute", "-dftalktest", "-screen-width", "640", "-screen-height", "360"], stock_mods)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, asked = "timeout", time.time() + timeout + 3, False
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if reload and not asked and "TTLOADNOW" in body:
            saves = sorted((runs / "saves").glob("auto*.zds"), key=lambda f: f.stat().st_mtime)
            if saves:
                with open(inbox, "a") as f:
                    f.write(f'l0 con load {saves[-1].name}\n')  # a name in -savedir: a full path is refused
            print("loading", saves[-1] if saves else "nothing: no autosave")
            asked = True
        if "TTDONE" in body:
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
        if re.match(r"TT[A-Z]+ ", line):
            print(line[:190])
            shown = line.startswith("TTPRESS")
        elif any(k in line for k in FATAL):
            print(line[:190])
        elif shown and line.strip() and not line.startswith(("DD", "DFGATES", "Doomerfall:", "[bridge]")):
            print("   doom shows:", line[:170])
    for line in read(runs / "df.log").splitlines():
        if re.search(r"talk:|talktest:|error", line):
            print("df", line[:300])
    df = read(runs / "df.log")
    folk = len(re.findall(r"talktest: talking to .*static npc none", df))
    merchant = bool(re.search(r"talktest: window Daggerfall(Merchant|Guild|Trade)\w*", df)) or bool(re.search(r"talktest: talking to .*static npc (?!none)", df))
    far = "too far" in read(console).lower() or "too far" in df.lower()
    # The crouched Use: Doom sent Steal, and Daggerfall ran its own Steal on the townsperson (a pickpocket attempt,
    # skillbasics 01; tools/skillbasics tests its tally).
    crouched = re.search(r"talk: use (\d+) on \S+ \(Steal, [^)]*\): .*crouching: pickpocket\), status 0", df)
    crouch_ok = bool(crouched) and bool(re.search(r"talk: activating townsperson .* in Steal mode", df))
    print("crouched townsperson Use pickpocketed:", crouch_ok)
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)
    reloaded = True
    if reload:
        dropped = re.search(r"talk: dropped \d+ townsperson stand-ins", df)
        after = df[dropped.end():] if dropped else ""
        reloaded = bool(dropped) and "TTLOADED" in read(console) and bool(re.search(r"talktest: talking to .*static npc none", after))
        print("stand-ins dropped on load and talk works after it:", reloaded)
    # Three townspeople are used; the crouched one is a pickpocket attempt, so two talk windows.
    print("RESULT", "PASS" if folk >= 2 and merchant and far and crouch_ok and reloaded else "FAIL",
          f"townsperson talk windows {folk}, merchant window {merchant}, too far {far}, crouched pickpocketed {crouch_ok}")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3")] + \
                  ([str(REVIEW / "doomerfall-drla.pk3")] if mods else []) + ["+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--stock-mods", action="store_true")
ap.add_argument("--reload", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.name))
elif args.command == "run":
    run(args.name, args.stock_mods, args.reload)
else:
    check()
