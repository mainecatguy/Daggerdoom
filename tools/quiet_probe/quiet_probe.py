"""Run a command and report whether it, or anything it starts, disturbs the desktop.

Usage: python quiet_probe.py [--json FILE] [--timeout SECONDS] -- PROGRAM [ARGS...]

Watches the command's process tree for:
  shown     a top-level window shown on screen and not minimized, even for a moment
  onscreen  a window found on screen and not minimized by the 50 ms poll
  focus     a window of the tree that became the foreground window
  flash     a taskbar flash request (HSHELL_FLASH)
  audio     a Windows audio session, and its peak level (above 0 means real sound)

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

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32")
dwmapi = ctypes.WinDLL("dwmapi")

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


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
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


class Tree:
    """The command's process tree, refreshed from process snapshots. Pids seen once stay members."""

    def __init__(self, root):
        self.lock = threading.Lock()
        self.members = {root: "?"}

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
                if pid in self.members:
                    self.members[pid] = exe
            grew = True
            while grew:
                grew = False
                for pid, parent, exe in entries:
                    if parent in self.members and pid not in self.members:
                        self.members[pid] = exe
                        grew = True

    def name(self, pid):
        with self.lock:
            return self.members.get(pid)


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


class Probe:
    def __init__(self, tree, start):
        self.tree = tree
        self.start = start
        self.lock = threading.Lock()
        self.events = []
        self.onscreen = {}
        self.audio = {}

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

        def visit(hwnd, _):
            pid = window_pid(hwnd)
            exe = self.tree.name(pid)
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


def summarize(probe, exit_code, timed_out):
    events = probe.events
    lines = [f"quiet_probe: exit {exit_code}{' (timed out)' if timed_out else ''}"]
    if not getattr(probe, "hooks_ok", False):
        lines.append("quiet_probe: WARNING some window or shell hooks failed; window results may be incomplete")
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
    return lines


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
    probe.stop_windows()
    exit_code = TIMED_OUT if timed_out else process.returncode

    for line in summarize(probe, exit_code, timed_out):
        print(line, file=sys.stderr)
    if options.json:
        with open(options.json, "w", encoding="utf-8") as out:
            json.dump({"exit": exit_code, "timed_out": timed_out, "events": probe.events,
                       "onscreen": list(probe.onscreen.values()),
                       "audio": {str(pid): a for pid, a in probe.audio.items()},
                       "processes": dict((str(k), v) for k, v in tree.members.items())}, out, indent=1)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
