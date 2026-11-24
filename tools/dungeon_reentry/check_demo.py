"""Runs play.bat's exact launcher command, minimized, and presses Use once without moving: it must enter Privateer's Hold."""
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeon-reentry")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
RUN = REVIEW / "test" / "demo-run"
if RUN.exists():
    shutil.rmtree(RUN)
RUN.mkdir(parents=True)
line = next(l for l in (REVIEW / "play.bat").read_text().splitlines() if l.startswith('start ""'))
line = line[len('start "" '):].replace("%HERE%run", str(RUN) + "\\").replace("%HERE%", str(REVIEW) + "\\").replace("\\\\", "\\")
args = [a.replace("\\\\", "\\") for a in shlex.split(line.replace("\\", "\\\\"))]
args[1:1] = ["--minimized", "--nodraw"]
args += ["--uzdoom-arg", "-noactivate", "--uzdoom-arg", "-nosound", "--uzdoom-arg", "+logfile", "--uzdoom-arg", "demo",
         "--uzdoom-arg", "+vid_activeinbackground", "--uzdoom-arg", "1", "--uzdoom-arg", "+vid_lowerinbackground", "--uzdoom-arg", "0",
         "--uzdoom-arg", "+wait 245;dd_tm_use 1;wait 105;dfmesh_status;quit"]
code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
log = RUN / "log-demo.txt"
text = log.read_text(errors="replace") if log.exists() else ""
meshes = re.findall(r"DFMesh: loaded (\d+) triangles", text)
entered = "DDTRANSITION enter-dungeon" in text
status = re.findall(r"DFSTATUS map=(\S+)", text)
print(f"exit {code}, entered dungeon from the start spot {entered}, map {status}, meshes {meshes}, fatal {sum(k in text for k in ('FATAL', 'VM execution aborted'))}")
for name in ("sndfile.dll", "soft_oal.dll"):
    print(name, "present", (REVIEW / "uzdoom" / name).exists())
sys.exit(0 if entered and status == ["MAP01"] and meshes and meshes[-1] == "8418" else 1)
