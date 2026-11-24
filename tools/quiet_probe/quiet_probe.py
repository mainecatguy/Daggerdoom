"""Run a command and report whether it, or anything it starts, disturbs the desktop.

Usage: python quiet_probe.py [--json FILE] [--timeout SECONDS] -- PROGRAM [ARGS...]

Watches the command's process tree for:
  shown     a top-level window shown on screen and not minimized, even for a moment
  onscreen  a window found on screen and not minimized by the 50 ms poll
  focus     a window of the tree that became the foreground window
  flash     a taskbar flash request (HSHELL_FLASH)
  audio     a Windows audio session, and its peak level (above 0 means real sound)

and, for the whole desktop (the mouse is shared, so these are tagged "tree" when they can be tied to the
command's windows, otherwise "other"):
  clip      the cursor confined to less than the whole screen (GetClipCursor)
  move      the cursor moved with no mouse input behind it (SetCursorPos and the like): a cursor change with no
            low-level mouse event (WH_MOUSE_LL) since the previous 4 ms sample or in the last 50 ms. A program
            move made while the mouse itself is moving is missed.
  hidden    the cursor hidden (GetCursorInfo)
  capture   a window of the tree, or the foreground thread, holding mouse capture (GetGUIThreadInfo)
  injected  synthetic mouse input (SendInput, mouse_event): it moves the user's real pointer
Raw input registrations (RIDEV_NOLEGACY, RIDEV_CAPTUREMOUSE) of other processes cannot be read; their effect only
reaches the user through focus, which is checked.

Exits with the command's exit code. Prints a summary to stderr and writes details to --json.
--timeout ends the whole tree and exits with 124.
"""
import argparse
import ctypes
import json
import subprocess
import sys
import threading
import time
from ctypes import wintypes

TIMED_OUT = 124
POLL_SECONDS = 0.05
AUDIBLE_PEAK = 0.0001

MOUSE_POLL_SECONDS = 0.004

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32")
dwmapi = ctypes.WinDLL("dwmapi")
# Physical pixels everywhere, so cursor, clip and window rectangles agree on scaled monitors.
user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2

HWINEVENTHOOK = wintypes.HANDLE
WinEventProc = ctypes.WINFUNCTYPE(None, HWINEVENTHOOK, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
                                  wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
WndProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.SetWinEventHook.restype = HWINEVENTHOOK
user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WinEventProc,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                   wintypes.HINSTANCE, wintypes.LPVOID]
user32.RegisterShellHookWindow.argtypes = [wintypes.HWND]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WndProc), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE),
                ("ptScreenPos", wintypes.POINT)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_SYSTEM_MINIMIZEEND = 0x0017
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0
GA_ROOT = 2
HSHELL_FLASH = 0x8006
WM_QUIT = 0x0012
DWMWA_CLOAKED = 14


def creation_time(pid):
    """A process's creation time, or None. It tells a reused pid from the process that first had it."""
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    times = [wintypes.FILETIME() for _ in range(4)]
    ok = kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
    kernel32.CloseHandle(handle)
    return (times[0].dwHighDateTime << 32 | times[0].dwLowDateTime) if ok else None


