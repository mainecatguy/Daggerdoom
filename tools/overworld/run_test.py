"""Runs one overworld test, minimized, and closes the game when it reports OWDONE.

Usage: run_test.py NAME MODE [--timeout S] [--packchance P] [--packsize N] [--classes A,B] [--start mx,my] [--stop-at TEXT] [--load SAVE]
Writes NAME.pk3, NAME.log, and NAME.csv to the work folder.
"""
import argparse, csv, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-overworld\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORK = r"D:\dev\DoomDaggerfall-build\overworld-tests"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error", "Execution could not continue")

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("mode")
ap.add_argument("--timeout", type=int, default=30)
ap.add_argument("--packchance", type=float, default=1.0)
ap.add_argument("--packsize", type=int, default=16)
ap.add_argument("--classes", default="ZombieMan,ShotgunGuy")
ap.add_argument("--start", default="862,442")
ap.add_argument("--stop-at", default="OWDONE")
ap.add_argument("--load")
ap.add_argument("--noverify", action="store_true", help="skip the height check, for clean frame timing")
ap.add_argument("--speed", default="4")
args = ap.parse_args()

os.makedirs(WORK, exist_ok=True)
pk3, frames = (os.path.join(WORK, args.name + e) for e in (".pk3", ".csv"))
log = os.path.join(WORK, "log-" + args.name + ".txt")  # The engine names its log file this way.
if not args.load:
    subprocess.check_call([sys.executable, os.path.join(HERE, "gen_overworld.py"), "--out", pk3, "--start", args.start,
                           "--packchance", str(args.packchance), "--packsize", str(args.packsize), "--classes", args.classes,
                           "--harness", os.path.join(HERE, "ow_harness.zs"), "--mode", args.mode], stdout=subprocess.DEVNULL)
else:
    pk3 = os.path.join(WORK, args.load + ".pk3")
for path in (log, frames):
    if os.path.exists(path):
        os.remove(path)

saves = os.path.join(WORK, "saves")
os.makedirs(saves, exist_ok=True)
game = [EXE, "-iwad", IWAD, "-file", pk3, "-config", os.path.join(WORK, "test.ini"), "-savedir", saves, "-nosound", "-noautoload",
        "-skill", "3", "-width", "1280", "-height", "720", "-noactivate", "-ddtmlog", frames, "+logfile", args.name,
        "+vid_fullscreen", "0", "+wipetype", "0", "+gl_cachenodes", "0", "+vid_vsync", "0", "+vid_maxfps", "0", "+cl_capfps", "0",
        "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
game += [] if args.noverify else ["-ddtmverify"]
newest = max((os.path.join(saves, f) for f in os.listdir(saves) if f.endswith(".zds")), key=os.path.getmtime) if args.load else None
game += ["-loadgame", os.path.basename(newest)] if args.load else ["+map", "DDOVER01"]

# Script errors open a blocking dialog in a normal launch, so check them first.
check = os.path.join(WORK, args.name + ".check")
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 7
with open(check, "wb") as out:
    code = subprocess.run([EXE, "-iwad", IWAD, "-file", pk3, "-config", os.path.join(WORK, "check.ini"), "-norun", "-nosound", "-noautoload",
                           "-noactivate", "-stdout", "+vid_fullscreen", "0"], stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                          startupinfo=startup, timeout=25).returncode
if code != 1337:
    print("script check failed, exit", code)
    for l in open(check, errors="replace").read().splitlines():
        if "error" in l.lower() or ", line " in l:
            print(l[:220])
    sys.exit(1)

proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(args.timeout), "--"] + game, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, cwd=WORK)
reason = "timeout"
end = time.time() + args.timeout + 5
while time.time() < end and proc.poll() is None:
    time.sleep(0.25)
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    if args.stop_at in text:
        reason = args.stop_at
        break
    if any(k in text for k in FATAL):
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
print("stopped:", reason)
for line in (open(log, errors="replace") if os.path.exists(log) else []):
    if any(k in line for k in ("DDTM", "OWRESULT", "OWBAD", "OWVANISH", "OWLEG", "OWSETUP", "OWAWAY", "OWPACK", "OWSAVED", "Script error", "rror:", "Fatal", "FATAL", "Cannot", "aborted")):
        print(line.rstrip()[:240])

shifts = frames + ".shifts.csv"
if os.path.exists(shifts):
    rows = list(csv.DictReader(open(shifts)))
    if rows:
        total = sorted(float(r["total_us"]) / 1000 for r in rows)
        err = max(float(r["plane_err"]) for r in rows)
        moved = max(int(r["moved"]) for r in rows)
        print(f"shifts={len(rows)} sim_ms median={total[len(total) // 2]:.2f} worst={total[-1]:.2f} maxMoved={moved} worstPlaneErr={err:.6f}")
