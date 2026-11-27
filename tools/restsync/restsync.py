"""Tests that Doom holds its view after a rest or loiter until Daggerfall's people are in place, in a paired run with
both real games on quiet_run's private desktop.

usage: restsync.py assemble | demo | run street|tavern|dungeon [--rest] [--fast] [--root DIR] | check
assemble: installs this worktree's builds into the review folder (data and item sprites copied from DATA_FROM).
run street: stands in Gothway's street and loiters 2 hours; run tavern: the same inside its tavern. run dungeon: enters Privateer's Hold, clears the monsters
near the entrance (test only) and rests 1 hour (--rest picks Rest For A While in the street too).
harness.zs follows every townsperson and NPC on every tic Doom plays and reports, for 4 s after the view comes back,
anyone who jumps more than 32 units in one tic, appears, vanishes, or is shown or hidden. --root runs an older
install (for a before/after comparison); its binaries must have -dfuitest and -dfresttest.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, and -norun.
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
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\restsync")
DATA_FROM = Path(r"D:\dev\DoomDaggerfall-loop\review\ammoname")  # Data and dfitems.pk3 from the latest install.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-restsync" / "Release"
BRIDGE_DLL = BUILD / "restsync-bridge" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "restsync-launcher" / "Release" / "doomerfall-launcher.exe"
SOUND = BUILD / "uzdoom-launcher" / "Release"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
# Daggerfall's 320x200 layout: the rest window's panel is centered at y 50; its buttons are Rest For A While, Rest Until
# Healed (tools/rest uses 160,75) and Loiter, 49 apart.
WHILE_BUTTON, LOITER_BUTTON, MESSAGE_CLICK = (111, 75), (209, 75), (160, 100)


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def door(root, dungeon):
    data = root / "data"
    rows = [l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines()]
    if dungeon:
        return next(r for r in rows if r[:2] == ["1", "187853213"])
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    return next(r for r in rows if r[0] == "0" and types.get(int(r[1])) == "Tavern")  # street and tavern


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", UZ_BUILD), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini", "*.ilk", "*.exp", "*.lib", "*.log"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    install.install_expanded_inventory(REVIEW / "dfu", BUILD / "restsync")
    if not (REVIEW / "data").exists():
        shutil.copytree(DATA_FROM / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    shutil.copy2(DATA_FROM / "dfitems.pk3", REVIEW / "dfitems.pk3")
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    d = door(REVIEW, False)
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(d[3:8])).replace("@MODE@", "demo"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "RSHarness" }\n')
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA) + " " + " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Rest sync. Starts in Gothway's street by the tavern door, with townspeople walking about. Press Z for Daggerfall's\r\n"
        "rem rest window, choose Loiter (right button), type 2 and Enter. When 'You finish loitering' shows, click it away at once.\r\n"
        "rem The street comes back with everyone already where Daggerfall's clock puts them: nobody jumps a moment later.\r\n"
        "rem (Before this change, clicking the message quickly showed people jumping to new places right after.) Resting\r\n"
        "rem outdoors in town is vagrancy in Daggerfall, so try Rest inside the tavern with a rented room, or in a dungeon.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg z --uzdoom-arg \"netevent df_rest\" --uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg q --uzdoom-arg \"netevent df_info\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --mod \"%HERE%demo_start.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Run:
    def __init__(self, mode, rest, root, fast=False):
        self.mode, self.rest, self.root, self.fast = mode, rest or mode == "dungeon", root, fast
        self.dir = REVIEW / "runs" / (("before-" if root != REVIEW else "") + mode + ("-rest" if rest else "") + ("-fast" if fast else ""))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-restsync.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "rest.log"
        self.proc = None

    def wait(self, path, pattern, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if re.search(pattern, read(path)):
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def top(self):
        tops = re.findall(r"top (\S+) \|", read(self.views))
        return tops[-1] if tops else None

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        d = door(self.root, self.mode == "dungeon")
        harness = self.dir / "restsync_harness.pk3"
        with zipfile.ZipFile(harness, "w") as z:
            z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(d[3:8])).replace("@MODE@", self.mode))
            z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "RSHarness" }\n')
        data = self.root / "data"
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", "1", "+dd_ui_test_menu", "10", "+dd_ui_test_hold", "1", "+logfile", "restsync", "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0", "+wipetype", "0",
              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfresttest", str(self.views),
              "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "200", "--", str(self.root / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(self.root / "uzdoom" / "uzdoom.exe"), "--dfu", str(self.root / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        mods = [MODS / n for n in DRLA] + [data / n for n in DATA] + [self.root / "dfitems.pk3", self.root / "doomerfall.pk3"]
        if (self.root / "doomerfall-drla.pk3").exists():
            mods.append(self.root / "doomerfall-drla.pk3")
        for mod in mods + [harness]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.drive()
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            print("driver error:", repr(e))
        finally:
            if self.proc.poll() is None:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.proc.wait()
        self.summary()

    def doom(self):
        # tools/levelup's window driver; that script runs its command line on import, so only its definitions are loaded.
        path = REPO / "tools" / "levelup" / "levelup.py"
        ns = {"__file__": str(path), "__name__": "levelup_driver"}
        exec(compile(read(path).split("\nap = argparse.ArgumentParser()")[0], str(path), "exec"), ns)
        doom = ns["Doom"](self.launcher)
        size = re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        doom.surface = (int(size[-1][0]), int(size[-1][1]))
        return doom

    def type(self, doom, text):
        # Digits as characters only (a key press as well types them twice); Enter as a key press.
        for ch in text:
            if ch != "\r":
                doom.user.PostMessageW(doom.hwnd, 0x102, ord(ch), 1)
                time.sleep(0.3)
                continue
            scan = doom.user.MapVirtualKeyW(0x0D, 0)
            doom.user.PostMessageW(doom.hwnd, 0x100, 0x0D, 1 | (scan << 16))
            time.sleep(0.12)
            doom.user.PostMessageW(doom.hwnd, 0x101, 0x0D, 1 | (scan << 16) | (3 << 30))
            time.sleep(0.4)

    def drive(self):
        if not self.wait(self.console, r"RSREADY", 150):
            print("FAIL: the harness never got ready")
            return
        if not self.wait(self.uz_log, r"Daggerfall opened menu 10 at", 15) or not self.wait(self.views, r"top DaggerfallRestWindow", 5):
            print("FAIL: the rest window did not open:", self.top())
            return
        doom = self.doom()
        doom.click(WHILE_BUTTON if self.rest else LOITER_BUTTON)
        if not self.wait(self.views, r"top DaggerfallInputMessageBox", 5):
            print("FAIL: no hours prompt:", self.top())
            return
        self.type(doom, ("1" if self.rest else "2") + "\r")
        end = time.time() + 60
        while time.time() < end and self.proc.poll() is None and "ui: closed" not in read(self.uz_log).split("opened menu 10", 1)[-1]:
            if self.top() == "DaggerfallMessageBox":
                if self.fast:  # As a quick player: click the end-of-rest message the moment it shows.
                    lp = doom.point(*MESSAGE_CLICK)
                    doom.user.PostMessageW(doom.hwnd, 0x200, 0x8000, lp)
                    doom.user.PostMessageW(doom.hwnd, 0x201, 1 | 0x8000, lp)
                    time.sleep(0.03)
                    doom.user.PostMessageW(doom.hwnd, 0x202, 0x8000, lp)
                    time.sleep(0.3)
                else:
                    doom.click(MESSAGE_CLICK)
            time.sleep(0.02 if self.fast else 0.5)
        self.wait(self.console, r"RSDONE", 15)

    def summary(self):
        console, uz, df = read(self.console), read(self.uz_log), read(self.df_log)
        for line in console.splitlines():
            if line.startswith("RS") or "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        for line in uz.splitlines():
            if re.search(r"resync:|ui: closed|ui: asked Daggerfall to open menu 10", line):
                print("uz.log", line[:200])
        for line in df.splitlines():
            if re.search(r"game minutes passed|rest: menu (opening|closed)|ui: menu 10", line):
                print("df.log", line[:200])
        tops = [l for l in read(self.views).splitlines() if "top " in l]
        print("windows:", sorted({re.search(r"top (\S+)", l).group(1) for l in tops}))
        result = re.findall(r"RSRESULT .*", console)
        print("RESULT", self.mode, "rest" if self.rest else "loiter", result[-1] if result else "none")


def check():
    runs = REVIEW / "check"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "60" if mods else "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 105;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge or resync lines", sum("bridge" in l.lower() or "resync" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "demo", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("street", "tavern", "dungeon"))
ap.add_argument("--rest", action="store_true")
ap.add_argument("--root", type=Path, default=REVIEW)
ap.add_argument("--fast", action="store_true", help="click the end-of-rest message the moment it shows")
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "demo":
    write_demo()
elif args.command == "check":
    check()
else:
    Run(args.mode or "street", args.rest, args.root, args.fast).go()
