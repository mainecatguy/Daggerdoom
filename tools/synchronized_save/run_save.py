"""Runs one synchronized save with both real games, minimized, and checks the resulting bundle.

Usage: run_save.py NAME [--fail df_write|uz_zip|uz_commit|uz_crash] [--keep-old] [--extra-uz ARG]... [--extra-df ARG]...
With --keep-old, the save file from the previous run of NAME stays, and must survive a failure byte for byte.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
import winreg
import zipfile
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\synchronized-saving")
DATA = REVIEW.parent / "combined-bridge" / "data"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
REAL_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")


def registry_hash():
    """A hash of the owner's real Daggerfall key. The values are never printed."""
    digest = hashlib.sha256()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REAL_KEY) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                digest.update(repr(winreg.EnumValue(key, index)).encode())
    except OSError:
        return "absent"
    return digest.hexdigest()[:16]


ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--fail")
ap.add_argument("--keep-old", action="store_true")
ap.add_argument("--timeout", type=int, default=35)
ap.add_argument("--map", default="DDT09183")
ap.add_argument("--extra-uz", action="append", default=[])
ap.add_argument("--extra-df", action="append", default=[])
ap.add_argument("--no-savetest", action="store_true", help="the run's own commands make the save")
ap.add_argument("--bundle", default="bundle.zds", help="the save file to check")
ap.add_argument("--mod", action="append", default=[], help="an extra mod to load")
ap.add_argument("--auto", type=int, default=0, help="make this many real autosaves instead of a menu save")
ap.add_argument("--until", default="", help="stop when this text appears in Doom's bridge log")
args = ap.parse_args()

run = REVIEW / "test" / args.name
(run / "saves").mkdir(parents=True, exist_ok=True)
uz_log, df_log = run / "uz.log", run / "df.log"
save = run / "saves" / args.bundle
for path in (uz_log, df_log, run / "launcher.log", run / "log-console.txt"):
    path.unlink(missing_ok=True)
if not args.keep_old:
    save.unlink(missing_ok=True)
before = hashlib.sha256(save.read_bytes()).hexdigest() if save.exists() else None
registry_before = registry_hash()

uz = ["-noactivate", "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-nosound",
      "-ddtowncache", str(DATA / "cache"), "-ddconverter", str(DATA / "converter" / "DungeonConverter.exe"),
      "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3", "+logfile", "console", "+map", args.map,
      "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
if args.auto:
    uz += ["-dfsavetest", f"auto{args.auto}", "+autosavecount", "1"]  # One slot, so a failed autosave targets the previous file.
elif not args.no_savetest:
    uz += ["-dfsavetest", str(save)]
df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
if args.fail == "df_write":
    df += ["-dfsavetestfail", "df_write"]
elif args.fail:
    uz += ["-dfsavetestfail", args.fail]
uz += args.extra_uz
df += args.extra_df

command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
           "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
for mod in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
    command += ["--mod", str(DATA / mod)]
for mod in args.mod:
    command += ["--mod", mod]
for arg in uz:
    command += ["--uzdoom-arg", arg]
for arg in df:
    command += ["--dfu-arg", arg]

proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason = "timeout"
end = time.time() + args.timeout + 3
while time.time() < end:
    if proc.poll() is not None:
        reason = "exited"
        break
    time.sleep(0.25)
    text = uz_log.read_text(errors="replace") if uz_log.exists() else ""
    text += df_log.read_text(errors="replace") if df_log.exists() else ""
    console = (run / "log-console.txt").read_text(errors="replace") if (run / "log-console.txt").exists() else ""
    if any(k in console for k in FATAL):
        reason = "fatal"
        break
    if args.until and args.until in text:
        reason = "reached " + args.until
        time.sleep(1.0)
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()

print("stopped:", reason)
for path, keys in ((uz_log, ("save", "Save")), (df_log, ("save ", "error", "sync test: entered", "plain save test", "load test"))):
    for line in path.read_text(errors="replace").splitlines() if path.exists() else []:
        if any(k in line for k in keys) and "hp: sent" not in line:
            print(path.stem, line[:230])
for line in (run / "log-console.txt").read_text(errors="replace").splitlines() if (run / "log-console.txt").exists() else []:
    if any(k in line for k in FATAL) or "Save failed" in line or "SAVEHORDE" in line:
        print("console", line[:200])

registry_after = registry_hash()
print("owner registry key unchanged:", registry_before == registry_after)
if before:
    print("previous save byte-identical:", save.exists() and hashlib.sha256(save.read_bytes()).hexdigest() == before)
print("leftovers:", sorted(p.name for p in (run / "saves").iterdir() if p.suffix != ".zds"))
if save.exists():
    with zipfile.ZipFile(save) as bundle:
        print("zip test:", bundle.testzip() or "ok")
        names = bundle.namelist()
        ours = [n for n in names if n.startswith("doomerfall/daggerfall/")]
        print(f"bundle: {save.stat().st_size} bytes, {len(names)} entries, {len(ours)} Daggerfall files")
        print("doom entries present:", all(n in names for n in ("info.json", "globals.json", "savepic.png")))
        if "doomerfall/manifest.json" in names:
            manifest = json.loads(bundle.read("doomerfall/manifest.json"))
            print("manifest:", {k: v for k, v in manifest.items() if k != "files"})
            print("manifest files match:", sorted(manifest["files"]) == sorted(n[len("doomerfall/daggerfall/"):] for n in ours))
            data = json.loads(bundle.read("doomerfall/daggerfall/SaveData.txt"))
            entity = data["playerData"]["playerEntity"]
            print("Daggerfall save: health", entity["currentHealth"], "of", entity["maxHealth"],
                  "position", data["playerData"]["playerPosition"]["worldPosX"], data["playerData"]["playerPosition"]["worldPosZ"])
