"""Builds, assembles, and tests the Doomerfall inventory menu demo in a private review folder.

usage: inventory_menu.py build | unity | assemble | run <name> | check | registry save|compare
Game data and generated files stay outside the repo. The Daggerfall copy is portable and patched to
its own product name, so it never touches the owner's real Daggerfall Unity settings or saves.
"""
import ctypes
import ctypes.wintypes as wt
import hashlib
import re
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\inventory-menu")
BUILD = REVIEW / "build"
RUN = REVIEW / "run"
PREVIOUS = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-arrival")  # Unchanged converter data, and the baseline Doom.
SOUND = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
RES = r"D:\dev\DoomDaggerfall\GameResources"
DAGGER = RES + r"\DAGGER"
IWAD2 = RES + r"\wads\DOOM2.WAD"
IWAD1 = RES + r"\wads\DOOM.WAD"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
REG_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
TIMEOUT = 32
TEST_MARK = 0x8000  # Doom ignores unmarked mouse messages in test mode, including the real cursor.
VK_ESC, VK_J = 0x1B, 0x4A

PLAY = r"""@echo off
rem Press I in Doom to open Daggerfall's inventory. Press I again, Esc, or Exit to close it.
rem Rebind it in Options, Customize Controls, Doomerfall Controls. The test character carries two weapons.
rem Daggerfall's window stays open behind Doom for now. Close either game and both close.
set "HERE=%~dp0"
if not exist "%HERE%play" mkdir "%HERE%play"
set BINDS=
if not exist "%HERE%play\uzdoom.ini" set BINDS=--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg "netevent df_inventory" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg "netevent df_fast_travel"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%HERE%ddruntime.pk3" --mod "%HERE%overworld.pk3" --mod "%HERE%doomerfall" --uzdoom-cwd "%HERE%play" --log "%HERE%play\launcher.log" --uzdoom-arg -config --uzdoom-arg "%HERE%play\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%play\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%play\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%HERE%town-cache" --uzdoom-arg -ddconverter --uzdoom-arg "%HERE%converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDOVER01 --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 %BINDS% --dfu-arg -dfbridgelog --dfu-arg "%HERE%play\df.log" --dfu-arg -dfsynctest --dfu-arg "D:\dev\DoomDaggerfall\GameResources\DAGGER" --dfu-arg -dfinventorytest --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800
"""


def call(args, log):
    with log.open("a", encoding="utf-8", errors="replace") as out:
        code = subprocess.call(args, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, cwd=WORKTREE)
    if code:
        sys.exit(f"failed ({code}): see {log}")


def build():
    BUILD.mkdir(parents=True, exist_ok=True)
    for name, source in (("bridge", "bridge"), ("launcher", "launcher"), ("uzdoom", "UZDoom")):
        target, log = BUILD / name, BUILD / f"{name}-build.log"
        log.unlink(missing_ok=True)
        if not (target / "CMakeCache.txt").exists():
            call(["cmake", "-S", str(WORKTREE / source), "-B", str(target), "-G", "Visual Studio 18 2026", "-A", "x64"], log)
        call(["cmake", "--build", str(target), "--config", "Release", "--parallel", "6"], log)
        print("built", name)


def unity():
    project = WORKTREE / "daggerfall-unity-master"
    if (project / "Temp" / "UnityLockfile").exists():
        print("note: a Unity lock file exists; Unity will refuse if an editor has this project open")
    log = project / "Logs" / "cli-build.log"
    log.unlink(missing_ok=True)
    code = subprocess.call([sys.executable, QUIET, "--timeout", "1800", "--", "Unity.exe", "-projectPath", str(project), "-buildTarget", "Win64",
                            "-executeMethod", "CliBuild.BuildWindows64", "-logFile", str(log)], stdin=subprocess.DEVNULL)
    text = read(log)
    ok = "CliBuild result: Succeeded" in text
    print(f"unity exit {code}, succeeded {ok}")
    for line in text.splitlines():
        if "error CS" in line:
            print(line[:220])
    if not ok:
        sys.exit(1)


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.exp", "*.lib", "*.log", "CMakeFiles"))


