"""Launches the exact play.bat command, minimized and without focus, and reports whether both games reached play."""
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\connected-transitions")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
RUN = REVIEW / "run"
RUN.mkdir(exist_ok=True)
for name in ("uz.log", "df.log", "launcher.log"):
    (RUN / name).unlink(missing_ok=True)

line = next(l for l in (REVIEW / "play.bat").read_text().splitlines() if l.startswith('start ""'))
line = line[len('start "" '):].replace("%HERE%", str(REVIEW) + "\\")
args = shlex.split(line, posix=False)
args = [a.strip('"') for a in args]
args[1:1] = ["--minimized"]
args += ["--uzdoom-arg", "-noactivate", "--uzdoom-arg", "+vid_activeinbackground", "--uzdoom-arg", "1", "--uzdoom-arg", "+vid_lowerinbackground", "--uzdoom-arg", "0"]
proc = subprocess.Popen([sys.executable, QUIET, "--timeout", "25", "--"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
end = time.time() + 27
while time.time() < end and proc.poll() is None:
    time.sleep(0.5)
    df = (RUN / "df.log").read_text(errors="replace") if (RUN / "df.log").exists() else ""
    if "sync: aligned" in df:
        time.sleep(2)
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
df = (RUN / "df.log").read_text(errors="replace") if (RUN / "df.log").exists() else ""
uz = (RUN / "uz.log").read_text(errors="replace") if (RUN / "uz.log").exists() else ""
print("Doom attached:", "attached to session" in uz, "| Daggerfall aligned:", re.findall(r"sync: aligned[^\n]*", df)[:1], "| errors:", re.findall(r"error:[^\n]*", df)[:3])
print("sound libraries:", all((REVIEW / "uzdoom" / n).exists() for n in ("sndfile.dll", "soft_oal.dll")))
