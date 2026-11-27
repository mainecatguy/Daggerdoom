"""Screenshots of the rooms on foot from Privateer's Hold's starting cave (stairs_views.zs).

usage: run_stairs_views.py <uzdoom.exe> <play data folder with privateershold.wad> <output folder>
Runs the converted map alone (no Daggerfall, no monsters) on a private desktop (quiet_run). Screenshots land in
<output>/shots, in the order of the SVIEW lines printed here."""
import subprocess
import sys
import time
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

uz, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
shots = out / "shots"
shots.mkdir(parents=True, exist_ok=True)
for f in shots.glob("*.png"):
    f.unlink()
pk3 = out / "first_room_stairs_views.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("stairs_views.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { AddEventHandlers = "FirstRoomStairsViews" }\n')
log = out / "log-stairs-views-log.txt"  # UZDoom names +logfile stairs-views.log this way
log.unlink(missing_ok=True)
files = [str(data / n) for n in ("ddruntime.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
cmd = [sys.executable, QUIET, "--timeout", "90", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *files, str(pk3),
       "-config", str(out / "stairs-views.ini"), "+logfile", "stairs-views.log", "+map", "MAP01",
       "-shotdir", str(shots), "+enablescriptscreenshot", "1", "+vid_fullscreen", "0", "+wipetype", "0", "+fov", "100",
       "+win_w", "1280", "+win_h", "800", "+vid_scalemode", "0", "+vid_scalefactor", "1", "+show_messages", "0",
       "+screenblocks", "11",
       "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.time() + 90
while time.time() < deadline and proc.poll() is None:
    text = log.read_text(errors="replace") if log.exists() else ""
    if "SVIEWS done" in text or "Fatal error" in text or "VM execution aborted" in text:
        time.sleep(1.5)
        break
    time.sleep(0.5)
subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
text = log.read_text(errors="replace") if log.exists() else ""
for l in text.splitlines():
    if l.startswith("SVIEW") or "error" in l.lower():
        print(l)
for f in sorted(shots.glob("*.png")):
    print(f)
