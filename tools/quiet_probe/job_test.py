"""Tests quiet_run.py's job object with harmless programs. Usage: python job_test.py [QUIET_RUN_PY]

Run it wrapped in quiet_run.py, as AGENTS.md says (the start-ed sleepers open console windows):
  python scripts/overnight/quiet_run.py --timeout 200 -- python tools/quiet_probe/job_test.py

The sleeper is a copy of ping.exe under a unique name in a temp folder, so the test can count its own processes
without touching anything else. It checks that quiet_run waits for a child a .bat starts with `start` and exits,
that its timeout and its own death end that child, that nested quiet_runs work, and that a process with the same
program name started outside quiet_run survives. Nothing here kills by program name.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

QUIET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "scripts",
                                                          "overnight", "quiet_run.py")
WORK = tempfile.mkdtemp(prefix="quietrun-job-")
SLEEPER = os.path.join(WORK, "qrsleeper.exe")
LAUNCH = os.path.join(WORK, "launch.bat")
shutil.copy(os.path.join(os.environ["SystemRoot"], "System32", "PING.EXE"), SLEEPER)
with open(LAUNCH, "w") as f:  # starts a sleeper through `start` and exits at once, like our launcher .bat files
    f.write('@echo off\r\nstart "" /min "%~dp0qrsleeper.exe" -n %1 127.0.0.1\r\nexit /b 7\r\n')

kernel32 = ctypes.WinDLL("kernel32")
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]


def sleepers():
    """PIDs of every qrsleeper.exe (a read-only listing)."""
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq qrsleeper.exe", "/FO", "CSV", "/NH"], capture_output=True,
                         text=True).stdout
    return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"qrsleeper')}


results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)


def quiet(flags, *command, timeout=None):
    extra = ["--timeout", str(timeout)] if timeout else []
    return [sys.executable, QUIET, *flags, *extra, "--", *command]


in_job = wintypes.BOOL()
kernel32.IsProcessInJob(kernel32.GetCurrentProcess(), None, ctypes.byref(in_job))
print(f"test runner already in a job: {bool(in_job.value)}")

outsider = subprocess.Popen([SLEEPER, "-n", "120", "127.0.0.1"], stdout=subprocess.DEVNULL)
time.sleep(0.5)
print(f"outsider pid {outsider.pid}")

for flags in ([], ["--user-desktop"]):
    tag = "private" if not flags else "user-desktop"
    before = sleepers()
    t = time.monotonic()
    code = subprocess.run(quiet(flags, "cmd", "/c", LAUNCH, "4", timeout=30)).returncode
    took = time.monotonic() - t
    check(f"[{tag}] waits for start-ed child", 3 <= took < 20 and code == 7, f"took {took:.1f}s exit {code}")
    check(f"[{tag}] no leftover sleepers", sleepers() - before == set(), str(sleepers() - before))

    before = sleepers()
    t = time.monotonic()
    code = subprocess.run(quiet(flags, "cmd", "/c", LAUNCH, "60", timeout=2)).returncode
    took = time.monotonic() - t
    time.sleep(0.3)
    check(f"[{tag}] timeout ends orphan", code == 124 and took < 6 and sleepers() - before == set(),
          f"took {took:.1f}s exit {code} left {sleepers() - before}")

    before = sleepers()
    q = subprocess.Popen(quiet(flags, "cmd", "/c", LAUNCH, "60"))
    deadline = time.monotonic() + 10
    while not (sleepers() - before) and time.monotonic() < deadline:
        time.sleep(0.1)
    started = sleepers() - before
    subprocess.run(["taskkill", "/PID", str(q.pid), "/F"], capture_output=True)  # quiet_run's own pid only, no /T
    q.wait()
    time.sleep(0.5)
    check(f"[{tag}] killing quiet_run ends children", bool(started) and not (started & sleepers()),
          f"started {started} still {started & sleepers()}")

before = sleepers()
code = subprocess.run(quiet([], sys.executable, QUIET, "--", "cmd", "/c", LAUNCH, "60", timeout=3)).returncode
time.sleep(0.3)
check("nested quiet_run: outer timeout ends inner job", code == 124 and sleepers() - before == set(),
      f"exit {code} left {sleepers() - before}")
before = sleepers()
code = subprocess.run(quiet([], sys.executable, QUIET, "--", "cmd", "/c", LAUNCH, "3", timeout=30)).returncode
check("nested quiet_run: normal finish", code == 7 and sleepers() - before == set(), f"exit {code}")

check("outsider with the same program name survived", outsider.poll() is None and outsider.pid in sleepers())
outsider.kill()  # by its own handle
outsider.wait()
shutil.rmtree(WORK, ignore_errors=True)
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