def assemble():
    RUN.mkdir(parents=True, exist_ok=True)
    dfu = REVIEW / "dfu"
    copy_tree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
    (dfu / "Portable.txt").touch()
    if not (dfu / "PortableAppdata").exists():
        shutil.copytree(PREVIOUS / "dfu" / "PortableAppdata", dfu / "PortableAppdata", ignore=shutil.ignore_patterns("*.log"))
    manager = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if b"Daggerfall Unity" in data:
        manager.write_bytes(data.replace(b"Daggerfall Unity", b"Doomerfall Local"))
    elif b"Doomerfall Local" not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge" / "Release" / "doomerfall_bridge.dll", plugins)
    uz = REVIEW / "uzdoom"
    copy_tree(BUILD / "uzdoom" / "Release", uz)
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / name, uz)
    shutil.copy2(BUILD / "launcher" / "Release" / "doomerfall-launcher.exe", REVIEW)
    copy_tree(WORKTREE / "mods" / "doomerfall" / "src", REVIEW / "doomerfall")
    copy_tree(PREVIOUS / "converter", REVIEW / "converter")
    for name in ("ddruntime.pk3", "overworld.pk3"):
        shutil.copy2(PREVIOUS / name, REVIEW)
    (REVIEW / "town-cache").mkdir(exist_ok=True)
    (REVIEW / "play.bat").write_text(PLAY.replace("\n", "\r\n"), newline="")
    print("assembled", REVIEW)


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


class Doom:
    """Posts window messages to this run's Doom only. Other agents may have their own open."""

    def __init__(self, launcher_log, surface):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self.user.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)
        self.surface = surface
        pids = {int(m) for m in re.findall(r"started UZDoom pid (\d+)", read(launcher_log))}
        found = []
        proc_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def visit(hwnd, _):
            pid = wt.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids and self.user.IsWindowVisible(hwnd) and not self.user.GetWindow(hwnd, 4):
                found.append(hwnd)
            return True

        self.user.EnumWindows(proc_type(visit), 0)
        if not found:
            raise SystemExit("could not find this run's Doom window")
        self.hwnd = found[0]

    def key(self, vk):
        scan = self.user.MapVirtualKeyW(vk, 0)
        self.user.PostMessageW(self.hwnd, 0x100, vk, 1 | (scan << 16))
        time.sleep(0.08)
        self.user.PostMessageW(self.hwnd, 0x101, vk, 1 | (scan << 16) | (3 << 30))
        time.sleep(0.3)

    def point(self, x, y):
        width, height = self.surface
        scale = min(width / 320, height / 200)
        return int((height - 200 * scale) / 2 + y * scale) << 16 | int((width - 320 * scale) / 2 + x * scale)

    def click(self, x, y):
        lp = self.point(x, y)
        self.user.PostMessageW(self.hwnd, 0x200, TEST_MARK, lp)
        time.sleep(0.2)
        self.user.PostMessageW(self.hwnd, 0x201, 1 | TEST_MARK, lp)
        time.sleep(0.08)
        self.user.PostMessageW(self.hwnd, 0x202, TEST_MARK, lp)
        time.sleep(0.4)


def wait_for(path, text, count, deadline, proc, console):
    while time.time() < deadline and proc.poll() is None:
        if read(path).count(text) >= count:
            return True
        if any(k in read(console) for k in FATAL):
            return False
        time.sleep(0.05)
    return False


