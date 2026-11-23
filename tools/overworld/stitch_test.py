"""Runs the town stitch test, minimized, and stops at STITCHDONE or the first fatal error.

Usage: stitch_test.py NAME [--mode roundtrip|savetown|loadtown] [--speed 40] [--timeout 30] [--town DIR] [--world DIR]
Generated files go to the test folder outside the repository.
"""
import argparse, glob, os, subprocess, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-stitch\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORK = r"D:\dev\DoomDaggerfall-build\stitch-tests"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error", "Execution could not continue")
KEYS = ("STITCH", "DDSTITCH", "DDSEAM", "DDTOWN", "DFGATES", "Script error", "FATAL", "aborted")

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--mode", default="roundtrip", choices=["roundtrip", "savetown", "saveover", "loadtown"])
ap.add_argument("--speed", default="40")
ap.add_argument("--timeout", type=int, default=30)
ap.add_argument("--town", default=r"D:\dev\DoomDaggerfall-build\stitch-data\town")
ap.add_argument("--slug", default="daggerfall_city")
ap.add_argument("--world", default=r"D:\dev\DoomDaggerfall-build\stitch-data")
ap.add_argument("--start-tile", default=None)
ap.add_argument("--side", default="east", choices=["east", "west", "north", "south"], help="the side of the City of Daggerfall to approach")
ap.add_argument("--dir", help="run direction x,y, for other locations")
ap.add_argument("--cachenodes", action="store_true", help="use the engine's default node cache, as a player would")
args = ap.parse_args()

SIDES = {"east": ("26592,36608", "-1.0", "0.0"), "west": ("26400,36608", "1.0", "0.0"), "north": ("26496,36704", "0.0", "-1.0"), "south": ("26496,36512", "0.0", "1.0")}
start_tile, dir_x, dir_y = SIDES[args.side]
if args.start_tile:
    start_tile = args.start_tile
if args.dir:
    dir_x, dir_y = (str(float(v)) for v in args.dir.split(","))
os.makedirs(WORK, exist_ok=True)
over = os.path.join(WORK, args.name + "_over.pk3")
harness = os.path.join(WORK, args.name + "_harness.pk3")
subprocess.check_call([sys.executable, os.path.join(HERE, "gen_overworld.py"), "--out", over, "--world-dir", args.world, "--ground-from", os.path.join(args.town, args.slug + "_mesh.pk3"), "--start-tile", start_tile,
                       "--start-angle", "180", "--packchance", "0"], stdout=subprocess.DEVNULL)
text = open(os.path.join(HERE, "stitch_harness.zs")).read()
text = text.replace("@DIRX@", dir_x).replace("@DIRY@", dir_y).replace("@SPEED@", args.speed + ".0").replace("@SAVETOWN@", "true" if args.mode == "savetown" else "false").replace("@SAVEOVER@", "true" if args.mode == "saveover" else "false").replace("@SKIPGATE@", "true" if args.mode == "loadtown" else "false")
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "StitchHarness" }\n')

log = os.path.join(WORK, f"log-{args.name}.txt")
if os.path.exists(log):
    os.remove(log)
saves = os.path.join(WORK, "saves")
os.makedirs(saves, exist_ok=True)
files = [over, os.path.join(args.town, args.slug + ".wad"), os.path.join(args.town, args.slug + "_mesh.pk3"), harness]
game = [EXE, "-iwad", IWAD, "-file"] + files + ["-config", os.path.join(WORK, "test.ini"), "-savedir", saves, "-nosound", "-noautoload", "-skill", "3",
        "-width", "1280", "-height", "720", "-noactivate", "-ddtmverify", "+logfile", args.name, "+vid_fullscreen", "0", "+gl_cachenodes", "1" if args.cachenodes else "0",
        "+vid_vsync", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
if args.mode == "loadtown":
    newest = max(glob.glob(os.path.join(saves, "auto*.zds")), key=os.path.getmtime)
    game += ["-loadgame", os.path.basename(newest)]
else:
    game += ["+map", "DDOVER01"]

proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(args.timeout), "--"] + game, cwd=WORK,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason = "timeout"
end = time.time() + args.timeout + 3
while time.time() < end and proc.poll() is None:
    time.sleep(0.2)
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    if "STITCHDONE" in body:
        reason = "done"
        break
    if any(k in body for k in FATAL):
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
print("stopped:", reason)
for line in (open(log, errors="replace") if os.path.exists(log) else []):
    if any(k in line for k in KEYS):
        print(line.rstrip()[:230])
sys.exit(0 if reason == "done" else 1)
