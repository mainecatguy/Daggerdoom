"""Tests Daggerfall's transport menu (foot, horse, cart, ship) opened from Doom, in a paired run with both real games on
quiet_run's private desktop.

usage: transport.py assemble | run owned | run none | check
All runs start outside Privateer's Hold with DRLA. Daggerfall's -dftransporttest gives the player a horse, a cart and a
small ship ("none": takes them away) and logs the top window, the transport mode, what the player owns, the map pixel
and the transport panel. Doom's -dfuitest opens the menu through the command the key is bound to (netevent
df_transport); every click after that is a real window message through Doom's window.
run owned: the menu opens with horse, cart and ship available; Horse rides and closes the menu, and the mode stays Horse
  while Doom runs; Cart switches to the cart; Ship shows a message and does not move the player (Doom cannot follow
  the ship teleport yet); Exit closes; Foot gets off.
run none: the menu opens with nothing owned; the Horse row does nothing; Exit closes it, still on foot.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, plus the new event doing nothing there, and -norun.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\transport")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\runtime-dungeons")  # Data, converter, item and sprite packages.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-dungeonrt" / "Release"  # Configured from this worktree (tools/transport/build_native.py).
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-statuskey" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-statuskey" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
MENU = 13  # DFB_UI_TRANSPORT
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
# DaggerfallTransportWindow rows, inside its panel: foot (5,5), horse (5,14), cart (5,23), ship (5,32), each 120x7;
# Exit (44,42 43x15). Clicks aim at the middle of each.
ROWS = {"foot": (65, 8), "horse": (65, 17), "cart": (65, 26), "ship": (65, 35), "exit": (65, 49)}
MESSAGE_CLICK = (160, 100)
BINDS = ["+bind", "t", "netevent df_transport"]


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


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
    binds = ("--uzdoom-arg +bind --uzdoom-arg t --uzdoom-arg \"netevent df_transport\" "
             "--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\" "
             "--uzdoom-arg +bind --uzdoom-arg j --uzdoom-arg \"netevent df_journal\" --uzdoom-arg +bind --uzdoom-arg z --uzdoom-arg \"netevent df_rest\" "
             "--uzdoom-arg +bind --uzdoom-arg p --uzdoom-arg \"netevent df_character\"")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Transport menu. Starts outside Privateer's Hold with DRLA. A second after the game starts, a test hook gives you a horse,\r\n"
        "rem a cart and a small ship. Press T to open Daggerfall's transport menu (T, Escape or Exit closes it). Pick Horse or Cart:\r\n"
        "rem Daggerfall keeps the choice (press T again to see it, or P then check after a save and load). Doom's movement does not\r\n"
        "rem change yet. Ship says you cannot board it yet. Indoors, T says you cannot change transportation indoors.\r\n"
        "rem Rebind the key in Options, Customize Controls, Doomerfall Controls, as Open Transport.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={binds}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dftransporttest --dfu-arg \"%HERE%play\\transport.log\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Run:
    def __init__(self, mode):
        self.mode = mode
        self.dir = REVIEW / f"run-{mode}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-transport.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "transport.log"
        self.results = []
        self.proc = None

    def case(self, ok, what):
        self.results.append((bool(ok), what))
        print("CASE", "pass" if ok else "FAIL", what)

    def wait(self, path, pattern, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if re.search(pattern, read(path)):
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def count(self, path, pattern):
        return len(re.findall(pattern, read(path)))

    def wait_count(self, path, pattern, n, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if self.count(path, pattern) >= n:
                return True
            time.sleep(0.2)
        return False

    def state(self):
        """The last logged state: dict of top, mode, horse, cart, ship, pixel, panel."""
        rows = re.findall(r"top (\S+) \| mode (\w+) \| horse (\w+) cart (\w+) ship (\w+) \| pixel (\S+) \| panel (.*)", read(self.views))
        if not rows:
            return None
        return dict(zip(("top", "mode", "horse", "cart", "ship", "pixel", "panel"), rows[-1]))

    def top_is(self, name, seconds=5):
        end = time.time() + seconds
        while time.time() < end:
            s = self.state()
            if s and s["top"] == name:
                return True
            time.sleep(0.2)
        return False

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        opens = {"owned": 4, "none": 1}[self.mode]
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", str(opens), "+dd_ui_test_menu", str(MENU), *BINDS, "+logfile", "transport", "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0", "+wipetype", "0",
              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dftransporttest", str(self.views), *(["none"] if self.mode == "none" else []),
              "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "240", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if not self.wait(self.views, r"prepared:", 120):
                self.case(False, "the test never prepared the player (game not ready)")
            else:
                print("  ", [l for l in read(self.views).splitlines() if "prepared" in l])
                getattr(self, self.mode)()
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            self.case(False, f"driver error: {e!r}")
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
        # Daggerfall may shrink the surface right after opening (640x400 to Doom's 320x200), so its newest size counts.
        size = re.findall(r"ui: surface (\d+)x(\d+) for", read(self.df_log)) or re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        doom.surface = (int(size[-1][0]), int(size[-1][1]))
        return doom

    def row(self, name):
        """A transport row in Daggerfall's 320x200 layout. The panel is centered both ways (its alignment overrides the
        logged Position), so its corner comes from the logged size."""
        m = re.match(r"(-?\d+),(-?\d+) (\d+)x(\d+)", (self.state() or {}).get("panel", ""))
        w, h = (int(m.group(3)), int(m.group(4))) if m else (130, 60)
        x, y = (320 - w) // 2, (200 - h) // 2
        return x + ROWS[name][0], y + ROWS[name][1]

    def open(self, n):
        ok = self.wait_count(self.uz_log, r"Daggerfall opened menu %d at" % MENU, n, 60) and self.top_is("DaggerfallTransportWindow")
        time.sleep(0.5)
        return ok

    def closed(self, n):
        ok = self.wait_count(self.uz_log, r"ui: closed \(", n, 8)
        return ok, re.findall(r"ui: closed \(([^)]*)\)", read(self.uz_log))

    def choose(self, n, name, mode):
        if not self.open(n):
            self.case(False, f"the transport menu opened (open {n})")
            return False
        self.doom().click(self.row(name))
        ok, reasons = self.closed(n)
        s = self.state()
        self.case(ok and s and s["mode"] == mode and self.top_is("DaggerfallHUD"), f"{name.title()} sets Daggerfall's transport mode to {mode} and closes the menu (mode {s and s['mode']}, {reasons})")
        return ok

    def owned(self):
        if not self.open(1):
            self.case(False, "the transport key opens Daggerfall's transport menu in Doom")
            return
        s = self.state()
        self.case(s["horse"] == s["cart"] == s["ship"] == "True" and s["mode"] == "Foot" and "transport menu, owns horse True cart True ship True" in read(self.df_log),
                  f"the transport key opens Daggerfall's transport menu in Doom, listing a horse, cart and ship (state {s})")
        self.doom().click(self.row("horse"))
        ok, reasons = self.closed(1)
        s = self.state()
        self.case(ok and s and s["mode"] == "Horse", f"Horse sets Daggerfall's transport mode to Horse and closes the menu (mode {s and s['mode']}, {reasons})")
        # Doom runs between menus (3 s); the choice is Daggerfall's and stays.
        if not self.open(2):
            self.case(False, "the transport menu opened a second time")
            return
        s = self.state()
        times = [int(t) for t in re.findall(r"maptime \d+ then (\d+)", read(self.uz_log))]
        asked = [int(t) for t in re.findall(r"asked Daggerfall to open menu %d, maptime (\d+)" % MENU, read(self.uz_log))]
        self.case(s["mode"] == "Horse" and times and len(asked) >= 2 and asked[1] > times[0],
                  f"Daggerfall still rides the horse after Doom ran (mode {s['mode']}, map time at close {times[:1]}, at the next open {asked[1:2]})")
        self.doom().click(self.row("cart"))
        ok, reasons = self.closed(2)
        s = self.state()
        self.case(ok and s and s["mode"] == "Cart", f"Cart sets the mode to Cart and closes the menu (mode {s and s['mode']}, {reasons})")
        # The ship: Daggerfall would teleport its world to the ship, which Doom cannot follow yet.
        if not self.open(3):
            self.case(False, "the transport menu opened a third time")
            return
        before = self.state()
        self.doom().click(self.row("ship"))
        box = self.top_is("DaggerfallMessageBox") and self.wait(self.df_log, r"ship boarding held", 3)
        time.sleep(1.5)
        after = self.state()
        self.case(box and after and after["pixel"] == before["pixel"] and after["mode"] == "Cart" and self.count(self.uz_log, r"ui: closed \(") == 2 and "travel:" not in read(self.df_log),
                  f"Ship shows a message and does not move the player (pixel {before['pixel']} -> {after and after['pixel']}, mode {after and after['mode']}, menu still open)")
        doom = self.doom()
        doom.click(MESSAGE_CLICK)
        self.case(self.top_is("DaggerfallTransportWindow"), "a click closes the message, back to the transport menu")
        doom.click(self.row("exit"))
        ok, reasons = self.closed(3)
        s = self.state()
        self.case(ok and s and s["mode"] == "Cart", f"Exit closes the menu and keeps the cart (mode {s and s['mode']}, {reasons})")
        self.choose(4, "foot", "Foot")

    def none(self):
        if not self.open(1):
            self.case(False, "the transport key opens Daggerfall's transport menu in Doom")
            return
        s = self.state()
        self.case(s["horse"] == s["cart"] == s["ship"] == "False" and "owns horse False cart False ship False" in read(self.df_log),
                  f"with nothing owned, the menu opens listing no horse, cart or ship (state {s})")
        doom = self.doom()
        doom.click(self.row("horse"))
        time.sleep(1.0)
        s = self.state()
        self.case(s["top"] == "DaggerfallTransportWindow" and s["mode"] == "Foot" and "ui: closed" not in read(self.uz_log), f"the greyed Horse row does nothing (state {s})")
        doom.click(self.row("exit"))
        ok, reasons = self.closed(1)
        s = self.state()
        self.case(ok and s and s["mode"] == "Foot", f"Exit closes the menu, still on foot ({reasons})")

    def summary(self):
        for line in read(self.views).splitlines():
            if "error" in line or "prepared" in line:
                print("df", line)
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:6])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT transport {self.mode}: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run-check"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "60" if mods else "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;netevent df_transport;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()),
              "| menu lines", sum("menu" in l.lower() and "daggerfall" in l.lower() for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("owned", "none"), default="owned")
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run(args.mode).go()
