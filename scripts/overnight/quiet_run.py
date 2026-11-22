"""Run a desktop program minimized, and keep it from taking focus.

Usage: python quiet_run.py [--timeout SECONDS] [--cwd DIR] -- PROGRAM [ARGS...]
Exits with the program's exit code, or 124 if it timed out.
"""
import argparse
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

SW_SHOWMINNOACTIVE = 7
TIMED_OUT = 124
POLL_SECONDS = 0.01

user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def keep_quiet(pid, previous):
    def visit(hwnd, _):
        if window_pid(hwnd) == pid and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
        return True

    user32.EnumWindows(EnumWindowsProc(visit), 0)
    foreground = user32.GetForegroundWindow()
    if previous and foreground and foreground != previous and window_pid(foreground) == pid:
        user32.SetForegroundWindow(previous)


def main():
    argv = sys.argv[1:]
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        sys.exit(__doc__)
    split = argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--cwd")
    options = parser.parse_args(argv[:split])

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWMINNOACTIVE
    previous = user32.GetForegroundWindow()
    process = subprocess.Popen(argv[split + 1:], cwd=options.cwd, startupinfo=startup)
    print(f"quiet_run: pid {process.pid}", file=sys.stderr, flush=True)

    deadline = time.monotonic() + options.timeout if options.timeout else None
    while process.poll() is None:
        keep_quiet(process.pid, previous)
        if deadline and time.monotonic() >= deadline:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait()
            sys.exit(TIMED_OUT)
        time.sleep(POLL_SECONDS)
    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
