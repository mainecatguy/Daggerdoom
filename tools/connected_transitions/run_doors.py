"""Walks real doors with both real games, minimized, and compares what each game says happened.

Usage: run_doors.py NAME --group 9183 --targets id,id|dungeon [--mode route|save] [--resume SAVE] [--timeout 30]
route goes in and out of each door. save autosaves inside the first one. --resume loads that save and walks out.
Generated files stay in the review folder.
"""
import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import winreg
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).parent
REVIEW = Path(os.environ.get("DD_REVIEW", r"D:\dev\DoomDaggerfall-loop\review\connected-transitions"))
TEST_ROOT = Path(os.environ.get("DD_TEST_ROOT", str(REVIEW / "test")))  # Lets a later task keep its logs apart from this demo's evidence.
SOURCE_CACHE = REVIEW.parent / "combined-bridge" / "data" / "cache"
CACHE = REVIEW / "test-cache"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
REAL_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")


def registry_hash():
    """A hash of the owner's real Daggerfall key. The values are never printed."""
    digest = hashlib.sha256()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REAL_KEY) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                digest.update(repr(winreg.EnumValue(key, index)).encode())
    except OSError:
        return "absent"
    return digest.hexdigest()


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def building_types(group):
    out = subprocess.run([str(REVIEW / "converter" / "DungeonConverter.exe"), "--group", str(group), "--list-buildings", "--out", str(REVIEW / "build"),
                          "--arena2", str(GAME / "DAGGER" / "ARENA2")], capture_output=True, text=True, timeout=60).stdout
    return {p[1]: p[2] for p in (l.split() for l in out.splitlines() if l.startswith("BUILDING"))}


ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--group", type=int, default=9183)
ap.add_argument("--targets", default="")
ap.add_argument("--pick", type=int, default=0, help="choose this many doors of different real building types")
ap.add_argument("--mode", default="route")
ap.add_argument("--resume")
ap.add_argument("--brief", action="store_true")
ap.add_argument("--timeout", type=int, default=30)
ap.add_argument("--exe", default=str(REVIEW / "uzdoom" / "uzdoom.exe"), help="UZDoom build to test")
args = ap.parse_args()

if not CACHE.exists():
    shutil.copytree(SOURCE_CACHE, CACHE)
run = TEST_ROOT / args.name
(run / "saves").mkdir(parents=True, exist_ok=True)
uz_log, df_log, console = run / "uz.log", run / "df.log", run / "log-console.txt"
for path in (uz_log, df_log, console, run / "launcher.log"):
    path.unlink(missing_ok=True)

