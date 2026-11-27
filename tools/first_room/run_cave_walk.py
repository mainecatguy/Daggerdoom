"""Walking distance from Privateer's Hold's starting cave to every enemy placement (cave_walk.zs).

usage: run_cave_walk.py <uzdoom.exe> <play data folder with privateershold.wad> <output folder>
Runs the converted map alone (no Daggerfall) on a private desktop (quiet_run) and prints the CAVEWALK lines,
nearest placement first."""
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

uz, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
pk3 = out / "first_room_cave_walk.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("cave_walk.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { AddEventHandlers = "FirstRoomCaveWalk" }\n')
log = out / "log-cave-walk-log.txt"  # UZDoom names +logfile cave-walk.log this way
log.unlink(missing_ok=True)
files = [str(data / n) for n in ("ddruntime.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
cmd = [sys.executable, QUIET, "--timeout", "90", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *files, str(pk3),
       "-config", str(out / "cave-walk.ini"), "+logfile", "cave-walk.log", "+map", "MAP01",
       "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.time() + 90
while time.time() < deadline and proc.poll() is None:
    text = log.read_text(errors="replace") if log.exists() else ""
    if "CAVEWALK done" in text or "Fatal error" in text or "VM execution aborted" in text:
        break
    time.sleep(0.5)
subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
text = log.read_text(errors="replace") if log.exists() else ""
rows = [l for l in text.splitlines() if l.startswith("CAVEWALK p")]
key = lambda l: (int(re.search(r"walk (-?\d+)", l).group(1)) < 0, int(re.search(r"walk (-?\d+)", l).group(1)))
for l in [l for l in text.splitlines() if l.startswith("CAVEWALK nodes")] + sorted(rows, key=key):
    print(l)
if not rows:
    print("\n".join(l for l in text.splitlines() if "error" in l.lower())[-2000:])
