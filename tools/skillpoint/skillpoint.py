"""Tests the skill point sound and message in a paired run with both real games on quiet_run's private desktop.

usage: skillpoint.py assemble | run | check
run: starts outside Privateer's Hold with DRLA. Daggerfall's -dfskillpointtest earns skill points the way play does
(uses, then Daggerfall's own skill check): round 1 raises Climbing, round 2 raises Climbing and Running in the same
check. Checks, for each round: Daggerfall's message "Your <skill> skill has improved." reached Doom's HUD (Doom's
console log), and Doom played Daggerfall's skill point sound (uz.log "ui sound 32 from Daggerfall", a real DAGGER.SND
clip), once per check. quiet_run adds -nosound, so the sound is logged here, not heard; hearing it is a play-test item.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set (no "ui sound" line), and -norun.
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\skill-point")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\runtime-dungeons")  # Data, converter, item and sprite packages.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-items" / "Release"  # Configured from this worktree (tools/skillpoint/build_native.py).
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-skillpoint" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-skillpoint" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
CLIP = 32  # SoundClips.ArenaFanfareLevelUp (DoomerfallPerks.SkillPointClip)
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


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
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Skill point sound and message. Starts outside Privateer's Hold with DRLA. A few seconds after the game starts, a test\r\n"
        "rem hook earns a Climbing point through Daggerfall's own skill check: you hear Daggerfall's fanfare and the top of the screen\r\n"
        "rem says 'Your Climbing skill has improved.' Six seconds later it earns Climbing and Running together: one fanfare, two messages.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dfskillpointtest --dfu-arg \"%HERE%play\\skillpoint.log\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800\r\n",
        newline="")


HEALED_BUTTON = (160, 75)  # The rest window's Rest Until Healed (tools/rest).
MESSAGE_CLICK = (160, 100)


class Run:
    def __init__(self, mode=None):
        self.mode = mode
        self.dir = REVIEW / (f"run-{mode}" if mode else "run")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-skillpoint.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "skillpoint.log"
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

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              *(["-dfuitest", "1", "+dd_ui_test_menu", "10" if self.mode == "rest" else "1",
                 "+screenshot_dir", str(self.dir / "shots")] if self.mode else []),
              "+logfile", "skillpoint", "+vid_fullscreen", "0", "+wipetype", "0",
              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfskillpointtest", str(self.views),
              *(["prime"] if self.mode else []), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "300" if self.mode else "180", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
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
        if self.mode:
            return self.drive_real()
        sound = r"ui sound %d from Daggerfall" % CLIP
        for n, skills in ((1, ["Climbing"]), (2, ["Climbing", "Running"])):
            if not self.wait(self.views, r"round %d: skill check ran" % n, 150 if n == 1 else 30):
                self.case(False, f"round {n}: the test never ran Daggerfall's skill check (game not ready)")
                return
            line = re.findall(r"round %d: skill check ran, ([^\n]*)" % n, read(self.views))[-1]
            values = re.findall(r"(\w+) (\d+)", line)
            half = len(values) // 2
            rose = all(int(values[i + half][1]) == int(values[i][1]) + 1 for i in range(half))
            messages = all(self.wait(self.console, r"Your %s skill has improved\." % s, 10) for s in skills)
            heard = self.wait(self.uz_log, r"(?s)(%s.*){%d}" % (re.escape(sound), n), 10)
            time.sleep(1.5)  # Nothing more may arrive for this check.
            count = len(re.findall(re.escape(sound), read(self.uz_log)))
            sent = len(re.findall(r"skill point: sound %d sent to Doom" % CLIP, read(self.df_log)))
            self.case(rose, f"round {n}: Daggerfall's skill check raised {', '.join(skills)} by one ({line})")
            self.case(messages, f"round {n}: Doom's HUD showed Daggerfall's message for each: " + ", ".join(f"'Your {s} skill has improved.'" for s in skills))
            self.case(heard and count == n and sent == n and "no such clip" not in read(self.uz_log),
                      f"round {n}: Doom played Daggerfall's skill point sound (clip {CLIP}) once for the check: {count} played, {sent} sent so far")

    def drive_real(self):
        """A real rest (Rest Until Healed) or fast travel (row 3 of the region's list, as tools/levelup) runs the check."""
        sound = r"ui sound %d from Daggerfall" % CLIP
        if not self.wait(self.views, r"primed:", 150):
            self.case(False, "the test never primed Climbing (game not ready)")
            return
        menu = 10 if self.mode == "rest" else 1
        if not self.wait(self.uz_log, r"Daggerfall opened menu %d at" % menu, 90):
            self.case(False, f"Doom never showed menu {menu}")
            return
        time.sleep(1.5)
        doom = self.doom()
        if self.mode == "rest":
            doom.click(HEALED_BUTTON)
            if not self.wait(self.df_log, r"top window is DaggerfallMessageBox", 90):
                self.case(False, "the rest never finished")
                return
            time.sleep(0.5)
            if re.search(sound, read(self.uz_log)):
                self.case(False, "the sound played before the rest-finished message was closed")
            doom.click(MESSAGE_CLICK)
        else:
            doom.click((20, 190))  # I'm At.
            doom.press(0x0D)  # Open the region.
            doom.press(0x4C)  # The location list.
            time.sleep(1.0)
            doom.double_click((100, 64 + 3 * 6))
            if self.wait(self.df_log, r"top window is DaggerfallMessageBox", 5):
                time.sleep(0.3)
                doom.press(0x59)  # Yes.
            if self.wait(self.df_log, r"top window is DaggerfallTravelPopUp", 5):
                time.sleep(0.4)
                doom.press(0x42)  # Begin.
            if not self.wait(self.df_log, r"travel: arrived at world", 90):
                self.case(False, "the fast travel never arrived")
                return
        heard = self.wait(self.uz_log, sound, 90)
        shown =self.wait(self.console, r"Your Climbing skill has improved\.", 10)
        time.sleep(2.0)
        rose = re.search(r"hud: top \d+ ms: Your Climbing skill has improved\.", read(self.df_log))
        uz = read(self.uz_log)
        count = len(re.findall(sound, uz))
        self.case(rose, f"the {self.mode}'s own skill check raised Climbing (Daggerfall's RaiseSkills message in df.log)")
        self.case(shown, "Doom's HUD showed 'Your Climbing skill has improved.'")
        self.case(heard and count == 1, f"Doom played the skill point sound once ({count})")
        at = uz.find(sound)
        if self.mode == "rest":
            # Daggerfall's rest pops to its HUD before its skill check, so the sound is sent once the rest-finished message
            # has closed; Doom gets it in the same pump as the menu's close (both lines within a few ms).
            df = read(self.df_log)
            box = df.rfind("top window is DaggerfallMessageBox")
            hud = df.find("top window is DaggerfallHUD", box)
            sent = df.find("skill point: sound", box)
            t_sound = re.search(r"([\d.]+) ui sound", uz)
            t_close = re.findall(r"([\d.]+) ui: closed", uz)
            gap = abs(float(t_sound.group(1)) - float(t_close[-1])) if t_sound and t_close else None
            self.case(heard and 0 <= box < hud < sent and gap is not None and gap < 0.1,
                      f"the sound was sent after the rest-finished message closed, and Doom played it with the menu's close ({gap} s apart)")
        else:
            placed = uz.find("travel: Daggerfall placed the player")
            reached = re.search(r"([\d.]+) travel: Doom reached pixel", read(self.df_log))
            sent = re.search(r"([\d.]+) skill point: sound", read(self.df_log))
            self.case(heard and 0 <= placed < at and reached and sent and float(sent.group(1)) >= float(reached.group(1)),
                      f"the sound was sent after Doom arrived (Doom reached pixel at {reached and reached.group(1)}, sound sent at {sent and sent.group(1)})")
            print("  uz.log from the placement to the sound:")
            for line in uz[placed:at + 60].splitlines()[:40]:
                if "heartbeat" not in line and "tic=" not in line:
                    print("   ", line[:170])

    def summary(self):
        for line in read(self.views).splitlines():
            print("df", line)
        for line in read(self.df_log).splitlines():
            if "skill point" in line or "perks:" in line or "hud:" in line and "skill" in line:
                print("df.log", line[:200])
        for line in read(self.uz_log).splitlines():
            if "ui sound" in line:
                print("uz.log", line[:200])
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL) or "skill has improved" in line:
                print("uz", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:6])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT skillpoint: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run-check"
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
              "| ui sound lines", sum("ui sound" in l for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("rest", "travel"))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run(args.mode).go()
