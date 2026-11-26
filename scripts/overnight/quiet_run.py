"""Run a program, and everything it starts, where the user can never see, hear, or feel it.

Usage: python quiet_run.py [--timeout SECONDS] [--cwd DIR] [--user-desktop] [--sound] -- PROGRAM [ARGS...]
Exits with the program's exit code, or 124 if it timed out.

By default the program runs on a private desktop the user never sees, started minimized and kept minimized there
(so games render exactly as they did minimized on the user's desktop). Nothing on a private desktop can show a
window, take focus, flash the taskbar, or touch the mouse: Windows refuses ClipCursor and SetCursorPos from it.
It also adds, when missing:
  uzdoom.exe            +vid_fullscreen 0, -noactivate (no crash dialogs), -nosound, and Doomerfall's graphics
                        settings (architecture.md, Graphics) so screenshots and frame times match what players see
  DaggerfallUnity.exe   -dfmute
--sound leaves sound on. --user-desktop runs on the user's desktop, minimized and pushed out of focus, as before;
use it only for something that cannot work on a private desktop, and say why.
--desktop is accepted for older callers and changes nothing (it is the default).
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
user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, EnumWindowsProc, wintypes.LPARAM]
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


def minimize_windows(pid, desktop=None):
    def visit(hwnd, _):
        if window_pid(hwnd) == pid and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
        return True

    if desktop:
        user32.EnumDesktopWindows(desktop, EnumWindowsProc(visit), 0)
    else:
        user32.EnumWindows(EnumWindowsProc(visit), 0)


def keep_quiet(pid, previous):
    minimize_windows(pid)
    foreground = user32.GetForegroundWindow()
    if previous and foreground and foreground != previous and window_pid(foreground) == pid:
        user32.SetForegroundWindow(previous)


class DesktopProcess:
    """A process started minimized on a new private desktop, with the small part of the Popen interface used here."""

    def __init__(self, command, cwd):
        self.name = f"quiet-run-{os.getpid()}"
        self.desktop = user32.CreateDesktopW(self.name, None, None, 0, 0x10000000, None)  # GENERIC_ALL
        if not self.desktop:
            raise OSError(f"could not create a private desktop (error {ctypes.get_last_error()})")
        startup = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop=self.name, dwFlags=1,  # STARTF_USESHOWWINDOW
                               wShowWindow=SW_SHOWMINNOACTIVE)
        info = PROCESS_INFORMATION()
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        if not kernel32.CreateProcessW(None, line, None, None, True, 0, None, cwd, ctypes.byref(startup),
                                       ctypes.byref(info)):
            raise OSError(f"could not start {command[0]} (error {ctypes.get_last_error()})")
        kernel32.CloseHandle(info.hThread)
        self.handle, self.pid, self.returncode = info.hProcess, info.dwProcessId, None

    def keep_quiet(self):
        """Keeps the program's own windows minimized, as on the user's desktop, so games render at the same size."""
        if self.returncode is None:
            minimize_windows(self.pid, self.desktop)

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


# Doomerfall's graphics settings (architecture.md, Graphics). The launcher adds the same.
GRAPHICS = ["+gl_bloom", "1", "+gl_light_shadowmap", "1", "+gl_ssao", "2", "+gl_lens", "1"]


def quiet_arguments(command, sound):
    """Adds the known quiet switches for the programs agents start, when the caller left them out."""
    name = os.path.basename(command[0]).lower()
    if name.endswith(".exe"):
        name = name[:-4]
    added = []
    if name == "uzdoom":
        if "+vid_fullscreen" not in command:
            added += ["+vid_fullscreen", "0"]
        if "-noactivate" not in command:
            added.append("-noactivate")
        if not sound and "-nosound" not in command:
            added.append("-nosound")
        for i in range(0, len(GRAPHICS), 2):
            if GRAPHICS[i] not in command:
                added += GRAPHICS[i:i + 2]
    elif name == "daggerfallunity" and not sound and "-dfmute" not in command:
        added.append("-dfmute")
    return command[:1] + added + command[1:]


def main():
    argv = sys.argv[1:]
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        sys.exit(__doc__)
    split = argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--cwd")
    parser.add_argument("--desktop", action="store_true", help="the default; kept for older callers")
    parser.add_argument("--user-desktop", action="store_true")
    parser.add_argument("--sound", action="store_true")
    options = parser.parse_args(argv[:split])

    previous = user32.GetForegroundWindow()
    command = quiet_arguments(argv[split + 1:], options.sound)
    private = not options.user_desktop
    if private:
        process = DesktopProcess(command, options.cwd)
    else:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = SW_SHOWMINNOACTIVE
        process = subprocess.Popen(command, cwd=options.cwd, startupinfo=startup)
    print(f"quiet_run: pid {process.pid}{' on a private desktop' if private else ''}", file=sys.stderr, flush=True)

    deadline = time.monotonic() + options.timeout if options.timeout else None
    while process.poll() is None:
        if private:
            process.keep_quiet()
        else:
            keep_quiet(process.pid, previous)
        if deadline and time.monotonic() >= deadline:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait()
            sys.exit(TIMED_OUT)
        time.sleep(POLL_SECONDS)
    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
