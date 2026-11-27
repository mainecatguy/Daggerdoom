"""Dropped ammo piles look like their ammo and stay, with both real games, minimized. Based on tools/ammo/ammo.py.

usage: ammo_pile.py assemble | uzdoom | dfu | first | load | check
assemble: builds the review folder from this worktree's builds (build_native.py trees and Daggerfall Unity's build).
uzdoom:   copies only a fresh UZDoom build (and the doomerfall mod) into the review folder.
dfu:      copies only a fresh Daggerfall Unity build into the review folder.
first:    enters Privateer's Hold, gives the four ammo types in Doom; Daggerfall's -dfammopiletest hook drops 10 bullets,
          every shell, rocket and cell, and 5 bullets with a ruby, one inventory window drop each. Prints the piles, leaves
          to town, comes back, prints them again and autosaves inside.
load:     loads that autosave in fresh copies of both games and prints the piles again. Then compares all three.
check:    DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, plus the -norun startup check.
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
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-pile")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # Data, sprite package, and demo items.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-ammopile" / "Release"
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-ammopile" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-ammopile" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
AMMO_SPRITES = {"CLIPA0": "bullets", "SHELA0": "shells", "ROCKA0": "rocket", "CELLA0": "cell",
                "AMMOA0": "bullet box", "SBOXA0": "shell box", "BROKA0": "rocket box", "CELPA0": "cell pack"}
AMMO_TYPE = {"CLIPA0": 0, "AMMOA0": 0, "SHELA0": 1, "SBOXA0": 1, "ROCKA0": 2, "BROKA0": 2, "CELLA0": 3, "CELPA0": 3}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def harness(load):
    cache = REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt"
    for other in cache.parent.glob("T*.ddt"):
        other.unlink()
    shutil.copy(SOURCE / "data" / "cache" / cache.name, cache)
    door = next(l.split() for l in lumps(cache)["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    with zipfile.ZipFile(REVIEW / "data" / "privateershold_doors.pk3") as z:
        exit_row = next(l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
    text = (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@EXIT@", ", ".join(exit_row[:5])).replace("@LOADRUN@", "1" if load else "0")
    path = REVIEW / "run" / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "APHarness" }\n')
    return path


def copy_uzdoom():
    if (REVIEW / "uzdoom").exists():
        shutil.rmtree(REVIEW / "uzdoom")
    shutil.copytree(UZ_BUILD, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])


def unity():
    project = REPO / "daggerfall-unity-master"
    log = project / "Logs" / "cli-build.log"
    log.unlink(missing_ok=True)
    exe = shutil.which("Unity.exe") or r"C:\Program Files\Unity\Hub\Editor\2019.4.41f2\Editor\Unity.exe"
    code = subprocess.call([sys.executable, QUIET, "--timeout", "2400", "--", exe, "-projectPath", str(project), "-buildTarget", "Win64",
                            "-executeMethod", "CliBuild.BuildWindows64", "-logFile", str(log)], stdin=subprocess.DEVNULL)
    text = read(log)
    print(f"unity exit {code}, succeeded {'CliBuild result: Succeeded' in text}")
    for line in text.splitlines():
        if "error CS" in line:
            print(line[:220])


def copy_dfu():
    if (REVIEW / "dfu").exists():
        shutil.rmtree(REVIEW / "dfu")
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    copy_uzdoom()
    copy_dfu()
    if (REVIEW / "data").exists():
        shutil.rmtree(REVIEW / "data")
    shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    pickups = REVIEW.parent / "pickups" / "data"  # The converter's newer dungeon, as ammo.py uses.
    for name in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        if (pickups / name).exists():
            shutil.copy2(pickups / name, REVIEW / "data" / name)
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    print("assembled", REVIEW)


def run(name):
    load = name == "load"
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    saves = runs / "saves"
    saves.mkdir(exist_ok=True)
    if not load:
        for old in saves.glob("*.zds"):
            old.unlink()
    autosaves = sorted(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime)
    if load and not autosaves:
        sys.exit("no autosave from the first run")
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    if load:
        uz += ["-dfloadtest", f"resume:{autosaves[-1]}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfammopiletest", *([] if load else ["-dfammopiledrop"]), "-dfarealevel", "20",
          "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 120 if load else 200
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness(load)]:
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
        if "APDONE" in body:
            reason = "harness finished"
            time.sleep(2)
            break
        if any(k in body for k in FATAL) or re.search(r"[1-9]\d* errors?, \d+ warnings? while compiling", body):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if re.match(r"AP[A-Z]+ ", line) or "Script error" in line or any(k in line for k in FATAL):
            print("uz", line[:220])
    for line in read(df_log).splitlines():
        if "ammopiletest" in line or "piles:" in line or "after load" in line:
            print("df", line[:400])


def stage(body, when):
    return {m.group(1): (m.group(2), int(m.group(3))) for m in re.finditer(rf"APPILE {when} id=(\S+) sprite=(\S+) items=(\d+)", body)}


def last_df(body):
    lines = [l for l in body.splitlines() if "ammopiletest:" in l and "dropped piles:" in l]
    if not lines:
        return []
    return sorted(p.strip() for p in lines[-1].split("dropped piles:", 1)[1].split("|") if p.strip())


def compare():
    first, load = read(REVIEW / "run" / "log-first.txt"), read(REVIEW / "run" / "log-load.txt")
    before, dropped, returned, loaded = stage(first, "before"), stage(first, "dropped"), stage(first, "returned"), stage(load, "loaded")
    new = {k: v for k, v in dropped.items() if k not in before}
    ammo = {k: v for k, v in new.items() if v[0] in AMMO_SPRITES}
    other = {k: v for k, v in new.items() if v[0] not in AMMO_SPRITES}
    print("new piles:", len(new))
    for k, v in sorted(new.items()):
        print(f"  {k} {v[0]:10} {AMMO_SPRITES.get(v[0], 'loot pile picture')}, {v[1]} item(s)")
    ok_look = len(new) == 5 and len(ammo) == 4 and sorted(AMMO_TYPE[v[0]] for v in ammo.values()) == [0, 1, 2, 3] and len(other) == 1 and list(other.values())[0][0].startswith("DP") and list(other.values())[0][1] == 2
    print("look:", "PASS" if ok_look else "FAIL", "(four single-type ammo piles with four different ammo sprites, one 2-item pile with the loot pile picture)")
    for label, seen in (("returned", returned), ("loaded", loaded)):
        same = all(seen.get(k) == v for k, v in new.items())
        print(f"{label}:", "PASS" if same and new else "FAIL", f"({sum(seen.get(k) == v for k, v in new.items())}/{len(new)} piles with the same id, sprite and item count)")
    df_first, df_load = last_df(read(REVIEW / "run" / "first-df.log")), last_df(read(REVIEW / "run" / "load-df.log"))
    print("Daggerfall contents after the first run:")
    for p in df_first:
        print("  ", p)
    print("Daggerfall contents after the load:", "PASS (same)" if df_first and df_first == df_load else "FAIL")
    for p in df_load:
        if p not in df_first:
            print("   load only:", p)


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"  # UZDoom writes +logfile NAME to log-NAME.txt.
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3"), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()), "| E1M1 entered", "E1M1" in body)
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "assemble":
        assemble()
    elif command == "uzdoom":
        copy_uzdoom()
    elif command == "unity":
        unity()
    elif command == "dfu":
        copy_dfu()
    elif command == "first":
        run("first")
    elif command == "load":
        run("load")
        compare()
    elif command == "compare":
        compare()
    elif command == "check":
        check()
    else:
        sys.exit(__doc__)
