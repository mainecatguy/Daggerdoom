"""Repeated door trips, checking that the mesh in the GPU buffer is the mesh of the place the player is in.

Usage: check.py --exe PATH_TO_UZDOOM [--only NAME] [--cycles 6]
Every "DFMesh: loaded" line is a buffer replacement, so the last one before leaving a place says what was drawn there.
Exit code 0 means every scenario passed. Files stay in the review folder.
"""
import argparse
import hashlib
import re
import shutil
import struct
import subprocess
import sys
import time
import winreg
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync-10hz")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeon-reentry")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
REAL_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")
GROUP = 7154
TIMEOUT = 30


def registry_hash():
    digest = hashlib.sha256()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REAL_KEY) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                digest.update(repr(winreg.EnumValue(key, index)).encode())
    except OSError:
        return "absent"
    return digest.hexdigest()


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def triangles(mesh):
    return struct.unpack_from("<i", mesh, 20)[0] // 3


def prepare():
    """A private copy of the demo's data, so no run touches another review folder."""
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3", "doomerfall-launcher.exe"):
        if not (REVIEW / name).exists():
            shutil.copy2(SOURCE / name, REVIEW / name)
    for name in ("town-cache", "converter", "dfu", "doomerfall"):
        if not (REVIEW / name).exists():
            shutil.copytree(SOURCE / name, REVIEW / name)


def scenario_data(kind):
    doors = [l.split() for l in lumps(REVIEW / "town-cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
    if kind == "dungeon":
        door = next(d for d in doors if d[0] == "1")
        with zipfile.ZipFile(REVIEW / "privateershold_doors.pk3") as z:
            exit_spot = next(l.split()[1:6] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
        with zipfile.ZipFile(REVIEW / "privateershold_mesh.pk3") as z:
            name = next(n for n in z.namelist() if Path(n).stem.upper() == "DFMESH")
            expected = triangles(z.read(name))
        return door, exit_spot, expected
    for door in doors:
        path = REVIEW / "town-cache" / f"T{door[1]}.ddt"
        if door[0] == "0" and path.exists():
            return door, ["0"] * 5, triangles(lumps(path)["DFMESH"])
    sys.exit("no cached building door in this town")


def run(exe, name, kind, fireball, bridge, cycles):
    door, exit_spot, expected = scenario_data(kind)
    folder = REVIEW / "test" / f"{exe.parent.parent.name}-{name}"
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "saves").mkdir(parents=True)
    console = folder / "log-console.txt"
    text = (HERE / "harness.zs").read_text()
    for key, value in (("@DOOR@", ", ".join(door[3:8])), ("@EXIT@", ", ".join(exit_spot)), ("@CYCLES@", str(cycles)),
                       ("@FIREBALL@", str(int(fireball))), ("@BRIDGE@", str(int(bridge)))):
        text = text.replace(key, value)
    harness = folder / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DRHarness" }\n')
    mods = [str(REVIEW / m) for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")] + [str(harness)]
    uz = ["-noactivate", "-config", str(folder / "uz.ini"), "-savedir", str(folder / "saves"), "-nosound", "-ddtowncache", str(REVIEW / "town-cache"),
          "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3",
          "+logfile", "console", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
          "+map", f"DDT{GROUP:05d}", f"+wait {(cycles * 90 + 140) if not bridge else (cycles * 90 + 420)};quit"]  # A clean quit flushes the console log.
    if bridge:
        uz += ["-dfbridgelog", str(folder / "uz.log")]
        command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--uzdoom", str(exe),
                   "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(folder), "--log", str(folder / "launcher.log")]
        for mod in mods:
            command += ["--mod", mod]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in ["-dfbridgelog", str(folder / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]:
            command += ["--dfu-arg", arg]
    else:
        command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--cwd", str(folder), "--", str(exe), "-iwad", str(GAME / "wads" / "DOOM2.WAD"), "-file"] + mods + uz

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stopped, end = "timeout", time.time() + TIMEOUT + 3
    while time.time() < end:
        if proc.poll() is not None:
            stopped = "exited"
            break
        time.sleep(0.25)
        log = console.read_text(errors="replace") if console.exists() else ""
        if any(k in log for k in FATAL):
            stopped = "fatal"
            break
        if "DRDONE" in log:
            stopped = "finished"
            time.sleep(1.5 if bridge else 0.3)
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()

    log = console.read_text(errors="replace") if console.exists() else ""
    if "DRDONE" in log and stopped == "exited":
        stopped = "finished"
    enter, leave = ("enter-dungeon", "exit-dungeon") if kind == "dungeon" else ("enter-building", "exit-building")
    drawn, inside, wrong, visits, loaded_this_visit, unrendered = None, False, [], 0, False, 0
    for line in log.splitlines():
        found = re.match(r"DFMesh: loaded (\d+) triangles", line)
        if found:
            drawn = int(found.group(1))
            loaded_this_visit = True
        elif f"DDTRANSITION {enter}" in line:
            inside, loaded_this_visit = True, False
        elif f"DDTRANSITION {leave}" in line and inside:
            inside = False
            visits += 1
            if visits == 1 and not loaded_this_visit:
                unrendered += 1
            if drawn != expected:
                wrong.append((visits, drawn))
    returns = len(re.findall(r"^DRRETURN", log, re.M))
    failures = re.findall(r"^DRFAIL.*", log, re.M)
    fatal = [l[:140] for l in log.splitlines() if any(k in l for k in FATAL)]
    shots = re.findall(r"^DRFIRE cycle=\d+ projectiles=(\d+)", log, re.M)
    ok = stopped == "finished" and visits == cycles and returns == cycles and not wrong and not failures and not fatal and not unrendered
    if fireball:
        ok = ok and len(shots) == cycles and all(int(s) > 0 for s in shots)
    print(f"{'PASS' if ok else 'FAIL'} {name}: stopped={stopped} exit={proc.returncode} visits={visits}/{cycles} returns={returns} expected_tris={expected} wrong_mesh_visits={wrong[:4]}"
          f"{' first visit never drew' if unrendered else ''} failures={failures[:2]} fatal={fatal[:1]}" + (f" projectiles_seen={shots}" if fireball else ""), flush=True)
    return ok


ap = argparse.ArgumentParser()
ap.add_argument("--exe", required=True, type=Path)
ap.add_argument("--only")
ap.add_argument("--cycles", type=int, default=6)
args = ap.parse_args()
prepare()
scenarios = [("dungeon-solo", "dungeon", False, False), ("dungeon-solo-fire", "dungeon", True, False), ("building-solo", "building", False, False),
             ("dungeon-bridge", "dungeon", False, True), ("dungeon-bridge-fire", "dungeon", True, True), ("building-bridge", "building", False, True)]
before = registry_hash()
results = [run(args.exe.resolve(), n, k, f, b, args.cycles) for n, k, f, b in scenarios if not args.only or args.only in n]
same = before == registry_hash()
print("owner registry key unchanged:", same)
sys.exit(0 if results and all(results) and same else 1)
