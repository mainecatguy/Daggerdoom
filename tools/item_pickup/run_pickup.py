"""Runs the real pickup route with both games, minimized, and prints the evidence.

usage: run_pickup.py NAME [--load] [--timeout 40]
--load resumes from the newest save the previous run made.
"""
import argparse
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\item-pickup")
DATA = Path(r"D:\dev\DoomDaggerfall-loop\review\combined-bridge\data")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
GROUP = 7154  # The location whose dungeon door leads to the packaged Privateer's Hold (map id 187853213).
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error", "Execution could not continue", "Unable to open map")

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--load", action="store_true")
ap.add_argument("--weight", action="store_true", help="test the weight limit, a partial pickup, and the remainder after re-entry")
ap.add_argument("--shot", action="store_true", help="press F12 as Interact fires; pictures go to run/shots")
ap.add_argument("--timeout", type=int, default=40)
args = ap.parse_args()

run = REVIEW / "run"
saves = run / "saves"
saves.mkdir(parents=True, exist_ok=True)
uz_log, df_log, console, launcher_log = run / f"{args.name}-uz.log", run / f"{args.name}-df.log", run / f"log-{args.name}.txt", run / f"{args.name}-launcher.log"
for path in (uz_log, df_log, console, launcher_log):
    path.unlink(missing_ok=True)


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


doors = [l.split() for l in lumps(DATA / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
door = next(d for d in doors if d[0] == "1")
with zipfile.ZipFile(DATA / "privateershold_doors.pk3") as z:
    exit_row = next(l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
text = (HERE / "pickup_harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@EXIT@", ", ".join(exit_row[:5])).replace("@MODE@", "weight" if args.weight else "take")
harness = run / f"{args.name}_harness.pk3"
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "IPHarness" }\n')

uz_args = ["-noactivate", "-config", str(run / f"{args.name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
           "-ddtowncache", str(DATA / "cache"), "-ddconverter", str(DATA / "converter" / "DungeonConverter.exe"), "-ddarena2", DAGGER + r"\ARENA2",
           "+logfile", args.name, "+screenshot_dir", str(run / "shots"), "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
if args.load:
    newest = max(saves.glob("*.zds"), key=lambda p: p.stat().st_mtime, default=None)
    if newest is None:
        sys.exit("no save to load")
    resume = saves / "resume.zds"
    if newest != resume:
        shutil.copy2(newest, resume)
    # Waits for both games, as the in-game load menu would.
    uz_args += ["+map", f"DDT{GROUP:05d}", "-dfloadtest", "resume:" + str(resume), "+dd_ui_test_hold", "1"]
else:
    for old in saves.glob("*.zds"):
        old.unlink()
    uz_args += ["+map", f"DDT{GROUP:05d}"]
if args.shot:  # A window message cannot reach Doom's game keys in the background, so take a picture every half second.
    uz_args += ["+alias", "ipshot", "screenshot;wait 18;ipshot", "+wait 70;ipshot"]
dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
if args.weight:
    dfu_args.append("-dfitemweighttest")
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
           "--uzdoom-cwd", str(run), "--log", str(launcher_log)]
for mod in [DATA / n for n in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall", harness]:
    command += ["--mod", str(mod)]
for arg in uz_args:
    command += ["--uzdoom-arg", arg]
for arg in dfu_args:
    command += ["--dfu-arg", arg]

proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason, end = "timeout", time.time() + args.timeout + 3
shot_sent = False
while time.time() < end and proc.poll() is None:
    time.sleep(0.2)
    body = read(console)
    if args.shot and not shot_sent and "IPPRESS" in body:  # In weight mode the pile stays in view after the press.
        shot_sent = time.time()
    if "IPDONE" in body:
        reason = "route finished"
        time.sleep(1.0)
        break
    if any(k in body for k in FATAL):
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()

if args.shot:  # Keep the first picture taken after Interact fired, while the pile is still in view.
    pictures = sorted((run / "shots").glob("*.png"), key=lambda p: p.stat().st_mtime)
    chosen = next((p for p in pictures if shot_sent and p.stat().st_mtime >= shot_sent), None)
    for picture in pictures:
        if picture != chosen:
            picture.unlink()
    print("picture:", chosen)
print("stopped:", reason)
for line in read(console).splitlines():
    if re.match(r"IP[A-Z]+ ", line) or line.startswith(("You take", "You cannot", "There is nothing")) or any(k in line for k in FATAL):
        print(line[:190])
for line in read(df_log).splitlines():
    if "items:" in line or "error" in line or re.search(r"load \d+:|save \d+: wrote", line):
        print("df", line[:210])
player = REVIEW / "dfu" / "PortableAppdata" / "Player.log"
exceptions = sorted({l[:170] for l in read(player).splitlines() if "Exception" in l})
print("Player.log exception kinds:", len(exceptions))
for line in exceptions[:5]:
    print("  ", line)