class Tree:
    """The command's process tree, refreshed from process snapshots. Pids seen once stay members.
    A child must start after its parent, so a pid reused by an unrelated process does not pull it in."""

    def __init__(self, root):
        self.lock = threading.Lock()
        self.members = {root: "?"}
        self.created = {root: creation_time(root)}
        self.start = time.monotonic()
        self.lifetimes = {root: [0.0, None]}  # pid -> [first seen, gone] in seconds from the start

    def _same(self, pid):
        known = self.created.get(pid)
        now = creation_time(pid)
        return known is None or now is None or known == now

    def refresh(self):
        snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
        if snap in (None, wintypes.HANDLE(-1).value):
            return
        entries = []
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            entries.append((entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
        kernel32.CloseHandle(snap)
        with self.lock:
            for pid, _, exe in entries:
                if pid in self.members and self._same(pid):
                    self.members[pid] = exe
            grew = True
            while grew:
                grew = False
                for pid, parent, exe in entries:
                    if parent in self.members and pid not in self.members and self._same(parent):
                        parent_time, child_time = self.created.get(parent), creation_time(pid)
                        if parent_time and child_time and child_time < parent_time:
                            continue
                        self.members[pid] = exe
                        self.created[pid] = child_time
                        self.lifetimes[pid] = [round(time.monotonic() - self.start, 3), None]
                        grew = True
            alive = {pid for pid, _, _ in entries}
            for pid, life in self.lifetimes.items():
                if life[1] is None and pid not in alive:
                    life[1] = round(time.monotonic() - self.start, 3)

    def name(self, pid):
        with self.lock:
            if pid not in self.members or not self._same(pid):
                return None
            return self.members[pid]


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_text(func, hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    func(hwnd, buffer, 256)
    return buffer.value


def on_screen(hwnd):
    """True when a top-level window can be seen: visible, not minimized or cloaked, and over a monitor."""
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    cloaked = wintypes.DWORD()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
        return False
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or rect.right - rect.left < 2 or rect.bottom - rect.top < 2:
        return False
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    right, bottom = left + user32.GetSystemMetrics(78), top + user32.GetSystemMetrics(79)
    return rect.left < right and rect.right > left and rect.top < bottom and rect.bottom > top


def virtual_screen():
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    return (left, top, left + user32.GetSystemMetrics(78), top + user32.GetSystemMetrics(79))


def rect_tuple(rect):
    return (rect.left, rect.top, rect.right, rect.bottom)


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                ("ptMinPosition", wintypes.POINT), ("ptMaxPosition", wintypes.POINT),
                ("rcNormalPosition", wintypes.RECT)]


EnumDesktopsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.LPWSTR, wintypes.LPARAM)
user32.EnumDesktopsW.argtypes = [wintypes.HANDLE, EnumDesktopsProc, wintypes.LPARAM]
user32.GetProcessWindowStation.restype = wintypes.HANDLE
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, EnumWindowsProc, wintypes.LPARAM]
user32.CloseDesktop.argtypes = [wintypes.HANDLE]
user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]


def other_desktop_windows():
    """Top-level windows on the window station's other desktops (private desktops of quiet_run and the launcher)."""
    names = []
    user32.EnumDesktopsW(user32.GetProcessWindowStation(), EnumDesktopsProc(lambda name, _: names.append(name) or True),
                         0)
    found = []
    for name in names:
        if name.lower() in ("default", "winlogon", "disconnect"):
            continue
        desktop = user32.OpenDesktopW(name, 0, False, 0x0001 | 0x0040)  # DESKTOP_READOBJECTS | DESKTOP_ENUMERATE
        if desktop:
            user32.EnumDesktopWindows(desktop, EnumWindowsProc(lambda hwnd, _: found.append(hwnd) or True), 0)
            user32.CloseDesktop(desktop)
    return found


def window_rects(hwnd):
    """The window, client, and restored (for a minimized window) rectangles of a window, in screen pixels."""
    found = []
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        found.append(rect_tuple(rect))
    placement = WINDOWPLACEMENT(length=ctypes.sizeof(WINDOWPLACEMENT))
    if user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
        found.append(rect_tuple(placement.rcNormalPosition))
    client = wintypes.RECT()
    origin = wintypes.POINT(0, 0)
    if user32.GetClientRect(hwnd, ctypes.byref(client)) and user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        found.append((origin.x, origin.y, origin.x + client.right, origin.y + client.bottom))
    return found


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


LowLevelMouseProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, LowLevelMouseProc, wintypes.HINSTANCE, wintypes.DWORD]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
LLMHF_INJECTED = 1
MOUSE_SETTLE_SECONDS = 0.05


