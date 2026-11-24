"""Checks that quiet_probe.py notices a window, a taskbar flash, and sound, using signals too small to notice.

Usage: python self_test.py
Shows a 3x3 pixel window in the screen corner without activating it, flashes its taskbar button once, and plays
half a second of a -60 dB tone. Then clips the cursor to one pixel less than the screen, moves it one pixel and back,
hides it over a 3x3 window at the pointer, captures the mouse with that window, and nudges the mouse one pixel and
back with injected input (which must count as injected input, not as a program move). Then runs a silent,
windowless command and expects nothing.
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
    disturb_mouse()


def pump(user32, seconds):
    msg = wintypes.MSG()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.005)


def disturb_mouse():
    """One-pixel versions of each mouse disturbance: a clip one pixel short of the screen, a one-pixel cursor move
    and back, a cursor hidden over a 3x3 window at the pointer, and mouse capture by that window."""
    user32 = ctypes.WinDLL("user32")
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    user32.ClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
    user32.GetClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                       wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.SetCursor.argtypes = [wintypes.HANDLE]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
                                    wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    right, bottom = left + user32.GetSystemMetrics(78), top + user32.GetSystemMetrics(79)

    # Clip: the whole screen but its last column, for 0.2 s.
    previous = wintypes.RECT()
    user32.GetClipCursor(ctypes.byref(previous))
    user32.ClipCursor(ctypes.byref(wintypes.RECT(left, top, right - 1, bottom)))
    time.sleep(0.2)
    user32.ClipCursor(ctypes.byref(previous))
    time.sleep(0.1)

    # Hidden and capture: a 3x3 window under the pointer that clears the cursor shape.
    WndProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    def wnd_proc(hwnd, message, wparam, lparam):
        if message == 0x0020:  # WM_SETCURSOR
            user32.SetCursor(None)
            return 1
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    proc = WndProc(wnd_proc)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WndProc), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW(ctypes.byref(WNDCLASSW(lpfnWndProc=proc, lpszClassName="QuietProbeNoCursor")))
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    x, y = point.x, point.y
    step = 1 if x + 1 < right else -1
    WS_POPUP, WS_EX_NOACTIVATE, WS_EX_TOPMOST, WS_EX_TOOLWINDOW = 0x80000000, 0x08000000, 0x8, 0x80
    hwnd = user32.CreateWindowExW(WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW, "QuietProbeNoCursor", "",
                                  WS_POPUP, x - 1, y - 1, 3, 3, None, None, None, None)
    user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
    pump(user32, 0.05)

    # Move: one pixel and back. The moves also make Windows ask the window under the pointer for its cursor.
    user32.SetCursorPos(x + step, y)
    pump(user32, 0.1)
    user32.SetCursorPos(x, y)
    pump(user32, 0.2)

    user32.SetCapture(hwnd)
    pump(user32, 0.2)
    user32.ReleaseCapture()
    user32.DestroyWindow(hwnd)
    pump(user32, 0.3)
    nudge_mouse()


def nudge_mouse():
    """Injected relative mouse input, one pixel and back: real mouse movement, which must not count as a move."""
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]  # 40 bytes, as SendInput requires on x64

    user32 = ctypes.WinDLL("user32")
    for dx in (1, -1, 1, -1):
        item = INPUT(0, MOUSEINPUT(dx, 0, 0, 1, 0, 0))  # INPUT_MOUSE, MOUSEEVENTF_MOVE
        user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))
        time.sleep(0.1)


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
    mouse = loud["mouse"]
    # The clip covers almost the whole screen, so it cannot be tied to the test's window; any owner counts.
    if not any(e["kind"] == "clip" for e in mouse):
        failures.append("disturbing run: no mouse clip")
    for kind, wanted in (("move", 2), ("hidden", 1), ("capture", 1)):
        found = sum(1 for e in mouse if e["kind"] == kind and e["owner"] == "tree")
        if found < wanted:
            failures.append(f"disturbing run: {found} mouse {kind} tied to the test, expected {wanted}")
    # The injected nudges go through the mouse hook, so they count as injected input and not as program moves.
    if not any(e["kind"] == "injected" for e in mouse):
        failures.append("disturbing run: no injected mouse input")
    moves = sum(1 for e in mouse if e["kind"] == "move")
    if moves != 2:
        failures.append(f"disturbing run: {moves} program moves, expected exactly 2")

    quiet = probe([sys.executable, "-c", "import time; time.sleep(1)"])
    if quiet["events"] or quiet["onscreen"] or quiet["audio"] or quiet["mouse"]:
        failures.append("quiet run: probe reported something")

    for failure in failures:
        print("FAIL", failure)
    print("PASS" if not failures else "FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
