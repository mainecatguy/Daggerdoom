"""Locked dungeon doors with both real games, minimized (goal 20261125-202715).

usage: run_paired.py take | load | check   [--root DIR]
take: enters Privateer's Hold, and on door 29539363 (lock 2): label, refusal without picks, damage cancel, miss, hit,
      then a synchronized autosave. Daggerfall runs with -dflocktest (takes the picks, gives 3 back after 20 s).
load: loads that autosave in fresh copies of both games, closes the door, and checks Daggerfall keeps it unlocked.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set.
--root is a folder made by scripts/play/install.py (default: the review demo folder). Logs go to <root>/test.
"""
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
ROOT = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else Path(r"D:\dev\DoomDaggerfall-loop\review\locked-doors")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
LOADID = 29539363
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def harness(runs, load, demo=False):
    cache = ROOT / "data" / "cache" / f"T{GROUP:05d}.ddt"
    door = next(l.split() for l in lumps(cache)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    text = (HERE / "harness.zs").read_text()
    text = text.replace("@DOOR@", ", ".join(door[3:8])).replace("@LOADRUN@", "1" if load else "0").replace("@LOADID@", str(LOADID))
    text = text.replace("@DEMO@", "1" if demo else "0")
    path = runs / ("demo_door.pk3" if demo else "harness.pk3")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DLHarness" }\n')
    return path


def run(name):
    runs = ROOT / "test"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    if name == "take":
        for old in saves.glob("*.zds"):
            old.unlink()
    autosaves = sorted(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime)
    if name == "load" and not autosaves:
        sys.exit("no autosave from the take run")
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(ROOT / "data" / "cache"), "-ddconverter", str(ROOT / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    if name == "load":
        uz += ["-dfloadtest", f"resume:{autosaves[-1]}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    if name == "take":
        df.append("-dflocktest")
    timeout = 110 if name == "take" else 75
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(ROOT / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(ROOT / "uzdoom" / "uzdoom.exe"), "--dfu", str(ROOT / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [ROOT / "data" / n for n in DATA] + [ROOT / "dfitems.pk3", ROOT / "doomerfall.pk3", harness(runs, name == "load")]:
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
        if "DLDONE" in body:
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
        if re.match(r"DL[A-Z]+ ", line) or line.startswith("look: ") or "lockpick" in line.lower() or "lock" in line and "door" in line.lower() or any(k in line for k in FATAL):
            print("uz", line[:200])
    for line in read(uz_log).splitlines():
        if "doors:" in line or re.search(r"load test", line, re.I):
            print("uz-bridge", line[:200])
    for line in read(df_log).splitlines():
        if "doors:" in line or "locktest:" in line or "look: request" in line and "target 6" in line:
            print("df", line[:240])
    kinds = sorted({l[:150] for l in read(ROOT / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


def check():
    runs = ROOT / "test"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(ROOT / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "-file", str(ROOT / "doomerfall.pk3"), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| door or lockpick lines", sum("door" in l.lower() or "lockpick" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))


def demo():
    """play.bat: both games, Privateer's Hold, standing at the locked door. -dflocktest takes the picks for the
    first 20 seconds inside (to show the refusal), then gives 3."""
    harness(ROOT, False, demo=True)
    if (ROOT / "play.bat").exists() and not (ROOT / "play-newgame.bat").exists():
        (ROOT / "play.bat").rename(ROOT / "play-newgame.bat")  # install.py's normal game
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA) + " " + " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (ROOT / "play.bat").write_text(
        "@echo off\r\n"
        "rem Locked doors demo: you enter Privateer's Hold and stand at the locked door 29539363 (lock 2). Look at it: \"Locked.\"\r\n"
        "rem For the first 20 seconds you hold no lockpicks, so Use (E) is refused. Then Daggerfall gives you 3.\r\n"
        "rem Use again: Fire when the gold chevron is over the white arc. A miss breaks one pick (I shows the count); a hit opens it.\r\n"
        "rem Getting hit, walking away, or pressing Use again cancels for free. Save, reload: the door stays unlocked.\r\n"
        "rem play-newgame.bat in this folder is the normal game (New Game starts in Privateer's Hold with your starting picks).\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play-door\\saves\" mkdir \"%HERE%play-door\\saves\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%demo_door.pk3\" --uzdoom-cwd \"%HERE%play-door\" --log \"%HERE%play-door\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play-door\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play-door\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play-door\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play-door\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dflocktest --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800\r\n",
        newline="")
    print("wrote", ROOT / "play.bat")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "demo":
        demo()
    elif command in ("take", "load"):
        run(command)
    elif command == "check":
        check()
    else:
        sys.exit(__doc__)