class MouseInput:
    """Low-level mouse hook on its own thread. It only notes when mouse movement arrived, so the user's mouse is
    not slowed; the hook is skipped by Windows if it ever stalls (LowLevelHooksTimeout)."""

    def __init__(self):
        self.count = 0  # low-level mouse move events so far
        self.last = -1.0  # monotonic time of the latest one
        self.injected = []  # monotonic times of injected movement (SendInput, mouse_event)
        self.ok = False
        self.thread_id = None
        ready = threading.Event()
        threading.Thread(target=self.run, args=(ready,), daemon=True).start()
        ready.wait(5)

    def run(self, ready):
        self.thread_id = kernel32.GetCurrentThreadId()

        def on_mouse(code, wparam, lparam):
            if code == 0 and wparam == WM_MOUSEMOVE:
                info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                now = time.monotonic()
                self.count += 1
                self.last = now
                if info.flags & LLMHF_INJECTED:
                    self.injected.append(now)
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._proc = LowLevelMouseProc(on_mouse)
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        self.ok = bool(hook)
        ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        if hook:
            user32.UnhookWindowsHookEx(hook)

    def stop(self):
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class Probe:
    def __init__(self, tree, start):
        self.tree = tree
        self.start = start
        self.lock = threading.Lock()
        self.events = []
        self.onscreen = {}
        self.audio = {}
        self.mouse = []
        self.tree_windows = {}  # hwnd -> (pid, thread id) on this desktop, refreshed by poll_windows
        self.private_windows = []  # the tree's windows on other (private) desktops
        self.stopping = threading.Event()

    # Mouse: the cursor is shared by the whole desktop, so these watch globally and tag what can be tied to the tree.
    def tree_hwnd(self, hwnd):
        if not hwnd:
            return False
        root = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
        return self.tree.name(window_pid(root)) is not None

    def owner(self, point=None, rect=None):
        if self.tree_hwnd(user32.GetForegroundWindow()):
            return "tree"
        if point is not None and self.tree_hwnd(user32.WindowFromPoint(wintypes.POINT(*point))):
            return "tree"
        if rect is not None:
            with self.lock:
                hwnds = list(self.tree_windows) + list(self.private_windows)
            center = ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
            for hwnd in hwnds:
                for candidate in window_rects(hwnd):
                    if all(abs(a - b) <= 2 for a, b in zip(candidate, rect)):
                        return "tree"
                    # A locked game cursor is a one-point clip at the centre of the game's window.
                    middle = ((candidate[0] + candidate[2]) // 2, (candidate[1] + candidate[3]) // 2)
                    if abs(middle[0] - center[0]) <= 2 and abs(middle[1] - center[1]) <= 2:
                        return "tree"
            if self.tree_hwnd(user32.WindowFromPoint(wintypes.POINT(*center))):
                return "tree"
        return "other"

    def mouse_event(self, kind, owner, **extra):
        event = {"t": round(time.monotonic() - self.start, 3), "kind": kind, "owner": owner}
        event.update(extra)
        with self.lock:
            self.mouse.append(event)
        return event

    def watch_mouse(self, mouse_input):
        screen = virtual_screen()
        last = None
        clip = hidden = None
        injected_seen = 0
        moves_seen = mouse_input.count
        while not self.stopping.is_set():
            now = round(time.monotonic() - self.start, 3)
            point = wintypes.POINT()
            # The hook runs before Windows moves the cursor, so read its count first: a cursor change with no
            # mouse event since the previous sample, nor in the last 50 ms, was made by a program (SetCursorPos
            # makes no mouse event). The 50 ms covers small cursor steps seen without a hook event while the
            # mouse is in use (measured: about one a second, 1 to 3 pixels).
            moves_now = mouse_input.count
            quiet_mouse = time.monotonic() - mouse_input.last > MOUSE_SETTLE_SECONDS
            if user32.GetCursorPos(ctypes.byref(point)):
                current = (point.x, point.y)
                if last is not None and current != last and moves_now == moves_seen and quiet_mouse:
                    # rect: a move to a tree window's centre (a one-point clip drags the cursor there) is the tree's.
                    self.mouse_event("move", self.owner(point=current, rect=current + current), to=current, frm=last)
                last = current
            moves_seen = moves_now
            if len(mouse_input.injected) > injected_seen:
                injected_seen = len(mouse_input.injected)
                episode = next((e for e in reversed(self.mouse) if e["kind"] == "injected"), None)
                if episode and now - episode["until"] < 0.5:
                    episode["until"] = now
                else:
                    self.mouse_event("injected", self.owner(point=last), until=now)
            rect = wintypes.RECT()
            if user32.GetClipCursor(ctypes.byref(rect)):
                confined = rect_tuple(rect)
                if confined != screen and clip is None:
                    clip = self.mouse_event("clip", self.owner(point=last, rect=confined), rect=confined, until=now)
                elif confined != screen:
                    clip["until"] = now
                elif clip is not None:
                    clip = None
            info = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
            if user32.GetCursorInfo(ctypes.byref(info)):
                gone = not (info.flags & 1) or not info.hCursor
                if gone and hidden is None:
                    hidden = self.mouse_event("hidden", self.owner(point=last), until=now)
                elif gone:
                    hidden["until"] = now
                elif hidden is not None:
                    hidden = None
            time.sleep(MOUSE_POLL_SECONDS)

    def poll_capture(self):
        """Mouse capture held by any thread that owns a window of the tree, or by the foreground thread."""
        with self.lock:
            threads = {tid: pid for pid, tid in self.tree_windows.values()}
        threads.setdefault(0, None)
        for tid, pid in threads.items():
            info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
            if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)) or not info.hwndCapture:
                continue
            if not self.tree_hwnd(info.hwndCapture):
                continue
            hwnd = info.hwndCapture
            now = round(time.monotonic() - self.start, 3)
            with self.lock:
                open_episode = next((e for e in self.mouse if e["kind"] == "capture" and e["hwnd"] == hex(hwnd)
                                     and now - e["until"] < 0.2), None)
                if open_episode:
                    open_episode["until"] = now
                    continue
            self.mouse_event("capture", "tree", hwnd=hex(hwnd), pid=window_pid(hwnd),
                             exe=self.tree.name(window_pid(hwnd)), cls=window_text(user32.GetClassNameW, hwnd),
                             until=now)

    def record(self, kind, hwnd, pid, **extra):
        exe = self.tree.name(pid)
        if exe is None:
            return
        event = {"t": round(time.monotonic() - self.start, 3), "kind": kind, "pid": pid, "exe": exe}
        if hwnd:
            event.update(hwnd=hex(hwnd), cls=window_text(user32.GetClassNameW, hwnd),
                         title=window_text(user32.GetWindowTextW, hwnd))
        event.update(extra)
        with self.lock:
            self.events.append(event)

    # Window events and taskbar flashes, on one thread with a message loop.
    def watch_windows(self, ready):
        self.thread_id = kernel32.GetCurrentThreadId()

        def on_event(_hook, event, hwnd, id_object, id_child, _thread, _time):
            if not hwnd or id_object != 0 or id_child != 0 or user32.GetAncestor(hwnd, GA_ROOT) != hwnd:
                return
            pid = window_pid(hwnd)
            if self.tree.name(pid) is None:
                self.tree.refresh()
            if event == EVENT_SYSTEM_FOREGROUND:
                self.record("focus", hwnd, pid)
            elif on_screen(hwnd):
                self.record("shown", hwnd, pid)

        self._event_proc = WinEventProc(on_event)
        hooks = [user32.SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, None, self._event_proc, 0, 0,
                                        WINEVENT_OUTOFCONTEXT),
                 user32.SetWinEventHook(EVENT_SYSTEM_MINIMIZEEND, EVENT_SYSTEM_MINIMIZEEND, None, self._event_proc, 0,
                                        0, WINEVENT_OUTOFCONTEXT),
                 user32.SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW, None, self._event_proc, 0, 0,
                                        WINEVENT_OUTOFCONTEXT)]

        shell_message = user32.RegisterWindowMessageW("SHELLHOOK")

        def wnd_proc(hwnd, message, wparam, lparam):
            if message == shell_message and wparam == HSHELL_FLASH and lparam:
                target = wintypes.HWND(lparam).value
                pid = window_pid(target)
                if self.tree.name(pid) is None:
                    self.tree.refresh()
                self.record("flash", target, pid)
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._wnd_proc = WndProc(wnd_proc)
        window_class = WNDCLASSW(lpfnWndProc=self._wnd_proc, lpszClassName="QuietProbeShellHook")
        user32.RegisterClassW(ctypes.byref(window_class))
        listener = user32.CreateWindowExW(0, "QuietProbeShellHook", "quiet probe", 0, 0, 0, 0, 0, None, None, None,
                                          None)
        shell_hooked = bool(listener and user32.RegisterShellHookWindow(listener))
        self.hooks_ok = all(hooks) and shell_hooked
        ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop_windows(self):
        user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)

    def poll_windows(self):
        now = round(time.monotonic() - self.start, 3)
        found = {}

        def visit(hwnd, _):
            pid = wintypes.DWORD()
            tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid = pid.value
            exe = self.tree.name(pid)
            if exe is not None:
                found[hwnd] = (pid, tid)
            if exe is not None and on_screen(hwnd):
                key = (pid, hwnd)
                with self.lock:
                    if key not in self.onscreen:
                        self.onscreen[key] = {"first": now, "last": now, "pid": pid, "exe": exe, "hwnd": hex(hwnd),
                                              "cls": window_text(user32.GetClassNameW, hwnd),
                                              "title": window_text(user32.GetWindowTextW, hwnd)}
                    self.onscreen[key]["last"] = now
            return True

        user32.EnumWindows(EnumWindowsProc(visit), 0)
        # Windows on private desktops cannot be seen, but a clip they make still reaches the user's pointer.
        private = []
        for hwnd in other_desktop_windows():
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if self.tree.name(pid.value) is not None:
                private.append(hwnd)
        with self.lock:
            self.tree_windows = found
            self.private_windows = private
        self.poll_capture()

    def poll_audio(self, sessions):
        now = round(time.monotonic() - self.start, 3)
        for pid, state, peak in sessions():
            exe = self.tree.name(pid)
            if exe is None:
                continue
            with self.lock:
                entry = self.audio.setdefault(pid, {"exe": exe, "first": now, "max_peak": 0.0, "active_s": 0.0,
                                                    "audible_s": 0.0})
                entry["max_peak"] = max(entry["max_peak"], peak)
                if state == 1:
                    entry["active_s"] = round(entry["active_s"] + POLL_SECONDS, 3)
                if peak > AUDIBLE_PEAK:
                    entry["audible_s"] = round(entry["audible_s"] + POLL_SECONDS, 3)


