"""Tests travel from Daggerfall's logbook in a paired run, with both real games on quiet_run's private desktop.

usage: sheettravel.py assemble | run [journal] | check
run: starts outside Privateer's Hold with DRLA. Daggerfall's -dfleveluptest earns a level, so Daggerfall opens its
level-up character sheet by itself (Doom menu 7), and -dfjournaltest adds two quests. The harness clicks as a player:
Logbook, the first quest, Yes. With bonus points unspent the sheet stays (Daggerfall's own message). Then it spends the
points, goes Logbook > quest > Yes again, and checks the menu closes, Doom's fast travel opens on the quest's place,
and a trip from it (Yes, Begin) arrives with both engines at the same map pixel.
run journal: the same trip from the journal Doom's J command opens (menu 9), with no level-up.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, and -norun.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\sheettravel")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\skillbasics")  # Data, converter and sprite package.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-shoplvl" / "Release"  # Configured from this worktree.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-shoplvl" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-shoplvl" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
PACKS = ["dfitems.pk3", "doomerfall.pk3", "doomerfall-drla.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
TEST_MARK = 0x8000
SHEET, JOURNAL = "DaggerfallCharacterSheetWindow", "DaggerfallQuestJournalWindow"
# Daggerfall's 320x200 native layout (DaggerfallCharacterSheetWindow.Setup, StatsRollout, DaggerfallQuestJournalWindow).
LOGBOOK, MESSAGE_CLICK, FIRST_QUEST = (35, 171), (160, 100), (100, 44)
VK_Y, VK_B = 0x59, 0x42


def stat_button(i):
    return (155, 16 + 24 * i)


def spinner_up(i):
    return (183, 9 + 24 * i)


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
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    packs = " ".join(f'--mod "%HERE%{n}"' for n in PACKS)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Travel from the logbook. Starts outside Privateer's Hold with DRLA. A few seconds in, test hooks add two quests\r\n"
        "rem and earn a level, so Daggerfall's level-up character sheet opens inside Doom.\r\n"
        "rem Click Logbook, click the first quest and answer Yes: with bonus points left, Daggerfall asks you to spend them.\r\n"
        "rem Spend them (click a stat, then its small up arrow), then Logbook, the quest, Yes again: the menu closes and fast\r\n"
        "rem travel opens on the quest's place. Yes, then Begin, travels; Doom arrives at the same place.\r\n"
        "rem Later, J opens the journal and P the character sheet; the same click travels the same way. Indoors, it says you cannot.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\" --uzdoom-arg +bind --uzdoom-arg j --uzdoom-arg \"netevent df_journal\" --uzdoom-arg +bind --uzdoom-arg p --uzdoom-arg \"netevent df_character\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} {packs} "
        "--uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dfjournaltest --dfu-arg \"%HERE%play\\journal.log\" "
        "--dfu-arg -dfleveluptest --dfu-arg \"%HERE%play\\levelup.log\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Doom:
    """Posts window messages to this run's Doom window, on whichever desktop quiet_run put it (as tools/journal)."""

    def __init__(self, launcher_log, surface):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        # Doom is DPI aware; a DPI-unaware sender would have its posted mouse coordinates rescaled.
        self.user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.user.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self.user.OpenDesktopW.restype = wt.HANDLE
        self.user.OpenDesktopW.argtypes = (wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD)
        self.user.EnumDesktopWindows.argtypes = (wt.HANDLE, ctypes.c_void_p, wt.LPARAM)
        self.user.EnumDesktopsW.argtypes = (wt.HANDLE, ctypes.c_void_p, wt.LPARAM)
        self.user.GetProcessWindowStation.restype = wt.HANDLE
        self.user.CloseDesktop.argtypes = (wt.HANDLE,)
        self.user.SetThreadDesktop.argtypes = (wt.HANDLE,)
        self.surface = surface
        pids = {int(m) for m in re.findall(r"started UZDoom pid (\d+)", read(launcher_log))}
        names, found = [], []
        desk_proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.LPWSTR, wt.LPARAM)
        win_proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        keep = [desk_proc(lambda name, _: names.append(name) or True)]
        self.user.EnumDesktopsW(self.user.GetProcessWindowStation(), keep[0], 0)

        def visit(hwnd, _):
            pid = wt.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and not self.user.GetWindow(hwnd, 4) and self.user.GetWindowTextLengthW(hwnd) > 0:
                found.append(hwnd)
            return True

        callback = win_proc(visit)
        for name in names:
            desk = self.user.OpenDesktopW(name, 0, False, 0x01FF)
            if not desk:
                continue
            before = len(found)
            self.user.EnumDesktopWindows(desk, callback, 0)
            if len(found) > before:
                self.user.SetThreadDesktop(desk)
                del found[:before]
                break
            self.user.CloseDesktop(desk)
        if not found:
            raise RuntimeError(f"could not find this run's Doom window (pids {pids}, desktops {names})")
        info = []
        for h in found:
            buf = ctypes.create_unicode_buffer(128)
            self.user.GetClassNameW(h, buf, 128)
            info.append((h, buf.value))
        self.hwnd = next((h for h, c in info if "doom" in c.lower()), None) or next((h for h, c in info if not c.startswith(("NV", "IME", "MSCTF", "Default IME"))), found[0])

    def point(self, x, y):
        width, height = self.surface
        scale = min(width / 320, height / 200)
        return int((height - 200 * scale) / 2 + y * scale) << 16 | int((width - 320 * scale) / 2 + x * scale)

    def press(self, vk):
        scan = self.user.MapVirtualKeyW(vk, 0)
        self.user.PostMessageW(self.hwnd, 0x100, vk, 1 | (scan << 16))
        time.sleep(0.12)
        self.user.PostMessageW(self.hwnd, 0x101, vk, 1 | (scan << 16) | (3 << 30))
        time.sleep(0.6)

    def click(self, xy):
        lp = self.point(*xy)
        self.user.PostMessageW(self.hwnd, 0x200, TEST_MARK, lp)
        time.sleep(0.4)
        self.user.PostMessageW(self.hwnd, 0x200, TEST_MARK, lp)  # A second move, so the hover is settled before the press.
        time.sleep(0.4)
        self.user.PostMessageW(self.hwnd, 0x201, 1 | TEST_MARK, lp)
        time.sleep(0.25)
        self.user.PostMessageW(self.hwnd, 0x202, TEST_MARK, lp)
        time.sleep(0.8)


