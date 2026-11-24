"""Run a desktop program minimized, and keep it from taking focus.

Usage: python quiet_run.py [--timeout SECONDS] [--cwd DIR] [--desktop] -- PROGRAM [ARGS...]
Exits with the program's exit code, or 124 if it timed out.

--desktop runs the program, and anything it starts, on a private desktop the user never sees, so no window,
dialog, or focus change can reach the user's desktop. Sound is not affected.
"""
import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

SW_SHOWMINNOACTIVE = 7
TIMED_OUT = 124
POLL_SECONDS = 0.01

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.CreateDesktopW.restype = wintypes.HANDLE
user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID]
user32.CloseDesktop.argtypes = [wintypes.HANDLE]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD)]


kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
                                    wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOW),
                                    ctypes.POINTER(PROCESS_INFORMATION)]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


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


class DesktopProcess:
    """A process started on a new private desktop, with the small part of the Popen interface used here."""

    def __init__(self, command, cwd):
        self.name = f"quiet-run-{os.getpid()}"
        self.desktop = user32.CreateDesktopW(self.name, None, None, 0, 0x10000000, None)  # GENERIC_ALL
        if not self.desktop:
            raise OSError(f"could not create a private desktop (error {ctypes.get_last_error()})")
        startup = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop=self.name)
        info = PROCESS_INFORMATION()
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        if not kernel32.CreateProcessW(None, line, None, None, True, 0, None, cwd, ctypes.byref(startup),
                                       ctypes.byref(info)):
            raise OSError(f"could not start {command[0]} (error {ctypes.get_last_error()})")
        kernel32.CloseHandle(info.hThread)
        self.handle, self.pid, self.returncode = info.hProcess, info.dwProcessId, None

    def poll(self):
        if self.returncode is None and kernel32.WaitForSingleObject(self.handle, 0) == 0:
            code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code))
            self.returncode = ctypes.c_int32(code.value).value
            kernel32.CloseHandle(self.handle)
            user32.CloseDesktop(self.desktop)
        return self.returncode

    def wait(self):
        while self.poll() is None:
            time.sleep(POLL_SECONDS)
        return self.returncode


def main():
    argv = sys.argv[1:]
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        sys.exit(__doc__)
    split = argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--cwd")
    parser.add_argument("--desktop", action="store_true")
    options = parser.parse_args(argv[:split])

    previous = user32.GetForegroundWindow()
    command = argv[split + 1:]
    if os.path.basename(command[0]).lower() in ("uzdoom", "uzdoom.exe"):
        command[1:1] = ["+vid_fullscreen", "0"]
    if options.desktop:
        process = DesktopProcess(command, options.cwd)
    else:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = SW_SHOWMINNOACTIVE
        process = subprocess.Popen(command, cwd=options.cwd, startupinfo=startup)
    print(f"quiet_run: pid {process.pid}", file=sys.stderr, flush=True)

    deadline = time.monotonic() + options.timeout if options.timeout else None
    while process.poll() is None:
        if not options.desktop:
            keep_quiet(process.pid, previous)
        if deadline and time.monotonic() >= deadline:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait()
            sys.exit(TIMED_OUT)
        time.sleep(POLL_SECONDS)
    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
