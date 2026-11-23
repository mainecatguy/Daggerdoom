"""Drives one real fast travel through the launcher, minimized, using window messages to Doom.

usage: run_travel.py <name> <list row> [second row]   Rows are alphabetical in the player's region.
With one row, the first menu is cancelled with Esc and must change nothing, and the second travels.
With two rows, it makes both trips, so the second leaves from inside a town.
Stops at once on a fatal error.
"""
import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-arrival")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
TIMEOUT = 32
TEST_MARK = 0x8000
ROW_HEIGHT = 6
SURFACE = [1280, 800]

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
WM_KEYDOWN, WM_KEYUP, WM_MOUSEMOVE, WM_LDOWN, WM_LUP = 0x100, 0x101, 0x200, 0x201, 0x202
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def doom_window(launcher_log):
    pids = {int(m) for m in re.findall(r"started UZDoom pid (\d+)", read(launcher_log))}
    found = []

    def visit(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(visit), 0)
    return found[0] if found else None


def key(hwnd, vk):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 1 | (scan << 16))
    time.sleep(0.08)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 1 | (scan << 16) | (3 << 30))
    time.sleep(0.25)


def point(x, y):
    width, height = SURFACE
    scale = min(width / 320, height / 200)
    px, py = int((width - 320 * scale) / 2 + x * scale), int((height - 200 * scale) / 2 + y * scale)
    return py << 16 | px


def move(hwnd, x, y):
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, TEST_MARK, point(x, y))
    time.sleep(0.05)


def click(hwnd, x, y, times=1):
    move(hwnd, x, y)
    time.sleep(0.2)
    for _ in range(times):
        user32.PostMessageW(hwnd, WM_LDOWN, 1 | TEST_MARK, point(x, y))
        time.sleep(0.05)
        user32.PostMessageW(hwnd, WM_LUP, TEST_MARK, point(x, y))
        time.sleep(0.05)


def wait_for(path, text, count, deadline, proc, console):
    while time.time() < deadline and proc.poll() is None:
        if read(path).count(text) >= count:
            return True
        if any(k in read(console) for k in FATAL):
            return False
        time.sleep(0.05)
    return False


def main():
    name, row = sys.argv[1], int(sys.argv[2])
    second = int(sys.argv[3]) if len(sys.argv) > 3 else None
    run = REVIEW / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log, console, launcher = run / f"{name}-uz.log", run / f"{name}-df.log", run / f"log-{name}.txt", run / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)

    uz_args = ["-noactivate", "-config", str(run / f"{name}.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-dfuitest", "2",
               "-ddtowncache", str(REVIEW / "town-cache"), "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"),
               "-ddarena2", DAGGER + r"\ARENA2", "-nosound", "-noautoload", "-skill", "3", "+logfile", name, "+map", "DDOVER01",
               "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(run / "shots"),
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--mod", str(REVIEW / "ddruntime.pk3"), "--mod", str(REVIEW / "overworld.pk3"), "--mod", str(REVIEW / "doomerfall"),
               "--uzdoom-cwd", str(run), "--log", str(launcher)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT
    result = "timeout"
    begin = None
    try:
        if wait_for(uz_log, "ui test: screenshot", 1, deadline, proc, console):
            hwnd = doom_window(launcher)
            if not hwnd:
                raise SystemExit("could not find this run's Doom window")
            size = re.search(r"opened menu 1 at (\d+)x(\d+)", read(uz_log))
            SURFACE[:] = [int(size.group(1)), int(size.group(2))]
            def trip(number, target):
                """Picks a list row in the open map and waits until Doom has reached it."""
                click(hwnd, 20, 190)  # I'm At.
                time.sleep(0.7)
                key(hwnd, 0x0D)  # Open the region.
                time.sleep(0.7)
                key(hwnd, 0x4C)  # The location list.
                time.sleep(0.6)
                click(hwnd, 100, 64 + target * ROW_HEIGHT, 2)
                if wait_for(df_log, "top window is DaggerfallMessageBox", number, deadline, proc, console):
                    time.sleep(0.3)
                    key(hwnd, 0x59)  # Yes.
                if wait_for(df_log, "top window is DaggerfallTravelPopUp", number, deadline, proc, console):
                    time.sleep(0.4)
                    key(hwnd, 0x42)  # Begin.
                return wait_for(df_log, "travel: Doom reached", number, deadline, proc, console)

            if second is None:
                key(hwnd, 0x1B)  # Cancel the first menu.
                ready = wait_for(uz_log, "ui: closed", 1, deadline, proc, console) and wait_for(uz_log, "Daggerfall opened menu", 2, deadline, proc, console)
                if ready:
                    time.sleep(1.0)
                    begin = time.time()
                    result = "arrived" if trip(1, row) else "arrival not seen"
            else:  # Two trips and no cancel, so the second leaves from inside the first town within the time limit.
                begin = time.time()
                result = "first trip not seen"
                if trip(1, row) and wait_for(console, "DDTOWN active", 1, deadline, proc, console) and wait_for(uz_log, "Daggerfall opened menu", 2, deadline, proc, console):
                    time.sleep(1.0)
                    result = "both trips arrived" if trip(2, second) else "second trip not seen"
            if "arrived" in result:
                result += f", {time.time() - begin:.2f} s after the route began"
                time.sleep(2.5)  # Let the position update run, so its log shows Doom's real position.
    finally:
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()

    print("stopped:", result)
    for line in read(console).splitlines():
        if any(k in line for k in FATAL) or line.startswith(("DDTRAVEL", "DDSTITCH", "DDTOWN active", "DDTCONV")):
            print("console", line[:190])
    for label, path in (("uz", uz_log), ("df", df_log)):
        lines = read(path).splitlines()
        for line in lines:
            if "travel" in line or "ui: world" in line or "error" in line or "ui: closed" in line:
                print(label, line[:210])
        status = [line for line in lines if "sync engaged" in line]
        if status:
            print(label, "last", status[-1][:150])


if __name__ == "__main__":
    main()
