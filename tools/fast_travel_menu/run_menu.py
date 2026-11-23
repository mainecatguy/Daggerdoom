"""Drives the real fast travel menu through the launcher, minimized, using window messages to Doom.

Open 1: move the mouse, then Esc closes the map.
Open 2: click a region, open its list, pick a location, confirm, and press Begin.
Prints the evidence from both games' logs. Stops at once on a fatal error.
"""
import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-menu")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
TIMEOUT = 32
TEST_MARK = 0x8000  # Doom ignores unmarked mouse messages in test mode, including the real cursor.
SURFACE = [1280, 800]  # Replaced with the size Daggerfall reports.

user32 = ctypes.WinDLL("user32", use_last_error=True)
# Without this, Windows rescales the posted mouse coordinates by the display's DPI (2.25 on this machine).
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
WM_KEYDOWN, WM_KEYUP, WM_MOUSEMOVE, WM_LDOWN, WM_LUP = 0x100, 0x101, 0x200, 0x201, 0x202
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)


def doom_window(launcher_log):
    """Only this run's Doom. Other agents may have their own UZDoom open."""
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


def surface_point(x, y):
    """Daggerfall's 320x200 UI, centered and scaled to fit the surface."""
    width, height = SURFACE
    scale = min(width / 320, height / 200)
    return int((width - 320 * scale) / 2 + x * scale), int((height - 200 * scale) / 2 + y * scale)


def move(hwnd, x, y):
    px, py = surface_point(x, y)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, TEST_MARK, py << 16 | px)
    time.sleep(0.05)


def click(hwnd, x, y):
    move(hwnd, x, y)
    time.sleep(0.15)
    px, py = surface_point(x, y)
    lp = py << 16 | px
    user32.PostMessageW(hwnd, WM_LDOWN, 1 | TEST_MARK, lp)
    time.sleep(0.08)
    user32.PostMessageW(hwnd, WM_LUP, TEST_MARK, lp)
    time.sleep(0.4)


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def wait_for(path, text, count, deadline, proc, console):
    while time.time() < deadline and proc.poll() is None:
        if read(path).count(text) >= count:
            return True
        if any(k in read(console) for k in FATAL):
            return False
        time.sleep(0.05)
    return False


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "menu"
    run = REVIEW / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log, console = run / f"{name}-uz.log", run / f"{name}-df.log", run / f"log-{name}.txt"
    for path in (uz_log, df_log, console, run / f"{name}-launcher.log"):
        path.unlink(missing_ok=True)

    uz_args = ["-noactivate", "-config", str(run / f"{name}.ini"), "-dfbridgelog", str(uz_log), "-dfuitest", "2", "-nosound", "-noautoload",
               "-skill", "3", "+logfile", name, "+map", "DDOVER01", "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(run / "shots"),
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--mod", str(REVIEW / "overworld.pk3"), "--mod", str(REVIEW / "doomerfall"), "--uzdoom-cwd", str(run),
               "--log", str(run / f"{name}-launcher.log")]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT
    result = "timeout"
    try:
        if wait_for(uz_log, "ui test: screenshot", 1, deadline, proc, console):
            hwnd = doom_window(run / f"{name}-launcher.log")
            if not hwnd:
                raise SystemExit("could not find this run's Doom window")
            size = re.search(r"opened menu 1 at (\d+)x(\d+)", read(uz_log))
            SURFACE[:] = [int(size.group(1)), int(size.group(2))]
            for x in range(40, 280, 20):
                move(hwnd, x, 100)
            key(hwnd, 0x1B)
            if wait_for(uz_log, "ui: closed", 1, deadline, proc, console) and wait_for(uz_log, "Daggerfall opened menu", 2, deadline, proc, console):
                time.sleep(1.0)  # Let the first frames of the reopened map arrive.
                click(hwnd, 20, 190)  # "I'm At": identify the player's own region.
                time.sleep(0.7)
                key(hwnd, 0x0D)  # Enter: open that region.
                time.sleep(0.7)
                key(hwnd, 0x4C)  # L: the region's location list.
                time.sleep(0.6)
                move(hwnd, 100, 64)  # The first row of the location list.
                time.sleep(0.2)
                px, py = surface_point(100, 64)
                for _ in range(2):  # Double click picks it.
                    user32.PostMessageW(hwnd, WM_LDOWN, 1 | TEST_MARK, py << 16 | px)
                    time.sleep(0.05)
                    user32.PostMessageW(hwnd, WM_LUP, TEST_MARK, py << 16 | px)
                    time.sleep(0.05)
                if wait_for(df_log, "top window is DaggerfallMessageBox", 1, deadline, proc, console):
                    time.sleep(0.3)
                    key(hwnd, 0x59)  # Y: travel there.
                if wait_for(df_log, "top window is DaggerfallTravelPopUp", 1, deadline, proc, console):
                    time.sleep(0.4)
                    key(hwnd, 0x42)  # B: Begin.
                result = "route finished" if wait_for(uz_log, "ui: closed", 2, deadline, proc, console) else "second close not seen"
                time.sleep(2.2)
    finally:
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()

    print("stopped:", result)
    for line in read(console).splitlines():
        if any(k in line for k in FATAL):
            print(line[:200])
    for label, path in (("uz", uz_log), ("df", df_log)):
        for line in read(path).splitlines():
            if " ui" in line or "error" in line:
                print(label, line[:230])


if __name__ == "__main__":
    main()
