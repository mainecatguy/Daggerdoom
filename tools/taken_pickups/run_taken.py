"""Daggerfall remembers taken Doom pickups, with both real games, minimized (goal 20261126-212713).

usage: run_taken.py take | loadin | loadout | all | check   [--root DIR]
take:    town start (-dfsynctest), into Privateer's Hold, takes the nearest map pickups (a stimpack and tiered ammo) by
         touch and leaves others; leaves and comes back and checks; autosaves inside; leaves; autosaves in town.
loadin:  loads the take run's inside autosave in fresh copies of both games (Doom's snapshot stands) and checks; then
         leaves, comes back and checks again.
loadout: loads the take run's town autosave in fresh copies and enters: the dungeon is rebuilt without any Doom snapshot,
         from Daggerfall's location record alone (saves keep no Doom world table).
all:     take, loadin, loadout.
check:   DOOM.WAD E1M1 with no bridge, stock and with the DRLA set.
--root: a folder made by scripts/play/install.py. Logs go to <root>/test-taken. The harness is harness.zs here.
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
ROOT = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else Path(r"D:\dev\DoomDaggerfall-loop\review\taken-pickups")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
MODES = {"take": 0, "loadin": 1, "loadout": 2}
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
RUNS = ROOT / "test-taken"


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def take_results():
    body = read(RUNS / "log-take.txt")
    taken = re.findall(r"PTTAKEN (\S+) (\S+)", body)
    kept = re.findall(r"PTKEPT (\S+) (\S+)", body)
    arrival = re.search(r"PTARRIVAL (\S+) (\S+) (\S+) (\S+)", body)
    if not taken or not kept or not arrival:
        sys.exit("the take run logged no taken/kept spots or arrival")
    return taken, kept, arrival.groups()


def autosave(where):
    """The take run's last committed autosave made inside the dungeon (where='inside') or in town."""
    log = read(RUNS / "take-uz.log")
    committed = set(re.findall(r"save (\d+): .*autosave committed", log))
    found = [(n, m, f) for n, m, f in re.findall(r"save (\d+): Doom frozen at tic \d+, map (\S+), .*file (auto\d+\.zds)", log) if n in committed]
    inside = lambda m: m.upper().startswith("DDS") or m.upper() == "MAP01"
    found = [f for n, m, f in found if inside(m.rstrip(",")) == (where == "inside")]
    if not found:
        sys.exit(f"the take run made no committed {where} autosave")
    return RUNS / "saves" / found[-1]


def harness(mode):
    door = next(l.split() for l in lumps(ROOT / "data" / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    taken, kept, arrival = ("0",), ("0",), ("0", "0", "0", "0")  # placeholders: constant indexes are bounds-checked when compiled
    if mode != "take":
        t, k, a = take_results()
        taken = [v for spot in t for v in spot]
        kept = [v for spot in k for v in spot]
        arrival = a
    text = (HERE / "harness.zs").read_text()
    text = text.replace("@DOOR@", ", ".join(door[3:8])).replace("@MODE@", str(MODES[mode])).replace("@TAKE@", "3").replace("@KEEP@", "3")
    text = text.replace("@TAKENSPOTS@", ", ".join(taken)).replace("@KEPTSPOTS@", ", ".join(kept)).replace("@ARRIVAL@", ", ".join(arrival))
    path = RUNS / f"harness-{mode}.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PTHarness" }\n')
    return path


def run(mode):
    saves = RUNS / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    if mode == "take":
        for old in saves.glob("*.zds"):
            old.unlink()
    uz_log, df_log, console, launcher = RUNS / f"{mode}-uz.log", RUNS / f"{mode}-df.log", RUNS / f"log-{mode}.txt", RUNS / f"{mode}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(RUNS / f"{mode}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(ROOT / "data" / "cache"), "-ddconverter", str(ROOT / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", mode, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+map", f"DDT{GROUP:05d}"]
    if mode != "take":
        save = RUNS / ("inside.zds" if mode == "loadin" else "town.zds")  # kept by the take run; autosave slots rotate
        print("loading", save.name)
        uz += ["-dfloadtest", f"resume:{save}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 190 if mode == "take" else 120
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(ROOT / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(ROOT / "uzdoom" / "uzdoom.exe"), "--dfu", str(ROOT / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(RUNS), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [ROOT / "data" / n for n in DATA] + [ROOT / "dfitems.pk3", ROOT / "doomerfall.pk3", harness(mode)]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        if "PTDONE" in body:
            reason = "harness finished"
            time.sleep(3)  # the town autosave's commit and Daggerfall's last lines
            break
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?(, \d+ warnings?)? while (compiling|parsing)", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print(f"[{mode}] stopped:", reason)
    if mode == "take" and reason == "harness finished":
        for where in ("inside", "town"):
            shutil.copy2(autosave(where), RUNS / f"{where}.zds")
    for line in read(console).splitlines():
        if re.match(r"PT[A-Z]+ ", line) or "DDLOC" in line and ("report" in line or "rebuilt" in line or "applied" in line or "record" in line) \
                or "DDTM place" in line or any(k in line for k in FATAL) or "Script error" in line:
            print("  uz", line[:220])
    for line in read(uz_log).splitlines():
        if "load test" in line.lower() or "autosave committed" in line or "Doom frozen" in line:
            print("  uz-bridge", line[:200])
    for line in read(df_log).splitlines():
        if "locations:" in line or "ammo: take" in line or "dfa_take" in line:
            print("  df", line[:240])
    return reason


def check():
    RUNS.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = RUNS / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(RUNS), "--", str(ROOT / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(RUNS / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "-file", str(ROOT / "doomerfall.pk3"),
                   "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lines = read(log).splitlines()
        print(label, "exit", code, "| lines", len(lines), "| DDLOC/DDTM lines", sum("DDLOC" in l or "DDTM" in l for l in lines),
              "| script errors", sum("Script error" in l for l in lines), "| fatal", sum(any(k in l for k in FATAL) for l in lines))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in MODES:
        run(command)
    elif command == "all":
        for m in MODES:
            if run(m) != "harness finished":
                break
    elif command == "check":
        check()
    else:
        sys.exit(__doc__)
