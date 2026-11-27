"""Stock check for the distant terrain view: DOOM.WAD E1M1 runs for about 10 s, plain and with the DRLA set, and the
log must show no DDHORIZON build and no fatal error. Also runs the -norun startup check (exit code 1337).

usage: check_stock.py [--exe uzdoom.exe]
"""
import argparse, os, subprocess, sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
WORK = r"D:\dev\DoomDaggerfall-build\distantlod-tests\stock"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")

ap = argparse.ArgumentParser()
ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-distantlod\Release\uzdoom.exe")
args = ap.parse_args()
os.makedirs(WORK, exist_ok=True)
ini = os.path.join(WORK, "stock.ini")
with open(ini, "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\n")
cfg = os.path.join(WORK, "stock.cfg")
with open(cfg, "w", newline="\n") as f:
    f.write("wait 350; quit\n")
code = subprocess.run([sys.executable, QUIET, "--timeout", "30", "--cwd", WORK, "--", args.exe, "-iwad", WAD, "-config", ini, "-norun", "-stdout"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
print("norun exit", code, "PASS" if code == 1337 else "FAIL")
ok = code == 1337
for name, files in (("plain", []), ("drla", [os.path.join(MODS, m) for m in DRLA])):
    log = os.path.join(WORK, f"log-{name}.txt")  # the engine names +logfile NAME as log-NAME.txt
    if os.path.exists(log):
        os.remove(log)
    command = [sys.executable, QUIET, "--timeout", "40", "--cwd", WORK, "--", args.exe, "-iwad", WAD, *(["-file", *files] if files else []),
               "-config", ini, "-skill", "3", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+logfile", name, "+map", "E1M1", "+exec", cfg]
    code = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    fatal = [l for l in body.splitlines() if any(k in l for k in FATAL)]
    horizon = "DDHORIZON" in body
    entered = "E1M1" in body
    good = entered and not fatal and not horizon
    ok &= good
    print(name, "exit", code, "entered E1M1" if entered else "no E1M1 in log", "| horizon built" if horizon else "| horizon off", "| fatal:", fatal[:2], "PASS" if good else "FAIL")
print("ALL PASS" if ok else "FAILED")
