"""Builds, assembles, and tests the monster death demo in a private review folder.

usage: monster_deaths.py build | unity | wad | assemble | run NAME [--load] | check | registry save|compare
Game data and generated maps stay outside the repo.
"""
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "item_pickup"))
import item_pickup as pickup  # noqa: E402

base = pickup.base
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\monster-deaths")
base.REVIEW, base.BUILD, base.RUN = REVIEW, REVIEW / "build", REVIEW / "run"
pickup.REVIEW = REVIEW
SOURCE_SPRITES = Path(r"D:\dev\DoomDaggerfall-loop\review\item-pickup\dfitems.pk3")
QUEST = "N0C00Y12"  # A shipped kill quest: one Imp at a marker in a remote dungeon, and no local town requirement.
WAD = "privateershold.wad"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error", "Execution could not continue", "Unable to open map")
EXTRA_DF = []  # Extra Daggerfall arguments for a run, set by tools that reuse this one.


def read_wad(path):
    data = Path(path).read_bytes()
    count, table = struct.unpack("<ii", data[4:12])
    return [(data[table + 16 * i + 8:table + 16 * i + 16].rstrip(b"\0").decode(),
             data[struct.unpack("<i", data[table + 16 * i:table + 16 * i + 4])[0]:][:struct.unpack("<i", data[table + 16 * i + 4:table + 16 * i + 8])[0]])
            for i in range(count)]


def write_wad(path, lumps):
    with open(path, "wb") as f:
        f.write(b"PWAD" + struct.pack("<ii", len(lumps), 12 + sum(len(d) for _, d in lumps)))
        offset = 12
        rows = b""
        for name, body in lumps:
            f.write(body)
            rows += struct.pack("<ii", offset, len(body)) + name.encode().ljust(8, b"\0")
            offset += len(body)
        f.write(rows)


def things(text):
    return re.findall(rb"thing \{[^}]*\}", text)


def make_wad():
    """Adds the converter's id lump to the packaged map, after proving both maps place the same things."""
    out = REVIEW / "wad"
    out.mkdir(parents=True, exist_ok=True)
    code = subprocess.call(["dotnet", "run", "-c", "Release", "-v", "q", "--project", str(base.WORKTREE / "tools" / "dungeon_converter" / "DungeonConverter.csproj"),
                            "--", "Privateer's Hold", "--out", str(out)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if code:
        sys.exit(f"converter failed ({code})")
    fresh = dict(read_wad(out / WAD))
    packaged = read_wad(pickup.DATA / WAD)
    old = things(dict(packaged)["TEXTMAP"])
    new = things(fresh["TEXTMAP"])
    rows = fresh["DDMONST"].decode().splitlines()
    print(f"things packaged {len(old)}, fresh {len(new)}, identical {old == new}, id rows {len(rows)}, unique ids {len({r.split()[1] for r in rows})}")
    if old != new:
        sys.exit("the packaged map places different things; refusing to attach ids to it")
    write_wad(out / ("ids_" + WAD), [l for l in packaged if l[0] != "DDMONST"] + [("DDMONST", fresh["DDMONST"])])


def assemble():
    base.assemble()
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(base.SOUND / name, REVIEW / "uzdoom")
    pickup.demo_data()
    shutil.copy2(REVIEW / "wad" / ("ids_" + WAD), REVIEW / "data" / WAD)
    shutil.copy2(SOURCE_SPRITES, REVIEW / "dfitems.pk3")
    here = "%HERE%"
    args = pickup.launch_args(here, [], ["-dfmonsterquest", QUEST])
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Starts at the Privateer's Hold door with a real kill quest running. Press Use to enter. Kill monsters, then press E on a drop.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={pickup.quoted(pickup.bind_args)}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" {pickup.quoted(args)} %BINDS%\r\n", newline="")
    print("assembled", REVIEW)


def run(name, load, drla=False, presave=False):
    fatal = tuple(k for k in FATAL if k != "Script error") if drla else FATAL  # The DRLA set always logs 3 known script errors.
    data, runs = REVIEW / "data", REVIEW / "run"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"log-{name}.txt", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    lumps = dict(pickup_lumps(data / "cache" / f"T{pickup.GROUP:05d}.ddt"))
    door = next(l.split() for l in lumps["DDDOORS"].decode().splitlines() if l.startswith("1 187853213"))
    with zipfile.ZipFile(data / "privateershold_doors.pk3") as z:
        exit_row = next(l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
    text = (HERE / "harness.zs").read_text().replace("@DOOR@", ", ".join(door[3:8])).replace("@EXIT@", ", ".join(exit_row[:5])).replace("@MODE@", "presave" if presave else "normal")
    harness = runs / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "MDHarness" }\n')
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-savedir", str(saves), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3", "-ddmontest",
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", base.DAGGER + r"\ARENA2",
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{pickup.GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", base.DAGGER, "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"] + EXTRA_DF
    if load:
        newest = max(saves.glob("*.zds"), key=lambda p: p.stat().st_mtime, default=None)
        if newest is None:
            sys.exit("no save to load")
        resume = saves / "resume.zds"
        if newest != resume:
            shutil.copy2(newest, resume)
        uz += ["-dfloadtest", "resume:" + str(resume), "+dd_ui_test_hold", "1"]
        df.append("-dfmonsterreport")
    else:
        for old in saves.glob("*.zds"):
            old.unlink()
        df += ["-dfmonsterquest", QUEST]
    timeout = 75
    command = [sys.executable, base.QUIET, "--timeout", str(timeout), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", base.IWAD2,
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    extra = [base.MODS / n for n in base.DRLA] if drla else []
    for mod in extra + [data / n for n in ("ddruntime.pk3", "overworld.pk3", WAD, "privateershold_mesh.pk3", "privateershold_doors.pk3")] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = base.read(console)
        if "MDDONE" in body:
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
        if re.match(r"MD[A-Z]+ ", line) or line.startswith("DDMON ") and "claimed" not in line or line.startswith("You ") or any(k in line for k in fatal):
            print(line[:170])
    print("claimed:", sum("DDMON claimed" in l for l in base.read(console).splitlines()))
    for line in base.read(df_log).splitlines():
        if "monsters:" in line or "error" in line or "ledger" in line:
            print("df", line[:190])
    player = REVIEW / "dfu" / "PortableAppdata" / "Player.log"
    kinds = sorted({l[:150] for l in base.read(player).splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:6]:
        print("  ", line)


def pickup_lumps(path):
    import zlib
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return [(name, zlib.decompress(f.read(packed)) if raw else b"") for name, raw, packed in heads]


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        base.build()
    elif command == "unity":
        base.unity()
    elif command == "wad":
        make_wad()
    elif command == "assemble":
        assemble()
    elif command == "run":
        run(sys.argv[2], "--load" in sys.argv, "--drla" in sys.argv, "--presave" in sys.argv)
    elif command == "playcheck":
        launch = pickup.launch_args
        pickup.launch_args = lambda here, uz=(), df=(), minimized=False: launch(here, uz, list(df) + ["-dfmonsterquest", QUEST], minimized)
        pickup.play_check()
        log = base.read(REVIEW / "dfu" / "PortableAppdata" / "Player.log")
        print("quest parsed:", f"Parsing quest {QUEST}" in log and f"Parsing quest {QUEST} FAILED" not in log)
    elif command == "check":
        base.check()
    elif command == "registry":
        base.registry(sys.argv[2])
    else:
        sys.exit(__doc__)
