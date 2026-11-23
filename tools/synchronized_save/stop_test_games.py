"""Stops only game processes this suite started: PIDs from its launcher logs whose exe is inside the review folder."""
import ctypes
import re
import subprocess
from ctypes import wintypes as wt
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\synchronized-saving")
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.OpenProcess.restype = wt.HANDLE
kernel.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
kernel.CloseHandle.argtypes = (wt.HANDLE,)
kernel.QueryFullProcessImageNameW.argtypes = (wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD))


def image(pid):
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    buffer, size = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
    ok = kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
    kernel.CloseHandle(handle)
    return buffer.value if ok else None


def stop_all():
    stopped = 0
    logs = list((REVIEW / "test").glob("*/launcher.log")) + [REVIEW / "run" / "launcher.log"]
    for log in logs:
        if not log.exists():
            continue
        for pid in {int(p) for p in re.findall(r"started (?:UZDoom|Daggerfall Unity) pid (\d+)", log.read_text(errors="replace"))}:
            path = image(pid)
            if path and path.lower().startswith(str(REVIEW).lower() + "\\"):
                subprocess.call(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("stopped", pid, Path(path).name)
                stopped += 1
    return stopped


if __name__ == "__main__":
    print("stopped", stop_all(), "leftover test processes")
