"""Run the scripted route through the real launcher, minimized, and print the sync results.

Usage: run_sync.py NAME [--nodraw] [--timeout S]
Stops as soon as the route finishes or either log reports a fatal error.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error", "error:")

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--nodraw", action="store_true")
ap.add_argument("--timeout", type=int, default=40)
ap.add_argument("--enemy-ai", action="store_true", help="negative control: leave Daggerfall's enemy AI on")
args = ap.parse_args()

run = REVIEW / "run"
uz_log, df_log, console = run / f"{args.name}-uz.log", run / f"{args.name}-df.log", run / f"log-{args.name}.txt"
for path in (uz_log, df_log, console):
    path.unlink(missing_ok=True)

uz_args = ["-noactivate", "-config", str(run / f"{args.name}.ini"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
           "+logfile", args.name, "+map", "DDOVER01", "+vid_fullscreen", "0", "+wipetype", "0",
           "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized",
           "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
           "--mod", str(run / "route.pk3"), "--uzdoom-cwd", str(run), "--log", str(run / f"{args.name}-launcher.log")]
if args.nodraw:
    command.append("--nodraw")
if args.enemy_ai:
    dfu_args.append("-dfsynctestenemyai")
for arg in uz_args:
    command += ["--uzdoom-arg", arg]
for arg in dfu_args:
    command += ["--dfu-arg", arg]

proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason = "timeout"
end = time.time() + args.timeout + 3
while time.time() < end and proc.poll() is None:
    time.sleep(0.25)
    text = console.read_text(errors="replace") if console.exists() else ""
    bridge = df_log.read_text(errors="replace") if df_log.exists() else ""
    if "OWDONE" in text:
        reason = "route finished"
        time.sleep(2.2)  # one more Daggerfall status line
        break
    if any(k in text for k in FATAL) or "error:" in bridge:
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()

print("stopped:", reason)
for line in console.read_text(errors="replace").splitlines() if console.exists() else []:
    if any(k in line for k in ("SYNCROUTE", "Script error", "Fatal", "FATAL", "aborted")):
        print(line[:200])
lines = df_log.read_text(errors="replace").splitlines() if df_log.exists() else []
for line in lines:
    if "error" in line or " sync: " in line or "sync test" in line:
        print(line[:220])
status = [l for l in lines if " sync engaged=" in l]
for line in status[-3:]:
    print(line[:520])
frames = [re.search(r"frame n=(\d+) p50=([\d.]+)ms p99=([\d.]+)ms max=([\d.]+)ms", l) for l in status if "engaged=True" in l]
frames = [m for m in frames if m][1:]  # The first window holds the world load.
if frames:
    p50 = sorted(float(m.group(2)) for m in frames)[len(frames) // 2]
    print(f"steady frames: {len(frames)} windows, median p50 {p50:.2f}ms, worst p99 {max(float(m.group(3)) for m in frames):.2f}ms, "
          f"worst frame {max(float(m.group(4)) for m in frames):.2f}ms")
