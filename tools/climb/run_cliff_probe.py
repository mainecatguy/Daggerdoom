"""Climbs a steep stair in a converted dungeon map with the current Doomerfall mod (cliff_probe.zs, no Daggerfall).

usage: run_cliff_probe.py <uzdoom.exe> <play data folder with privateershold.wad> <output folder> [--run]
       [--at x y z angle top] [--chances 100:100:100:100:0] [--tics 900]
Default: Privateer's Hold's steep stair that rises from 384 to 768 (found by find_steep_stairs.py), climbed westward.
Builds doomerfall.pk3 from mods/doomerfall, runs on a private desktop (quiet_run), prints the CLIFF and DFCLIMB lines."""
import argparse
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

ap = argparse.ArgumentParser()
ap.add_argument("uz"); ap.add_argument("data"); ap.add_argument("out")
ap.add_argument("--run", action="store_true")
ap.add_argument("--at", nargs=5, metavar="N", default=["942", "-96", "384", "180", "768"])
ap.add_argument("--chances", default="100:100:100:100:0")
ap.add_argument("--tics", default="900")
ap.add_argument("--map", default="privateershold")
a = ap.parse_args()
uz, data, out = Path(a.uz), Path(a.data), Path(a.out)
out.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(out / "doomerfall.pk3")], check=True,
               stdout=subprocess.DEVNULL)
pk3 = out / "cliff_probe.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("cliff_probe.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { PlayerClasses = "CliffProbePlayer" AddEventHandlers = "CliffProbe" }\n')
    z.writestr("cvarinfo.txt", "server string cliff_at = \"\";\nserver bool cliff_run = false;\n"
               "server string cliff_chances = \"100:100:100:100:0\";\nserver int cliff_tics = 900;\n")
log = out / "log-cliff-log.txt"
log.unlink(missing_ok=True)
files = [str(data / n) for n in ("ddruntime.pk3", a.map + ".wad", a.map + "_mesh.pk3", a.map + "_doors.pk3")]
cmd = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *files,
       str(out / "doomerfall.pk3"), str(pk3), "-config", str(out / "cliff.ini"), "+logfile", "cliff.log", "+map", "MAP01",
       "+cliff_at", ",".join(a.at), "+cliff_run", "1" if a.run else "0",
       "+cliff_chances", a.chances, "+cliff_tics", a.tics, "+dd_debugmessages", "1",
       "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.time() + 30
text = ""
while time.time() < deadline and proc.poll() is None:
    time.sleep(1)
    text = log.read_text(errors="replace") if log.exists() else ""
    if "CLIFF summary" in text or "Script error" in text or "FATAL" in text.upper():
        break
proc.wait()  # quiet_run ends UZDoom at its 30-second timeout
text = log.read_text(errors="replace") if log.exists() else ""
for l in text.splitlines():
    if l.startswith("CLIFF") or "DFCLIMB" in l or "error" in l.lower():
        print(l)
