"""Runs the exact launch line from play.bat, minimized and without taking focus, and reports whether both games came up."""
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\combined-bridge")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
SECONDS = 30

line = next(l for l in (REVIEW / "play.bat").read_text().splitlines() if l.startswith('start ""'))
line = line[len('start ""'):].replace("%HERE%", str(REVIEW) + "\\").replace("%DRAW%", "--nodraw")
parts = [p.strip('"') for p in shlex.split(line, posix=False)]
parts[1:1] = ["--minimized"]
for arg in ("-noactivate", "-nosound", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"):
    parts += ["--uzdoom-arg", arg]

uz, df = REVIEW / "run" / "uz.log", REVIEW / "run" / "df.log"
for path in (uz, df):
    path.unlink(missing_ok=True)
proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(SECONDS), "--"] + parts, cwd=REVIEW, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
end = time.time() + SECONDS
ready = False
while time.time() < end and proc.poll() is None and not ready:
    time.sleep(0.5)
    ready = df.exists() and "sync: aligned" in df.read_text(errors="replace")
if ready:
    time.sleep(3)
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
text = df.read_text(errors="replace") if df.exists() else ""
print("Doom saw Daggerfall:", uz.exists() and "Daggerfall is live" in uz.read_text(errors="replace"))
print("aligned:", re.findall(r"sync: aligned with Doom at pixel \S+", text)[:1], "errors:", text.count("error"))
