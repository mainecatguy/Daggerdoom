"""Assembles and tests the Use-to-pick-up rule with both real games, minimized.

usage: autopickup.py assemble | run NAME [--stock-mods] | check
run uses DRLA, DRLA Monsters, and DRLAX unless --stock-mods is given. check runs E1M1 with no bridge.
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
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\autopickup")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\monster-deaths")
UZ_BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-autopickup\Release")
SOUND = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
BRIDGE_DLL = Path(r"D:\dev\DoomDaggerfall-build\bridge-autopickup\Release\doomerfall_bridge.dll")  # The header's layout check must match.
LAUNCHER = Path(r"D:\dev\DoomDaggerfall-build\launcher-autopickup\Release\doomerfall-launcher.exe")  # It creates the session, so it must match too.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")

STOCK_TOUCH = ["Stimpack", "Medikit", "HealthBonus", "Soulsphere", "Megasphere", "Clip", "ClipBox", "Shell", "ShellBox", "RocketAmmo", "RocketBox", "Cell", "CellPack"]
DRLA_TOUCH = ["RLHealthBonus", "RLStimpack", "RLMedikit", "RLSoulsphere", "RLMegasphere", "RLClip", "RLClipBox", "RLShell", "RLShellBox", "RLRocketAmmo", "RLRocketBox", "RLCell", "RLCellPack"]
STOCK_USE = ["Chaingun", "GreenArmor", "ArmorBonus", "BlueCard", "Backpack", "Blursphere", "Berserk"]
DRLA_USE = ["RLGreenArmorPickup", "RLPistolPickup","RLBulletProofVestArmorPickup", "RLBlurSphere", "RLBerserk", "RLPhaseDevice"]

STOCK_CHECK = """version "4.14"
class APStock : EventHandler
{
	int t;
	Actor item;
	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p) return;
		t++;
		if (t == 10) item = Actor.Spawn("Chaingun", p.pos, NO_REPLACE);
		if (t > 10 && t < 40) p.TryMove(p.pos.xy + ((t & 1) ? (1, 0) : (-1, 0)), 0);
		if (t == 40)
		{
			Console.Printf("APSTOCK touch pickup of a weapon: %s", !item || !item.bSPECIAL ? "pass" : "FAIL");
			Console.Printf("APDONE");
		}
	}
}
"""


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", UZ_BUILD), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if not (REVIEW / "data").exists():
        shutil.copytree(SOURCE / "data", REVIEW / "data")
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    # A row of real DRLA items just inside the dungeon, so the rule can be tried at once.
    touch = ["RLStimpack", "RLClipBox", "RLShellBox"]
    use = ["RLPistolPickup", "RLBulletProofVestArmorPickup", "RLBlurSphere"]
    names = ", ".join(f'"{n}"' for n in touch + use)
    demo = f"""version "4.14"
class APDemo : EventHandler
{{
	static const String ITEMS[] = {{ {names} }};
	override void WorldLoaded(WorldEvent e)
	{{
		if (e.IsSaveGame || !(level.MapName.Left(3) ~== "DDS")) return;
		let p = players[0].mo;
		if (!p) return;
		vector2 f = (cos(p.angle), sin(p.angle)), s = (-f.y, f.x);
		for (int i = 0; i < ITEMS.Size(); i++)
		{{
			class<Actor> c = ITEMS[i];
			if (c) Actor.Spawn(c, (p.pos.xy + f * 72 + s * (i - 2.5) * 24, p.pos.z), NO_REPLACE);
		}}
	}}
}}
"""
    with zipfile.ZipFile(REVIEW / "demo_items.pk3", "w") as z:
        z.writestr("zscript.txt", demo)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "APDemo" }\n')
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"))
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Starts at the Privateer's Hold door with DRLA. Press Use to enter. Health and ammo pick up by touch.\r\n"
        "rem Weapons, armor, and powerups need Use while you look at them. Crouch and press Use to Steal.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        "if not exist \"%HERE%play\\uzdoom.ini\" set BINDS=--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%demo_items.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


def run(name, stock_mods):
    data, runs = REVIEW / "data", REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "saves").mkdir(exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    door = next(l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    touch = STOCK_TOUCH if stock_mods else STOCK_TOUCH + DRLA_TOUCH
    # DRLA replaces stock armor with its own system, which refuses an unreplaced GreenArmor.
    use = STOCK_USE if stock_mods else [n for n in STOCK_USE if n != "GreenArmor"] + DRLA_USE
    text = (HERE / "harness.zs").read_text()
    for key, value in (("@DOOR@", ", ".join(door[3:8])), ("@TOUCH@", ", ".join(f'"{n}"' for n in touch)), ("@USE@", ", ".join(f'"{n}"' for n in use))):
        text = text.replace(key, value)
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "APHarness" }\n')
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    timeout = 45 if stock_mods else 60
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [data / n for n in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness]
    for mod in mods:
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
    for line in read(console).splitlines():
        if re.match(r"AP[A-Z]+ ", line) or any(k in line for k in FATAL):
            print(line[:170])
    for line in read(df_log).splitlines():
        if "items: take" in line:
            print("df", line[:200])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    harness = runs / "stock_check.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", STOCK_CHECK)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "APStock" }\n')
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(harness), "+logfile", log.name, "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()), "| script errors", sum("Script error" in l for l in body.splitlines()), "| unknown class", sum("Unknown" in l for l in body.splitlines()))
        for line in body.splitlines():
            if line.startswith("APSTOCK") or any(k in line for k in FATAL):
                print(" ", line[:150])


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--stock-mods", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "run":
    run(args.name, args.stock_mods)
else:
    check()
