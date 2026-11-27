"""Launch check for the staged demo: expands play.bat's engine line (HERE, MAP, the spot file) and runs it on the
private desktop for a short while with a log file, then reports the horizon lines and any fatal error.

usage: check_demo.py [--demo DIR] [--mode woodland|dungeon|city]
"""
import argparse, os, re, shlex, subprocess, sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
ap = argparse.ArgumentParser()
ap.add_argument("--demo", default=r"D:\dev\DoomDaggerfall-loop\review\distant-lod-flats")
ap.add_argument("--mode", default="woodland")
a = ap.parse_args()
here = a.demo.rstrip("\\/") + "\\"
bat = open(os.path.join(a.demo, "play.bat")).read()
line = next(l for l in bat.splitlines() if l.startswith('start ""'))[len('start "" '):]
mapname = "DDT07154" if a.mode == "dungeon" else "DDOVER01"
spot = "26489 36672" if a.mode == "city" else "15632 31040"
run = os.path.join(a.demo, "run")
for d in ("saves", "cache"):
    os.makedirs(os.path.join(run, d), exist_ok=True)
with open(os.path.join(run, "spot.cfg"), "w") as f:
    f.write("\n" if mapname != "DDOVER01" else f'wait 70; dd_tm_warp "{spot}"\n')
line = line.replace("%HERE%", here).replace("%MAP%", mapname)
args = shlex.split(line.replace("\\", "/"), posix=True)
args += ["-stdout", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
out = subprocess.run([sys.executable, QUIET, "--timeout", "35", "--cwd", run, "--", *args], capture_output=True, text=True, errors="replace")
body = out.stdout + out.stderr
hits = [l for l in body.splitlines() if "DDHORIZON" in l or any(k in l for k in FATAL)]
print("\n".join(hits) or "no DDHORIZON line")
print("RESULT", "PASS" if any("flats" in l for l in hits) and not any(k in body for k in FATAL) else "FAIL")
