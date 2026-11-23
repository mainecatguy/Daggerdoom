"""Loads a converted dungeon with its mesh and door/action packages in the mesh build for about 20 seconds and reports script errors.

Usage: python smoke_load.py <folder> <slug> [--seconds 20]
Needs <slug>.wad, <slug>_mesh.pk3 and <slug>_doors.pk3 (the converter's --export-mesh). Private config, minimized, no focus.
"""
import argparse
import os
import subprocess
import sys
import time

UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

parser = argparse.ArgumentParser()
parser.add_argument("folder")
parser.add_argument("slug")
parser.add_argument("--seconds", type=int, default=20)
args = parser.parse_args()
folder = os.path.abspath(args.folder)
log = os.path.join(folder, "smoke.log")
if os.path.exists(log):
    os.remove(log)
config = os.path.join(folder, "smoke.ini")
with open(config, "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 7
files = [os.path.join(folder, args.slug + s) for s in (".wad", "_mesh.pk3", "_doors.pk3")]
missing = [p for p in files if not os.path.exists(p)]
if missing:
    sys.exit(f"missing {missing}")
console = open(os.path.join(folder, "smoke.stdout"), "w")
process = subprocess.Popen([UZDOOM, "-iwad", IWAD, "-file", *files, "-config", config, "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
                            "-stdout", "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                            "+vid_lowerinbackground", "0", "+logfile", "smoke.log", "+map", "MAP01"],
                           cwd=folder, startupinfo=startup, stdout=console, stderr=subprocess.STDOUT)
began = time.time()
bad = False
try:
    while time.time() - began < args.seconds and process.poll() is None:
        time.sleep(0.5)
        text = open(console.name, errors="replace").read()
        if "Script error" in text or "VM execution aborted" in text or "FatalError" in text or "Unknown texture" in text:
            bad = True
            break
finally:
    alive = process.poll() is None
    if alive:
        process.kill()
    process.wait()
console.close()
text = open(console.name, errors="replace").read()
lines = text.splitlines()
started = any(l.startswith("MAP01") for l in lines)
errors = [l for l in lines if "rror" in l and "DOOM2" not in l][:6]
info = [l for l in lines if l.startswith(("DFACTIONS", "DFDOORS", "DFRULE"))][:4]
print(f"map started: {started}; still running after {time.time() - began:.0f}s: {alive}; errors: {errors or 'none'}")
print("\n".join(l[:160] for l in info))
sys.exit(0 if started and alive and not errors else 1)
