"""Tests Doom's Status key (netevent df_status): Daggerfall's location and time box, then its health box, shown in Doom,
outdoors in town and indoors, in a paired run with both real games on quiet_run's private desktop.

usage: statuskey.py assemble | run dungeon | run building | check
run dungeon: outdoors in the town by Privateer's Hold, then inside Privateer's Hold.
run building: outdoors, then inside the first building of the town's door list.
Each area: the bridge's -dfuitest opens the status boxes through the command the key is bound to; after that the key
presses are real window messages to Doom's window. The first press of Y must page from the location box to the health
box (Daggerfall's own Status key does that), and the second must close it. In the building run the second press is
Escape instead. Daggerfall's -dfstatustest logs the top window, its text, and Daggerfall's area, location and hour.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, the new event doing nothing there, and -norun.
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
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\status-key")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\looklabel")  # Data, converter, cache, item and sprite packages.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-dungeonrt" / "Release"  # Configured from this worktree (tools/status_key/build_native.py).
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-statuskey" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-statuskey" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
DUNGEON_DOOR = "1 187853213"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
VK_Y, VK_ESC = 0x59, 0x1B
BINDS = ["+bind", "y", "netevent df_status"]
HEALTH = re.compile(r"healthy|poison|disease|suffer|infect", re.I)


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def door_row(mode):
    rows = [l.split() for l in lumps(REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines()]
    if mode == "dungeon":
        return next(r for r in rows if " ".join(r[:2]) == DUNGEON_DOOR)
    return next(r for r in rows if r[0] == "0")


def harness(mode, folder):
    door = door_row(mode)
    print("door", " ".join(door[:3]))
    path = folder / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SKHarness" }\n')
    return path


def doom_driver(launcher_log, uz_log):
    """tools/map_keys' window driver; that script runs its command line on import, so only its definitions are loaded."""
    path = REPO / "tools" / "map_keys" / "mapkeys.py"
    ns = {"__file__": str(path), "__name__": "mapkeys_driver"}
    exec(compile(read(path).split("\nclass Run:")[0], str(path), "exec"), ns)
    doom = ns["Doom"](launcher_log)
    size = re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(uz_log))
    if size:
        doom.surface = (int(size[-1][0]), int(size[-1][1]))
    return doom


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
    if (REVIEW / "data").exists():
        shutil.rmtree(REVIEW / "data")
    shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    binds = ("--uzdoom-arg +bind --uzdoom-arg y --uzdoom-arg \"netevent df_status\" --uzdoom-arg +bind --uzdoom-arg q --uzdoom-arg \"netevent df_info\" "
             "--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\" "
             "--uzdoom-arg +bind --uzdoom-arg j --uzdoom-arg \"netevent df_journal\" --uzdoom-arg +bind --uzdoom-arg z --uzdoom-arg \"netevent df_rest\" "
             "--uzdoom-arg +bind --uzdoom-arg p --uzdoom-arg \"netevent df_character\"")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Status key. Starts in the town outside Privateer's Hold with DRLA. Press Y for Daggerfall's status: where you are and the\r\n"
        "rem date and time. Press Y again for your health, and once more to close it (Enter, a click or Escape work too).\r\n"
        "rem Try it outdoors, inside a building (Use opens doors) and inside Privateer's Hold (the big door in town).\r\n"
        "rem Rebind it in Options, Customize Controls, Doomerfall Controls, Status.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={binds}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Run:
    def __init__(self, mode):
        self.mode = mode
        self.dir = REVIEW / f"run-{mode}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-status.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "status.log"
        self.results = []
        self.proc = None
        self.greetings = 0  # building greeting boxes closed before the indoor status check

    def case(self, ok, what):
        self.results.append((bool(ok), what))
        print("CASE", "pass" if ok else "FAIL", what)

    def wait(self, path, pattern, seconds, start=0):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if re.search(pattern, read(path)[start:]):
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def last_box(self, start=0):
        rows = re.findall(r"top DaggerfallMessageBox \| area (\S+) \| here '(.*?)' \| hour (\d+) \| text '(.*)'", read(self.views)[start:])
        return rows[-1] if rows else None

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        shutil.rmtree(self.dir / "shots", ignore_errors=True)
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", "2", "+dd_ui_test_hold", "1", "+dd_ui_test_menu", "13", *BINDS, "+logfile", "status", "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0",
              "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfstatustest", str(self.views),
              "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "200", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", harness(self.mode, self.dir)]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if self.area(1, "outdoors", ("outside",), VK_Y):
                self.close_greeting()
                self.area(2, "indoors", ("dungeon",) if self.mode == "dungeon" else ("building",), VK_ESC if self.mode == "building" else VK_Y)
            self.wait(self.console, "SKDONE", 5)
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            self.case(False, f"driver error: {e!r}")
        finally:
            if self.proc.poll() is None:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.proc.wait()
        self.summary()

    def close_greeting(self):
        """Entering a shop or home shows Daggerfall's greeting box (menu 7) first, as in Daggerfall Unity; close it."""
        if self.mode != "building":
            return
        if self.wait(self.uz_log, r"(?s)Daggerfall opened menu 7 at|(Daggerfall opened menu 13 at.*){2}", 90) and "opened menu 7 at" in read(self.uz_log):
            time.sleep(1.0)
            doom_driver(self.launcher, self.uz_log).tap(VK_ESC)
            self.greetings = 1
            print("  closed the building's greeting box")

    def area(self, n, where, areas, second_key):
        mark = len(read(self.views))
        if not self.wait(self.uz_log, r"(?s)(Daggerfall opened menu 13 at.*){%d}" % n, 150 if n == 1 else 90):
            self.case(False, f"{where}: the status key opened Daggerfall's status in Doom")
            return False
        self.wait(self.views, r"top DaggerfallMessageBox ", 5, mark)
        time.sleep(1.0)
        first = self.last_box(mark)
        print("  first box:", first)
        self.case(first and first[0] in areas and first[3] and not HEALTH.search(first[3]),
                  f"{where}: the key shows Daggerfall's location and time box in Doom (area {first and first[0]}, here '{first and first[1]}', hour {first and first[2]}: '{first and first[3]}')")
        doom = doom_driver(self.launcher, self.uz_log)
        mark2 = len(read(self.views))
        doom.tap(VK_Y)
        time.sleep(1.0)
        second = self.last_box(mark2)
        print("  second box:", second)
        closes = len(re.findall(r"ui: closed \(", read(self.uz_log)))
        self.case(second and HEALTH.search(second[3]) and closes == n - 1 + self.greetings,
                  f"{where}: pressing the key again shows Daggerfall's health box, the menu stays open ('{second and second[3]}')")
        doom.tap(second_key)
        ok = self.wait(self.uz_log, r"(?s)(ui: closed \(.*){%d}" % (n + self.greetings), 8)
        reasons = re.findall(r"ui: closed \(([^)]*)\)", read(self.uz_log))
        self.case(ok and self.wait(self.views, r"top DaggerfallHUD ", 5, mark2),
                  f"{where}: {'Escape' if second_key == VK_ESC else 'the key'} closes it back to Doom ({reasons})")
        return ok

    def summary(self):
        # A mod's defaultbind on the same key would print this and lose its default (DRLA Arsenal binds L to its PDA).
        clashes = [l for l in read(self.console).splitlines() if "Key already bound" in l]
        self.case(not any("df_status" in l for l in clashes), f"no mod's default key is taken by the Status bind (clash lines: {clashes})")
        for line in read(self.console).splitlines():
            if line.startswith(("SKSTAGE", "SKREADY", "SKDONE")) or "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        print("df:", [l for l in read(self.df_log).splitlines() if "ui: status" in l])
        shots = sorted((self.dir / "shots").glob("*")) if (self.dir / "shots").exists() else []
        print("screenshots:", [s.name for s in shots])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:4])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT {self.mode}: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run-check"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        files = [*mods, str(REVIEW / ("doomerfall-drla.pk3" if mods else "doomerfall.pk3"))]
        if mods:
            files.insert(len(mods), str(REVIEW / "doomerfall.pk3"))
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *files, "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;netevent df_status;wait 35;netevent df_status;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        lines = body.splitlines()
        print(label, "exit", code, "| lines", len(lines), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in lines),
              "| unknown action lines", sum("unknown action" in l for l in lines), "| script errors", sum("Script error" in l for l in lines),
              "| fatal", sum(any(k in l for k in FATAL) for l in lines))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("dungeon", "building"))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run(args.mode or "dungeon").go()
