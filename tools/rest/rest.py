"""Tests Daggerfall's rest window opened from Doom, in a paired run with both real games on quiet_run's private desktop.

usage: rest.py assemble | run [monsters] | check
run: starts outside Privateer's Hold with DRLA. Daggerfall's -dfresttest takes the player to a quarter of their health
and earns exactly one level (without running the skill check). Doom's -dfuitest presses the rest control (netevent
df_rest, the same command the key runs). The harness clicks Rest Until Healed in Doom's window as a player would, waits
for Daggerfall's "you are healed" message, clicks it away, and expects Daggerfall's own skill check at the end of the rest
to open the level-up sheet. It spends the points (Strength up arrow) and exits, then checks: time passed, HP full in
Daggerfall and in Doom, recovery per hour three times Daggerfall's, the new level, and Doom's HUD line.
run stop: as run, but the harness presses the rest key (Z) after the first hour; Daggerfall must wake the
player as its own rest key does. It presses Z again on the wake-up message, which must close that message as a click
does, so the skill check still opens the level-up sheet.
run monsters: Doom summons monsters near the player (notarget, so they stay put) and the rest control must be refused
with Daggerfall's "enemies nearby" message, with no time passing.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, and -norun.
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\rest")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\journal")  # Data, converter and sprite package.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-items" / "Release"  # Configured from this worktree.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-items" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-items" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
# Daggerfall's 320x200 layout: the rest window's panel is centered at y 50 and Rest Until Healed (53,13 48x24) is its
# middle button; the character sheet as tools/levelup.
HEALED_BUTTON = (160, 75)
MESSAGE_CLICK = (160, 100)
EXIT_BUTTON = (69, 188)
STAT_BUTTON = (155, 16)
SPINNER_UP = (183, 9)


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
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Rest. Starts outside Privateer's Hold with DRLA. A second after the game starts, a test hook takes you to a quarter\r\n"
        "rem of your health and earns one level. Press Z to open Daggerfall's rest window, choose Rest Until Healed (HP comes\r\n"
        "rem back three times as fast as in Daggerfall), click away the message, and the level-up sheet opens. After it closes,\r\n"
        "rem Doom's HUD says 'You have reached level 2'. Press Z with monsters close by and Daggerfall refuses. Rebind the key in\r\n"
        "rem Options, Customize Controls, Doomerfall Controls.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg z --uzdoom-arg \"netevent df_rest\" --uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\" --uzdoom-arg +bind --uzdoom-arg j --uzdoom-arg \"netevent df_journal\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dfresttest --dfu-arg \"%HERE%play\\rest.log\" --dfu-arg level "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Run:
    def __init__(self, mode=None):
        self.monsters, self.stop = mode == "monsters", mode == "stop"
        self.dir = REVIEW / (f"run-{mode}" if mode else "run")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-rest.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "rest.log"
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

    def state(self):
        """The last logged state: (top, hp, maxhp, level, ready, game minutes)."""
        rows = re.findall(r"top (\S+) \| hp (\d+)/(\d+) fatigue \S+ magicka \S+ level (\d+) ready (\w+) game_minutes (\d+)", read(self.views))
        if not rows:
            return None
        t, hp, mx, lv, ready, minutes = rows[-1]
        return t, int(hp), int(mx), int(lv), ready == "True", int(minutes)

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        cache = REVIEW / "data" / "cache"
        # A monster in front of the player a second into the map (the rest control fires about 3 s in); notarget keeps it from
        # attacking, so only the 12 m distance rule can block the rest.
        extra = ["+wait 35;summon ZombieMan;notarget"] if self.monsters else []
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(cache), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", "1", "+dd_ui_test_menu", "10", "+bind", "z", "netevent df_rest", "+logfile", "rest", "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0", "+wipetype", "0",
              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}", *extra]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfresttest", str(self.views), *([] if self.monsters else ["level"]),
              "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "240", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]:
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

    def doom(self):
        # tools/levelup's window driver; that script runs its command line on import, so only its definitions are loaded.
        path = REPO / "tools" / "levelup" / "levelup.py"
        ns = {"__file__": str(path), "__name__": "levelup_driver"}
        exec(compile(read(path).split("\nap = argparse.ArgumentParser()")[0], str(path), "exec"), ns)
        doom = ns["Doom"](self.launcher)
        size = re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        doom.surface = (int(size[-1][0]), int(size[-1][1]))
        return doom

    def drive(self):
        if not self.wait(self.views, r"prepared:", 120):
            self.case(False, "the test never prepared the player (game not ready)")
            return
        print("  ", [l for l in read(self.views).splitlines() if "prepared" in l or "earned" in l])
        opened = self.wait(self.uz_log, r"Daggerfall opened menu 10 at", 60)
        rest_line = re.findall(r"rest: \d+ hostile monsters near[^\n]*", read(self.uz_log))
        print("  doom:", rest_line)
        if self.monsters:
            refused = self.wait(self.views, r"top DaggerfallMessageBox", 5)
            time.sleep(1.0)
            s = self.state()
            self.case(opened and refused and rest_line and " 0 hostile" not in rest_line[-1] and "monsters near True" in read(self.df_log),
                      f"with monsters near, the rest control shows Daggerfall's message box instead of the rest window ({rest_line[-1:] if rest_line else None})")
            before = s[5] if s else None
            doom = self.doom()
            doom.click(MESSAGE_CLICK)
            closed = self.wait(self.uz_log, r"ui: closed", 6)
            time.sleep(1.0)
            # Daggerfall's clock at the menu's open and close (after it closes, normal play moves the clock on again).
            ends = re.findall(r"rest: menu (?:opening|closed): [^\n]* game_minutes (\d+)", read(self.df_log))
            self.case(closed and len(ends) == 2 and ends[0] == ends[1] and "DaggerfallRestWindow" not in read(self.views),
                      f"the message closes back to Doom, no rest window opened and no time passed (game minutes at open, close: {ends})")
            return

        shown = self.wait(self.views, r"top DaggerfallRestWindow", 5)
        start = self.state()
        self.case(opened and shown and rest_line and "on the ground 1" in rest_line[-1],
                  f"the rest control opens Daggerfall's rest window in Doom (state {start})")
        if not (opened and shown):
            return
        prepared = re.search(r"prepared: hp (\d+)/(\d+), recovery per hour (\d+) \(scale (\d+)\)", read(self.views))
        doom = self.doom()
        doom.click(HEALED_BUTTON)
        if self.stop:
            # Doom's rest key mid-rest, after the first hour: Daggerfall's end of rest (wake-up message, then the skill check).
            self.wait(self.views, r"top DaggerfallRestWindow \| hp (?!%d/)\d+/" % start[1], 30)
            doom.press(0x5A)
            woke = self.wait(self.views, r"top DaggerfallMessageBox", 5) and self.wait(self.df_log, r"rest: Doom's rest key handled by the rest window", 2)
            time.sleep(0.5)
            s = self.state()
            self.case(woke and s and start[1] < s[1] < s[2] and "ui: closed" not in read(self.uz_log).split("opened menu 10", 1)[-1],
                      f"the rest key mid-rest woke the player with Daggerfall's message, menu still open ({start[1]} -> {s and s[1]}/{s and s[2]})")
        healed = self.stop or self.wait(self.views, r"top DaggerfallMessageBox \| hp (\d+)/\1 ", 90)
        time.sleep(0.5)
        s = self.state()
        hours = (s[5] - start[5]) / 60 if s else 0
        gained = s[1] - start[1] if s else 0
        self.case(healed and s and (self.stop or s[1] == s[2]) and hours >= 1,
                  f"Rest Until Healed passed {hours:.0f} game hours and healed {start[1]} -> {s and s[1]}/{s and s[2]} in Daggerfall")
        scale = int(prepared.group(4)) if prepared else 0
        per_hour = int(prepared.group(3)) if prepared else 0
        hps = [int(v) for v in re.findall(r"\| hp (\d+)/", read(self.views).split("top DaggerfallRestWindow", 1)[-1])]
        steps = [b - a for a, b in zip(hps, hps[1:]) if b > a]
        self.case(scale == 3 and steps and max(steps) == per_hour,
                  f"HP per hour of rest is 3x Daggerfall's: {per_hour} = 3 x {per_hour // 3} (scale {scale}); steps seen {sorted(set(steps))}, {gained} HP in {hours:.0f} h")
        if self.stop:
            # The rest key again on the wake-up message: it must close the message as a click does, so the skill check runs.
            doom.press(0x5A)
        else:
            doom.click(MESSAGE_CLICK)
        sheet = self.wait(self.views, r"top DaggerfallCharacterSheetWindow \| [^\n]* level %d ready False" % (start[3] + 1), 10)
        sent = self.wait(self.df_log, r"rest: level up, sent the HUD line for level %d" % (start[3] + 1), 3)
        self.case(sheet and sent, f"the rest's own skill check opened the level-up sheet (level {start[3]} -> {start[3] + 1}) and sent the HUD line")
        if not sheet:
            return
        time.sleep(1.0)
        doom.click(STAT_BUTTON)
        for _ in range(6):  # The bonus pool is 4 to 6; extra clicks do nothing.
            doom.click(SPINNER_UP)
        doom.click(EXIT_BUTTON)
        closed = self.wait(self.uz_log, r"ui: closed", 8)
        line = self.wait(self.console, r"You have reached level %d" % (start[3] + 1), 5)
        self.case(closed and line, f"after the sheet closes, Doom's HUD shows 'You have reached level {start[3] + 1}'")
        time.sleep(3.0)
        hp = re.findall(r"hp: shown=(\d+) confirmed=(\d+)/(\d+)", read(self.uz_log))
        s = self.state()
        self.case(hp and s and int(hp[-1][0]) == s[1] and (self.stop or s[1] == s[2]) and int(hp[-1][2]) == s[2],
                  f"Doom's HP follows: last Doom hp line {hp[-1] if hp else None}, Daggerfall {s and s[1]}/{s and s[2]}")

    def summary(self):
        for line in read(self.views).splitlines():
            if "error" in line or "prepared" in line or "earned" in line:
                print("df", line)
        for line in read(self.df_log).splitlines():
            if "rest:" in line:
                print("df.log", line[:200])
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL) or "reached level" in line:
                print("uz", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:6])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT rest{' monsters' if self.monsters else ' stop' if self.stop else ''}: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "60" if mods else "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 105;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("monsters", "stop"))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run(args.mode).go()
