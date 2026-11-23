"""Run the in-game action check on a converted dungeon, minimized, with a private config.

Usage: python tools/dungeon_converter/action_check.py <dir with scourgbarrow.wad, _mesh.pk3, _doors.pk3> [--timeout 30]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

parser = argparse.ArgumentParser()
parser.add_argument("folder")
parser.add_argument("--slug", default="scourgbarrow")
parser.add_argument("--uzdoom", default=UZDOOM)
parser.add_argument("--iwad", default=IWAD)
parser.add_argument("--timeout", type=int, default=30)
args = parser.parse_args()
folder = os.path.abspath(args.folder)
log = os.path.join(folder, "actioncheck.log")
if os.path.exists(log):
    os.remove(log)
config = os.path.join(folder, "actioncheck.ini")
with open(config, "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE
files = [os.path.join(folder, args.slug + suffix) for suffix in (".wad", "_mesh.pk3", "_doors.pk3")]
startup_log = open(os.path.join(folder, "actioncheck.stdout"), "w")  # script compile errors happen before +logfile opens
process = subprocess.Popen([args.uzdoom, "-iwad", args.iwad, "-file", *files, os.path.join(HERE, "action_check"),
                            "-config", config, "-noactivate", "-nosound", "-nomonsters", "-skill", "3", "-stdout",
                            "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                            "+logfile", "actioncheck.log", "+map", "MAP01"],
                           cwd=folder, startupinfo=startup, stdout=startup_log, stderr=subprocess.STDOUT)
done = False
started = time.time()
try:
    while time.time() - started < args.timeout and process.poll() is None:
        time.sleep(0.5)
        if os.path.exists(log):
            text = open(log, errors="replace").read() + open(startup_log.name, errors="replace").read()
            if "ACDONE" in text or "Script error" in text or "FatalError" in text:
                break
finally:
    if process.poll() is None:
        process.kill()
    process.wait()
startup_log.close()
source = log if os.path.exists(log) else startup_log.name
lines = open(source, errors="replace").read().splitlines()
done = any(line.startswith("ACDONE") for line in lines)
for line in lines:
    if line.startswith(("AC ", "ACINFO", "ACDONE", "DFACTIONS", "DFRULE", "DFDOORS")) or "error" in line.lower():
        print(line)
print(f"finished={done} after {time.time() - started:.0f} s")
sys.exit(0 if done and "failed 0" in "\n".join(lines) else 1)
