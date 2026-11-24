"""Paired climbing probe: runs the climbing demo's play.bat command with a probe pk3 added, minimized, with all
logs in its own run folder, then prints the climb lines from UZDoom's and Daggerfall's logs.

usage: run_paired_probe.py <probe.zs> <run_dir> [--demo <demo folder>] [extra pk3 ...]
  probe.zs: paired_probe.zs (moves to town, finds the nearest wall, climbs) or hold_probe.zs (holds forward from
  the demo's own start). The run folder is deleted and recreated."""
import os, re, shutil, subprocess, sys, zipfile

argv = sys.argv[1:]
DEMO = r"D:\dev\DoomDaggerfall-loop\review\climbing"
if "--demo" in argv:
    i = argv.index("--demo")
    DEMO = argv[i + 1]
    del argv[i:i + 2]
probe_zs, run = argv[0], argv[1]
extra = argv[2:]
if os.path.isdir(run):
    shutil.rmtree(run)
os.makedirs(run)
pk3 = os.path.join(run, "probe.pk3")
with zipfile.ZipFile(pk3, "w") as z:
    z.write(probe_zs, "zscript/probe.zs")
    z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
    z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "ClimbProbe" }\n')

bat = open(os.path.join(DEMO, "play.bat")).read()
line = [l for l in bat.splitlines() if "doomerfall-launcher.exe" in l][0]
line = line.replace("%HERE%", DEMO + "\\").replace(DEMO + "\\play\\", run + "\\")
args = re.findall(r'"[^"]*"|\S+', line)[2:]  # drop: start ""
args = [a.strip('"') for a in args]
args = [run if a == DEMO + "\\play" else a for a in args]
exe = args.pop(0)
mods = []
for m in extra + [pk3]:
    mods += ["--mod", m]
i = args.index("--uzdoom-cwd")
args[i:i] = mods
args = ["--minimized"] + args + ["--uzdoom-arg", "+logfile", "--uzdoom-arg", "console.log"]
cmd = [sys.executable, r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py", "--timeout", "45", "--", exe] + args
print(" ".join(cmd))
r = subprocess.run(cmd)
print("exit", r.returncode, "(124 is the expected timeout: the launcher keeps running)")
for name in ("log-console-log.txt", "uz.log", "df.log"):
    p = os.path.join(run, name)
    if os.path.exists(p):
        for l in open(p, errors="replace"):
            if re.search(r"CLIMBPROBE|DFCLIMB|climb:", l):
                print(name, ":", l.rstrip())
