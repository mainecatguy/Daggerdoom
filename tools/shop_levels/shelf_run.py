"""Shop levels 2: paired runs proving shelves restock at the shop's level, and a demo folder.

usage: shelf_run.py assemble | run NAME [--building TYPE] [--rates] [--stock-mods]
assemble copies this checkout's builds (UZDoom, launcher and bridge DLL from BUILD, Daggerfall Unity, doomerfall.pk3)
and data made by this checkout's converter (scripts/play/install.py make_data) into REVIEW, and writes play.bat. run walks into the first building of TYPE
(default GeneralStore; the test town has no other shop) in the test town and presses Use on its shelves (tools/shop_menu/harness.zs, with Daggerfall's
-dfshoptest closing each window), then prints Daggerfall's "shop restock" lines: the level each shelf rolled at.
--rates also passes -dfshoplevelrates (1,000 weapon smith and armorer shelves at several levels).
--ledger passes -dfshopledgertest and prints its lines (shops 5).
--lots passes -dfshoplotstest and prints its lines (shops 7).
--identity passes -dfshopidentitytest and prints its lines (shops 6: survey of shop identities).
--buildinglevels passes -dfbuildingleveltest and prints its lines: the level inside each building entered (shop levels 4).
--review DIR assembles into or runs from another demo folder; assemble copies the data from the default folder if DIR has none.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = DEFAULT_REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\shop-shelf-levels")
BUILD = Path(r"D:\dev\DoomDaggerfall-build")

def build_dirs(tag):
    """Build dirs BUILD/{uzdoom,bridge,launcher}-TAG (--build-tag; another checkout may own the default)."""
    return BUILD / f"uzdoom-{tag}" / "Release", BUILD / f"bridge-{tag}" / "Release", BUILD / f"launcher-{tag}" / "Release"


UZ_BUILD, BRIDGE_BUILD, LAUNCHER_BUILD = build_dirs("shoplvl")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
EXTRA = ("dfitems.pk3", "doomerfall.pk3")
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    import struct
    import zlib
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    if REVIEW != DEFAULT_REVIEW and not (REVIEW / "data").exists() and (DEFAULT_REVIEW / "data" / "converter").exists():
        shutil.copytree(DEFAULT_REVIEW / "data", REVIEW / "data")
        shutil.copy2(DEFAULT_REVIEW / "dfitems.pk3", REVIEW / "dfitems.pk3")
    if not (REVIEW / "data" / "converter").exists() or "--fresh-data" in sys.argv:
        install.make_data(BUILD / "shoplvl-data", REVIEW)   # data, town cache and dfitems.pk3 from this checkout's converter
    for name, source in (("uzdoom", UZ_BUILD), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(BUILD / "uzdoom-launcher" / "Release" / dll, REVIEW / "uzdoom" / dll)
    shutil.copy2(LAUNCHER_BUILD / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    (REVIEW / "doomerfall-drla.pk3").unlink(missing_ok=True)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_BUILD / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    write_demo(args.demo_building, args.nth)
    print("assembled", REVIEW)


def building_doors(kind):
    """Doors of buildings of this Daggerfall type in the test town, as (building index, door row)."""
    data = REVIEW / "data"
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    rows = [l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    return [r for r in rows if types.get(int(r[1])) == kind]


def launch_args(play, uz_extra, df_extra, stock_mods=False):
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / n for n in EXTRA]
    uz = ["-config", str(play / "uzdoom.ini"), "-savedir", str(play / "saves"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+vid_fullscreen", "0", "+i_pauseinbackground", "0"] + uz_extra + ["+map", f"DDT{GROUP:05d}"]
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


def write_demo(kind="GeneralStore", nth=0):
    door = building_doors(kind)[nth]
    start = f"""version "4.14"
