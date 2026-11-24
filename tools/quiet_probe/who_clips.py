"""Watches the whole desktop and names the program behind each cursor clip.

Usage: python who_clips.py SECONDS [LOG_FILE]
Polls GetClipCursor every 2 ms. When the cursor gets confined, prints the clip rectangle, the foreground window's
process, and the process of the window under the clip's centre. A program can confine the cursor only while it is
on the user's desktop, and games do it for their focused window, so these name the culprit.
"""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
user32.GetForegroundWindow.restype = wintypes.HWND
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]


def describe(hwnd):
    if not hwnd:
        return "none"
    hwnd = user32.GetAncestor(hwnd, 2) or hwnd
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = ctypes.create_unicode_buffer(128)
    user32.GetWindowTextW(hwnd, title, 128)
    listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid.value}", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True).stdout.strip()
    return f"pid {pid.value} {listing.split(',')[0] if listing else '?'} title {title.value!r}"


EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]


def centred_on(x, y):
    """Every top-level window, shown or not, whose window or client rectangle is centred within 2 px of (x, y)."""
    found = []

    def visit(hwnd, _):
        rect, client, origin = wintypes.RECT(), wintypes.RECT(), wintypes.POINT()
        centres = []
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            centres.append(((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2))
        if user32.GetClientRect(hwnd, ctypes.byref(client)) and user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            centres.append((origin.x + client.right // 2, origin.y + client.bottom // 2))
        if any(abs(cx - x) <= 2 and abs(cy - y) <= 2 for cx, cy in centres) and rect.right - rect.left > 50:
            found.append(f"{describe(hwnd)} visible {bool(user32.IsWindowVisible(hwnd))} "
                         f"rect {(rect.left, rect.top, rect.right, rect.bottom)}")
        return True

    user32.EnumWindows(EnumWindowsProc(visit), 0)
    return found


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    if len(sys.argv) > 2:  # optional log file
        sys.stdout = open(sys.argv[2], "w", encoding="utf-8", buffering=1)
    screen = (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
              user32.GetSystemMetrics(76) + user32.GetSystemMetrics(78),
              user32.GetSystemMetrics(77) + user32.GetSystemMetrics(79))
    end, previous, start = time.monotonic() + seconds, None, time.monotonic()
    while time.monotonic() < end:
        rect = wintypes.RECT()
        user32.GetClipCursor(ctypes.byref(rect))
        clip = (rect.left, rect.top, rect.right, rect.bottom)
        if clip != previous:
            if clip != screen:
                centre = wintypes.POINT((clip[0] + clip[2]) // 2, (clip[1] + clip[3]) // 2)
                print(f"{time.monotonic() - start:7.3f}s clip {clip} foreground [{describe(user32.GetForegroundWindow())}] "
                      f"under centre [{describe(user32.WindowFromPoint(centre))}]", flush=True)
                for line in centred_on(centre.x, centre.y)[:8]:
                    print(f"         window centred there: {line}", flush=True)
            else:
                print(f"{time.monotonic() - start:7.3f}s clip released", flush=True)
            previous = clip
        time.sleep(0.002)


if __name__ == "__main__":
    main()