def run_route(name):
    """Open 1: equip by mouse, close with the bound key. Open 2: Exit button. Open 3: Info popup, Esc, Esc."""
    RUN.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = RUN / f"{name}-uz.log", RUN / f"{name}-df.log", RUN / f"log-{name}.txt", RUN / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz_args = ["-noactivate", "-config", str(RUN / f"{name}.ini"), "-savedir", str(RUN / "saves"), "-dfbridgelog", str(uz_log), "-dfuitest", "3",
               "-ddtowncache", str(REVIEW / "town-cache"), "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"),
               "-ddarena2", DAGGER + r"\ARENA2", "-nosound", "-noautoload", "-skill", "3", "+logfile", name, "+map", "DDOVER01",
               "+dd_ui_test_menu", "2", "+bind", "j", "netevent df_inventory",
               "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(RUN / "shots"),
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfinventorytest", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD2,
               "--mod", str(REVIEW / "ddruntime.pk3"), "--mod", str(REVIEW / "overworld.pk3"), "--mod", str(REVIEW / "doomerfall"),
               "--uzdoom-cwd", str(RUN), "--log", str(launcher)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # Otherwise Windows rescales posted coordinates.
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT
    result = "timeout"

    def seen(path, text, count):
        return wait_for(path, text, count, deadline, proc, console)

    try:
        if seen(uz_log, "ui test: screenshot", 1):
            size = re.search(r"opened menu 2 at (\d+)x(\d+)", read(uz_log))
            doom = Doom(launcher, [int(size.group(1)), int(size.group(2))])
            doom.click(197, 67)  # Equip the first item in the list.
            time.sleep(1.6)  # Leaves a screenshot of the changed inventory.
            doom.key(VK_J)
            result = "first close not seen"
            if seen(uz_log, "ui: closed", 1) and seen(uz_log, "Daggerfall opened menu", 2):
                time.sleep(1.0)
                doom.click(241, 189)  # Exit button.
                result = "second close not seen"
                if seen(uz_log, "ui: closed", 2) and seen(uz_log, "Daggerfall opened menu", 3):
                    time.sleep(1.0)
                    doom.click(241, 43)  # Info mode.
                    doom.click(197, 67)  # The next item.
                    result = "info popup not seen"
                    if seen(df_log, "top window is DaggerfallMessageBox", 1):
                        time.sleep(0.4)
                        doom.key(VK_ESC)  # Closes only the popup.
                        time.sleep(0.5)
                        still_open = read(uz_log).count("ui: closed") == 2
                        doom.key(VK_ESC)  # Closes the inventory.
                        result = "third close not seen"
                        if seen(uz_log, "ui: closed", 3):
                            result = "route finished" if still_open else "first Esc closed the whole menu"
                            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()

    print("stopped:", result)
    for line in read(console).splitlines():
        if any(k in line for k in FATAL):
            print("console", line[:200])
    for label, path in (("uz", uz_log), ("df", df_log)):
        for line in read(path).splitlines():
            if " ui" in line or "ui:" in line or "error" in line:
                print(label, line[:240])
    player = REVIEW / "dfu" / "PortableAppdata" / "Player.log"
    exceptions = [line for line in read(player).splitlines() if "Exception" in line]
    print("Player.log exception lines:", len(exceptions))
    for line in sorted(set(exceptions))[:5]:
        print("  ", line[:180])


def check():
    def doom(name, files, exe):
        log = RUN / f"log-{name}.txt"
        log.unlink(missing_ok=True)
        args = [str(exe), "-iwad", IWAD1, "-config", str(RUN / f"{name}.ini"), "-nosound", "-noautoload", "-noactivate", "-skill", "3",
                "+logfile", name, "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                "+vid_lowerinbackground", "0", "+map", "E1M1", "+netevent", "df_inventory", "+wait 175;quit"]
        if files:
            args[3:3] = ["-file"] + [str(MODS / f) for f in files]
        code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(RUN), "--"] + args,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        text = read(log)
        bad = [line for line in text.splitlines() if any(k in line for k in ("Fatal error", "FATAL", "VM execution aborted", "Script error"))]
        print(f"{name}: exit {code}, E1M1 {'E1M1' in text}, bridge lines {text.count('[bridge]')}, error lines {len(bad)}, unknown-class lines {text.count('Unknown class name')}")
        for line in bad[:3]:
            print("  ", line[:160])

    RUN.mkdir(parents=True, exist_ok=True)
    now = REVIEW / "uzdoom" / "uzdoom.exe"
    doom("stock", [], now)
    doom("drla", DRLA, now)
    doom("drla-before", DRLA, PREVIOUS / "uzdoom" / "uzdoom.exe")
    exe = REVIEW / "dfu" / "DaggerfallUnity.exe"
    player = REVIEW / "dfu" / "PortableAppdata" / "Player.log"
    code = subprocess.call([sys.executable, QUIET, "--timeout", "12", "--", str(exe), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = read(player)
    print(f"plain Daggerfall: exit {code}, log lines {len(text.splitlines())}, bridge mentions {text.lower().count('doomerfall_bridge')}, "
          f"DoomerfallUi mentions {text.count('DoomerfallUi')}, exceptions {text.count('Exception')}")


def registry(mode):
    store = RUN / "registry-before.txt"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as handle:
            count = winreg.QueryInfoKey(handle)[1]
            values = sorted(repr(winreg.EnumValue(handle, i)) for i in range(count))
        now = f"{count} values {hashlib.sha256(chr(10).join(values).encode()).hexdigest()}"
    except FileNotFoundError:
        now = "key absent"
    if mode == "save":
        RUN.mkdir(parents=True, exist_ok=True)
        store.write_text(now)
        print("saved:", now)
    else:
        before = store.read_text()
        print("unchanged" if before == now else "CHANGED", "| before:", before, "| after:", now)


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "build":
        build()
    elif command == "unity":
        unity()
    elif command == "assemble":
        assemble()
    elif command == "run":
        run_route(sys.argv[2])
    elif command == "check":
        check()
    elif command == "registry":
        registry(sys.argv[2])
    else:
        sys.exit(__doc__)
