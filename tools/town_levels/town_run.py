"""Shop levels 3: town levels. Runtime dump check, a paired run that walks out through a city gate, and a demo folder.

usage: town_run.py assemble | dump | run [NAME] [--stock-mods]
assemble: REVIEW gets this checkout's Daggerfall Unity build, UZDoom, launcher and bridge DLL (built into BUILD's
          *-towndanger folders; town_map in the bridge state), the data the shop levels 2 demo built from this branch
          (unchanged by this work), and a play.bat that starts in the City of Daggerfall.
dump:     Daggerfall Unity alone with -dfarealeveldump, then compare_runtime.py against area_level.py, then the town
          lines of sample.txt.
run:      paired games on the City of Daggerfall's map, with Daggerfall's -dfworldleveltest 1 (guard levels at the
          current place) and -dftownlevellog (a line whenever the level where the player stands changes), and
          gate_walk.zs, which stands inside a gate, walks out through it and on past the town map's edge, then back in
          until Doom loads the town map again.
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
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
sys.path.insert(0, str(REPO / "tools" / "area_level"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv
import dfdata  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\town-levels")
BASE = Path(r"D:\dev\DoomDaggerfall-loop\review\shop-shelf-levels")
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD, BRIDGE_BUILD, LAUNCHER_BUILD = (BUILD / f"{n}-towndanger" / "Release" for n in ("uzdoom", "bridge", "launcher"))
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
EXTRA = ("dfitems.pk3", "doomerfall.pk3")
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def city_group(region="Daggerfall", name="Daggerfall"):
    """The town cache group (DDT number) that holds this location, from ddruntime.pk3's DDGROUPS."""
    loc = next(l for l in dfdata.read_locations(str(ARENA2)) if l["region_name"] == region and l["name"] == name)
    tx, ty = loc["x"], 499 - loc["y"]
    data = REVIEW / "data" if (REVIEW / "data").exists() else BASE / "data"
    with zipfile.ZipFile(data / "ddruntime.pk3") as z:
        d = z.read("DDGROUPS")
    count, pos = struct.unpack_from("<i", d, 4)[0], 8
    for g in range(count):
        n, _large = struct.unpack_from("<hh", d, pos)
        pos += 4
        rects = [struct.unpack_from("<iiii", d, pos + 16 * i) for i in range(n)]
        pos += 16 * n
        if any(x0 // 128 == tx and y0 // 128 == ty for x0, _x1, y0, _y1 in rects):
            return g
    raise SystemExit(f"no group holds {region} / {name}")


def town_centre(group):
    """Centre of the group's largest location rectangle in the town map's Doom units, from the cached DDTOWN lump.
    The group is converted on first entry, so a first run without a cache file uses the map origin."""
    path = REVIEW / "data" / "cache" / f"T{group:05d}.ddt"
    if not path.exists():
        return 0.0, 0.0
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        body = ""
        for name, raw, packed in heads:
            data = f.read(packed)
            if name == "DDTOWN":
                body = (zlib.decompress(data) if raw else data).decode()
    rows = [l.split() for l in body.splitlines()]
    ox, oy = next((float(r[1]), float(r[2])) for r in rows if r[0] == "origin")
    x0, x1, y0, y1 = max((tuple(int(v) for v in r[1:5]) for r in rows if r[0] == "rect"), key=lambda r: (r[1] - r[0]) * (r[3] - r[2]))
    return ((x0 + x1) / 2 * 256 - ox) * 0.75, ((y0 + y1) / 2 * 256 - oy) * 0.75


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    cache, kept = REVIEW / "data" / "cache", REVIEW / "cache-kept"
    if cache.exists() and not kept.exists():   # converted towns survive a re-assemble
        shutil.move(str(cache), str(kept))
    for name in ("uzdoom", "dfu", "data"):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
    shutil.copytree(BASE / "uzdoom", REVIEW / "uzdoom")
    for f in UZ_BUILD.iterdir():   # this branch's engine over the base folder (sound DLLs and the like stay)
        if f.is_file() and f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, REVIEW / "uzdoom" / f.name)
    shutil.copytree(BASE / "data", REVIEW / "data")
    if kept.exists():
        if cache.exists():
            shutil.rmtree(cache)
        shutil.move(str(kept), str(cache))
    shutil.copy2(LAUNCHER_BUILD / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    for name in EXTRA:
        shutil.copy2(BASE / name, REVIEW / name)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_BUILD / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    write_demo(city_group())
    print("assembled", REVIEW)


def launch_args(play, group, uz_extra, df_extra, stock_mods=False):
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [REVIEW / "data" / n for n in DATA] + [REVIEW / n for n in EXTRA]
    uz = ["-config", str(play / "uzdoom.ini"), "-savedir", str(play / "saves"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(ARENA2), "+vid_fullscreen", "0", "+i_pauseinbackground", "0"] + uz_extra + ["+map", f"DDT{group:05d}"]
    df = ["-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0"] + df_extra
    args = ["--nodraw", "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
            "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(play)]
    for mod in mods:
        args += ["--mod", str(mod)]
    for a in uz:
        args += ["--uzdoom-arg", a]
    for a in df:
        args += ["--dfu-arg", a]
    return args


def write_demo(group):
    play = Path("%HERE%play")
    args = launch_args(play, group, ["-dfbridgelog", str(play / "uz.log")],
                       ["-dfbridgelog", str(play / "df.log"), "-dftownlevellog", "-screen-width", "1280", "-screen-height", "800", "-dfmute"])
    args = [a.replace(str(REVIEW) + "\\", "%HERE%") for a in args]
    i = args.index("--uzdoom-cwd")
    args[i:i] = ["--log", "%HERE%play\\launcher.log"]
    quoted = " ".join(f'"{a}"' if (" " in a or "%" in a or "\\" in a) else a for a in args)
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Town levels: starts in the City of Daggerfall (a capital, town level 20) with DRLA.\r\n"
        "rem Daggerfall writes the level where you stand to play\\df.log whenever it changes (\"townlevel: ...\").\r\n"
        "rem Walk out through a gate and on past the town map's edge: the level drops to the terrain level (2).\r\n"
        "rem The first visit converts the city in the background, so the first start can take a little longer.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" {quoted}\r\n",
        newline="")


def dump():
    out = REVIEW / "run" / "dump"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    # Paired runs get the data path from -dfsynctest. The standalone dump needs it in the private settings.
    ini = REVIEW / "dfu" / "PortableAppdata" / "settings.ini"
    if not ini.exists():
        ini.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE / "dfu" / "PortableAppdata" / "settings.ini", ini)
    ini.write_text(re.sub(r"(?m)^MyDaggerfallPath = .*$", lambda m: "MyDaggerfallPath = " + str(GAME / "DAGGER"), ini.read_text()))
    subprocess.call([sys.executable, QUIET, "--timeout", "90", "--", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
                     "-dfarealeveldump", str(out), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"],
                    stdin=subprocess.DEVNULL)
    subprocess.call([sys.executable, str(REPO / "tools" / "area_level" / "compare_runtime.py"), str(out)])
    body = read(out / "sample.txt")
    print(body[body.find("towns:"):] if "towns:" in body else body[-2000:])


def run(name, stock_mods, start):
    group = city_group()
    runs = REVIEW / "run" / name
    if runs.exists():
        shutil.rmtree(runs)
    (runs / "saves").mkdir(parents=True)
    uz_log, df_log, console = runs / "uz.log", runs / "df.log", runs / f"log-{name}.txt"
    cx, cy = town_centre(group)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "gate_walk.zs").read_text().replace("@START@", str(start))
                   .replace("@CITYX@", f"{cx:.1f}").replace("@CITYY@", f"{cy:.1f}"))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "TLGateWalk" }\n')
    uz = ["-noactivate", "-nosound", "-noautoload", "-dfbridgelog", str(uz_log), "+logfile", name, "+wipetype", "0",
          "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfworldleveltest", "1", "-dfworldleveltestontown", "-dftownlevellog", "-screen-width", "640", "-screen-height", "360"]
    args = launch_args(runs, group, uz, df, stock_mods) + ["--mod", str(harness), "--minimized", "--log", str(runs / "launcher.log")]
    timeout = 220
    proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe")] + args,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
        body = read(console)
        if "TLDONE" in body:
            reason = "route finished"
            time.sleep(1.5)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print(f"stopped: {reason} | map DDT{group:05d}")
    events = [(l.find("TL"), "uz " + l.strip()) for l in read(console).splitlines() if re.match(r"TL[A-Z]+", l) or any(k in l for k in FATAL)]
    for _, line in events:
        print(line[:200])
    guards = []
    for line in read(df_log).splitlines():
        m = re.search(r"worldleveltest: area here enemy Knight_CityWatch/\d+: level (\d+)", line)
        if m:
            guards.append(int(m.group(1)))
        if re.search(r"townlevel:|ammo: area level|worldleveltest: player level|worldleveltest: area here level|error|Exception", line):
            print("df", line[:330])
    if guards:
        ok = all(23 <= g <= 26 for g in guards)
        print(f"city watch guard levels here: {guards} (want 23-26 in a capital) {'PASS' if ok else 'FAIL'}")
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "dump", "run", "group"))
ap.add_argument("name", nargs="?", default="gate")
ap.add_argument("--stock-mods", action="store_true")
ap.add_argument("--start", type=int, default=700, help="run: tics on the town map before the walk starts")
a = ap.parse_args()
if a.command == "assemble":
    assemble()
elif a.command == "dump":
    dump()
elif a.command == "group":
    print(city_group())
else:
    run(a.name, a.stock_mods, a.start)
