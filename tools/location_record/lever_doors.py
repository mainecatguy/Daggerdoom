"""Card 5's lever-driven door check (lever_doors/zscript.zs), standalone: no Daggerfall, through quiet_run.

usage: lever_doors.py <dir with <slug>.wad, <slug>_mesh.pk3, <slug>_doors.pk3> [--slug wayrest]

The dungeon must be converted by this checkout's converter, so its doors package carries door_objects.zs's record.
Privateer's Hold has no door linked to an action, so the paired route (doors.py) cannot cover this case.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-locrecord\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

folder = Path(sys.argv[1]).resolve()
slug = sys.argv[sys.argv.index("--slug") + 1] if "--slug" in sys.argv else "wayrest"
files = [str(folder / (slug + s)) for s in (".wad", "_mesh.pk3", "_doors.pk3") if (folder / (slug + s)).exists()]
log = folder / "log-leverdoors-log.txt"  # quiet_run names the +logfile this way
log.unlink(missing_ok=True)
(folder / "leverdoors.ini").write_text("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\n")
subprocess.call([sys.executable, QUIET, "--timeout", "40", "--cwd", str(folder), "--", UZDOOM, "-iwad", IWAD, "-file", *files,
                 str(HERE / "lever_doors"), "-config", "leverdoors.ini", "-nomonsters", "-skill", "3", "+vid_fullscreen", "0",
                 "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                 "+logfile", "leverdoors.log", "+map", "MAP01"], stdin=subprocess.DEVNULL)
text = log.read_text(errors="replace") if log.exists() else ""
for line in text.splitlines():
    if line.startswith(("LV", "DFDOORS", "DFACTIONS", "ACDONE")) or "error" in line.lower():
        print(line[:400])
