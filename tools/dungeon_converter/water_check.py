"""Check a converted dungeon's water in the real engine.

Usage: python water_check.py <dir with slug.wad> <slug> [--exe uzdoom.exe] [--timeout 30]
Needs <slug>_waterprobe from the converter. Exits 0 only if every probe matches and the player swims.
"""
import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
FATAL = ("VM execution aborted", "Script error", "Execution could not continue", "FATAL")

parser = argparse.ArgumentParser()
parser.add_argument("dir")
parser.add_argument("slug")
parser.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe")
parser.add_argument("--timeout", type=int, default=30)
args = parser.parse_args()
folder = os.path.abspath(args.dir)
log = os.path.join(folder, f"log-water{args.slug}.txt")
if os.path.exists(log):
    os.remove(log)
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", folder, "--", args.exe, "-iwad", IWAD,
           "-file", os.path.join(folder, args.slug + ".wad"), os.path.join(folder, args.slug + "_waterprobe"),
           os.path.join(HERE, "water_check"), "-config", os.path.join(folder, "water_check.ini"),
           "-noactivate", "-nosound", "-skill", "3", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
           "+vid_lowerinbackground", "0", "+logfile", f"water{args.slug}", "+map", "MAP01"]
process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
began = time.time()
text = ""
while process.poll() is None and time.time() - began < args.timeout:
    time.sleep(0.5)
    if os.path.exists(log):
        with open(log, errors="replace") as f:
            text = f.read()
        if "DFWATER DONE" in text or any(word in text for word in FATAL):
            break
subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
if os.path.exists(log):
    with open(log, errors="replace") as f:
        text = f.read()
for line in text.splitlines():
    if "DFWATER" in line or any(word in line for word in FATAL):
        print(line.strip()[:200])
probes = re.search(r"DFWATER PROBES total=(\d+) wet=(\d+) dry=(\d+) mismatches=(\d+)", text)
swim = re.search(r"DFWATER SWIM .*start=([\d.-]+) level=(\d+) after1s=([\d.-]+) peak=([\d.-]+)", text)
if "DFWATER DONE" not in text or not probes:
    sys.exit("water check did not finish")
off_span = re.search(r"offspan=(\d+)", text)
# Points whose floor a fitted wall moved are not evidence either way, so a large share fails the check.
few_off_span = off_span is not None and int(off_span.group(1)) * 100 <= int(probes.group(1))
ok = probes.group(4) == "0" and few_off_span and swim is not None and int(swim.group(2)) >= 2 and float(swim.group(4)) > float(swim.group(3))
print("WATER CHECK", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
