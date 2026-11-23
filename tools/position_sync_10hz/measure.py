"""Measures Daggerfall's frame cost and position error at each update rate, with both real games minimized.

Usage: measure.py [--hz 1,10] [--places outdoor,building,dungeon] [--repeat 1] [--draw]
Each launch stops after 30 seconds, or at once on a fatal error. Output stays in the review folder.
"""
import argparse
import hashlib
import re
import struct
import subprocess
import sys
import time
import winreg
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync-10hz")
CACHE = REVIEW / "town-cache"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
REAL_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")
PLACES = {"outdoor": ("DDOVER01", None, None), "town": ("DDT07154", None, None),"building": ("DDT09183", 9183, "10403728"), "dungeon": ("DDT07154", 7154, "dungeon")}


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


def harness(run, place):
    _, group, target = PLACES[place]
    door, exit_ = ["0"] * 5, ["0"] * 5
    if group:
        doors = [l.split() for l in lumps(CACHE / f"T{group:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
        match = [d for d in doors if d[0] == "1"] if target == "dungeon" else [d for d in doors if d[0] == "0" and d[1] == target]
        door = match[0][3:8]
        if target == "dungeon":
            with zipfile.ZipFile(REVIEW / "privateershold_doors.pk3") as z:
                exit_ = next(l.split()[1:6] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
    text = (HERE / "measure_harness.zs").read_text()
    text = text.replace("@DOOR@", ", ".join(door)).replace("@EXIT@", ", ".join(exit_)).replace("@OUTDOOR@", "true" if not group else "false")
    path = run / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PSHarness" }\n')
    return path


def launch(name, place, hz, draw, extra=()):
    run = REVIEW / "test" / name
    (run / "saves").mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console = run / "uz.log", run / "df.log", run / "log-console.txt"
    for path in (uz_log, df_log, console, run / "launcher.log"):
        path.unlink(missing_ok=True)
    pack = harness(run, place)
    uz = ["-noactivate", "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-nosound", "-ddtowncache", str(CACHE),
          "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3",
          "+logfile", "console", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+map", PLACES[place][0]]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfsynchz", str(hz), *extra, "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", "30", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", *([] if draw else ["--nodraw"]),
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
    for mod in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        command += ["--mod", str(REVIEW / mod)]
    command += ["--mod", str(pack)]
    for a in uz:
        command += ["--uzdoom-arg", a]
    for a in df:
        command += ["--dfu-arg", a]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + 33
    while time.time() < end:
        if proc.poll() is not None:
            reason = "exited"
            break
        time.sleep(0.25)
        log = console.read_text(errors="replace") if console.exists() else ""
        if any(k in log for k in FATAL):
            reason = "fatal"
            break
        if "PSDONE" in log:
            reason = "finished"
            time.sleep(2.2)  # At least one more Daggerfall status line.
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()

    df_text = df_log.read_text(errors="replace") if df_log.exists() else ""
    con = console.read_text(errors="replace") if console.exists() else ""
    stats = re.findall(r"syncstat .*", df_text)
    side = "outdoor" if place in ("outdoor", "town") else "indoor"
    stat = re.search(side + r" (frames=.*?)(?: \||$)", stats[-1]).group(1) if stats else "no stats"
    if stats:
        stat += " | " + stats[-1].rsplit("| ", 1)[1]
    health = sorted({int(h) for h in re.findall(r"health[= ](-?\d+)", df_text)})
    print(f"{name}: {reason} | {stat}")
    print(f"    health {health}, failed {df_text.count('failed,')}, errors {len(re.findall(r'error:', df_text))}, PSFAIL {con.count('PSFAIL')}, submerged true {df_text.count('submerged True')}")
    for line in re.findall(r"sync indoor: .*|back on Doom's position.*?units", df_text):
        print("   ", line[:110])
    for line in re.findall(r"PSWALK end .*", con):
        print("   ", line[:80])
    return reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hz", default="1,10")
    ap.add_argument("--places", default="outdoor,building,dungeon")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--draw", action="store_true")
    ap.add_argument("--water", action="store_true", help="flooded block test, guard on and then off")
    args = ap.parse_args()
    before = registry_hash()
    if args.water:
        launch("water-guard", "dungeon", 10, False, ["-dfsynctestsink"])
        launch("water-noguard", "dungeon", 10, False, ["-dfsynctestsinknoguard"])
        print("owner registry key unchanged:", before == registry_hash())
        return
    for n in range(args.repeat):
        for place in args.places.split(","):
            for hz in args.hz.split(","):
                reason = launch(f"m-{place}-{hz}hz-{n}{'-draw' if args.draw else ''}", place, int(hz), args.draw)
                if reason == "fatal":
                    sys.exit("stopped on a fatal error")
    print("owner registry key unchanged:", before == registry_hash())


if __name__ == "__main__":
    main()