# Core Audio through raw COM vtables, so no extra packages are needed.
class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text):
        super().__init__()
        ole32.CLSIDFromString(ctypes.c_wchar_p("{" + text + "}"), ctypes.byref(self))


CLSID_MMDeviceEnumerator = GUID("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioSessionManager2 = GUID("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F")
IID_IAudioSessionControl2 = GUID("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D")
IID_IAudioMeterInformation = GUID("C02216F6-8C67-4B5B-9D00-D008E73E0064")


def com_call(obj, index, *args, argtypes=()):
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])(obj, *args)


def release(obj):
    if obj:
        com_call(obj, 2)


def audio_sessions_reader():
    """Returns a function that lists (pid, state, peak) for every session on every active output device."""
    ole32.CoInitializeEx(None, 0)
    enumerator = ctypes.c_void_p()
    if ole32.CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, 23, ctypes.byref(IID_IMMDeviceEnumerator),
                              ctypes.byref(enumerator)) != 0:
        return None
    managers = []
    devices = ctypes.c_void_p()
    if com_call(enumerator, 3, 0, 1, ctypes.byref(devices),
                argtypes=(ctypes.c_int, wintypes.DWORD, ctypes.c_void_p)) == 0:
        count = wintypes.UINT()
        com_call(devices, 3, ctypes.byref(count), argtypes=(ctypes.c_void_p,))
        for i in range(count.value):
            device = ctypes.c_void_p()
            if com_call(devices, 4, i, ctypes.byref(device), argtypes=(wintypes.UINT, ctypes.c_void_p)) != 0:
                continue
            manager = ctypes.c_void_p()
            if com_call(device, 3, ctypes.byref(IID_IAudioSessionManager2), 23, None, ctypes.byref(manager),
                        argtypes=(ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p)) == 0:
                managers.append(manager)
            release(device)
        release(devices)

    def sessions():
        found = []
        for manager in managers:
            listing = ctypes.c_void_p()
            if com_call(manager, 5, ctypes.byref(listing), argtypes=(ctypes.c_void_p,)) != 0:
                continue
            count = ctypes.c_int()
            com_call(listing, 3, ctypes.byref(count), argtypes=(ctypes.c_void_p,))
            for i in range(count.value):
                control = ctypes.c_void_p()
                if com_call(listing, 4, i, ctypes.byref(control), argtypes=(ctypes.c_int, ctypes.c_void_p)) != 0:
                    continue
                control2, meter = ctypes.c_void_p(), ctypes.c_void_p()
                pid, state, peak = wintypes.DWORD(), ctypes.c_int(), ctypes.c_float()
                if com_call(control, 0, ctypes.byref(IID_IAudioSessionControl2), ctypes.byref(control2),
                            argtypes=(ctypes.c_void_p, ctypes.c_void_p)) == 0:
                    com_call(control2, 14, ctypes.byref(pid), argtypes=(ctypes.c_void_p,))
                    com_call(control2, 3, ctypes.byref(state), argtypes=(ctypes.c_void_p,))
                    if com_call(control, 0, ctypes.byref(IID_IAudioMeterInformation), ctypes.byref(meter),
                                argtypes=(ctypes.c_void_p, ctypes.c_void_p)) == 0:
                        com_call(meter, 3, ctypes.byref(peak), argtypes=(ctypes.c_void_p,))
                    if pid.value:
                        found.append((pid.value, state.value, peak.value))
                release(meter)
                release(control2)
                release(control)
            release(listing)
        return found

    return sessions


