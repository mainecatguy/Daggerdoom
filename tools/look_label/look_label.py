"""Paired test and demo: the label under the crosshair names what the player looks at, within interaction reach.

usage: look_label.py assemble <source review folder> | run NAME [--stock-mods] | check
assemble copies the source folder's data and dfitems.pk3, this checkout's UZDoom, bridge DLL, launcher and Daggerfall Unity
builds, and a fresh doomerfall.pk3 into review\\look-label, and writes play.bat.
run starts both games (DRLA unless --stock-mods), town start, with Daggerfall's -dflooktest (drops a pile with an Iron
Longsword). tools/look_label/harness.zs stands in front of the pile, an NPC, a monster, a Doom gun and a store door, each
in and out of reach, and a bare wall; the engine logs every label change (`look: "..."`); this script checks each.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\look-label")
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-newgameesc" / "Release"  # This lane's trees.
BRIDGE_DLL = BUILD / "bridge-newgameesc" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-newgameesc" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SIZE = ["-width", "1280", "-height", "800", "+win_w", "1280", "+win_h", "800", "+vid_scalemode", "0", "+vid_scalefactor", "1"]
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def uw():
    """tools/use_wall's helpers, pointed at this review folder."""
    saved = sys.argv
    sys.argv = ["use_wall.py", "check"]
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("use_wall_lib", REPO / "tools" / "use_wall" / "use_wall.py")
        source = (REPO / "tools" / "use_wall" / "use_wall.py").read_text()
        module = importlib.util.module_from_spec(spec)
        code = source.split("\nap = argparse.ArgumentParser()")[0]  # Leave out its command line.
        exec(compile(code, str(spec.origin), "exec"), module.__dict__)
    finally:
        sys.argv = saved
    module.REVIEW = REVIEW
    return module


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
        shutil.copytree(source / name, REVIEW / name)
    for f in UZ_BUILD.glob("*"):
        if f.is_file() and f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, REVIEW / "uzdoom" / f.name)
    shutil.copy2(source / "dfitems.pk3", REVIEW / "dfitems.pk3")
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    dfu = REVIEW / "dfu"
    shutil.rmtree(dfu, ignore_errors=True)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, ignore=shutil.ignore_patterns("*.pdb"))
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    managers = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"  # As use_wall.py: never share the owner's settings.
    data = managers.read_bytes()
    stock, private = b"\x10\0\0\0Daggerfall Unity", b"\x10\0\0\0Doomerfall Local"
    if stock in data:
        managers.write_bytes(data.replace(stock, private))
    elif private not in data:
        sys.exit("could not isolate the Daggerfall registry key")
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    lib = uw()
    play = REVIEW / "play"
    command = lib.launch_args(play, [MODS / n for n in DRLA], SIZE + ["+i_pauseinbackground", "0"], ["-dfmute"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Town start with DRLA. Walk up to things: a short gold label under the crosshair names what you could Use,\r\n"
        "rem talk to, take or open from where you stand: townspeople and NPCs (their Daggerfall name), monsters, Doom\r\n"
        "rem guns and pickups, Daggerfall loot piles, and building doors (the building's Daggerfall name).\r\n"
        "rem Step back out of reach and the label goes away. Bare walls show nothing.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


def run(name, stock_mods):
    lib = uw()
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    door = lib.building_door("GeneralStore")
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LLHarness" }\n')
    console = runs / "log-console.txt"
    uz = SIZE + ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
                 "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    timeout = 180
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [harness]
    # Not --minimized: a minimized window renders at 320x200 (tools/hud_text). quiet_run keeps it on a private desktop.
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + lib.launch_args(runs, mods, uz, ["-dfmute", "-dflooktest"], False)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, shots, uses, logs, rotate = "timeout", time.time() + timeout + 3, 0, 0, 0, time.time() + 2

    def body_now():
        return "".join(read(runs / (f"log-console{k}.txt" if k else "log-console.txt")) for k in range(logs + 1))

    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        if time.time() > rotate:  # UZDoom's log file is buffered; switching files flushes the last one.
            logs, rotate = logs + 1, time.time() + 2
            with open(inbox, "a") as f:
                f.write(f"l{logs} con logfile console{logs}\n")
        body = body_now()
        for shot in re.findall(r"(?m)^LLSHOT (\S+)", body)[shots:]:
            shots += 1
            with open(inbox, "a") as f:
                f.write(f"s{shots} con screenshot \"{runs / ('shot-' + shot + '.png')}\"\n")
        for _ in re.findall(r"(?m)^LLUSE\s*$", body)[uses:]:
            uses += 1
            with open(inbox, "a") as f:
                f.write(f"u{uses} use\n")
        if "LLDONE" in body:
            reason = "route finished"
            time.sleep(1.5)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    label, results = "", []
    for line in body_now().splitlines():
        m = re.match(r'look: "(.*)"$', line)
        if m:
            label = m[1]
        elif line.startswith("LLEND "):
            case, expect = line[6:].split(" | ", 1) if " | " in line else (line[6:], "")
            results.append((case.strip(), expect, label))
        elif re.match(r"LL(FAIL|NOTE|NPC|GUN|DONE|READY)", line) or any(k in line for k in FATAL):
            print(line[:190])
    dflog = read(runs / "df.log")
    answers = re.findall(r"look: request \d+ target (\d+) id \w+: \[(.*)\]", dflog)
    for line in [l for l in dflog.splitlines() if "looktest:" in l or "look: request" in l][:12]:
        print("df", line[:200])
    checks = []
    for case, expect, got in results:
        if expect == "*":  # Daggerfall's name: any text, and it must be what Daggerfall answered.
            want = "an NPC name from Daggerfall" if case == "npc" else "a building name from Daggerfall"
            targets = ("1", "4") if case == "npc" else ("2",)
            ok = got != "" and any(t in targets and a == got for t, a in answers)
        else:
            want, ok = repr(expect), got == expect
        checks.append(ok)
        print("LLCHECK", "pass" if ok else "FAIL", f"{case}: label {got!r}, wanted {want}")
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)
    print("RESULT", "PASS" if len(checks) == 11 and all(checks) else f"FAIL ({len(checks)} of 11 cases ran)")


def check():
    uw().check()


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