// Demo only: starts the player a few steps from a {kind} door, facing it.
class SLDemoStart : StaticEventHandler
{{
	bool done;
	override void WorldLoaded(WorldEvent e) {{ if (e.IsSaveGame) done = true; }}
	override void WorldTick()
	{{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		let p = players[0].mo;
		p.SetOrigin(({door[3]} + {door[6]} * 160, {door[4]} + {door[7]} * 160, {door[5]}), false);
		p.angle = atan2(-({door[7]}), -({door[6]}));
	}}
}}
"""
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", start)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SLDemoStart" }\n')
    play = Path("%HERE%play")
    df = ["-dfbridgelog", str(play / "df.log"), "-screen-width", "1280", "-screen-height", "800", "-dfmute"]
    if kind != "GeneralStore":
        df += ["-dfbuildingleveltest", str(play / "buildings.log")]
    args = launch_args(play, ["-dfbridgelog", str(play / "uz.log")], df)
    args = [a.replace(str(REVIEW) + "\\", "%HERE%") for a in args]
    i = args.index("--uzdoom-cwd")
    args[i:i] = ["--mod", "%HERE%demo_start.pk3", "--log", "%HERE%play\\launcher.log"]
    quoted = " ".join(f'"{a}"' if (" " in a or "%" in a or "\\" in a) else a for a in args)
    if kind == "GeneralStore":
        about = ("rem Shop shelves roll at the shop's level. Town start with DRLA, facing a general store. Go in and Use a shelf.\r\n"
                 "rem Daggerfall writes the shop's level for each restock to play\\df.log (\"shop restock: ... at shop level N\").\r\n"
                 "rem Shelves are a ledger: each day cheap goods sell off fast and pricey goods slowly. Each shop has a fixed identity (lean,\r\n"
                 "rem breadth, trickle or big-delivery rhythm, regular suppliers); goods arrive on its delivery days, Doom ammo daily.\r\n"
                 "rem Sell something to the shopkeeper: it goes on a shelf. Rest a few days and look again (play\\df.log has \"shop ledger:\" lines).\r\n")
    else:
        about = (f"rem Houses and guild halls roll loot at a level from their own quality. Town start with DRLA, facing a {kind}.\r\n"
                 "rem Go into any building: play\\buildings.log gets one line per building with the level things roll at\r\n"
                 "rem (current) and the level enemies are made at (danger). Gothway Garden's Mages Guild is quality 17: level 24.\r\n"
                 "rem In the Mages Guild, Buy Magic Items to see level 24 stock; house containers roll at the house's level.\r\n")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n" + about +
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" {quoted}\r\n",
        newline="")


def run(name, building, rates, stock_mods, building_levels=False, nth=0, ledger=False, lots=False, identity=False):
    runs = REVIEW / "run" / name
    if runs.exists():
        shutil.rmtree(runs)
    (runs / "saves").mkdir(parents=True)
    uz_log, df_log, console = runs / "uz.log", runs / "df.log", runs / f"log-{name}.txt"
    door = building_doors(building)[nth]
    text = (REPO / "tools" / "shop_menu" / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8]))
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SMHarness" }\n')
    uz = ["-noactivate", "-nosound", "-noautoload", "-dfbridgelog", str(uz_log), "+logfile", name, "+wipetype", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfshoptest", "-screen-width", "640", "-screen-height", "360"] + (["-dfshoplevelrates"] if rates else []) + (["-dfshopledgertest"] if ledger else []) + (["-dfshoplotstest"] if lots else []) + (["-dfshopidentitytest"] if identity else [])
    if building_levels:
        df += ["-dfbuildingleveltest", str(runs / "buildings.log")]
    args = launch_args(runs, uz, df, stock_mods) + ["--mod", str(harness), "--minimized", "--log", str(runs / "launcher.log")]
    timeout = max(120, 450 * (ledger + lots + identity))   # each survey takes up to about 5 minutes
    proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe")] + args,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = read(console)
        dflog = read(df_log)
        if "NDDONE" in body and (not rates or "shoplevelrates: done" in dflog) and (not ledger or "shopledger: done" in dflog or "shopledger: FAILED" in dflog) and (not lots or "shoplots: done" in dflog or "shoplots: FAILED" in dflog) and (not identity or "shopidentity: done" in dflog or "shopidentity: FAILED" in dflog):
            reason = "route finished"
            time.sleep(1)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason, "| door", door[:3])
    for line in read(console).splitlines():
        if re.match(r"ND[A-Z]+ ", line) or any(k in line for k in FATAL):
            print(line[:190])
    for line in read(df_log).splitlines():
        if re.search(r"shop restock:|interior layout:|shoplevelrates:|shopledger:|shop ledger:|shoplots:|shopidentity:|items: (restored|closed)|shoptest: (Weapon|General|window|bought)|error", line):
            print("df", line[:1500])
    for line in read(runs / "buildings.log").splitlines():
        print("df", line[:1500])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--building", default="GeneralStore", help="Daggerfall building type to go into, as the converter lists it")
ap.add_argument("--rates", action="store_true")
ap.add_argument("--stock-mods", action="store_true")
ap.add_argument("--buildinglevels", action="store_true")
ap.add_argument("--ledger", action="store_true", help="also pass -dfshopledgertest (shops 5: months of simulated restocks)")
ap.add_argument("--lots", action="store_true", help="also pass -dfshoplotstest (shops 7: lot and exception survey)")
ap.add_argument("--identity", action="store_true", help="also pass -dfshopidentitytest (shops 6: survey of shop identities)")
ap.add_argument("--nth", type=int, default=0, help="which door of that building type (0 = first), for run and the demo")
ap.add_argument("--demo-building", default="GeneralStore", help="assemble: building type the demo starts facing")
ap.add_argument("--review", help="demo folder to assemble into or run from (default: the shop shelves demo)")
ap.add_argument("--fresh-data", action="store_true", help="assemble: remake the data even if present")
ap.add_argument("--build-tag", default="shoplvl", help="assemble: use the builds in BUILD/{uzdoom,bridge,launcher}-TAG")
args = ap.parse_args()
UZ_BUILD, BRIDGE_BUILD, LAUNCHER_BUILD = build_dirs(args.build_tag)
if args.review:
    REVIEW = Path(args.review)
if args.command == "assemble":
    assemble()
else:
    run(args.name, args.building, args.rates, args.stock_mods, args.buildinglevels, args.nth, args.ledger, args.lots, args.identity)
