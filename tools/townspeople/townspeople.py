"""Builds, assembles, and tests the persistent townspeople demo in a private review folder.

usage: townspeople.py build | unity | data | assemble | run NAME [--hour H] [--kill] [--trip] [--save] [--load] [--drla] | check
Game data and generated maps stay outside the repo.
"""
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "stationary_npcs"))
import stationary_npcs as sn  # noqa: E402

base, pickup, md = sn.base, sn.pickup, sn.md
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\townspeople")
PREVIOUS = Path(r"D:\dev\DoomDaggerfall-loop\review\stationary-npcs")
base.REVIEW, base.BUILD, base.RUN, base.PREVIOUS = REVIEW, REVIEW / "build", REVIEW / "run", PREVIOUS
pickup.REVIEW = md.REVIEW = sn.REVIEW = REVIEW
sn.PREVIOUS = PREVIOUS
sn.CONVERTER = CONVERTER = REVIEW / "data" / "converter" / "DungeonConverter.exe"


def run(name, hour=None, kill=False, save=False, load=False, drla=False, seconds=45, trip=False):
    """Starts in town beside a tavern door and stands still. The harness can kill the nearest townsperson and autosave,
    or (trip) go into the tavern, come back out, and list who is shown again."""
    if trip:
        seconds += 20
    data, runs = REVIEW / "data", REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    saves = runs / "saves"
    saves.mkdir(exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    rows, types, _ = sn.doors(pickup.GROUP)
    door = next(r for r in rows if types.get(int(r[1])) == "Tavern")
    harness = runs / f"{name}_harness.pk3"
    mode = ("kill " if kill else "") + ("trip " if trip else "") + ("save" if save else "")
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@MODE@", mode))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "TPHarness" }\n')
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(CONVERTER), "-ddarena2", base.DAGGER + r"\ARENA2",
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{pickup.GROUP:05d}"]
    if load:
        newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
        if newest is None:
            sys.exit("no save to load")
        resume = saves / "resume.zds"
        shutil.copy2(newest, resume)
        uz += ["-dfloadtest", "resume:" + str(resume), "+dd_ui_test_hold", "1"]
    elif save:
        for old in saves.glob("*.zds"):
            old.unlink()
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", base.DAGGER, "-dftownreport", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    if hour is not None:
        df += ["-dftownhour", str(hour)]
    command = [sys.executable, base.QUIET, "--timeout", str(seconds + 15), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", base.IWAD2, "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    dungeon = [data / n for n in (md.WAD, "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    for mod in ([base.MODS / n for n in base.DRLA] if drla else []) + [data / n for n in ("ddruntime.pk3", "overworld.pk3")] + dungeon + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    fatal = tuple(k for k in md.FATAL if k != "Script error") if drla else md.FATAL
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + seconds
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = base.read(console)
        if "TPDONE" in body:
            reason = "route finished"
            time.sleep(1)
            break
        if any(k in body for k in fatal):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in base.read(console).splitlines():
        if line.startswith(("TP", "DDTOWNSFOLK")) or any(k in line for k in fatal):
            print(line[:160])
    for line in base.read(df_log).splitlines():
        if "town:" in line or "townrow" in line or "exception" in line.lower():
            print("DF", line[:200])


def assemble():
    sn.assemble()
    (REVIEW / "play.bat").write_text((REVIEW / "play.bat").read_text().replace(
        "rem Starts in town facing a tavern door. Look for NPCs outside, then press Use to go in.",
        "rem Starts in Gothway beside a tavern. Townspeople walk the streets by day and go home at night."), newline="")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        base.build()
    elif command == "unity":
        base.unity()
    elif command == "data":
        sn.data()
    elif command == "assemble":
        assemble()
    elif command == "run":
        argv = sys.argv
        hour = float(argv[argv.index("--hour") + 1]) if "--hour" in argv else None
        run(argv[2], hour, "--kill" in argv, "--save" in argv, "--load" in argv, "--drla" in argv, trip="--trip" in argv)
    elif command == "check":
        base.check()
    else:
        sys.exit(__doc__)
