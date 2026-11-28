"""Tests the debug find-NPC tool (dd_findnpc) in a paired run with both real games on quiet_run's private desktop.

usage: findnpc.py assemble | run | check
assemble: the review folder (D:\\dev\\DoomDaggerfall-loop\\review\\find-npc) from this lane's builds, with play.bat.
run: in the town by Privateer's Hold. Daggerfall's -dffindtest starts two real quests, leaves one quest person in another
     town and points another's place at a building of this town. The harness opens the find menu (as N does); it opens
     with the active quests' NPCs listed, and the driver:
     (c) types the far quest person's surname with two letters swapped (a typo): Doom must show where in text;
     (a) picks the local quest person from the opening list without typing (arrow keys, Enter), outdoors: the marker
         must point at that building's door (checked against the town map's door list) and follow the player turning;
     then the harness walks into building door 0 (the marker must clear on the area change), and
     (b) types one word of a resident's name there: the marker must point at that NPC's own actor.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, running dd_findnpc there, and -norun.
"""
import argparse
import math
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "status_key"))
argv, sys.argv = sys.argv, [sys.argv[0], "check"]
sk_source = (REPO / "tools" / "status_key" / "statuskey.py").read_text()
sk = {"__file__": str(REPO / "tools" / "status_key" / "statuskey.py"), "__name__": "statuskey_defs"}
exec(compile(sk_source.split("\nap = argparse.ArgumentParser()")[0], "statuskey.py", "exec"), sk)  # its helpers only
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\find-npc")
LANE = REPO.parent / "DoomDaggerfall-build"
UZ_BUILD = LANE / "uzdoom" / "Release"
BRIDGE_DLL = LANE / "bridge" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = LANE / "launcher" / "Release" / "doomerfall-launcher.exe"
SHARED = Path(r"D:\dev\DoomDaggerfall-build")  # this lane's builds there are named <part>-quiet
if (SHARED / "uzdoom-quiet").exists():
    UZ_BUILD = SHARED / "uzdoom-quiet" / "Release"
    BRIDGE_DLL = SHARED / "bridge-quiet" / "Release" / "doomerfall_bridge.dll"
    LAUNCHER = SHARED / "launcher-quiet" / "Release" / "doomerfall-launcher.exe"
QUIET, GAME, MODS, DRLA, DATA, GROUP = sk["QUIET"], sk["GAME"], sk["MODS"], sk["DRLA"], sk["DATA"], sk["GROUP"]
FATAL = sk["FATAL"]
read, lumps = sk["read"], sk["lumps"]
VK_N, VK_O, VK_ENTER, VK_ESC, VK_DOWN = 0x4E, 0x4F, 0x0D, 0x1B, 0x28
BINDS = ["+bind", "n", "dd_findnpc", "+bind", "o", "netevent fn_go", "+dd_dev", "1"]
DRAW = re.compile(r"findnpc: draw (on|edge) screen (-?\d+) (-?\d+) target (\S+) (\S+) (\S+) player (\S+) (\S+) yaw (\S+) distance (\d+) actor (\d) centre (\d+)")


