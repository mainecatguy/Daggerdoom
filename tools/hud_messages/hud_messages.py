"""Daggerfall's top-of-screen HUD messages in Doom, side by side with Daggerfall Unity's own drawing.

usage: hud_messages.py assemble <source review folder> | run NAME [--size W H] | check
assemble builds review\\hud-messages from a paired review folder (launcher, data, dfitems.pk3) with this checkout's
UZDoom (D:\\dev\\DoomDaggerfall-build\\uzdoom-hudmsg), Daggerfall Unity build, ddruntime.pk3 with the Daggerfall font
(D:\\dev\\DoomDaggerfall-build\\hudmsg-data) and doomerfall.pk3, and writes the demo play.bat.
run starts both games on quiet_run's private desktop at a town start with DRLA. Daggerfall Unity's -dfhudtest shows a
sample of Daggerfall's HUD messages ten seconds into play and saves its window every 0.25 s for 5 s (df-NNN.png).
This script sees the sample go out in df.log and has Doom save its screen on the same schedule (uz-NNN.png),
then writes side-by-side frames (pair-NNN.png, Daggerfall Unity left, Doom right) and pairs.gif.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\hud-messages")
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")
STEP, SHOTS = 0.25, 21
DOOM_BORDER = (28, 79)  # Doom's window size includes its frame here: asking 1280x800 gives a 1252x721 screen (log "Resolution:")
SENT = "hudtest: sample sent"  # DoomerfallHudMessagesTest, in df.log


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def size_args(w, h):
    return ["-width", str(w), "-height", str(h), "+vid_fullscreen", "0", "+win_w", str(w), "+win_h", str(h), "+vid_scalemode", "0", "+vid_scalefactor", "1"]


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data", "dfu"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(source / "data", REVIEW / "data")
    shutil.copy2(BUILD / "hudmsg-data" / "ddruntime.pk3", REVIEW / "data" / "ddruntime.pk3")
    shutil.copytree(BUILD / "uzdoom-hudmsg" / "Release", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.lib", "*.exp"))
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    shutil.copy2(source / "dfitems.pk3", REVIEW / "dfitems.pk3")
    # The launcher and bridge DLL must come from this checkout: another branch's bridge layout refuses the session (-5).
    for name in ("launcher", "bridge"):
        out = BUILD / f"hudmsg-{name}"
        subprocess.check_call(["cmake", "-S", str(REPO / name), "-B", str(out), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=subprocess.DEVNULL)
        subprocess.check_call(["cmake", "--build", str(out), "--config", "Release", "--parallel", "6"], stdout=subprocess.DEVNULL)
    shutil.copy2(BUILD / "hudmsg-launcher" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(BUILD / "hudmsg-bridge" / "Release" / "doomerfall_bridge.dll", REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64")
    # -dfsynctest needs a portable install.
    shutil.copy2(source / "dfu" / "Portable.txt", REVIEW / "dfu")
    shutil.copytree(source / "dfu" / "PortableAppdata", REVIEW / "dfu" / "PortableAppdata", dirs_exist_ok=True)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def launch_args(runs, uz_extra, df_extra, minimized, size=(1280, 800)):
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"]:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0",
          "-screen-width", str(size[0]), "-screen-height", str(size[1])] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def write_demo():
    play = REVIEW / "play"
    command = launch_args(play, size_args(1280, 800) + ["+i_pauseinbackground", "0"], ["-dfmute", "-dfhudtest", str(play / "dfshots")], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Daggerfall's top-of-screen messages in Doom. Town start with DRLA in a 1280x800 window.\r\n"
        "rem About ten seconds after you can move, Daggerfall shows a sample of its own HUD messages (You are entering...,\r\n"
        "rem a disease line, a trap line, an Info line) and a mid-screen line (You have no arrows). Watch the top of Doom's\r\n"
        "rem screen: Daggerfall's font and colours, each line held as long as Daggerfall holds it, then scrolling up and\r\n"
        "rem vanishing at the line where the planned compass will sit. The Daggerfall Unity window shows the same lines.\r\n"
        "rem Real messages appear too: press a hotkey with nothing on it (for example 9), or Change Ammo with no gun.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


def pairs(runs):
    from PIL import Image
    frames = []
    for i in range(SHOTS):
        a, b = runs / "dfshots" / f"df-{i:03d}.png", runs / f"uz-{i:03d}.png"
        if not (a.exists() and b.exists()):
            continue
        left, right = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        if left.size != right.size:
            print(f"frame {i}: sizes differ, Daggerfall Unity {left.size}, Doom {right.size}; not compared")
            continue
        h = max(left.height, right.height)
        pair = Image.new("RGB", (left.width + right.width + 8, h), (40, 40, 40))
        pair.paste(left, (0, 0))
        pair.paste(right, (left.width + 8, 0))
        pair.save(runs / f"pair-{i:03d}.png")
        frames.append(pair.resize((pair.width // 2, pair.height // 2), Image.NEAREST))
    if frames:
        frames[0].save(runs / "pairs.gif", save_all=True, append_images=frames[1:], duration=int(STEP * 1000), loop=0)
    return len(frames)


def run(name, size):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "HMHarness" }\n')
    console = runs / "log-console.txt"
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "-file", str(harness), "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+dd_debugmessages", "0"] + size_args(size[0] + DOOM_BORDER[0], size[1] + DOOM_BORDER[1])
    timeout = 150
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, uz, ["-dfmute", "-dfhudtest", str(runs / "dfshots")], False, size)  # Not minimized: a minimized window renders at 320x200.
    # Both games get the same window size, and Daggerfall Unity's frames are its own screen size: its SDF text is laid out
    # in screen pixels (TextLabel: GL.LoadPixelMatrix(Screen.width, Screen.height)), so a render texture of another size
    # squashes it.
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def send(line):
        with open(inbox, "a") as f:
            f.write(line + "\n")

    reason, end, seen, sent = "timeout", time.time() + timeout + 3, None, 0
    while time.time() < end and proc.poll() is None:
        time.sleep(0.02)
        if seen is None:
            body = read(console)
            if any(k in body for k in FATAL):
                reason = "fatal"
                break
            if SENT in read(runs / "df.log"):
                seen = time.time()
            continue
        if sent < SHOTS and time.time() - seen >= sent * STEP:
            send(f"s{sent} con screenshot \"{runs / f'uz-{sent:03d}.png'}\"")
            sent += 1
        if sent >= SHOTS and time.time() - seen > SHOTS * STEP + 2:
            reason = "shots taken"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if any(k in line for k in FATAL) or "Script error" in line or line.startswith("HM"):
            print("  uz", line[:190])
    for line in read(runs / "df.log").splitlines():
        if "hud:" in line or "hudtest:" in line:
            print("  df", line[:200])
    count = pairs(runs)
    print("RESULT", "PASS" if count == SHOTS else "FAIL", count, "side-by-side frames in", runs)


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
ap.add_argument("command", choices=("assemble", "run", "check", "pairs"))
ap.add_argument("arg", nargs="?", default="t", help="assemble: the source review folder; run/pairs: a run name")
ap.add_argument("--size", type=int, nargs=2, default=(1252, 721), metavar=("W", "H"))  # fits quiet_run's private desktop
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.arg))
elif args.command == "run":
    run(args.arg, args.size)
elif args.command == "pairs":
    print(pairs(REVIEW / "run" / args.arg), "frames")
else:
    check()
