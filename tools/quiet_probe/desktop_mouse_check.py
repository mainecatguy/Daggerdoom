"""Checks whether a program on a private desktop can still reach the user's mouse.

Usage: python desktop_mouse_check.py
Runs this file's helper on a private desktop (through quiet_run.py --desktop) twice: once to clip the cursor to one
pixel less than the screen for a second, once to move it one pixel and back. Prints what the helper's calls returned
and what the user's desktop saw.
"""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
QUIET_RUN = os.path.join(HERE, "..", "..", "scripts", "overnight", "quiet_run.py")
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
user32.ClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
user32.GetClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]


def clip_now():
    rect = wintypes.RECT()
    user32.GetClipCursor(ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def cursor_now():
    point = wintypes.POINT()
    ok = user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y) if ok else None


def helper(mode, out_path):
    width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    result = {"mode": mode}
    if mode == "clip":
        result["clip_ok"] = bool(user32.ClipCursor(ctypes.byref(wintypes.RECT(0, 0, width - 1, height))))
        result["clip_error"] = ctypes.get_last_error()
        result["seen_here"] = clip_now()
        time.sleep(1.0)
        user32.ClipCursor(None)
    else:
        # GetCursorPos fails on a private desktop, so the user's cursor position comes from the parent.
        x, y = (int(v) for v in mode.split(":")[1].split(","))
        result["start_seen_here"] = cursor_now()
        result["move_ok"] = bool(user32.SetCursorPos(x + 1, y))
        result["move_error"] = ctypes.get_last_error()
        time.sleep(1.0)
        if result["move_ok"]:
            user32.SetCursorPos(x, y)
    with open(out_path, "w", encoding="utf-8") as out:
        json.dump(result, out)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--helper":
        helper(sys.argv[2], sys.argv[3])
        return 0
    with tempfile.TemporaryDirectory() as folder:
        for mode in ("clip", "move"):
            out_path = os.path.join(folder, mode + ".json")
            before_clip, before_cursor = clip_now(), cursor_now()
            if mode == "move":
                mode = f"move:{before_cursor[0]},{before_cursor[1]}"
            child = subprocess.Popen([sys.executable, QUIET_RUN, "--desktop", "--timeout", "20", "--", sys.executable,
                                      os.path.abspath(__file__), "--helper", mode, out_path])
            seen_clips, seen_cursors = set(), set()
            while child.poll() is None:
                seen_clips.add(clip_now())
                seen_cursors.add(cursor_now())
                time.sleep(0.01)
            with open(out_path, encoding="utf-8") as data:
                result = json.load(data)
            print(f"{mode}: helper {result}")
            print(f"{mode}: user desktop clip before {before_clip}, seen during {sorted(seen_clips)}")
            print(f"{mode}: user desktop cursor before {before_cursor}, seen during {len(seen_cursors)} positions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