def link_clips_to_exits(probe):
    """Windows on private desktops cannot be queried, so a clip they make looks like another program's. A clip that
    ends within half a second of one of the tree's processes exiting is marked with that process (ended_with)."""
    for event in probe.mouse:
        if event["kind"] != "clip" or event["owner"] == "tree":
            continue
        for pid, (first, gone) in probe.tree.lifetimes.items():
            if gone is not None and first <= event["t"] and abs(gone - event["until"]) <= 0.5:
                event["ended_with"] = f"{probe.tree.members.get(pid, '?')} pid {pid}"


def summarize(probe, exit_code, timed_out):
    link_clips_to_exits(probe)
    events = probe.events
    lines = [f"quiet_probe: exit {exit_code}{' (timed out)' if timed_out else ''}"]
    if not getattr(probe, "hooks_ok", False):
        lines.append("quiet_probe: WARNING some window or shell hooks failed; window results may be incomplete")
    if not getattr(probe, "mouse_hook_ok", False):
        lines.append("quiet_probe: WARNING mouse hook failed; every cursor change will look like a program move")
    if probe.audio_ok is False:
        lines.append("quiet_probe: WARNING could not read audio sessions")
    for kind in ("shown", "focus", "flash"):
        hits = [e for e in events if e["kind"] == kind]
        lines.append(f"quiet_probe: {kind}: {len(hits)}")
        for e in hits[:10]:
            lines.append(f"  {e['t']:8.3f}s {e['exe']} pid {e['pid']} class {e.get('cls', '')!r} title {e.get('title', '')!r}")
    lines.append(f"quiet_probe: onscreen: {len(probe.onscreen)}")
    for w in list(probe.onscreen.values())[:10]:
        lines.append(f"  {w['first']:8.3f}-{w['last']:.3f}s {w['exe']} pid {w['pid']} class {w['cls']!r} title {w['title']!r}")
    audible = {pid: a for pid, a in probe.audio.items() if a["max_peak"] > AUDIBLE_PEAK}
    lines.append(f"quiet_probe: audio sessions: {len(probe.audio)}, audible: {len(audible)}")
    for pid, a in probe.audio.items():
        lines.append(f"  {a['exe']} pid {pid} max peak {a['max_peak']:.4f}, active {a['active_s']}s, audible {a['audible_s']}s")
    for kind in MOUSE_KINDS:
        hits = [e for e in probe.mouse if e["kind"] == kind]
        mine = [e for e in hits if e["owner"] == "tree"]
        lines.append(f"quiet_probe: mouse {kind}: {len(mine)} (other programs: {len(hits) - len(mine)})")
        for e in hits[:10]:
            detail = {k: v for k, v in e.items() if k not in ("t", "kind")}
            lines.append(f"  {e['t']:8.3f}s {detail}")
    return lines