class Run:
    def __init__(self, mode=None):
        self.journal_only = mode == "journal"
        self.dir = REVIEW / (f"run-{mode}" if mode else "run")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-sheettravel.txt"
        self.launcher, self.levels, self.views = self.dir / "launcher.log", self.dir / "levelup.log", self.dir / "journal.log"
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

    def wait_more(self, path, pattern, before, seconds):
        """Waits until pattern appears more than before times."""
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if self.count(path, pattern) > before:
                return True
            time.sleep(0.2)
        return False

    def top(self):
        """The top window in the journal test's last line."""
        lines = [l for l in read(self.views).splitlines() if " top " in l]
        return lines[-1].split(" top ", 1)[1].split(" | ")[0] if lines else ""

    def sheet(self):
        """(leveling, pool, level, stats) from the level-up test's last line, or None when the sheet is not on top."""
        lines = [l for l in read(self.levels).splitlines() if " top " in l]
        m = re.search(rf"top {SHEET} view leveling (\w+) pool (-?\d+)(?: working [\d,]+)? \| level (\d+) stats ([\d,]+)", lines[-1]) if lines else None
        return (m.group(1) == "True", int(m.group(2)), int(m.group(3)), [int(v) for v in m.group(4).split(",")]) if m else None

    def doom(self):
        # Doom reads posted mouse positions as pixels of its screen, which Daggerfall's window is resized to and which can
        # be smaller than the client area on the private desktop (320x200 in a 640x400 client on 2026-11-27).
        size = re.findall(r"surface (\d+)x(\d+) for a", read(self.df_log)) or re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        print("  posting in Doom's", size[-1])
        return Doom(self.launcher, (int(size[-1][0]), int(size[-1][1])))

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views, self.levels):
            path.unlink(missing_ok=True)
        cache = REVIEW / "data" / "cache"
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(cache), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              # -dfuitest also makes Doom ignore the real cursor; with 0 it opens no menu, with 1 the journal (menu 9) once.
              "-dfuitest", "1" if self.journal_only else "0", "+dd_ui_test_menu", "9", "+logfile", "log-sheettravel", "+screenshot_dir", str(self.dir / "shots"),
              "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfjournaltest", str(self.views),
              *([] if self.journal_only else ["-dfleveluptest", str(self.levels)]), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "240", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / n for n in PACKS]:
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

    def find_quest(self, doom):
        """Clicks the journal's first quest and answers Yes to Daggerfall's 'find this place' box."""
        if not self.wait(self.views, r"seeded", 30):
            self.case(False, "the journal test never added its quests")
            return False
        doom.click(FIRST_QUEST)
        asked = "DaggerfallMessageBox" in self.top()
        doom.press(VK_Y)
        return asked

    def drive(self):
        if self.journal_only:
            menu = 9
            if not self.wait(self.uz_log, r"Daggerfall opened menu 9 at", 90) or not self.wait(self.views, rf"top {JOURNAL} ", 5):
                self.case(False, "Doom's J command never showed the journal")
                return
            time.sleep(1.0)
            doom = self.doom()
            if "mode ActiveQuests page 0 of 0" in read(self.views).splitlines()[-1]:
                self.case(False, "the journal opened before the test's quests were added")
                return
        else:
            menu = 7
            opened = self.wait(self.uz_log, r"Daggerfall opened menu 7 at", 90) and self.wait(self.levels, rf"top {SHEET} view leveling True", 5)
            time.sleep(1.0)
            state = self.sheet()
            self.case(opened and state and state[0] and state[1] > 0, f"Daggerfall opened its level-up sheet by itself and Doom showed it ({state})")
            if not state:
                return
            start_stats, pool = state[3], state[1]
            doom = self.doom()

            # Logbook > quest > Yes with points unspent: Daggerfall's message, and the menu stays.
            doom.click(LOGBOOK)
            journal = self.wait(self.views, rf"top {JOURNAL} ", 3)
            asked = self.find_quest(doom)
            waited = self.wait(self.df_log, r"travel from the journal waits", 3)
            message = self.wait(self.levels, r"top DaggerfallMessageBox [^\n]*\n?$", 3)
            doom.click(MESSAGE_CLICK)
            self.wait(self.levels, rf"top {SHEET} [^\n]*\n?$", 3)
            back = self.sheet()
            self.case(journal and asked and waited and message and back and back[0] and back[1] == pool and "menu 7 closed" not in read(self.df_log),
                      f"with {pool} points unspent, the journal's travel shows Daggerfall's message and keeps the sheet (sheet {back})")

            # Spend the points, then Logbook > quest > Yes again.
            stat = min(range(8), key=lambda i: start_stats[i])
            doom.click(stat_button(stat))
            for _ in range(pool):
                doom.click(spinner_up(stat))
            spent = self.sheet()
            self.case(spent and spent[1] == 0, f"spent the {pool} points on stat {stat} ({spent})")
            doom.click(LOGBOOK)
            if not self.wait(self.views, rf"top {JOURNAL} ", 3):
                self.case(False, "Logbook did not open the journal the second time")
                return
            self.expect = (stat, start_stats[stat] + pool, state[2])

        before_pixel = re.findall(r"ui: world before: pixel (\d+),(\d+)", read(self.df_log))[-1]
        opens = self.count(self.uz_log, r"Daggerfall opened menu 1 at")
        asked = self.find_quest(doom)
        closed = self.wait(self.df_log, rf"ui: menu {menu} closed, reason 3", 5)
        doom_asked = self.wait(self.uz_log, r"Daggerfall asked for fast travel to a place found in its journal", 5)
        travel_open = self.wait_more(self.uz_log, r"Daggerfall opened menu 1 at", opens, 8)
        on_place = self.wait(self.df_log, r"ui: fast travel opened on the journal's place", 3)
        finding = self.wait(self.views, r"top DaggerfallTravelMapWindow view region \d+ finding True", 5)
        self.case(asked and closed and doom_asked and travel_open and on_place and finding,
                  f"Yes closed menu {menu}, Doom asked for and opened fast travel (menu 1), and the travel map finds the quest's place")
        if not self.journal_only:
            levels = [l for l in read(self.levels).splitlines() if " top " in l]
            m = re.search(r"\| level (\d+) stats ([\d,]+)", levels[-1])
            stat, value, level = self.expect
            stats = [int(v) for v in m.group(2).split(",")]
            self.case(int(m.group(1)) == level and stats[stat] == value, f"the level-up was kept: level {m.group(1)}, stat {stat} = {stats[stat]} (expected {value})")
        if not travel_open:
            return

        # Daggerfall asks to travel to the found place when its animation ends; Yes, then Begin.
        doom = self.doom()
        if self.wait(self.views, r"top DaggerfallMessageBox [^\n]*\n?$", 8):
            time.sleep(0.3)
            doom.press(VK_Y)
        if self.wait(self.df_log, r"top window is DaggerfallTravelPopUp", 5):
            time.sleep(0.4)
            doom.press(VK_B)
        arrived = self.wait(self.df_log, r"travel: arrived at world", 90)
        placed = self.wait(self.uz_log, r"travel: Daggerfall placed the player .* loading", 10)
        reached = self.wait(self.df_log, r"travel: Doom reached pixel", 90)
        time.sleep(3.0)
        df = re.search(r"travel: arrived at world \S+ pixel (\d+),(\d+)", read(self.df_log))
        dr = re.search(r"travel: Doom reached pixel (\d+),(\d+)", read(self.df_log))
        moved = df and tuple(df.groups()) != tuple(before_pixel)
        same = df and dr and df.groups() == dr.groups()
        no_error = "error: Doom did not arrive" not in read(self.df_log)
        self.case(arrived and placed and reached and moved and same and no_error,
                  f"the trip arrived with both engines at one map pixel (from {before_pixel}: Daggerfall {df and df.groups()}, Doom {dr and dr.groups()})")

    def summary(self):
        for line in read(self.df_log).splitlines():
            if "journal" in line or "travel" in line or "ui: menu" in line or "error" in line:
                print("df", line[:200])
        for line in read(self.uz_log).splitlines():
            if "fast travel" in line or "travel:" in line or "ui: closed" in line or "opened menu" in line:
                print("uz", line[:200])
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL):
                print("console", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:6])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT sheettravel: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;netevent df_journal;netevent df_fast_travel;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("journal",))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run(args.mode).go()
