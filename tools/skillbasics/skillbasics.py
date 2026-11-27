"""Paired test of Daggerfall's interaction skills in a Doomerfall session: each one used through Doom, and its use
tallied by Daggerfall (Daggerfall Unity's -dfskillbasicstest logs every tally of Lockpicking, Pickpocket, Mercantile,
Etiquette, Streetwise and Medical). Both real games run on quiet_run's private desktop.

usage: skillbasics.py assemble <source review folder> | run town|rest [NAME] [--prime] [--stock-mods] | check
assemble builds review\\skillbasics from a paired review folder (UZDoom, launcher, data, dfitems.pk3, the bridge DLL
and the portable Daggerfall Unity settings) with this checkout's Daggerfall Unity build and doomerfall.pk3, and writes
the demo play.bat.
run town: in the test town, Use on a townsperson (talk; the test asks a polite and a blunt question: Etiquette,
Streetwise), crouching Use on two more (Daggerfall's Steal: Pickpocket), then the general store's merchant (Sell, with
-dfshoptest: Mercantile).
run rest: the rest control where the map starts, Rest Until Healed (Medical, one tally per hour).
--prime starts the six skills one use short of advancing, and runs Daggerfall's skill check after each tally.
Lockpicking is tested by tools/lockpick/paired/run_paired.py (its tally is DoomerfallLocks.Attempt).
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\skillbasics")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "errors, 0 warnings while compiling harness", "error while compiling harness", "VM execution aborted", "Execution could not continue", "Unable to open map")
PLUGIN = Path("DaggerfallUnity_Data") / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
EXPECT = {"town": ("Etiquette", "Streetwise", "Pickpocket", "Mercantile"), "rest": ("Medical",)}


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
    binds = ["+bind", "q", "netevent df_info", "+bind", "i", "netevent df_inventory", "+bind", "k", "netevent df_fast_travel",
             "+bind", "z", "netevent df_rest"]
    command = launch_args(play, None, ["+i_pauseinbackground", "0"], ["-screen-width", "1280", "-screen-height", "800"], minimized=False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    bind_args = " ".join(f'--uzdoom-arg "{a}"' for a in binds)
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Interaction skills. Starts in a town with DRLA, during the day. Each of these is Daggerfall's own rule:\r\n"
        "rem - Crouch (Sneaking shows) and Use a townsperson: you try to pickpocket them, once per person (Pickpocket).\r\n"
        "rem   A failure is recorded as a crime, but no guards appear in the streets yet.\r\n"
        "rem - Use a townsperson standing: talk. Asking in the polite tone uses Etiquette, the blunt tone Streetwise.\r\n"
        "rem - In a shop, buy or sell (Mercantile sets the prices and is practised by each trade).\r\n"
        "rem - Rest (Z) outside the town walls: each hour heals by Medical and practises it.\r\n"
        "rem - Locked dungeon doors: pick them (Lockpicking).\r\n"
        "rem Skills rise at Daggerfall's skill check (after resting or travelling); see the character sheet.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\\saves\" mkdir \"%HERE%play\\saves\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={bind_args}\r\n"
        f"start \"\" {line} %BINDS%\r\n", newline="")


def run(route, name, prime, stock_mods):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    door = store_door()
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@REST@", "1" if route == "rest" else "0"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SBHarness" }\n')
    console = runs / "log-console.txt"
    skills = runs / "skills.log"
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfmute", "-dfskillbasicstest", str(skills)] + (["prime"] if prime else []) + (["-dfshoptest"] if route == "town" else []) + \
         ["-screen-width", "640", "-screen-height", "360"]
    timeout = 150
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, harness, uz, df, stock_mods)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, pressed = "timeout", time.time() + timeout + 3, False
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if not pressed and "SBPRESS rest" in body:
            with open(inbox, "a") as f:
                f.write("l0 con netevent df_rest\n")
            pressed = True
        if "SBDONE" in body or (route == "rest" and "rest: closing its message box" in read(skills)):
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
        if re.match(r"SB[A-Z]+ ", line) or any(k in line for k in FATAL):
            print(line[:190])
    df_log = read(runs / "df.log")
    for line in df_log.splitlines():
        if re.search(r"talk: (use|activating)|shoptest: .*(window|done|choosing)|rest:|guards:|error", line):
            print("df", line[:240])
    body = read(skills)
    print(body)
    tallied = {s: bool(re.search(rf"tally {s}: uses (\d+) -> (\d+)", body)) for s in EXPECT[route]}
    ok = all(tallied.values())
    if route == "town":
        steal = bool(re.search(r"talk: activating townsperson .* in Steal mode", df_log))
        print("crouched Use ran Daggerfall's Steal on a townsperson:", steal)
        ok = ok and steal
    if prime:
        advanced = {s: bool(re.search(rf"advance {s}: skill", body)) for s in EXPECT[route]}
        print("advanced:", advanced)
        ok = ok and all(advanced.values())
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)
    print("RESULT", "PASS" if ok else "FAIL", "tallied", tallied)


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
ap.add_argument("route", nargs="?", default="town")
ap.add_argument("name", nargs="?")
ap.add_argument("--prime", action="store_true")
ap.add_argument("--stock-mods", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.route))
elif args.command == "run":
    run(args.route, args.name or args.route, args.prime, args.stock_mods)
else:
    check()
