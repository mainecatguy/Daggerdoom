"""Tests that Doom's movement keys pan Daggerfall's map screens, with both real games on quiet_run's private desktop.

usage: mapkeys.py [--review DIR] assemble | default | rebound | find | check
default: Doom's default bindings (W, S, A, D). rebound: W unbound and I bound to +forward.
find: types into the travel map's Find box through Doom (every letter, digits, space, Backspace, and Doom's menu key),
finds the town the player is in, then checks the movement keys pan the map again and the menu key closes it.
--review: the folder to assemble into and run from (default review/mapkeys).
Each run opens, through the real commands, the town's exterior automap, the travel map, and Privateer's Hold's
dungeon automap, and posts key presses to Doom's window. Daggerfall's -dfmapkeystest logs each map view, and the
harness logs the Doom player's position, which must not change while a menu is open.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\mapkeys")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\ammoname")  # Data, converter and sprite package.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-ammopile" / "Release"  # Configured from this worktree by an earlier task in this lane.
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-ammopile" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-ammopile" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
TEST_MARK = 0x8000
VK = {"W": 0x57, "S": 0x53, "A": 0x41, "D": 0x44, "I": 0x49, "TAB": 0x09, "K": 0x4B, "ESC": 0x1B, "RET": 0x0D, "BACK": 0x08}
CHAR_VK = {**{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"}, " ": 0x20, "'": 0xDE, "-": 0xBD, ".": 0xBE}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def harness(find=False):
    cache = REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt"
    for other in cache.parent.glob("T*.ddt"):
        if other != cache:
            other.unlink()
    shutil.copy(SOURCE / "data" / "cache" / cache.name, cache)
    door = next(l.split() for l in lumps(cache)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    path = REVIEW / "run" / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@FIND@", "true" if find else "false"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "MKHarness" }\n')
    return path


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", UZ_BUILD), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini", "*.ilk", "*.exp", "*.lib"))
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
        "rem Map keys. Starts outside Privateer's Hold with DRLA. Tab opens Daggerfall's map, K the travel map.\r\n"
        "rem In a map, your Doom forward, back and strafe keys (W S A D by default) pan the view.\r\n"
        "rem Travel map: in a region, right-click to zoom, then pan; unzoomed, the keys step between a region's map parts.\r\n"
        "rem Travel map Find (in a region): every key goes to the box while you type a place name, W A S D included.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Doom:
    """Posts window messages to this run's Doom window, on whichever desktop quiet_run put it."""

    def __init__(self, launcher_log):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self.user.OpenDesktopW.restype = wt.HANDLE
        self.user.OpenDesktopW.argtypes = (wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD)
        self.user.EnumDesktopWindows.argtypes = (wt.HANDLE, ctypes.c_void_p, wt.LPARAM)
        self.user.EnumDesktopsW.argtypes = (wt.HANDLE, ctypes.c_void_p, wt.LPARAM)
        self.user.GetProcessWindowStation.restype = wt.HANDLE
        self.user.CloseDesktop.argtypes = (wt.HANDLE,)
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
        self.user.SetThreadDesktop.argtypes = (wt.HANDLE,)
        for name in names:
            desk = self.user.OpenDesktopW(name, 0, False, 0x01FF)  # All desktop rights: enumerate, then join it.
            if not desk:
                continue
            before = len(found)
            self.user.EnumDesktopWindows(desk, callback, 0)
            if len(found) > before:
                # A window on another desktop is an invalid handle to threads outside it, so post from inside it.
                # This thread owns no windows, which SetThreadDesktop requires. The handle stays open while in use.
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
        print("  Doom windows:", info, "desktops:", names)
        self.hwnd = next((h for h, c in info if "doom" in c.lower()), None) or next((h for h, c in info if not c.startswith(("NV", "IME", "MSCTF", "Default IME"))), found[0])

    def down(self, vk):
        scan = self.user.MapVirtualKeyW(vk, 0)
        if not self.user.PostMessageW(self.hwnd, 0x100, vk, 1 | (scan << 16)):
            print("  PostMessage failed, error", ctypes.get_last_error())

    def up(self, vk):
        scan = self.user.MapVirtualKeyW(vk, 0)
        self.user.PostMessageW(self.hwnd, 0x101, vk, 1 | (scan << 16) | (3 << 30))

    def tap(self, vk):
        self.down(vk)
        time.sleep(0.04)
        self.up(vk)
        time.sleep(0.06)

    def type(self, text):
        """Key presses only: Doom's own message loop makes the characters, as for a real keyboard (no Shift)."""
        for c in text:
            self.tap(CHAR_VK[c])

    def hold(self, vk, seconds):
        self.down(vk)
        time.sleep(seconds)
        self.up(vk)
        time.sleep(0.4)

    def point(self, x, y):
        width, height = self.surface
        scale = min(width / 320, height / 200)
        return int((height - 200 * scale) / 2 + y * scale) << 16 | int((width - 320 * scale) / 2 + x * scale)

    def click(self, x, y, right=False):
        lp = self.point(x, y)
        self.user.PostMessageW(self.hwnd, 0x200, TEST_MARK, lp)
        time.sleep(0.2)
        self.user.PostMessageW(self.hwnd, 0x204 if right else 0x201, (2 if right else 1) | TEST_MARK, lp)
        time.sleep(0.08)
        self.user.PostMessageW(self.hwnd, 0x205 if right else 0x202, TEST_MARK, lp)
        time.sleep(0.5)


