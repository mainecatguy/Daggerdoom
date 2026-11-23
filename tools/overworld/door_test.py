"""Runs real location doors in UZDoom and prints the harness results.

Usage: door_test.py NAME --group 9183 --build DIR --targets id,id [--dungeon-dir DIR] [--timeout 30]
--targets lists interior space ids, or "dungeon" for the location's dungeon door. Generated files stay in DIR.
"""
import argparse, os, re, shutil, struct, subprocess, sys, time, zipfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error", "Execution could not continue", "Unable to open map")


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--group", type=int, required=True)
ap.add_argument("--build", required=True)
ap.add_argument("--targets", required=True)
ap.add_argument("--exe", required=True)
ap.add_argument("--dungeon-dir")
ap.add_argument("--timeout", type=int, default=30)
args = ap.parse_args()

cache = os.path.join(args.build, "testcache")
converter = os.path.join(args.build, "converter", "DungeonConverter.exe")
doors = [l.split() for l in lumps(os.path.join(cache, f"T{args.group:05d}.ddt"))["DDDOORS"].decode().splitlines() if l.strip()]
chosen, exits = [], []
for t in args.targets.split(","):
    match = [d for d in doors if d[0] == "1"] if t == "dungeon" else [d for d in doors if d[0] == "0" and d[1] == t]
    if not match:
        sys.exit("no door for " + t)
    chosen.append(match[0])
files = [os.path.join(args.build, "ddruntime.pk3"), os.path.join(args.build, "overworld.pk3")]
if args.dungeon_dir:
    files += [os.path.join(args.dungeon_dir, n) for n in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    with zipfile.ZipFile(files[-1]) as z:
        exits = [l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit")][:1]
text = open(os.path.join(HERE, "door_harness.zs")).read()
text = text.replace("@DOORS@", ", ".join(v for d in chosen for v in d[3:8])).replace("@EXITS@", ", ".join(v for e in exits for v in e) or "0")
if not exits:
    text = text.replace("EXITS.Size() >= FIELDS", "false")
work = os.path.join(args.build, "tests")
os.makedirs(os.path.join(work, "saves"), exist_ok=True)
harness = os.path.join(work, args.name + "_harness.pk3")
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DTHarness" }\n')
log = os.path.join(work, f"{args.name}.log")
if os.path.exists(log):
    os.remove(log)
game = [args.exe, "-iwad", IWAD, "-file", *files, harness, "-config", os.path.join(work, "test.ini"), "-savedir", os.path.join(work, "saves"), "-nosound", "-noautoload", "-skill", "3",
        "-width", "1280", "-height", "720", "-noactivate", "-ddtowncache", cache, "-ddconverter", converter, "-ddarena2", ARENA2,
        "+logfile", log, "+vid_fullscreen", "0", "+vid_vsync", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{args.group:05d}"]
proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(args.timeout), "--"] + game, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason, end = "timeout", time.time() + args.timeout + 3
while time.time() < end and proc.poll() is None:
    time.sleep(0.25)
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    if "DTDONE" in body:
        reason = "done"
        break
    if any(k in body for k in FATAL):
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
body = open(log, errors="replace").read() if os.path.exists(log) else ""
print("result:", reason)
for line in body.splitlines():
    if re.match(r"(DT[A-Z]+|DDTRANSITION|DDSTITCH arrive|DDTCONV)", line) or any(k in line for k in FATAL):
        print(line[:170])
