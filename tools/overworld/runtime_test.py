"""Visits generated Daggerfall locations in one UZDoom session and reports conversion, handoff, and frame times.

Usage: runtime_test.py NAME --groups 1,3,5,1 [--timeout 150] [--cache DIR] [--converter EXE] [--keep-cache]
A group listed twice is the return visit, which must come from the cache. Generated files stay outside the repository.
"""
import argparse, csv, glob, os, re, shutil, struct, subprocess, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-stitch\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORK = r"D:\dev\DoomDaggerfall-build\runtime-tests"
ROOT = r"D:\dev\DoomDaggerfall-loop\town-cache"
CONVERTER = r"D:\dev\DoomDaggerfall-loop\DoomDaggerfall-build\dungeon_converter\bin\Release\net9.0\DungeonConverter.exe"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error", "Execution could not continue", "Unable to open map")
KEYS = ("RTSAVE", "RTLOAD", "DDTOWN resumed", "DDSEAM", "RTLEG", "RTDONE", "DDTCONV", "DDTCACHE", "DDSTITCH arrive", "DDTLOD", "DDTOWN contents", "DFGATES", "DFMesh", "Script error", "aborted")


def read_groups(pk3):
    with zipfile.ZipFile(pk3) as z:
        d = z.read("DDGROUPS")
    count = struct.unpack_from("<i", d, 4)[0]
    at, out = 8, []
    for _ in range(count):
        n, large = struct.unpack_from("<hh", d, at)
        at += 4
        rects = [struct.unpack_from("<iiii", d, at + 16 * i) for i in range(n)]
        at += 16 * n
        out.append((rects, large != 0))
    return out


def boxes_near(groups, x0, x1, y0, y1, skip):
    return any(i != skip and any(r[0] - 26 < x1 and r[1] + 26 > x0 and r[2] - 26 < y1 and r[3] + 26 > y0 for r in g[0]) for i, g in enumerate(groups))


def route_for(groups, gid, run=44):
    rects = groups[gid][0]
    x0, x1, y0, y1 = min(r[0] for r in rects), max(r[1] for r in rects), min(r[2] for r in rects), max(r[3] for r in rects)
    r = rects[0]
    mx, my = (r[0] + r[1]) // 2, (r[2] + r[3]) // 2
    sides = [(x1 + run, my, -1, 0, r[1], (x1, x1 + run, my - 1, my + 1)), (x0 - run, my, 1, 0, r[0], (x0 - run, x0, my - 1, my + 1)),
             (mx, y1 + run, 0, -1, r[3], (mx - 1, mx + 1, y1, y1 + run)), (mx, y0 - run, 0, 1, r[2], (mx - 1, mx + 1, y0 - run, y0))]
    for sx, sy, dx, dy, edge, box in sides:
        if 200 < sx < 127800 and 200 < sy < 63800 and not boxes_near(groups, *box, gid):
            return sx, sy, dx, dy, edge
    sx, sy, dx, dy, edge, _ = sides[0]
    return sx, sy, dx, dy, edge


ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--groups", required=True)
ap.add_argument("--timeout", type=int, default=150)
ap.add_argument("--cache", default=os.path.join(ROOT, "test"))
ap.add_argument("--converter", default=CONVERTER)
ap.add_argument("--keep-cache", action="store_true")
ap.add_argument("--cap-mb", default=None)
ap.add_argument("--mode", default="route", choices=["route", "save", "load"])
ap.add_argument("--verify", action="store_true", help="measure the seam between each location and the overworld")
ap.add_argument("--exe", default=EXE)
ap.add_argument("--assets", default=os.path.join(ROOT, "ddruntime.pk3"))
ap.add_argument("--work", default=WORK)
args = ap.parse_args()
EXE, WORK = args.exe, args.work

assets = args.assets
groups = read_groups(assets)
ids = [int(v) for v in args.groups.split(",")]
if not args.keep_cache and os.path.isdir(args.cache):
    shutil.rmtree(args.cache)
os.makedirs(args.cache, exist_ok=True)
os.makedirs(os.path.join(WORK, "saves"), exist_ok=True)

route = []
for gid in ids:
    route += route_for(groups, gid)[:5] and [gid, *route_for(groups, gid)]
first = route_for(groups, ids[0])
over = os.path.join(WORK, args.name + "_over.pk3")
subprocess.check_call([sys.executable, os.path.join(HERE, "gen_overworld.py"), "--out", over, "--world-dir", r"D:\dev\DoomDaggerfall-build\stitch-data",
                       "--ground-from", assets, "--start-tile", f"{(first[0] - 64) // 32 * 32},{(first[1] - 64) // 32 * 32}", "--packchance", "0"], stdout=subprocess.DEVNULL)
harness = os.path.join(WORK, args.name + "_harness.pk3")
text = open(os.path.join(HERE, "runtime_harness.zs")).read().replace("@ROUTE@", ", ".join(map(str, route))).replace("@MODE@", args.mode)
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "RTHarness" }\n')

log = os.path.join(WORK, f"log-{args.name}.txt")
if os.path.exists(log):
    os.remove(log)
frames = os.path.join(WORK, args.name + ".csv")
game = [EXE, "-iwad", IWAD, "-file", assets, over, harness, "-config", os.path.join(WORK, "test.ini"), "-savedir", os.path.join(WORK, "saves"), "-nosound", "-noautoload", "-skill", "3",
        "-width", "1280", "-height", "720", "-noactivate", "-ddcrashexit", os.path.join(WORK, args.name + ".crash.txt"), "-ddtowncache", args.cache, "-ddconverter", args.converter, "-ddarena2", ARENA2, "-ddtmlog", frames,
        "+logfile", args.name, "+vid_fullscreen", "0", "+vid_vsync", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "DDOVER01"]
if args.verify:
    game.insert(1, "-ddtmverify")
if args.mode == "load":
    newest = max(glob.glob(os.path.join(WORK, "saves", "auto*.zds")), key=os.path.getmtime)
    game = game[:game.index("+map")] + ["-loadgame", os.path.basename(newest)]
if args.cap_mb:
    game[game.index("-ddtowncache"):game.index("-ddtowncache")] = ["-ddtowncachemb", args.cap_mb]
proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(args.timeout), "--"] + game, cwd=WORK, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason, end = "timeout", time.time() + args.timeout + 3
while time.time() < end and proc.poll() is None:
    time.sleep(0.25)
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    if "RTDONE" in body:
        reason = "done"
        break
    if any(k in body for k in FATAL):
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
print("stopped:", reason)
for line in open(log, errors="replace") if os.path.exists(log) else []:
    if any(k in line for k in KEYS):
        print(line.rstrip()[:170])
if os.path.exists(frames):
    rows = list(csv.DictReader(open(frames)))[30:]
    def stats(sel):
        v = sorted(float(r["frame_us"]) / 1000 for r in rows if sel(r))
        return f"n={len(v)} median={v[len(v) // 2]:.2f} p99={v[int(len(v) * .99)]:.2f} max={v[-1]:.2f} ms" if v else "n=0"
    print("frames idle:", stats(lambda r: r.get("converting") == "0"))
    print("frames converting:", stats(lambda r: r.get("converting") == "1"))
files = [f for f in os.listdir(args.cache) if f.endswith(".ddt")]
print(f"cache: {len(files)} files, {sum(os.path.getsize(os.path.join(args.cache, f)) for f in files) / 1048576:.1f} MB")
sys.exit(0 if reason == "done" else 1)
