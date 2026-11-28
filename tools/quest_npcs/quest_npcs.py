"""Quest-placed NPCs in Doom: assembles a review folder and runs the paired "Bugged" save test, minimized.

usage: quest_npcs.py runtime | assemble [--runtime PK3] | run NAME | check
runtime   builds the converter and a runtime package that holds every faction billboard (FACTION.TXT "flat:").
assemble  copies this lane's UZDoom, Daggerfall Unity and bridge builds into REVIEW, with the find-NPC stage's data
          (or DATA_OVERRIDE's runtime package when given with --runtime), and copies the "Bugged" save (never run in
          the owner's folder).
run       loads that save (inside The Woodwing Residence, quest A0C00Y15): Doom should place Gondoryan Yeomsley at the
          quest marker, Use on him opens Daggerfall's talk window, and Daggerfall's test hides and restores him.
check     E1M1 of DOOM.WAD with no bridge, stock and with DRLA.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\quest-npcs")
STAGE = Path(r"D:\dev\DoomDaggerfall-loop\review\findnpc-stage")
SAVE = STAGE / "run" / "saves" / "save18.zds"
BUILD = REPO.parent / "DoomDaggerfall-build"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def runtime_package():
    """Builds this checkout's converter and its runtime package (with every faction billboard) under DoomDaggerfall-build."""
    out = Path(r"D:\dev\DoomDaggerfall-build\quest-npcs")
    converter = out / "converter"
    subprocess.check_call(["dotnet", "build", str(REPO / "tools" / "dungeon_converter" / "DungeonConverter.csproj"), "-c", "Release", "-v", "q", "-o", str(converter),
                           f"-p:DungeonConverterBuildRoot={out / 'obj'}\\"], stdin=subprocess.DEVNULL)
    subprocess.check_call([str(converter / "DungeonConverter.exe"), "--runtime-assets", "--out", str(out / "ddruntime.pk3"), "--arena2", str(GAME / "DAGGER" / "ARENA2"),
                           "--dfu-fonts", str(REPO / "daggerfall-unity-master" / "Assets" / "Resources" / "Fonts")], stdin=subprocess.DEVNULL)
    print("runtime package", out / "ddruntime.pk3")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble(runtime):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", BUILD / "uzdoom" / "Release"), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini", "*_BackUpThisFolder_ButDontShipItWithYourGame"))
    for extra in ("sndfile.dll", "soft_oal.dll", "fm_banks", "soundfonts"):
        source = STAGE / "uzdoom" / extra
        if source.is_dir():
            shutil.copytree(source, REVIEW / "uzdoom" / extra, dirs_exist_ok=True)
        elif source.exists():
            shutil.copy2(source, REVIEW / "uzdoom" / extra)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / "bridge" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if not (REVIEW / "data").exists():
        shutil.copytree(STAGE / "data", REVIEW / "data")
    if runtime:
        shutil.copy2(runtime, REVIEW / "data" / "ddruntime.pk3")
    shutil.copy2(BUILD / "launcher" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    for pk3 in ("dfitems.pk3", "doomerfall-drla.pk3"):
        shutil.copy2(STAGE / pk3, REVIEW / pk3)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    saves = REVIEW / "play" / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SAVE, saves / "save18.zds")
    print("assembled", REVIEW)


def launch(name, extra_uz, extra_df, timeout, done):
    runs = REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SAVE, saves / "bugged.zds")  # a fresh copy each run
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = REVIEW / "data"
    uz = ["-noactivate", "-dfflow", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+dd_debugmessages", "1", "-loadgame", "bugged.zds"] + extra_uz
    df = ["-dfflow", str(GAME / "DAGGER"), "-dfbridgelog", str(df_log), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"] + extra_df
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [data / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"]:
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
        if done in body:
            reason = "route finished"
            time.sleep(1)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    return console, uz_log, df_log


def run(name):
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    harness = runs / f"{name}_harness.pk3"
    import zipfile
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "QNHarness" }\n')
    console, uz_log, df_log = launch(name, ["-file", str(harness)], ["-dftalktest", "-dfquestnpctest"], 120, "QNDONE")
    for line in read(console).splitlines():
        if line.startswith(("QN", "DDNPC")) or any(k in line for k in FATAL):
            print(line[:400])
    for line in read(df_log).splitlines():
        if re.search(r"npcs: |talk: |talktest:|questnpctest:|error|xception", line):
            print("df", line[:300])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3"), "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| DDNPC lines", body.count("DDNPC"), "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL), "| E1M1 reached", "E1M1" in body)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("runtime", "assemble", "run", "check"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--runtime", help="a ddruntime.pk3 to use instead of the find-NPC stage's")
args = ap.parse_args()
if args.command == "runtime":
    runtime_package()
elif args.command == "assemble":
    assemble(args.runtime)
elif args.command == "run":
    run(args.name)
else:
    check()
