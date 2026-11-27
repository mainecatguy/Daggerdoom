"""Paired screenshots of Doomerfall's own HUD labels (Sneaking, loaded ammo) next to a stock Doom pickup message.

usage: hud_text.py assemble <source review folder> | run NAME [--pk3 before|after] | check
assemble copies a paired review folder whose launcher, bridge DLL, UZDoom and Daggerfall Unity match this checkout (the
mod is the only change), keeps that folder's doomerfall.pk3 as doomerfall-before.pk3, builds this checkout's
doomerfall.pk3, and writes the demo play.bat into review\\hud-text.
run starts both games (on quiet_run's private desktop) with DRLA at 1280x800, town start, draws Daggerfall's test
pistol (-dfchangeammotest, key 4) so the loaded ammo label shows, holds crouch, picks up a stock Stimpack, and takes
run\\NAME\\shot.png. check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
"""
import argparse
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\hud-text")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")
SIZE = ["-width", "1280", "-height", "800", "+vid_fullscreen", "0", "+win_w", "1280", "+win_h", "800", "+vid_scalemode", "0", "+vid_scalefactor", "1"]


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data", "dfu"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
        shutil.copytree(source / name, REVIEW / name, ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    for name in ("dfitems.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(source / name, REVIEW / name)
    shutil.copy2(source / "doomerfall.pk3", REVIEW / "doomerfall-before.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    write_demo()
    print("assembled", REVIEW)


def launch_args(runs, extra_mods, pk3, uz_extra, df_extra, minimized):
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in extra_mods + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", pk3]:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0",
          "-screen-width", "1280", "-screen-height", "800"] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def write_demo():
    play = REVIEW / "play"
    command = launch_args(play, [MODS / n for n in DRLA], REVIEW / "doomerfall.pk3", SIZE + ["+i_pauseinbackground", "0"], ["-dfmute"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Town start with DRLA in a 1280x800 window. Crouch (C): \"Sneaking\" shows one size larger than before.\r\n"
        "rem The loaded ammo label (bottom right, e.g. \"Bullets\") and Climbing/Slipping are one size larger too.\r\n"
        "rem Pick something up: Doom's own pickup message (top left) is the same size as before.\r\n"
        "rem Doomerfall's labels follow the dd_hudtextstep setting (console): 1 = one size up (new default), 0 = the old size.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


def run(name, which, size):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "HTHarness" }\n')
    pk3 = REVIEW / ("doomerfall-before.pk3" if which == "before" else "doomerfall.pk3")
    console = runs / "log-console.txt"
    shot = runs / "shot.png"
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+dd_debugmessages", "0"] + SIZE + ["-width", str(size[0]), "-height", str(size[1]), "+win_w", str(size[0]), "+win_h", str(size[1])]
    timeout = 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, [MODS / n for n in DRLA] + [harness], pk3, uz, ["-dfmute", "-dfchangeammotest"], False)  # Not --minimized: a minimized window renders at 320x200.
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def send(line):
        with open(inbox, "a") as f:
            f.write(line + "\n")

    reason, end, step, at = "timeout", time.time() + timeout + 3, 0, 0.0
    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = read(console)
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
        if step == 0 and "HTREADY" in body:
            send("k1 con netevent dd_hotkey:4")
            step, at = 0.5, time.time()
        elif step == 0.5 and time.time() - at > 3:
            send("c1 con +crouch")
            step, at = 1, time.time()
        elif step == 1 and time.time() - at > 1.5:
            send("p1 con netevent htpickup")
            step, at = 2, time.time()
        elif step == 2 and time.time() - at > 0.8:
            send(f"s1 con screenshot \"{shot}\"")
            step, at = 3, time.time()
        elif step == 3 and (shot.exists() or time.time() - at > 5):
            time.sleep(0.5)
            reason = "shot taken" if shot.exists() else "no screenshot"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason, "| pk3", pk3.name)
    for line in read(console).splitlines():
        if line.startswith(("HT", "Doomerfall: loaded ammo")) or any(k in line for k in FATAL) or "Script error" in line:
            print("  ", line[:190])
    loaded = [l for l in read(runs / "df.log").splitlines() if "loaded" in l.lower()]
    for line in loaded[-3:]:
        print("df", line[:200])
    print("RESULT", "PASS" if shot.exists() else "FAIL", shot)


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3"), "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("arg", nargs="?", default="t", help="assemble: the source review folder; run: a run name")
ap.add_argument("--size", type=int, nargs=2, default=(1280, 800), metavar=("W", "H"))
ap.add_argument("--pk3", choices=("before", "after"), default="after")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.arg))
elif args.command == "run":
    run(args.arg, args.pk3, args.size)
else:
    check()
