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

Every launch, on either desktop, runs in its own Windows job object, so the program and everything it starts stay
one set, even through launchers and .bat files that use `start` and exit. quiet_run creates the program suspended,
puts it in the job, then lets it run; anything it starts joins the job. quiet_run returns when the program AND every
process in the job have exited (so a script that only starts a game returns when the game ends: pass --timeout),
and exits with the program's own exit code. On timeout it ends the whole job and exits 124. The job is set to
kill on close, so if quiet_run itself is killed, Windows ends exactly that set and nothing else. The private desktop
stays open until the whole job is done. Never stop test processes by program name: stop them by their own pid, or
let quiet_run's timeout or its own exit end the job.
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
CREATE_SUSPENDED = 0x4
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JOB_BASIC_ACCOUNTING = 1  # JobObjectBasicAccountingInformation
JOB_EXTENDED_LIMITS = 9  # JobObjectExtendedLimitInformation

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


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]


kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
                                    wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOW),
                                    ctypes.POINTER(PROCESS_INFORMATION)]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
kernel32.ResumeThread.restype = wintypes.DWORD
kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                               wintypes.LPVOID]
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]


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


def new_job():
    """A job object that ends every process in it when its last handle closes (including when quiet_run dies)."""
    job = kernel32.CreateJobObjectW(None, None)  # not inheritable, so only quiet_run holds it
    if not job:
        raise OSError(f"could not create a job object (error {ctypes.get_last_error()})")
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, JOB_EXTENDED_LIMITS, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise OSError(f"could not set up the job object (error {ctypes.get_last_error()})")
    return job


class JobProcess:
    """A program started minimized, in its own job object, on a new private desktop or on the user's desktop.

    It has the small part of the Popen interface used here. poll() returns the program's exit code only once the
    program and every process in its job have exited."""

    def __init__(self, command, cwd, private):
        self.desktop = self.name = None
        if private:
            self.name = f"quiet-run-{os.getpid()}"
            self.desktop = user32.CreateDesktopW(self.name, None, None, 0, 0x10000000, None)  # GENERIC_ALL
            if not self.desktop:
                raise OSError(f"could not create a private desktop (error {ctypes.get_last_error()})")
        self.job = new_job()
        startup = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop=self.name, dwFlags=1,  # STARTF_USESHOWWINDOW
                               wShowWindow=SW_SHOWMINNOACTIVE)
        info = PROCESS_INFORMATION()
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        if not kernel32.CreateProcessW(None, line, None, None, True, CREATE_SUSPENDED, None, cwd, ctypes.byref(startup),
                                       ctypes.byref(info)):
            raise OSError(f"could not start {command[0]} (error {ctypes.get_last_error()})")
        if not kernel32.AssignProcessToJobObject(self.job, info.hProcess):
            error = ctypes.get_last_error()
            kernel32.TerminateProcess(info.hProcess, 1)
            raise OSError(f"could not put {command[0]} in a job object (error {error})")
        kernel32.ResumeThread(info.hThread)
        kernel32.CloseHandle(info.hThread)
        self.handle, self.pid, self.returncode, self.main_code = info.hProcess, info.dwProcessId, None, None

    def main_running(self):
        return self.main_code is None

    def active_processes(self):
        accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not kernel32.QueryInformationJobObject(self.job, JOB_BASIC_ACCOUNTING, ctypes.byref(accounting),
                                                  ctypes.sizeof(accounting), None):
            return 0
        return accounting.ActiveProcesses

    def keep_quiet(self):
        """Keeps the program's own windows minimized, as on the user's desktop, so games render at the same size."""
        if self.desktop and self.main_running():
            minimize_windows(self.pid, self.desktop)

    def poll(self):
        if self.main_code is None and kernel32.WaitForSingleObject(self.handle, 0) == 0:
            code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code))
            self.main_code = ctypes.c_int32(code.value).value
            kernel32.CloseHandle(self.handle)
        if self.returncode is None and self.main_code is not None and self.active_processes() == 0:
            self.returncode = self.main_code
            self.close()
        return self.returncode

    def terminate(self):
        """Ends the program and everything it started: exactly the processes in this job."""
        kernel32.TerminateJobObject(self.job, 1)
        deadline = time.monotonic() + 10
        while self.active_processes() and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        if self.main_code is None:
            kernel32.CloseHandle(self.handle)
            self.main_code = 1
        self.close()

    def close(self):
        if self.job:
            kernel32.CloseHandle(self.job)
            self.job = None
        if self.desktop:
            user32.CloseDesktop(self.desktop)
            self.desktop = None


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
    process = JobProcess(command, options.cwd, private)
    print(f"quiet_run: pid {process.pid}{' on a private desktop' if private else ''}", file=sys.stderr, flush=True)

    deadline = time.monotonic() + options.timeout if options.timeout else None
    while process.poll() is None:
        if private:
            process.keep_quiet()
        elif process.main_running():
            keep_quiet(process.pid, previous)
        if deadline and time.monotonic() >= deadline:
            process.terminate()
            sys.exit(TIMED_OUT)
        time.sleep(POLL_SECONDS)
    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
