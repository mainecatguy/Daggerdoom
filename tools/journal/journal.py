"""Tests Daggerfall's quest journal in a paired run, with both real games on quiet_run's private desktop.

usage: journal.py assemble | run | check
run: starts outside Privateer's Hold with DRLA. Daggerfall's -dfjournaltest starts two real quests and adds notebook,
finished quest and message entries, then logs the journal's tab and page each time they change. Doom's -dfuitest
opens the journal through the real command its J key is bound to ("netevent df_journal"), and the harness posts
keys and clicks to Doom's window: tabs, paging, closing with J, with the journal's Exit button and with Escape, and
a quest's place found on the travel map, which stays inside the journal's menu.
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\journal")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\mapkeys")  # Data, converter and sprite package.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-dungeon-flats" / "Release"  # Configured from this worktree.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-journal" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-journal" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
TEST_MARK = 0x8000
VK = {"J": 0x4A, "N": 0x4E, "Y": 0x59, "ESC": 0x1B, "UP": 0x26, "DOWN": 0x28}
JOURNAL = "DaggerfallQuestJournalWindow"
# Journal buttons in Daggerfall's 320x200 native layout (DaggerfallQuestJournalWindow.Setup).
TAB_BUTTON, DOWN_ARROW, UP_ARROW, EXIT_BUTTON, FIRST_LINE = (66, 192), (215, 191), (187, 191), (293, 191), (100, 44)


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
        "rem Quest journal. Starts outside Privateer's Hold with DRLA; two test quests and some notes are added a few seconds in.\r\n"
        "rem J opens Daggerfall's quest journal (J again, Escape or its Exit button closes it). N or the bottom-left button\r\n"
        "rem changes tab (active quests, finished quests, notebook, messages); the arrows or Up/Down page.\r\n"
        "rem Click an active quest to find its place on the travel map. Rebind J in Options, Customize Controls, Doomerfall Controls.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\" --uzdoom-arg +bind --uzdoom-arg j --uzdoom-arg \"netevent df_journal\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dfjournaltest --dfu-arg \"%HERE%play\\journal.log\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Doom:
    """Posts window messages to this run's Doom window, on whichever desktop quiet_run put it (as tools/map_keys)."""

    def __init__(self, launcher_log):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self.user.OpenDesktopW.restype = wt.HANDLE
        self.user.OpenDesktopW.argtypes = (wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD)
        self.user.EnumDesktopWindows.argtypes = (wt.HANDLE, ctypes.c_void_p, wt.LPARAM)
        self.user.EnumDesktopsW.argtypes = (wt.HANDLE, ctypes.c_void_p, wt.LPARAM)
        self.user.GetProcessWindowStation.restype = wt.HANDLE
        self.user.CloseDesktop.argtypes = (wt.HANDLE,)
        self.user.SetThreadDesktop.argtypes = (wt.HANDLE,)
        self.surface = (320, 200)
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
                if not self.user.SetThreadDesktop(desk):
                    print("  SetThreadDesktop failed, error", ctypes.get_last_error())
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

    def press(self, key):
        vk = VK[key]
        scan = self.user.MapVirtualKeyW(vk, 0)
        self.user.PostMessageW(self.hwnd, 0x100, vk, 1 | (scan << 16))
        time.sleep(0.12)
        self.user.PostMessageW(self.hwnd, 0x101, vk, 1 | (scan << 16) | (3 << 30))
        time.sleep(0.6)

    def point(self, x, y):
        width, height = self.surface
        scale = min(width / 320, height / 200)
        return int((height - 200 * scale) / 2 + y * scale) << 16 | int((width - 320 * scale) / 2 + x * scale)

    def click(self, xy):
        lp = self.point(*xy)
        self.user.PostMessageW(self.hwnd, 0x200, TEST_MARK, lp)
        time.sleep(0.2)
        self.user.PostMessageW(self.hwnd, 0x201, 1 | TEST_MARK, lp)
        time.sleep(0.08)
        self.user.PostMessageW(self.hwnd, 0x202, TEST_MARK, lp)
        time.sleep(0.6)


