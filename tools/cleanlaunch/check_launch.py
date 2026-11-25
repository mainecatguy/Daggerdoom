"""Launches a play folder's play.bat several times and records every window each launch shows.

  check_launch.py <play folder> [--launches N] [--seconds S] [--fresh]

Run the whole script through quiet_run.py, so the games and every window they make stay on a private desktop.
Each launch runs play.bat's own command line with three test changes: UZDoom gets -noactivate and -nosound (on a
private desktop a mouse grab would still clip the owner's real pointer), Daggerfall gets -dfmute, and the run
folder becomes test-run, so the owner's run folder is untouched. --fresh deletes test-run before every launch, as
on a first start; otherwise only the first launch is fresh.

For each launch it reports the window timeline on the launch desktop (what a player would see), where Daggerfall
Unity's windows are and how big, whether Doom reached its title with Daggerfall ready behind it, and whether
closing Doom ends everything. Exit code 0 only if every launch passed.
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

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.OpenDesktopW.restype = wt.HANDLE
user32.OpenDesktopW.argtypes = (wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD)
user32.EnumDesktopWindows.argtypes = (wt.HANDLE, EnumProc, wt.LPARAM)
user32.CloseDesktop.argtypes = (wt.HANDLE,)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.GetWindowLongW.argtypes = (wt.HWND, ctypes.c_int)
kernel32.OpenProcess.restype = wt.HANDLE
GWL_STYLE, WS_CAPTION, WS_POPUP = -16, 0x00C00000, 0x80000000
WM_CLOSE = 0x10
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
READY = "flow: Daggerfall is ready behind Doom's title"
SCREEN = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def exe_name(pid, cache={}):
    if pid not in cache:
        name = "?"
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            buf, size = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = Path(buf.value).name
            kernel32.CloseHandle(handle)
        cache[pid] = name
    return cache[pid]


def windows(desktop=None):
    """Visible top-level windows: hwnd -> (exe, class, title, rect, minimized, styled)."""
    found = {}

    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        cls, title, rect = ctypes.create_unicode_buffer(128), ctypes.create_unicode_buffer(128), wt.RECT()
        user32.GetClassNameW(hwnd, cls, 128)
        user32.GetWindowTextW(hwnd, title, 128)
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        style = user32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
        kind = "captioned" if style & WS_CAPTION == WS_CAPTION else "popup" if style & WS_POPUP else "plain"
        found[hwnd] = (exe_name(pid.value), cls.value, title.value,
                       (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top), bool(user32.IsIconic(hwnd)), kind)
        return True

    callback = EnumProc(visit)
    if desktop:
        user32.EnumDesktopWindows(desktop, callback, 0)
    else:
        user32.EnumWindows(callback, 0)
    return found


def describe(info):
    exe, cls, title, (x, y, w, h), minimized, kind = info
    state = "minimized" if minimized else f"{w}x{h} at {x},{y}, {kind}"
    if not minimized and (w, h) == SCREEN and (x, y) == (0, 0):
        state += ", COVERS THE SCREEN"
    return f"{exe} [{cls}] '{title}' {state}"


def test_bat(play, run_name):
    text = (play / "play.bat").read_text()
    text = text.replace("%HERE%run", "%HERE%" + run_name)
    launch = re.search(r'^start "" "%HERE%doomerfall-launcher.exe" ', text, re.M)
    if not launch:
        raise SystemExit("play.bat has no launcher line")
    extra = "--uzdoom-arg -noactivate --uzdoom-arg -nosound --dfu-arg -dfmute "
    # Run the launcher in this console instead of start, so this script can wait on it.
    text = text[:launch.start()] + '"%HERE%doomerfall-launcher.exe" ' + extra + text[launch.end():]
    bat = play / "check-launch.bat"
    bat.write_text(text, newline="\r\n")
    return bat


def launch_once(play, index, seconds, fresh):
    run = play / "test-run"
    if fresh and run.exists():
        shutil.rmtree(run)
    run.mkdir(exist_ok=True)
    for name in ("launcher.log", "uz.log", "df.log"):
        (run / name).unlink(missing_ok=True)
    bat = test_bat(play, "test-run")
    start = time.time()
    proc = subprocess.Popen(["cmd", "/c", str(bat)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    before = windows()
    timeline, seen, df_seen, foreground = [], {}, {}, None
    desktop, ready_at, doom_hwnd, fatal = None, None, None, None
    try:
        while time.time() - start < seconds and proc.poll() is None:
            now = time.time() - start
            for hwnd, info in windows().items():
                if hwnd in before or info[0].lower() in ("cmd.exe", "conhost.exe", "python.exe"):
                    continue
                if seen.get(hwnd) != info:
                    timeline.append(f"{now:6.2f}s {'shown  ' if hwnd not in seen else 'changed'} {describe(info)}")
                    seen[hwnd] = info
                if info[0].lower() == "uzdoom.exe" and info[1] != "ConsoleWindowClass" and not user32.GetWindow(hwnd, 4):
                    doom_hwnd = doom_hwnd or hwnd
            fg = user32.GetForegroundWindow()
            if fg and fg != foreground and fg in seen:
                timeline.append(f"{now:6.2f}s focus   {seen[fg][0]} [{seen[fg][1]}]")
            foreground = fg
            if desktop is None:
                name = re.search(r"Daggerfall desktop (\S+)", read(run / "launcher.log"))
                if name:
                    desktop = user32.OpenDesktopW(name.group(1), 0, False, 0x0040 | 0x0001)  # DESKTOP_ENUMERATE | READOBJECTS
            if desktop:
                for hwnd, info in windows(desktop).items():
                    if df_seen.get(hwnd) != info:
                        df_seen[hwnd] = info
            logs = read(run / "uz.log") + read(run / "df.log")
            fatal = next((k for k in FATAL if k in logs), None)
            if fatal:
                break
            if READY in read(run / "df.log") and doom_hwnd and ready_at is None:
                ready_at = now
            if ready_at is not None and now - ready_at > 3:  # Watch a few seconds at the title for late windows.
                break
            time.sleep(0.05)

        closed = None
        if doom_hwnd and proc.poll() is None:
            user32.PostMessageW(doom_hwnd, WM_CLOSE, 0, 0)
            try:
                proc.wait(15)
                closed = time.time() - start
            except subprocess.TimeoutExpired:
                pass
    finally:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        if desktop:
            user32.CloseDesktop(desktop)

    dfu_here = [describe(i) for i in seen.values() if i[0].lower() == "daggerfallunity.exe"]
    dfu_there = [describe(i) for i in df_seen.values() if i[0].lower() == "daggerfallunity.exe"]
    covers = any("COVERS THE SCREEN" in d for d in dfu_here + dfu_there)
    doom_main = [describe(i) for h, i in seen.items() if h == doom_hwnd]
    problems = []
    if fatal:
        problems.append("fatal error in a log: " + fatal)
    if ready_at is None:
        problems.append("did not reach Doom's title with Daggerfall ready")
    if dfu_here:
        problems.append("a Daggerfall window showed on the launch desktop")
    if covers:
        problems.append("a Daggerfall window covers the screen")
    if closed is None:
        problems.append("closing Doom did not end the launch within 15 s")
    print(f"--- launch {index} ({'fresh config' if fresh else 'config kept'}): {'PASS' if not problems else 'FAIL: ' + '; '.join(problems)}")
    print(f"    title ready at {ready_at:.2f}s" if ready_at is not None else "    title not reached", f"| closed at {closed:.2f}s" if closed else "")
    print("    Doom main window:", doom_main[0] if doom_main else "none")
    print("    Daggerfall windows on its own desktop:", "; ".join(dfu_there) or "none")
    print("    windows a player would see, in order:")
    for line in timeline:
        print("     ", line)
    return not problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("play", type=Path)
    ap.add_argument("--launches", type=int, default=3)
    ap.add_argument("--seconds", type=float, default=40)
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()
    print("screen", SCREEN)
    results = [launch_once(args.play, i + 1, args.seconds, args.fresh or i == 0) for i in range(args.launches)]
    print(f"{sum(results)} of {len(results)} launches passed")
    (args.play / "check-launch.bat").unlink(missing_ok=True)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