def doors():
    rows = [l.split() for l in lumps(REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines()]
    return [r for r in rows if len(r) >= 8]


def assemble():
    sk["REVIEW"] = REVIEW
    sk["UZ_BUILD"], sk["BRIDGE_DLL"], sk["LAUNCHER"] = UZ_BUILD, BRIDGE_DLL, LAUNCHER
    sk["write_demo"] = write_demo
    sk["assemble"]()


def write_demo():
    sk["REVIEW"] = REVIEW
    sk["write_demo"].__globals__["REVIEW"] = REVIEW
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Find an NPC by name (a debug aid, dev mode only). Starts in the town outside Privateer's Hold with DRLA, dev mode on.\r\n"
        "rem Press N (or type dd_findnpc in the console). The box lists the NPCs your active quests name: arrows + Enter (or click) to pick.\r\n"
        "rem Or type any part of a name (any word, small typos are fine) to filter it, closest first, then everyone; Enter picks.\r\n"
        "rem A gold chevron then points at their building's door when you are outside, or at the NPC when you are in the same\r\n"
        "rem building; at the screen edge when off screen, with the name and distance. Someone in another place is shown as text.\r\n"
        "rem It clears when you change area (go through a door, travel, load) or search again. dd_findnpc <name> searches directly.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg n --uzdoom-arg dd_findnpc --uzdoom-arg +bind --uzdoom-arg q --uzdoom-arg \"netevent df_info\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +dd_dev --uzdoom-arg 1 "
        "--uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Run:
    def __init__(self):
        self.dir = REVIEW / "run"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-findnpc.txt"
        self.launcher, self.test = self.dir / "launcher.log", self.dir / "findtest.log"
        self.results, self.proc = [], None

    def case(self, ok, what):
        self.results.append((bool(ok), what))
        print("CASE", "pass" if ok else "FAIL", what)

    def wait(self, path, pattern, seconds, start=0):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            m = re.search(pattern, read(path)[start:])
            if m:
                return m
            if any(k in read(self.console) for k in FATAL):
                return None
            time.sleep(0.2)
        return None

    def harness(self):
        door = next(r for r in doors() if r[0] == "0")
        path = self.dir / "harness.pk3"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])))
            z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "FNHarness" }\n')
        return path

    def find(self, text, n):
        """Types into the find menu (the harness opens it as N would) and presses Enter: one match is picked at once,
        several focus the list, where a second Enter picks the first (closest) row."""
        if not self.wait(self.console, r"FNMENU %d" % n, 90):
            raise RuntimeError(f"find menu {n} did not open")
        mark = len(read(self.uz_log))
        doom = sk["doom_driver"](self.launcher, self.uz_log)
        time.sleep(1.0)
        doom.type(text)
        time.sleep(0.8)
        doom.tap(VK_ENTER)
        if not self.wait(self.uz_log, r"findnpc: (marker on|elsewhere)", 2, mark):
            doom.tap(VK_ENTER)
        return mark

    def pick(self, name, n):
        """Picks a name from the list the find menu opens with, without typing: Down to its row, Enter."""
        df_mark = len(read(self.df_log))
        if not self.wait(self.console, r"FNMENU %d" % n, 90):
            raise RuntimeError(f"find menu {n} did not open")
        mark = len(read(self.uz_log))
        listed = self.wait(self.df_log, r'findnpc: request \d+ "" \(list\): (\d+) matches', 10, df_mark)
        rows = re.findall(r"findnpc: match (\d+) target \d+ id \S+ at \S+ \S+: (.*)", read(self.df_log)[df_mark:])
        labels = [label.strip() for _, label in rows]
        self.case(listed and any(l.startswith(name) for l in labels), f"the box opens with the active quests' NPCs: {labels}")
        index = next((i for i, l in enumerate(labels) if l.startswith(name)), None)
        if index is None:
            return mark
        doom = sk["doom_driver"](self.launcher, self.uz_log)
        time.sleep(1.0)
        for _ in range(index):
            doom.tap(VK_DOWN)
            time.sleep(0.15)
        doom.tap(VK_ENTER)
        return mark

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.test):
            path.unlink(missing_ok=True)
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              *BINDS, "+logfile", "findnpc", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
              "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dffindtest", str(self.test), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "300", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", self.harness()]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.drive()
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            self.case(False, f"driver error: {e!r}")
        finally:
            if self.proc.poll() is None:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.proc.wait()
        self.summary()

    def drive(self):
        quest = self.wait(self.test, r"FT quest (.+?)\|(\d+)\|(.*)", 180)
        far = self.wait(self.test, r"FT far (.+?)\|(.*)", 5)
        ok = self.wait(self.console, r"FNSTAGE 0 outdoors", 30)
        self.case(quest and far and ok, f"setup: quests started, far {far and far.groups()}, local {quest and quest.groups()}")
        if not (quest and far and ok):
            return
        time.sleep(2.0)
        # (c) another town: text only, typed with a typo.
        name = far.group(1)
        word = name.split()[-1].lower()
        typo = word[:2] + word[3] + word[2] + word[4:]
        mark = self.find(typo, 1)
        m = self.wait(self.uz_log, r"findnpc: elsewhere: (.*)", 8, mark)
        self.case(m and name in m.group(1) and far.group(2) in m.group(1), f"(c) far quest NPC, typed \"{typo}\", shown as text: {m and m.group(1)}")
        # (a) quest NPC in a town building, outdoors, picked from the opening list.
        name = quest.group(1)
        mark = self.pick(name, 2)
        m = self.wait(self.uz_log, r"findnpc: marker on (.*), target kind (\d+) id \S+ point (\S+) (\S+)", 8, mark)
        self.case(m and name in m.group(1) and m.group(2) == "3", f"(a) quest NPC outdoors, picked from the list, points at their building: {m and m.groups()}")
        door = re.search(r"findnpc: building %s block .* (door|origin)" % quest.group(2), read(self.df_log))
        self.case(door and door.group(1) == "door", f"(a) Daggerfall placed the building's door from map data: {door and door.group(0)}")
        time.sleep(9.0)  # the harness turns the player through a full circle
        draws = [DRAW.search(l) for l in read(self.uz_log)[mark:].splitlines()]
        draws = [d for d in draws if d]
        if draws:
            tx, ty = float(draws[0].group(4)), float(draws[0].group(5))
            near = min(math.hypot(float(r[3]) - tx, float(r[4]) - ty) for r in doors() if r[0] == "0")
            self.case(near <= 48, f"(a) the marker's target {tx:.0f},{ty:.0f} is a door of the town map (nearest door {near:.0f} units)")
            self.check_follow(draws, "(a)")
        else:
            self.case(False, "(a) the marker was drawn")
        # Into building door 0: the marker clears.
        mark = len(read(self.uz_log))
        m = self.wait(self.uz_log, r"findnpc: marker cleared \((.*)\)", 90, mark)
        self.case(m, f"area change clears the marker: {m and m.group(1)}")
        if self.wait(self.uz_log, r"Daggerfall opened menu 7 at", 30, mark):
            time.sleep(1.0)
            sk["doom_driver"](self.launcher, self.uz_log).tap(VK_ESC)
        ready = self.wait(self.console, r"FNREADY indoors", 60)
        residents = re.findall(r"FT resident (.+?)\|", read(self.test))
        self.case(ready and residents, f"inside the building, residents present: {residents}")
        if not (ready and residents):
            return
        # (b) a resident while inside their building.
        name = residents[0]
        mark = self.find(name.split()[-1].lower(), 3)  # one word of the name
        m = self.wait(self.uz_log, r"findnpc: marker on (.*), target kind (\d+) id (\S+)", 8, mark)
        self.case(m and name in m.group(1) and m.group(2) in ("2", "4") and "here" in m.group(1), f"(b) resident inside points at the NPC: {m and m.groups()}")
        time.sleep(9.0)
        draws = [d for d in (DRAW.search(l) for l in read(self.uz_log)[mark:].splitlines()) if d]
        self.case(draws and all(d.group(11) == "1" for d in draws), f"(b) the marker follows the NPC's own actor ({len(draws)} draw lines)")
        if draws:
            self.check_follow(draws, "(b)")

    def check_follow(self, draws, tag):
        """The chevron moves as the player turns, and is on the side of the screen the target is on."""
        xs = {int(d.group(2)) for d in draws}
        states = {d.group(1) for d in draws}
        wrong = 0
        for d in draws:
            if d.group(1) != "on":
                continue
            bearing = math.degrees(math.atan2(float(d.group(5)) - float(d.group(8)), float(d.group(4)) - float(d.group(7))))
            rel = (bearing - float(d.group(9)) + 540) % 360 - 180  # positive: to the left
            centre = int(d.group(12))  # the view's centre that frame
            if abs(rel) > 8 and (rel > 0) != (int(d.group(2)) < centre):
                wrong += 1
        self.case(len(xs) >= 4 and states == {"on", "edge"} and wrong == 0,
                  f"{tag} the chevron follows the turning player: {len(draws)} positions, states {sorted(states)}, wrong side {wrong}")

    def summary(self):
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        print("df findnpc:", [l[:160] for l in read(self.df_log).splitlines() if "findnpc:" in l][:12])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run-check"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        files = [*mods, str(REVIEW / "doomerfall.pk3")] + ([str(REVIEW / "doomerfall-drla.pk3")] if mods else [])
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *files, "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;dd_findnpc foo;dd_dev 1;dd_findnpc foo;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lines = read(log).splitlines()
        print(label, "exit", code, "| lines", len(lines), "| E1M1", any("E1M1" in l for l in lines), "| needs dd_dev", sum("needs dd_dev" in l for l in lines),
              "| script errors", sum("Script error" in l for l in lines), "| fatal", sum(any(k in l for k in FATAL) for l in lines))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
args = ap.parse_args()
{"assemble": assemble, "check": check, "run": lambda: Run().go()}[args.command]()