class Run:
    def __init__(self):
        self.dir = REVIEW / "run"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-journal.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "journal.log"
        self.results = []
        self.proc = None

    def case(self, ok, what):
        self.results.append((bool(ok), what))
        print("CASE", "pass" if ok else "FAIL", what)

    def view(self):
        """The last logged state line, without its time."""
        lines = [l for l in read(self.views).splitlines() if " top " in l]
        return lines[-1].split(" ", 1)[1] if lines else ""

    def journal(self):
        """(mode, page, count) of the open journal, or None when the journal is not on top."""
        m = re.search(rf"top {JOURNAL} view mode (\w+) page (\d+) of (\d+)", self.view())
        return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None

    def wait(self, path, pattern, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if re.search(pattern, read(path)):
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def closes(self):
        return len(re.findall(r"ui: closed", read(self.uz_log)))

    def opened(self, number):
        """Waits for Doom's -dfuitest to open the journal for the number-th time, and returns a driver for it."""
        if not self.wait(self.uz_log, rf"(?s)(Daggerfall opened menu 9 at.*){{{number}}}", 60) or not self.wait(self.views, rf"top {JOURNAL} ", 5):
            self.case(False, f"journal opening {number} never appeared")
            return None
        time.sleep(1.0)
        doom = Doom(self.launcher)
        size = re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        doom.surface = (int(size[-1][0]), int(size[-1][1]))
        return doom

    def closed_by(self, doom, how, before):
        if how in VK:
            doom.press(how)
        else:
            doom.click(how)
        ok = self.wait(self.uz_log, rf"(?s)(ui: closed.*){{{before + 1}}}", 8)
        time.sleep(0.5)
        return ok and not self.journal()

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        cache = REVIEW / "data" / "cache"
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(cache), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", "8", "+dd_ui_test_menu", "9", "+bind", "j", "netevent df_journal",
              "+logfile", "log-journal", "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfjournaltest", str(self.views), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "180", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
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

    def drive(self):
        # Opening 1, and more if the test's quests were not started yet when it opened: the active quest list is read
        # as the journal opens. Close with J (the key bound to the command that opened it) until it has the quests.
        number = 0
        while True:
            number += 1
            doom = self.opened(number)
            if not doom:
                return
            state = self.journal()
            print(f"  opening {number}: {state}")
            if "seeded" in read(self.views) and state and state[2] >= 2 or number >= 3:
                break
            if not self.closed_by(doom, "J", self.closes()):
                self.case(False, f"opening {number}: J did not close the journal")
                return
        self.case(state and state[0] == "ActiveQuests" and state[2] >= 2, f"J opened the journal on Active Quests with the test's quest entries ({state})")

        # Paging: the down and up arrows, then the keyboard's arrows.
        doom.click(DOWN_ARROW)
        down = self.journal()
        doom.click(UP_ARROW)
        up = self.journal()
        doom.press("DOWN")
        key_down = self.journal()
        doom.press("UP")
        key_up = self.journal()
        print(f"  paging: arrow down {down}, arrow up {up}, key down {key_down}, key up {key_up}")
        self.case(down and down[1] == 1 and up and up[1] == 0 and key_down and key_down[1] == 1 and key_up and key_up[1] == 0,
                  "paging: the journal's arrows and the Up/Down keys turn the page forward and back")

        # Tabs: the bottom-left button, round all four.
        tabs = []
        for _ in range(4):
            doom.click(TAB_BUTTON)
            tabs.append(self.journal())
            if tabs[-1] and tabs[-1][0] == "Notebook":
                doom.press("DOWN")
                doom.press("DOWN")
                tabs.append(("notebook paged",) + (self.journal() or ("", -1, 0))[1:])
        print("  tabs:", tabs)
        modes = [t[0] for t in tabs if t]
        self.case(modes == ["FinshedQuests", "Notebook", "notebook paged", "Messages", "ActiveQuests"], f"tabs: Finished Quests, Notebook, Messages, back to Active Quests ({modes})")
        paged = next((t for t in tabs if t and t[0] == "notebook paged"), None)
        self.case(paged and paged[1] == 2 and paged[2] >= 3, f"notebook pages through its three test notes ({paged})")

        # Daggerfall's N is both the journal's next-tab shortcut and its Notebook key, which closes the journal. Recorded only.
        before = self.closes()
        doom.press("N")
        time.sleep(0.5)
        print(f"  N pressed: now {self.view()}, menu closes {self.closes() - before}")
        if self.closes() > before:
            doom = self.opened(number + 1)
            number += 1
            if not doom:
                return
            before = self.closes()
        self.case(self.closed_by(doom, "J", before), "J closed the journal back to Doom")

        # Opening 2: the journal's own Exit button closes it.
        doom = self.opened(number + 1)
        if not doom:
            return
        self.case(self.closed_by(doom, EXIT_BUTTON, self.closes()), "the journal's Exit button closed it back to Doom")

        # Opening 3: a quest's place, found on the travel map, stays inside the journal's menu. Escape closes it.
        doom = self.opened(number + 2)
        if not doom:
            return
        before = self.closes() - 1  # So the menu still open is before + 1 and closed is before + 2.
        doom.click(FIRST_LINE)
        asked = "message box" in self.view()
        doom.press("Y")
        time.sleep(1.5)
        travel = self.view()
        print(f"  find: asked {asked}, then {travel}")
        self.case(asked and "DaggerfallTravelMapWindow" in travel and self.closes() == before + 1,
                  f"clicking an active quest offers its place, and Yes shows it on the travel map inside the same menu ({travel})")
        for _ in range(3):  # The region view steps back to the world map first, then the map closes.
            if self.closes() > before + 1:
                break
            doom.press("ESC")
            time.sleep(0.5)
        self.wait(self.uz_log, rf"(?s)(ui: closed.*){{{before + 2}}}", 8)
        v = self.view()
        self.case(self.closes() == before + 2 and ("DaggerfallHUD" in v or v.startswith("top none")), f"Escape closed the travel map and the menu ({v})")

    def summary(self):
        for line in read(self.views).splitlines():
            if "seeded" in line or "error" in line:
                print("df", line)
        refused = [l for l in read(self.df_log).splitlines() if "refused" in l]
        print("Daggerfall refusals:", refused[:5])
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:6])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT journal: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;netevent df_journal;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run().go()
