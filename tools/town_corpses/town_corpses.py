"""Daggerfall townspeople and guards leave corpses in Doom, drawn from Daggerfall's own files at run time.

usage: town_corpses.py assemble <source review folder> | run NAME (kill | guard | load | guardload | guardreload) [--pack] | check
assemble builds review\\town-corpses from a paired review folder (data, dfitems.pk3, portable Daggerfall Unity) with
this checkout's UZDoom (D:\\dev\\DoomDaggerfall-build\\uzdoom-corpses), launcher, bridge, Daggerfall Unity build and
doomerfall.pk3, and writes the demo play.bat.
run kill: town start with DRLA; kill the nearest townsperson (test only), screenshots before, during the blood splash
and of the corpse, leave town and walk back, list the corpses again, autosave.
run guard: the same at noon with Daggerfall's -dfguardtest: enter the Gothway tavern, kill one of the guard bots
Daggerfall sends in, screenshots, go out and back in, list the corpses again, autosave.
run guardreload: load the guard autosave with -dfguardtest, kill one of the new guards, list the corpses (two).
run load / guardload: load that autosave in a fresh launch and list the corpses. --pack first puts a stand-in texture pack image
for the human corpse (TEXTURE.380 record 1) in Daggerfall Unity's StreamingAssets/Textures, and removes it after.
The stand-in is drawn here (a plain shape), not taken from the game.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
"""
import re
import shutil
import struct
import zlib
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
# Copied from tools/hud_messages/hud_messages.py, which parses its command line on import.
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\town-corpses")
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")
STEP, SHOTS = 0.25, 21
DOOM_BORDER = (28, 79)  # Doom's window size includes its frame here: asking 1280x800 gives a 1252x721 screen (log "Resolution:")

def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def size_args(w, h):
    return ["-width", str(w), "-height", str(h), "+vid_fullscreen", "0", "+win_w", str(w), "+win_h", str(h), "+vid_scalemode", "0", "+vid_scalefactor", "1"]


def launch_args(runs, uz_extra, df_extra, minimized, size=(1280, 800)):
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"]:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0",
          "-screen-width", str(size[0]), "-screen-height", str(size[1])] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3")] + \
                  ([str(REVIEW / "doomerfall-drla.pk3")] if mods else []) + ["+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))


