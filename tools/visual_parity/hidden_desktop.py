"""Runs a program on a new desktop that nobody ever sees, with its window shown normally (not minimized) and never
activated, then returns its exit code.

usage: python hidden_desktop.py --timeout <seconds> -- <program> <args>

Always started through quiet_run.py (AGENTS.md), so it is itself on quiet_run's private desktop. quiet_run keeps the
windows on its desktop minimized, and a minimized Unity player gets no OnGUI Repaint, so Daggerfall Unity's IMGUI
windows are never drawn there. The launcher solves the same problem for the paired game by putting Daggerfall Unity on
a desktop of its own (launcher/main.cpp, "Daggerfall desktop"); this does the same for the capture player. Nothing on
either desktop can reach the owner's screen, focus, or mouse.
"""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

SW_SHOWNOACTIVATE = 4
STARTF_USESHOWWINDOW = 1
CREATE_DEFAULT_ERROR_MODE = 0x04000000
GENERIC_ALL = 0x10000000
INFINITE_WAIT_STEP_MS = 200

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.CreateDesktopW.restype = wintypes.HANDLE
user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD), ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


def main():
    args = sys.argv[1:]
    timeout = 300
    if args[:1] == ["--timeout"]:
        timeout = int(args[1])
        args = args[2:]
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        sys.exit(__doc__)
    name = f"doomerfall-vp-{kernel32.GetCurrentProcessId()}"
    desktop = user32.CreateDesktopW(name, None, None, 0, GENERIC_ALL, None)
    if not desktop:
        sys.exit(f"could not create the desktop: error {ctypes.get_last_error()}")
    startup = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop=name, dwFlags=STARTF_USESHOWWINDOW, wShowWindow=SW_SHOWNOACTIVATE)
    info = PROCESS_INFORMATION()
    line = ctypes.create_unicode_buffer(subprocess.list2cmdline(args))
    if not kernel32.CreateProcessW(None, line, None, None, False, CREATE_DEFAULT_ERROR_MODE, None, None, ctypes.byref(startup), ctypes.byref(info)):
        user32.CloseDesktop(desktop)
        sys.exit(f"could not start {args[0]}: error {ctypes.get_last_error()}")
    code = wintypes.DWORD(1)
    end = time.time() + timeout
    while kernel32.WaitForSingleObject(info.hProcess, INFINITE_WAIT_STEP_MS) != 0:
        if time.time() > end:
            print(f"hidden_desktop: {args[0]} timed out after {timeout} s; ended", file=sys.stderr)
            kernel32.TerminateProcess(info.hProcess, 124)
            kernel32.WaitForSingleObject(info.hProcess, 5000)
            break
    kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    kernel32.CloseHandle(info.hThread)
    kernel32.CloseHandle(info.hProcess)
    user32.CloseDesktop(desktop)
    return code.value


if __name__ == "__main__":
    sys.exit(main())
