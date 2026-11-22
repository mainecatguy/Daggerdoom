"""Launch one treadmill run. Usage: treadmill_run.py NAME STOP_UNITS [--quiet] [engine flags...]

Uses an isolated config, and writes NAME.log and NAME.csv to the review folder.
"""
import os, subprocess, sys

REVIEW = r"D:\dev\DoomDaggerfall-loop\review\terrain-treadmill"
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-treadmill\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"

name, stop = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]
quiet = "--quiet" in extra
extra = [a for a in extra if a != "--quiet"]
log, csv = os.path.join(REVIEW, name + ".log"), os.path.join(REVIEW, name + ".csv")
for path in (log, csv):
    if os.path.exists(path):
        os.remove(path)
shots = os.path.join(REVIEW, "shots")
os.makedirs(shots, exist_ok=True)
game = [EXE, "-iwad", IWAD, "-file", os.path.join(REVIEW, "treadmill.pk3"), "-config", os.path.join(REVIEW, "treadmill.ini"),
        "-ddtreadmill", os.path.join(REVIEW, "heights.bin"), "-ddtmlog", csv, "-ddtmstop", stop,
        "-nosound", "-noautoload", "-skill", "3", "-width", "1920", "-height", "1080", "-noactivate",
        "-stdout", "+vid_fullscreen", "0", "+wipetype", "0", "+gl_cachenodes", "0", "+disableautosave", "1", "+vid_vsync", "0", "+vid_maxfps", "0", "+cl_capfps", "0",
        "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
        "+screenshot_dir", shots, "+map", "TREADM01"] + extra
timeout = int(float(stop) / 583) + 120
cmd = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + game if quiet else game
try:
    with open(log, "wb") as out:
        code = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=REVIEW, timeout=timeout + 15).returncode
except subprocess.TimeoutExpired:
    code = 124
print("exit", code)
for line in open(log, errors="replace"):
    if any(k in line for k in ("DDTM active", "DDTM failed", "DDTM stop", "TMSUM", "TMVIEW", "rror", "Renderer:", "Vulkan Device", "GL_RENDERER")):
        last = line.rstrip()[:260]
        print(last)

