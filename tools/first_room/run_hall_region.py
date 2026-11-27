"""Which enemy placements share a floor with p37, p2, the corridor east of p0, and p0 (hall_region.zs).

usage: run_hall_region.py <uzdoom.exe> <play data folder with privateershold.wad> <output folder>
Runs the converted map alone (no Daggerfall) on a private desktop (quiet_run) and prints the HALL lines."""
import subprocess
import sys
import time
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

uz, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
pk3 = out / "first_room_hall_region.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("hall_region.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { AddEventHandlers = "FirstRoomHallRegion" }\n')
log = out / "log-hall-region-log.txt"  # UZDoom names +logfile hall-region.log this way
log.unlink(missing_ok=True)
files = [str(data / n) for n in ("ddruntime.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
cmd = [sys.executable, QUIET, "--timeout", "300", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *files, str(pk3),
       "-config", str(out / "hall-region.ini"), "+logfile", "hall-region.log", "+map", "MAP01",
       "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.time() + 300
while time.time() < deadline and proc.poll() is None:
    text = log.read_text(errors="replace") if log.exists() else ""
    if "HALLREGION done" in text or "Fatal error" in text or "VM execution aborted" in text:
        break
    time.sleep(0.5)
subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
text = log.read_text(errors="replace") if log.exists() else ""
rows = [l for l in text.splitlines() if l.startswith("HALL")]
print("\n".join(rows) if rows else "\n".join(l for l in text.splitlines() if "error" in l.lower())[-2000:])