MOUSE_KINDS = ("clip", "move", "hidden", "capture", "injected")


def counts(probe):
    """One number per check, counting only what is tied to the command's tree. The table in the notes uses this."""
    result = {kind: sum(1 for e in probe.events if e["kind"] == kind) for kind in ("shown", "focus", "flash")}
    result["onscreen"] = len(probe.onscreen)
    result["audible"] = sum(1 for a in probe.audio.values() if a["max_peak"] > AUDIBLE_PEAK)
    for kind in MOUSE_KINDS:
        result[kind] = sum(1 for e in probe.mouse if e["kind"] == kind and e["owner"] == "tree")
        result[kind + "_other"] = sum(1 for e in probe.mouse if e["kind"] == kind and e["owner"] != "tree")
    result["clip_ended_with_tree_exit"] = sum(1 for e in probe.mouse if e.get("ended_with"))
    return result


def main():
    argv = sys.argv[1:]
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        sys.exit(__doc__)
    split = argv.index("--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--json")
    parser.add_argument("--timeout", type=float)
    options = parser.parse_args(argv[:split])

    start = time.monotonic()
    process = subprocess.Popen(argv[split + 1:])
    tree = Tree(process.pid)
    probe = Probe(tree, start)
    ready = threading.Event()
    threading.Thread(target=probe.watch_windows, args=(ready,), daemon=True).start()
    ready.wait(5)
    mouse_input = MouseInput()
    probe.mouse_hook_ok = mouse_input.ok
    mouse_thread = threading.Thread(target=probe.watch_mouse, args=(mouse_input,), daemon=True)
    mouse_thread.start()

    sessions = audio_sessions_reader()
    probe.audio_ok = sessions is not None
    deadline = start + options.timeout if options.timeout else None
    timed_out = False
    while process.poll() is None:
        tree.refresh()
        probe.poll_windows()
        if sessions:
            probe.poll_audio(sessions)
        if deadline and time.monotonic() >= deadline:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait()
            timed_out = True
            break
        time.sleep(POLL_SECONDS)
    tree.refresh()  # notes when the last processes exited
    probe.stop_windows()
    probe.stopping.set()
    mouse_thread.join(1)
    mouse_input.stop()
    exit_code = TIMED_OUT if timed_out else process.returncode

    for line in summarize(probe, exit_code, timed_out):
        print(line, file=sys.stderr)
    if options.json:
        with open(options.json, "w", encoding="utf-8") as out:
            json.dump({"exit": exit_code, "timed_out": timed_out, "events": probe.events,
                       "onscreen": list(probe.onscreen.values()), "mouse": probe.mouse,
                       "counts": counts(probe),
                       "audio": {str(pid): a for pid, a in probe.audio.items()},
                       "processes": dict((str(k), v) for k, v in tree.members.items()),
                       "lifetimes": dict((str(k), v) for k, v in tree.lifetimes.items())}, out, indent=1)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
