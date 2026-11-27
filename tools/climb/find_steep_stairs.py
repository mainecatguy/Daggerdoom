"""Finds steep stairs (risers over Doom's 24-unit step, short treads) reachable on foot in a converted dungeon map.

usage: find_steep_stairs.py <uzdoom.exe> <play data folder with privateershold.wad> <output folder> [x y z]
Default start: the cave a new character wakes in, in Privateer's Hold (510,1672 on floor 960).
Runs the map alone (no Daggerfall) on a private desktop (quiet_run) and prints the STEEP lines, tallest first."""
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

uz, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
start = sys.argv[4:7] or ["510", "1672", "960"]
out.mkdir(parents=True, exist_ok=True)
pk3 = out / "find_steep_stairs.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("find_steep_stairs.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { AddEventHandlers = "FindSteepStairs" }\n')
    z.writestr("cvarinfo.txt", "server int steep_x = 0;\nserver int steep_y = 0;\nserver int steep_z = 0;\n")
log = out / "log-steep-log.txt"
log.unlink(missing_ok=True)
files = [str(data / n) for n in ("ddruntime.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
cmd = [sys.executable, QUIET, "--timeout", "300", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *files, str(pk3),
       "-config", str(out / "steep.ini"), "+logfile", "steep.log", "+map", "MAP01", "+steep_x", start[0], "+steep_y", start[1],
       "+steep_z", start[2], "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.time() + 300
text = ""
while time.time() < deadline and proc.poll() is None:
    time.sleep(1)
    text = log.read_text(errors="replace") if log.exists() else ""
    if "STEEP done" in text or "Script error" in text or "FATAL" in text.upper():
        break
subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
proc.wait(10)
text = log.read_text(errors="replace") if log.exists() else ""
rows = [l for l in text.splitlines() if l.startswith("STEEP at")]
rows.sort(key=lambda l: -int(re.search(r"rise (\d+)", l).group(1)))
for l in text.splitlines():
    if l.startswith("STEEP nodes") or l.startswith("STEEP done") or "error" in l.lower():
        print(l)
for l in rows[:40]:
    print(l)
