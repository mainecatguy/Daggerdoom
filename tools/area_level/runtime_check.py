"""Runs the area level checks against a real Daggerfall Unity build, minimized.

usage: runtime_check.py build | stage | dump | paired NAME [--area N] [--kill]

build   builds the bridge, launcher, UZDoom, and doomerfall.pk3 from this worktree into the review folder.
stage  copies Builds/Windows64 to a private review folder, with the current bridge DLL and isolated settings.
dump    starts that Daggerfall alone with -dfarealeveldump, then compares its levels with area_level.py.
paired  starts both games with the Doom items demo (review\\doom-items, read only) and this Daggerfall,
        walks into Privateer's Hold, and prints the monsters lines that give the area level the drops use.
Game data and anything derived from it stay in the review folder, outside the repo.
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

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\area-levels")
DEMO = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items")  # Doom side, data, and harness source. Not modified.
BRIDGE_DLL = REVIEW / "build" / "bridge" / "Release" / "doomerfall_bridge.dll"
SOUND = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def build():
    """Bridge, launcher, and UZDoom from this worktree, so the bridge schema matches this Daggerfall build."""
    out = REVIEW / "build"
    out.mkdir(parents=True, exist_ok=True)
    for name, source in (("bridge", REPO / "bridge"), ("launcher", REPO / "launcher"), ("uzdoom", REPO / "UZDoom")):
        log = out / f"{name}-build.log"
        with log.open("w", encoding="utf-8", errors="replace") as f:
            steps = [] if (out / name / "CMakeCache.txt").exists() else [["cmake", "-S", str(source), "-B", str(out / name), "-G", "Visual Studio 18 2026", "-A", "x64"]]
            for step in steps + [["cmake", "--build", str(out / name), "--config", "Release", "--parallel", "6"]]:
                if subprocess.call(step, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, cwd=REPO):
                    sys.exit(f"{name} failed: see {log}")
        print("built", name)
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, out / "uzdoom" / "Release" / dll)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])


def stage():
    dfu = REVIEW / "dfu"
    if dfu.exists():
        shutil.rmtree(dfu)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, ignore=shutil.ignore_patterns("*.pdb"))
    plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (dfu / "Portable.txt").write_text("")
    install.isolate_registry(dfu)
    (dfu / "PortableAppdata").mkdir()
    for name in ("settings.ini", "KeyBinds.txt"):
        shutil.copy2(DEMO / "dfu" / "PortableAppdata" / name, dfu / "PortableAppdata" / name)
    # Paired runs get the path from -dfsynctest. The standalone dump needs it in the private settings.
    ini = dfu / "PortableAppdata" / "settings.ini"
    ini.write_text(re.sub(r"(?m)^MyDaggerfallPath = .*$", lambda m: "MyDaggerfallPath = " + str(GAME / "DAGGER"), ini.read_text()))
    print("staged", dfu)


def dump():
    out = REVIEW / "dump"
    shutil.rmtree(out, ignore_errors=True)
    start = time.time()
    code = subprocess.call([sys.executable, QUIET, "--desktop", "--timeout", "120", "--", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
                            "-dfmute", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360", "-dfarealeveldump", str(out)],
                           stdin=subprocess.DEVNULL)
    print(f"daggerfall exit {code} after {time.time() - start:.1f} s")
    print(read(out / "sample.txt"))
    sys.exit(subprocess.call([sys.executable, str(HERE / "compare_runtime.py"), str(out)]))


def kill_harness():
    """The monster deaths route: enter, kill until a drop appears, take it, leave, and come back."""
    door = demo_door()
    with zipfile.ZipFile(DEMO / "data" / "privateershold_doors.pk3") as z:
        exit_row = next(l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
    text = (REPO / "tools" / "monster_deaths" / "harness.zs").read_text()
    text = text.replace("@DOOR@", ", ".join(door[3:8])).replace("@EXIT@", ", ".join(exit_row[:5])).replace("@MODE@", "normal")
    path = REVIEW / "run" / "kill_harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "MDHarness" }\n')
    return path


def demo_door():
    cache = DEMO / "data" / "cache" / f"T{GROUP:05d}.ddt"
    with open(cache, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        lumps = {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}
    return next(l.split() for l in lumps["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))


def harness():
    cache = DEMO / "data" / "cache" / f"T{GROUP:05d}.ddt"
    with open(cache, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        lumps = {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}
    door = next(l.split() for l in lumps["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    text = (REPO / "tools" / "doomitems" / "harness.zs").read_text()
    text = text.replace("@DOOR@", ", ".join(door[3:8])).replace("@LOADRUN@", "0").replace("@USE@", '"RLPistolPickup"')
    path = REVIEW / "run" / "harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DIHarness" }\n')
    return path


def paired(name, area, kill=False):
    runs = REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    for old in saves.glob("*.zds"):
        old.unlink()
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(DEMO / "data" / "cache"), "-ddconverter", str(DEMO / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    if area is not None:
        df += ["-dfarealevel", str(area)]
    if kill:
        uz.insert(0, "-ddmontest")
        df += ["-dfmonsterquest", "N0C00Y12"]  # The monster deaths quest: one Imp at a marker in this dungeon.
    timeout = 75
    native = REVIEW / "build"
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(native / "launcher" / "Release" / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(native / "uzdoom" / "Release" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [DEMO / "data" / n for n in DATA] + [DEMO / "dfitems.pk3", REVIEW / "doomerfall.pk3", kill_harness() if kill else harness()]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        if kill and "MDDONE" in read(console):
            reason = "route finished"
            time.sleep(1)
            break
        if not kill and "placements at area level" in read(df_log):
            reason = "dungeon placements built"
            time.sleep(2)
            break
        if any(k in read(console) for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(console).splitlines():
        if re.match(r"MD[A-Z]+ ", line) or line.startswith("You ") or any(k in line for k in FATAL):
            print("uz", line[:200])
    for line in read(df_log).splitlines():
        if "monsters:" in line or "area level" in line or "error" in line.lower():
            print("df", line[:240])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        build()
    elif command == "stage":
        stage()
    elif command == "dump":
        dump()
    elif command == "paired" and len(sys.argv) > 2:
        paired(sys.argv[2], int(sys.argv[sys.argv.index("--area") + 1]) if "--area" in sys.argv else None, "--kill" in sys.argv)
    else:
        sys.exit(__doc__)