doors = [l.split() for l in lumps(CACHE / f"T{args.group:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
types = building_types(args.group)
targets = [t for t in args.targets.split(",") if t]
if args.pick:
    seen = set()
    for d in doors:
        if d[0] == "0" and (CACHE / f"T{d[1]}.ddt").exists() and types.get(d[1]) not in seen:
            seen.add(types.get(d[1]))
            targets.append(d[1])
    targets = targets[:args.pick]
chosen, exits = [], []
for t in targets:
    match = [d for d in doors if d[0] == "1"] if t == "dungeon" else [d for d in doors if d[0] == "0" and d[1] == t]
    if not match:
        sys.exit(f"no door for {t}")
    chosen.append(match[0])
    if t == "dungeon":
        with zipfile.ZipFile(REVIEW / "privateershold_doors.pk3") as z:
            exits = [l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit")][:1]
print("doors:", [(t, types.get(t, "dungeon")) for t in targets])

text = (HERE.parent / "overworld" / "door_harness.zs").read_text()
text = text.replace("@DOORS@", ", ".join(v for d in chosen for v in d[3:8])).replace("@EXITS@", ", ".join(v for e in exits for v in e) or "0, 0, 0, 0, 0")
text = text.replace("@MODE@", "save" if args.mode == "save" else "route")
text = text.replace("EXITS.Size() >= FIELDS", "HasExit()").replace("const FIELDS = 5;", "const FIELDS = 5;\n\tbool HasExit() { int i = level.maptime * 0 + 3; return EXITS[i] != 0 || EXITS[i + 1] != 0; }")
# Doors wait until Daggerfall is playing, because the test is about both games.
text = text.replace("if (inside || level.maptime < 4) break;", 'if (inside || level.maptime < 4 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3 || CVar.FindCVar("dd_ui_test_hold").GetInt()) break;')
if args.mode == "saveout":  # Autosaves three tics after coming back out, while Daggerfall may still be settling.
    text = text.replace('Console.Printf("DTRETURN', 'level.MakeAutoSave(); Console.Printf("DTRETURN')
harness = run / "harness.pk3"
with zipfile.ZipFile(harness, "w") as z:  # Same classes as the saved run, so a resumed save continues its route.
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DTHarness" }\n')
if args.resume:
    shutil.copy2(args.resume, run / "saves" / "resume.zds")

uz = ["-noactivate", "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-nosound", "-ddtowncache", str(CACHE),
      "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3",
      "+logfile", "console", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+autosavecount", "1"]
uz += ["+map", f"DDT{args.group:05d}"]
if args.resume:  # Waits for both games, as the in-game load menu would.
    uz += ["-dfloadtest", "resume:" + str(run / "saves" / "resume.zds"), "+dd_ui_test_hold", "1"]
df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", args.exe, "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
           "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
for mod in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
    command += ["--mod", str(REVIEW / mod)]
command += ["--mod", str(harness)]
for a in uz:
    command += ["--uzdoom-arg", a]
for a in df:
    command += ["--dfu-arg", a]

before = registry_hash()
proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason, end = "timeout", time.time() + args.timeout + 3
while time.time() < end:
    if proc.poll() is not None:
        reason = "exited"
        break
    time.sleep(0.25)
    log = console.read_text(errors="replace") if console.exists() else ""
    if any(k in log for k in FATAL):
        reason = "fatal"
        break
    if "DTDONE" in log or (args.mode in ("save", "saveout") and uz_log.exists() and "autosave committed" in uz_log.read_text(errors="replace")):
        reason = "finished"
        time.sleep(2.5)  # Lets Daggerfall finish following the last door.
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()

print("stopped:", reason)
for line in console.read_text(errors="replace").splitlines() if console.exists() else []:
    if line.startswith(("DTFAIL", "DTDONE")) or any(k in line for k in FATAL) or (not args.brief and line.startswith(("DTARRIVE", "DTRETURN", "DDTRANSITION"))):
        print("doom", line[:170])
for line in df_log.read_text(errors="replace").splitlines() if df_log.exists() else []:
    if ("transition" in line and not (args.brief and ("door found" in line or (len(targets) > 3 and "error" not in line)))) or "error" in line or re.search(r"load \d+:|save \d+:", line):
        print("df  ", line[:210])
for line in uz_log.read_text(errors="replace").splitlines() if uz_log.exists() else []:
    if re.search(r"(save|load) \d+:", line):
        print("uz  ", line[:170])
console_text = console.read_text(errors="replace") if console.exists() else ""
df_text = df_log.read_text(errors="replace") if df_log.exists() else ""
entered = re.findall(r"Daggerfall is in building \d+ type (\w+) in .*?, target (\d+),", df_text)
wrong = [(t, target, types.get(target)) for t, target in entered if types.get(target) != t]
door_errors = [float(e) for e in re.findall(r"door found in .*?, error ([\d.]+) units", df_text)]
exits = [float(e) for e in re.findall(r"after the exit, off by ([\d.]+) units", df_text)]
healths = {int(h) for h in re.findall(r"health (-?\d+)", df_text)}
print(f"summary: {len(entered)} building entries, {len(set(t for t, _ in entered))} types, wrong type {wrong}, worst door match {max(door_errors, default=-1)} units, "
      f"exits back on Doom's position {len(exits)} (worst {max(exits, default=-1)} units), Daggerfall health values {sorted(healths)}, failed transitions {df_text.count('failed,')}")
player_log = REVIEW / "dfu" / "PortableAppdata" / "Player.log"
player_text = player_log.read_text(errors="replace") if player_log.exists() else ""
lines = player_text.splitlines()
where = [next((l.strip()[:90] for l in lines[i + 1:i + 4] if "DaggerfallWorkshop" in l), "unknown") for i, l in enumerate(lines) if "Exception" in l]
other = [w for w in where if "DaggerfallUI.SetupSingleton" not in w]  # This one is logged at every bridge startup, also on earlier builds.
print(f"Daggerfall exceptions: {len(other)} new, {len(where) - len(other)} known startup", other[:3])
print("owner registry key unchanged:", before == registry_hash())
