"""Tests the map command with both real games, minimized, one scenario per launch.

usage: run_map.py town|wild|building|dungeon|doom|travel-colliders|travel-doommap|stock
Each launch has a private config and a time limit, and stops at once on a fatal error.
"""
import ctypes
import re
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "inventory_menu"))
import inventory_menu as base  # noqa: E402

HERE = Path(__file__).parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\daggerfall-map")
RUN = REVIEW / "run"
CACHE = REVIEW / "test-cache"
BASELINE = Path(r"D:\dev\DoomDaggerfall-loop\review\connected-transitions\uzdoom\uzdoom.exe")
VK_J, ROW_HEIGHT = 0x4A, 6
TIMEOUT = 30
HOUSE, GARDEN = (9183, "10403728"), (7154, "dungeon")


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def door_harness(path, group, target):
    """The transition suite's door walker, holding inside until the map command has been tested."""
    doors = [l.split() for l in lumps(CACHE / f"T{group:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
    door = next(d for d in doors if (d[0] == "1" if target == "dungeon" else d[0] == "0" and d[1] == target))
    text = (HERE.parent / "overworld" / "door_harness.zs").read_text()
    text = text.replace("@DOORS@", ", ".join(door[3:8])).replace("@EXITS@", "0, 0, 0, 0, 0").replace("@MODE@", "shot")
    text = text.replace("if (inside || level.maptime < 4) break;", 'if (inside || level.maptime < 4 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;')
    text = text.replace('Console.Printf("DTARRIVE', 'CVar.FindCVar("dd_ui_test_hold").SetInt(0); Console.Printf("DTARRIVE').replace("st.timer > 330", "st.timer > 3000")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DTHarness" }\n')


def automap_probe(path):
    text = 'version "4.14"\nclass AMProbe : EventHandler { int last; override void WorldTick() { int now = automapactive; ' \
           'if (now != last) Console.Printf("AMSTATE %d", now); last = now; } }\n'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AMProbe" }\n')


def launch(name, start, mods, extra, opens):
    run = RUN / name
    (run / "saves").mkdir(parents=True, exist_ok=True)
    logs = {k: run / f"{k}.log" for k in ("uz", "df", "launcher")}
    console = run / "log-console.txt"
    for path in (*logs.values(), console, run / "uz.ini"):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(logs["uz"]), "-dfuitest", str(opens),
          "-ddtowncache", str(CACHE), "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"), "-ddarena2", base.DAGGER + r"\ARENA2",
          "-nosound", "-noautoload", "-skill", "3", "+logfile", "console", "+map", start, "+bind", "j", "togglemap",
          "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(run / "shots"),
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", *extra]
    df = ["-dfbridgelog", str(logs["df"]), "-dfsynctest", base.DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, base.QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", base.IWAD2,
               "--uzdoom-cwd", str(run), "--log", str(logs["launcher"])]
    for mod in mods:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc, logs, console, time.time() + TIMEOUT


def stop(proc):
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()


def report(name, result, logs, console):
    print(f"[{name}] stopped: {result}")
    for line in base.read(console).splitlines():
        if any(k in line for k in base.FATAL) or line.startswith(("AMSTATE", "DTFAIL")):
            print("  doom", line[:170])
    keys = ("ui: map", "top window", "ui: closed", "asked Daggerfall", "opened menu", "travel:", "ui test: Doom", "error", "Daggerfall is in")
    for label in ("uz", "df"):
        for line in base.read(logs[label]).splitlines():
            if any(k in line for k in keys):
                print(f"  {label}", line[:190])
    player = base.read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines()
    where = [next((l.strip()[:90] for l in player[i + 1:i + 4] if "DaggerfallWorkshop" in l), "unknown") for i, l in enumerate(player) if "Exception" in l]
    other = [w for w in where if "DaggerfallUI.SetupSingleton" not in w]
    print(f"  Daggerfall exceptions: {len(other)} new, {len(where) - len(other)} known startup", sorted(set(other))[:3])


def open_close(name, start, mods, extra=()):
    """Opens through the real command, holds for a screenshot, and closes with the bound key."""
    proc, logs, console, deadline = launch(name, start, mods, ["+dd_ui_test_menu", "3", *extra], 2)
    result = "no menu seen"
    try:
        if base.wait_for(logs["uz"], "ui test: screenshot", 1, deadline, proc, console):
            size = re.search(r"opened menu 3 at (\d+)x(\d+)", base.read(logs["uz"]))
            doom = base.Doom(logs["launcher"], [int(size.group(1)), int(size.group(2))])
            time.sleep(0.5)
            doom.key(VK_J)
            result = "bound key did not close it"
            if base.wait_for(logs["uz"], "ui: closed", 1, deadline, proc, console):
                result = "opened and closed"
                time.sleep(0.7)
    finally:
        stop(proc)
    report(name, result, logs, console)


def travel(name, extra):
    """Travels through Daggerfall's real map, then checks what Doom left open."""
    proc, logs, console, deadline = launch(name, "DDOVER01", [REVIEW / "ddruntime.pk3", REVIEW / "overworld.pk3", REVIEW / "doomerfall"], extra, 1)
    result = "no menu seen"
    try:
        if base.wait_for(logs["uz"], "ui test: screenshot", 1, deadline, proc, console):
            size = re.search(r"opened menu \d at (\d+)x(\d+)", base.read(logs["uz"]))
            doom = base.Doom(logs["launcher"], [int(size.group(1)), int(size.group(2))])
            doom.click(20, 190)  # I'm At.
            time.sleep(0.7)
            doom.key(0x0D)  # Open the region.
            time.sleep(0.7)
            doom.key(0x4C)  # The location list.
            time.sleep(0.6)
            lp = doom.point(100, 64)
            doom.user.PostMessageW(doom.hwnd, 0x200, base.TEST_MARK, lp)
            time.sleep(0.25)
            for _ in range(2):  # A double click on the first row.
                doom.user.PostMessageW(doom.hwnd, 0x201, 1 | base.TEST_MARK, lp)
                time.sleep(0.05)
                doom.user.PostMessageW(doom.hwnd, 0x202, base.TEST_MARK, lp)
                time.sleep(0.05)
            if base.wait_for(logs["df"], "top window is DaggerfallMessageBox", 1, deadline, proc, console):
                time.sleep(0.3)
                doom.key(0x59)  # Yes.
            if base.wait_for(logs["df"], "top window is DaggerfallTravelPopUp", 1, deadline, proc, console):
                time.sleep(0.4)
                doom.key(0x42)  # Begin.
            result = "arrival not seen"
            if base.wait_for(logs["df"], "travel: Doom reached", 1, deadline, proc, console):
                result = "arrived"
                time.sleep(1.0)
    finally:
        stop(proc)
    report(name, result, logs, console)


def stock():
    def doom(name, files, exe):
        base.RUN.mkdir(parents=True, exist_ok=True)
        log = RUN / f"log-{name}.txt"
        log.unlink(missing_ok=True)
        args = [str(exe), "-iwad", base.IWAD1, "-config", str(RUN / f"{name}.ini"), "-nosound", "-noautoload", "-noactivate", "-skill", "3",
                "+logfile", name, "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                "+vid_lowerinbackground", "0", "+map", "E1M1", "+wait 70;togglemap;wait 35;togglemap;wait 35;quit"]
        if files:
            args[3:3] = ["-file"] + [str(base.MODS / f) for f in files]
        code = subprocess.call([sys.executable, base.QUIET, "--timeout", "30", "--cwd", str(RUN), "--"] + args,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        text = base.read(log)
        bad = [l for l in text.splitlines() if any(k in l for k in ("Fatal error", "FATAL", "VM execution aborted", "Script error"))]
        print(f"{name}: exit {code}, E1M1 {'E1M1' in text}, bridge lines {text.count('[bridge]')}, error lines {len(bad)}, unknown-class lines {text.count('Unknown class name')}")

    now = REVIEW / "uzdoom" / "uzdoom.exe"
    doom("stock", [], now)
    doom("drla", base.DRLA, now)
    doom("drla-before", base.DRLA, BASELINE)
    exe = REVIEW / "dfu" / "DaggerfallUnity.exe"
    code = subprocess.call([sys.executable, base.QUIET, "--timeout", "12", "--", str(exe), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    text = base.read(REVIEW / "dfu" / "PortableAppdata" / "Player.log")
    print(f"plain Daggerfall: exit {code}, bridge mentions {text.lower().count('doomerfall_bridge')}, DoomerfallUi mentions {text.count('DoomerfallUi')}, exceptions {text.count('Exception')}")


def main():
    which = sys.argv[1]
    RUN.mkdir(parents=True, exist_ok=True)
    world = [REVIEW / "ddruntime.pk3", REVIEW / "overworld.pk3"]
    dungeon = [REVIEW / n for n in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    if which == "town":
        open_close("town", "DDT07154", [*world, *dungeon, REVIEW / "doomerfall"])
    elif which == "city":
        open_close("city", "DDT09183", [*world, *dungeon, REVIEW / "doomerfall"])
    elif which == "wild":
        open_close("wild", "DDOVER01", [*world, REVIEW / "doomerfall"])
    elif which in ("building", "dungeon"):
        group, target = HOUSE if which == "building" else GARDEN
        (RUN / which).mkdir(parents=True, exist_ok=True)
        harness = RUN / which / "harness.pk3"
        door_harness(harness, group, target)
        open_close(which, f"DDT{group:05d}", [*world, *dungeon, harness], ["+dd_ui_test_hold", "1"])
    elif which == "doom":
        (RUN / "doom").mkdir(parents=True, exist_ok=True)
        probe = RUN / "doom" / "probe.pk3"
        automap_probe(probe)
        proc, logs, console, deadline = launch("doom", "MAP01", [*world, probe], ["+wait 140;togglemap;wait 70;togglemap"], 0)  # Daggerfall stays out of play on a non-Daggerfall map.
        try:
            result = "Doom's map opened and closed" if base.wait_for(console, "AMSTATE", 2, deadline, proc, console) else "Doom's map did not toggle twice"
        finally:
            stop(proc)
        report("doom", result, logs, console)
    elif which == "travel-colliders":
        travel(which, ["+dd_ui_test_menu", "3", "+dfmesh_view", "0"])
    elif which == "travel-doommap":
        travel(which, ["+dd_ui_test_menu", "1", "+dd_ui_test_doommap", "1"])
    elif which == "stock":
        stock()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