# Copied from tools/npc_kill/npckill.py.
def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def tavern_door():
    """The Gothway tavern's door row (x y z nx ny in fields 3-7), as tools/npc_kill/npckill.py picks it."""
    data = REVIEW / "data"
    listed = subprocess.run([str(data / "converter" / "DungeonConverter.exe"), "--group", str(GROUP), "--list-buildings", "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    types = {int(m[0]): m[1] for m in re.findall(r"BUILDING (\d+) (\S+)", listed.stdout)}
    rows = [l.split() for l in lumps(data / "cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    return next(r for r in rows if types.get(int(r[1])) == "Tavern")


PACK = REVIEW / "dfu" / "DaggerfallUnity_Data" / "StreamingAssets" / "Textures" / "380_1-0.png"


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data", "dfu"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(source / "data", REVIEW / "data")
    shutil.copytree(BUILD / "uzdoom-corpses" / "Release", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.lib", "*.exp"))
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    shutil.copy2(source / "dfitems.pk3", REVIEW / "dfitems.pk3")
    for name in ("launcher", "bridge"):
        out = BUILD / f"corpses-{name}"
        subprocess.check_call(["cmake", "-S", str(REPO / name), "-B", str(out), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=subprocess.DEVNULL)
        subprocess.check_call(["cmake", "--build", str(out), "--config", "Release", "--parallel", "6"], stdout=subprocess.DEVNULL)
    shutil.copy2(BUILD / "corpses-launcher" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(BUILD / "corpses-bridge" / "Release" / "doomerfall_bridge.dll", REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64")
    shutil.copy2(source / "dfu" / "Portable.txt", REVIEW / "dfu")
    shutil.copytree(source / "dfu" / "PortableAppdata", REVIEW / "dfu" / "PortableAppdata", dirs_exist_ok=True)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    play = REVIEW / "play"
    command = launch_args(play, size_args(1280, 800) + ["+i_pauseinbackground", "0"], ["-dfmute"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Townspeople leave corpses. Town start with DRLA in a 1280x800 window.\r\n"
        "rem Shoot a townsperson: Daggerfall's blood splash plays and Daggerfall's corpse stays where they fell. Daggerfall\r\n"
        "rem counts it as murder and calls the guards. Walk out of town and back, or save and load: the corpse is still there.\r\n"
        "rem Kill a guard inside a building: the same. The images come from Daggerfall's own files, so a texture pack\r\n"
        "rem image in dfu\\DaggerfallUnity_Data\\StreamingAssets\\Textures (for example 380_1-0.png) shows in Doom too.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


def make_pack():
    from PIL import Image, ImageDraw
    PACK.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (256, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 40, 248, 92), fill=(255, 0, 255, 255), outline=(0, 255, 0, 255), width=6)
    d.text((90, 56), "TEXTURE PACK", fill=(0, 0, 0, 255))
    img.save(PACK)


def run(name, mode, pack):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    runs.mkdir(parents=True)
    saves = REVIEW / "run" / "saves"
    saves.mkdir(exist_ok=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@MODE@", mode).replace("@DOOR@", ", ".join(tavern_door()[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "TCHarness" }\n')
    console = runs / "log-console.txt"
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "-file", str(harness), "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+dd_debugmessages", "0"] + size_args(1280, 800)
    if mode.endswith("load"):
        newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
        if newest is None:
            sys.exit("no save to load")
        resume = saves / "resume.zds"
        shutil.copy2(newest, resume)
        uz += ["-dfloadtest", "resume:" + str(resume), "+dd_ui_test_hold", "1"]
    else:
        for old in saves.glob("*.zds"):
            old.unlink()
    uz = [a if a != str(runs / "saves") else str(saves) for a in uz]
    if pack:
        make_pack()
    timeout = 100 if mode.endswith("load") else 150
    df = ["-dfmute"] + ([] if mode.endswith("load") else ["-dftownhour", "12"]) + (["-dfguardtest"] if mode in ("guard", "guardreload") else [])
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, uz, df, False)
    command = [str(saves) if a == str(runs / "saves") else a for a in command]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, shots, sent = "timeout", time.time() + timeout + 3, set(), 0
    try:
        while time.time() < end and proc.poll() is None:
            time.sleep(0.05)
            body = read(console)
            if any(k in body for k in FATAL):
                reason = "fatal"
                break
            for line in body.splitlines():
                if line.startswith("TCSHOT ") and line not in shots:
                    shots.add(line)
                    with open(inbox, "a") as f:
                        f.write(f"s{sent} con screenshot \"{runs / (line.split()[1] + '.png')}\"\n")
                    sent += 1
            if "TCDONE" in body:
                reason = "done"
                time.sleep(1.5)
                break
    finally:
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
        if pack:
            PACK.unlink(missing_ok=True)
    print("stopped:", reason)
    for line in read(console).splitlines():
        if line.startswith("TC") or any(k in line for k in FATAL):
            print(line[:220])
    for line in read(runs / "uz.log").splitlines():
        if "DDCORPSE" in line or "DDDFTEX" in line:
            print("UZ", line[:220])
    for line in read(runs / "df.log").splitlines():
        if "corpse" in line or "guardtest: called" in line or "guards:" in line or "town: death" in line or "town: murder" in line or "ledger" in line or "exception" in line.lower():
            print("DF", line[:220])


if __name__ == "__main__":
    argv = sys.argv
    command = argv[1] if len(argv) > 1 else ""
    if command == "assemble" and len(argv) > 2:
        assemble(Path(argv[2]))
    elif command == "run" and len(argv) > 3:
        run(argv[2], argv[3], "--pack" in argv)
    elif command == "check":
        check()
    else:
        sys.exit(__doc__)