class Run:
    def __init__(self, name, binds, keys):
        self.name, self.binds, self.keys = name, binds, keys
        self.dir = REVIEW / "run" / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / f"log-{name}.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "mapkeys.log"
        self.results = []
        self.proc = None

    def view(self, window):
        """The last logged view of a window, or None."""
        lines = [l for l in read(self.views).splitlines() if f"top {window} " in l]
        if not lines:
            return None
        return re.search(r"view (.*?) keys", lines[-1]).group(1)

    def keys_seen(self):
        return set(re.findall(r"keys ([A-Za-z,]*) player", read(self.views)))

    def wait(self, path, pattern, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            body = read(path)
            if re.search(pattern, body):
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def case(self, ok, what):
        self.results.append((ok, what))
        print("CASE", "pass" if ok else "FAIL", what)

    def pan(self, doom, window, key):
        before = self.view(window)
        doom.hold(VK[key], 0.5)
        time.sleep(0.3)
        after = self.view(window)
        return before, after

    @staticmethod
    def vec(text):
        return [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", text or "")]

    def automap(self, doom, window):
        fwd, back, left, right = self.keys
        moves = {}
        for key in (fwd, back, left, right):
            before, after = self.pan(doom, window, key)
            a, b = self.vec(before), self.vec(after)
            moves[key] = [y - x for x, y in zip(a, b)] if len(a) == len(b) == 3 else None
            print(f"  {window} {key}: {before} -> {after}")
        ok = all(m and any(abs(v) > 0.01 for v in m) for m in moves.values())
        self.case(ok, f"{window}: each of {fwd} {back} {left} {right} moves the view")
        if ok:
            dot = lambda u, v: sum(x * y for x, y in zip(u, v))
            self.case(dot(moves[fwd], moves[back]) < 0 and dot(moves[left], moves[right]) < 0, f"{window}: forward and back pan opposite ways, and so do the strafes")
            self.case(abs(dot(moves[fwd], moves[left])) < 0.2 * (dot(moves[fwd], moves[fwd]) ** 0.5) * (dot(moves[left], moves[left]) ** 0.5), f"{window}: forward and strafe pan at right angles")
        if self.name == "rebound":
            before, after = self.pan(doom, window, "W")
            self.case(before == after, f"{window}: W, no longer bound to +forward, does not pan ({before} -> {after})")

    def travel(self, doom):
        fwd, back, left, right = self.keys
        window = "DaggerfallTravelMapWindow"
        before, after = self.pan(doom, window, fwd)
        print(f"  world map {fwd}: {before} -> {after}")
        doom.click(20, 190)  # I'm At: the player's region on the world map.
        time.sleep(0.5)
        doom.down(VK["RET"]); time.sleep(0.1); doom.up(VK["RET"])  # Open the region.
        time.sleep(1.0)
        region = self.view(window)
        print("  region:", region)
        steps = []
        for key in (right, back, left, fwd):
            b, a = self.pan(doom, window, key)
            steps.append((key, b, a))
            print(f"  region {key}: {b} -> {a}")
        multi = any(b != a for _, b, a in steps)
        print("  region has several map parts:", multi)
        doom.click(160, 100, right=True)  # Zoom.
        time.sleep(0.5)
        zoomed = self.view(window)
        print("  zoomed:", zoomed)
        moves = {}
        for key in (back, fwd, right, left):  # The zoom may start at the top-left edge, so back and right move first.
            b, a = self.pan(doom, window, key)
            pb, pa = re.search(r"at \((.*?)\)", b or ""), re.search(r"at \((.*?)\)", a or "")
            moves[key] = [float(y) - float(x) for x, y in zip(pb.group(1).split(","), pa.group(1).split(","))] if pb and pa else None
            print(f"  zoomed {key}: {b} -> {a}")
        self.case("zoom True" in (zoomed or ""), "travel map: right-click zoomed the region")
        ok = moves[fwd] and moves[back] and moves[left] and moves[right] and moves[fwd][1] < 0 and moves[back][1] > 0 and moves[right][0] > 0 and moves[left][0] < 0
        self.case(bool(ok), f"travel map zoomed: {fwd} pans up, {back} down, {left} left, {right} right")
        if self.name == "rebound":
            b, a = self.pan(doom, window, "W")
            self.case(b == a, f"travel map: W, no longer bound to +forward, does not pan ({b} -> {a})")

    def menu_still(self, stage):
        """Doom's player stood still across the menu: the position before it opened equals the one after it closed."""
        lines = [l for l in read(self.console).splitlines() if l.startswith(f"MKPOS stage {stage}")]
        for i, line in enumerate(lines):
            if "after-menu" in line and i > 0:
                a, b = self.vec(lines[i - 1].split(maxsplit=3)[3]), self.vec(line.split("after-menu")[1])
                return a == b, lines[i - 1], line
        return False, None, None

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", "3", "+dd_ui_test_hold", "1", "+dd_ui_test_menu", "3", "+bind", "k", "netevent df_fast_travel", *self.binds,
              "+logfile", self.name, "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfmapkeystest", str(self.views), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        timeout = 150
        command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", harness(self.name == "find")]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.drive_find() if self.name == "find" else self.drive()
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            self.case(False, f"driver error: {e}")
        finally:
            if self.proc.poll() is None:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.proc.wait()
        self.summary()

    def opened(self, window, seconds):
        if not self.wait(self.views, rf"top {window} ", seconds):
            self.case(False, f"{window} never opened")
            return None
        time.sleep(1.0)
        doom = Doom(self.launcher)
        size = re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        if size:
            doom.surface = (int(size[-1][0]), int(size[-1][1]))
        return doom

    def closed(self, doom, key, count):
        doom.down(VK[key]); time.sleep(0.1); doom.up(VK[key])
        if not self.wait(self.uz_log, rf"(?s)(ui: closed.*){{{count}}}", 8):
            self.case(False, f"menu {count} did not close with {key}")
            return False
        return True

    def drive(self):
        doom = self.opened("DaggerfallExteriorAutomapWindow", 90)
        if not doom:
            return
        self.automap(doom, "DaggerfallExteriorAutomapWindow")
        if not self.closed(doom, "TAB", 1):
            return
        doom = self.opened("DaggerfallTravelMapWindow", 20)
        if not doom:
            return
        self.travel(doom)
        doom.down(VK["ESC"]); time.sleep(0.1); doom.up(VK["ESC"])  # Leave the region.
        time.sleep(0.6)
        if not self.closed(doom, "K", 2):
            return
        doom = self.opened("DaggerfallAutomapWindow", 45)
        if not doom:
            return
        self.automap(doom, "DaggerfallAutomapWindow")
        if not self.closed(doom, "TAB", 3):
            return
        self.wait(self.console, "MKDONE", 5)

    def box_text(self):
        view = self.view("DaggerfallInputMessageBox") or ""
        m = re.match(r"text '(.*?)'(?: here '.*')?$", view)
        return m.group(1) if m else None

    def drive_find(self):
        doom = self.opened("DaggerfallExteriorAutomapWindow", 90)
        if not doom or not self.closed(doom, "TAB", 1):
            return
        window = "DaggerfallTravelMapWindow"
        doom = self.opened(window, 20)
        if not doom:
            return
        doom.click(20, 190)  # I'm At: the player's region on the world map.
        time.sleep(0.5)
        doom.tap(VK["RET"])  # Open the region.
        time.sleep(1.0)
        region = self.view(window) or ""
        here = re.search(r"here '(.*)'", region)
        print("  region:", region)
        doom.click(25, 180)  # Find.
        if not self.wait(self.views, r"top DaggerfallInputMessageBox ", 5):
            self.case(False, "the Find box opened")
            return
        self.case(self.wait(self.uz_log, r"ui: text entry started", 3), "Doom heard that a text box takes typing")
        # k is Doom's travel map key here, so it would close the menu if Doom still read it as a control.
        for text in ("abcdefghijklmnopqrstuvwxyz", "0123456789 wasd k"):
            doom.type(text)
            time.sleep(0.6)
            got = self.box_text()
            self.case(got == text, f"Find box took '{text}' (has '{got}')")
            for _ in text:
                doom.tap(VK["BACK"])
            time.sleep(0.6)
            got = self.box_text()
            self.case(got == "", f"Backspace erased it (has '{got}')")
        if not here:
            self.case(False, "Daggerfall named the town the player is in")
            return
        name = here.group(1).lower()
        doom.type(name)
        time.sleep(0.6)
        got = self.box_text()
        self.case(got == name, f"Find box took the town's name '{name}' (has '{got}')")
        doom.tap(VK["RET"])
        time.sleep(1.0)
        found = self.view(window) or ""
        print("  after Find:", found)
        self.case("found True selected True" in found, f"Find found '{name}' ({found})")
        self.case(self.wait(self.uz_log, r"ui: text entry ended", 3), "Doom heard that typing ended")
        fwd, back, left, right = self.keys
        doom.click(160, 100, right=True)  # Zoom, so the movement keys have room to pan.
        time.sleep(0.5)
        moved = []
        for key in (back, right, fwd, left):  # The zoom may start at the top-left edge, so back and right move first.
            b, a = self.pan(doom, window, key)
            pb, pa = re.search(r" at \((.*?)\)", b or ""), re.search(r" at \((.*?)\)", a or "")
            moved.append(bool(pb and pa and pb.group(1) != pa.group(1)))
            print(f"  zoomed {key}: {b} -> {a}")
        self.case(all(moved), f"after the Find box closed, {back} {right} {fwd} {left} pan the map again ({moved})")
        if self.closed(doom, "K", 2):
            self.case(True, "after the Find box closed, Doom's travel map key closes the menu again")
        self.wait(self.console, "MKDONE", 5)

    def summary(self):
        stages = ((0, "exterior automap"), (1, "travel map"), (2, "dungeon automap"))
        for stage, what in stages[:2] if self.name == "find" else stages:
            ok, before, after = self.menu_still(stage)
            self.case(ok, f"Doom's player did not move while the {what} was open ({before} | {after})")
        seen = self.keys_seen()
        if self.name != "find":  # The Find box gets the raw keys by design.
            self.case(not any(k in s for s in seen for k in ("W,", "A,", "S,", "D,")) or self.name == "rebound" and seen and all(k not in s for s in seen for k in ("A,", "S,", "D,")),
                      f"Daggerfall saw arrow keys, never the raw movement keys (held sets seen: {sorted(seen)})")
        for line in read(self.console).splitlines():
            if line.startswith(("MKSTAGE", "MKREADY", "MKDONE")) or "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:4])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT {self.name}: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;togglemap;wait 35;togglemap;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "default", "rebound", "find", "check"))
ap.add_argument("--review", type=Path, default=REVIEW)
args = ap.parse_args()
REVIEW = args.review
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
elif args.command == "find":
    Run("find", [], ("W", "S", "A", "D")).go()
elif args.command == "default":
    Run("default", [], ("W", "S", "A", "D")).go()
else:
    # "+forward" on the command line would start a console command of its own, so the binding goes in a file.
    binds = REVIEW / "run" / "rebound.cfg"
    binds.parent.mkdir(parents=True, exist_ok=True)
    binds.write_text("unbind w\nbind i +forward\n")
    Run("rebound", ["+exec", str(binds)], ("I", "S", "A", "D")).go()
