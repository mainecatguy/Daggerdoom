"""Autosaves on stitched map changes, in a paired session through the launcher, minimized.

usage: autosaves.py assemble SOURCE | walk | load [FILE] | loadtest cycle|death|menu | report [NAME]
assemble: makes REVIEW from a play folder SOURCE (junctions to its dfu and data, copies of the launcher and pk3s) with
          this worktree's UZDoom build.
walk: starts in Gothway Garden, walks out to the wilderness, back into town, into a building and out (autosaves.zs).
      Every map change should autosave before its first frame; the bridge log shows each one with its frozen time.
load: loads an autosave from the walk (default: the newest) in fresh copies of both games.
loadtest: regression, Doom's own -dfloadtest save, load and death test, started in the same town.
report: prints the walk's autosaves and the load's restored positions side by side.
"""
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\autosaves")
BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-npckill\Release")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
TIMEOUT = 150


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def ddt_lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def assemble(source):
    source = Path(source).resolve()
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("dfu", "data"):
        if not (REVIEW / name).exists():
            subprocess.check_call(["cmd", "/c", "mklink", "/J", str(REVIEW / name), str(source / name)], stdout=subprocess.DEVNULL)
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(source / name, REVIEW / name)
    if not (REVIEW / "uzdoom").exists():
        shutil.copytree(source / "uzdoom", REVIEW / "uzdoom")
    for name in ("uzdoom.exe", "uzdoom.pk3"):
        shutil.copy2(BUILD / name, REVIEW / "uzdoom" / name)
    print("assembled", REVIEW)


def harness(load):
    rows = [l.split() for l in ddt_lumps(REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    door = rows[0][3:8]
    path = REVIEW / "run" / f"harness-{'load' if load else 'walk'}.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", (HERE / "autosaves.zs").read_text().replace("@DOOR@", ", ".join(door)))
        z.writestr("mapinfo.txt", f'gameinfo {{ addeventhandlers = "{"ASLoadHarness" if load else "ASHarness"}" }}\n')
    return path


def run(name, loadtest=None):
    load_file = loadtest and loadtest.startswith("resume:")
    runs = REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    if name == "walk":
        for old in saves.glob("*"):
            old.unlink() if old.is_file() else shutil.rmtree(old)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(ARENA2),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
          "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    if loadtest:
        uz += ["-dfloadtest", loadtest]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness(bool(loadtest))]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, loaded_at = "timeout", time.time() + TIMEOUT + 3, None
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if "ASDONE" in body:
            reason = "harness finished: " + re.search(r"ASDONE (\w+)", body).group(1)
            time.sleep(1)
            break
        verdict = re.search(r"load test: (PASS|FAIL)", read(uz_log))
        if verdict:
            reason = "load test " + verdict.group(1)
            time.sleep(1)
            break
        if load_file and "ASLOADED" in body:
            loaded_at = loaded_at or time.time()
            if time.time() - loaded_at > 2:
                reason = "loaded"
                break
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?, \d+ warnings? while compiling", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    report(name)


def report(name):
    runs = REVIEW / "run"
    for line in read(runs / f"log-{name}.txt").splitlines():
        if re.match(r"AS[A-Z]+ |DDSTITCH|DDTRANSITION|DDTOWN active", line) or "Script error" in line and "DoomRL" not in line or any(k in line for k in FATAL):
            print("uz ", line[:240])
    for line in read(runs / f"{name}-uz.log").splitlines():
        if re.search(r"save|load", line, re.I):
            print("bridge", line[:260])
    for line in read(runs / f"{name}-df.log").splitlines():
        if re.search(r"save \d+:|load \d+:|transition|sync: aligned", line):
            print("df ", line[:260])


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "assemble":
        assemble(sys.argv[2])
    elif command == "walk":
        run("walk")
    elif command == "load":
        saves = REVIEW / "run" / "saves"
        chosen = Path(sys.argv[2]) if len(sys.argv) > 2 else max(saves.glob("*auto*.zds"), key=lambda p: p.stat().st_mtime)
        print("loading", chosen)
        run(f"load-{chosen.stem}", f"resume:{chosen}")
    elif command == "loadtest":  # Regression: Doom's own save/load/death test (cycle, death, menu) in this town start.
        mode = sys.argv[2]
        run(f"loadtest-{mode}", f"{mode}:{REVIEW / 'run' / 'saves' / f'loadtest-{mode}.zds'}")
    elif command == "report":
        report(sys.argv[2] if len(sys.argv) > 2 else "walk")
