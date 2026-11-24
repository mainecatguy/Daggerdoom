"""Checks that quiet_probe.py notices a window, a taskbar flash, and sound, using signals too small to notice.

Usage: python self_test.py
Shows a 3x3 pixel window in the screen corner without activating it, flashes its taskbar button once, and plays
half a second of a -60 dB tone. Then runs a silent, windowless command and expects nothing.
Exits 0 when the probe reports exactly what was expected.
"""
import ctypes
import io
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave
import winsound
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "quiet_probe.py")


def disturb():
    user32 = ctypes.WinDLL("user32")
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                       wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    WS_POPUP = 0x80000000
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_APPWINDOW = 0x00040000
    hwnd = user32.CreateWindowExW(WS_EX_NOACTIVATE | WS_EX_APPWINDOW, "STATIC", "quiet probe self test", WS_POPUP,
                                  0, 0, 3, 3, None, None, None, None)
    user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

    user32.FlashWindowEx.argtypes = [ctypes.POINTER(FLASHWINFO)]
    flash = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 2, 1, 0)  # FLASHW_TRAY, once
    user32.FlashWindowEx(ctypes.byref(flash))

    rate = 44100
    samples = b"".join(struct.pack("<h", int(32767 * 0.001 * math.sin(2 * math.pi * 440 * i / rate)))
                       for i in range(rate // 2))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples)
    winsound.PlaySound(buffer.getvalue(), winsound.SND_MEMORY)
    time.sleep(0.3)
    user32.DestroyWindow(hwnd)


def probe(command):
    with tempfile.TemporaryDirectory() as folder:
        report = os.path.join(folder, "report.json")
        subprocess.run([sys.executable, PROBE, "--json", report, "--timeout", "30", "--"] + command)
        with open(report, encoding="utf-8") as data:
            return json.load(data)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--disturb":
        disturb()
        return 0
    failures = []
    loud = probe([sys.executable, os.path.abspath(__file__), "--disturb"])
    kinds = {e["kind"] for e in loud["events"]}
    for kind in ("shown", "flash"):
        if kind not in kinds:
            failures.append(f"disturbing run: no {kind} event")
    if "focus" in kinds:
        failures.append("disturbing run: unexpected focus event")
    if not loud["onscreen"]:
        failures.append("disturbing run: window not found on screen")
    if not any(a["max_peak"] > 0.0001 for a in loud["audio"].values()):
        failures.append("disturbing run: no audible session")

    quiet = probe([sys.executable, "-c", "import time; time.sleep(1)"])
    if quiet["events"] or quiet["onscreen"] or quiet["audio"]:
        failures.append("quiet run: probe reported something")

    for failure in failures:
        print("FAIL", failure)
    print("PASS" if not failures else "FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
