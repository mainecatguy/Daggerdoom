"""Pickup mix survey (the dungeons-only mix with a fixed lean per dungeon, PickupExport.cs).

usage: mix_survey.py lean | convert [COUNT | #MAPID...] | markers
lean: every dungeon's fixed lean and expected mix from the converter's --pickup-lean-survey, with the average.
convert: converts COUNT dungeons (default 40, a fixed spread through the map table) and tallies the pickups really
         placed: the overall mix, each dungeon's mix, and a second conversion of a few to prove the result is fixed.
markers: DOOM.WAD E1M1, stock and with DRLA, spawns every pickup marker and logs the item each becomes (needs the
         review folder from tools/housepickups/housepickups.py assemble).
Output goes to D:\\dev\\DoomDaggerfall-build\\pickupmix (outside the repo: converted maps are game data).
Building interiors: tools/housepickups/housepickups.py survey (every building of a town must report no pickups).
"""
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = Path(r"D:\dev\DoomDaggerfall-build\pickupmix")
CONVERTER = OUT / "converter" / "DungeonConverter.exe"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
NAMES = {31640: "health", 31641: "clips", 31642: "shells", 31643: "rockets", 31644: "cells", 31645: "berserk",
         31646: "invisibility", 31647: "visor", 31648: "soulsphere", 31649: "megasphere", 31650: "invulnerability"}
POWERUPS = {"berserk", "invisibility", "visor", "soulsphere", "megasphere", "invulnerability"}
BASE = {"clips": 30, "shells": 25, "health": 30, "rockets": 10, "cells": 3, "powerups": 2}


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["dotnet", "build", str(REPO / "tools" / "dungeon_converter" / "DungeonConverter.csproj"), "-c", "Release", "-v", "q",
                           "-o", str(CONVERTER.parent), f"-p:BaseIntermediateOutputPath={OUT / 'obj'}\\"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


def run(args):
    return subprocess.run([str(CONVERTER), *args, "--arena2", ARENA2], stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace")


def things(folder):
    """Pickup things in the first WAD under folder, as (x, y, type) tuples."""
    import struct
    wad = next(folder.glob("*.wad"), None)
    if not wad:
        return None
    data = wad.read_bytes()
    count, offset = struct.unpack_from("<ii", data, 4)
    for n in range(count):
        at, size = struct.unpack_from("<ii", data, offset + 16 * n)
        if data[offset + 16 * n + 8:offset + 16 * n + 16].rstrip(b"\0") == b"TEXTMAP":
            text = data[at:at + size].decode(errors="replace")
            return sorted((float(m[1]), float(m[2]), int(m[3])) for m in re.finditer(r"x = ([-\d.]+); y = ([-\d.]+);[^}]*?type = (316[45]\d);", text))
    return None


def mix_line(counter, total):
    keys = ["clips", "shells", "health", "rockets", "cells"]
    parts = [f"{k}={100 * counter[k] / total:.1f}%" for k in keys]
    parts.append(f"powerups={100 * sum(counter[k] for k in POWERUPS) / total:.1f}%")
    return " ".join(parts)


def lean():
    out = run(["--pickup-lean-survey"])
    (OUT / "lean.txt").write_text(out.stdout)
    print("\n".join(out.stdout.splitlines()[-3:]))
    print("full list:", OUT / "lean.txt")


def dungeon_ids():
    out = run(["--list-main", "--list-all"])
    ids = [int(m[1]) for m in re.finditer(r"MAIN (\d+) .*hasDungeon=True", out.stdout)]
    return ids


def convert(count, picked=None):
    if not picked:
        ids = dungeon_ids()
        step = max(1, len(ids) // count)
        picked = ids[::step][:count]
    total = Counter()
    rows = []
    lumps = {}
    for mid in picked:
        folder = OUT / "maps" / str(mid)
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        res = run([f"#{mid}", "--out", str(folder)])
        line = next((l for l in res.stdout.splitlines() if l.startswith("pickups:")), None)
        got = things(folder)
        if line is None or got is None:
            print(f"#{mid}: no map (exit {res.returncode}) {res.stderr[-200:]}")
            continue
        lumps[mid] = got
        c = Counter(NAMES[t] for _, _, t in got)
        total.update(c)
        lean_m = re.search(r"lean (\w+) ([\d.]+)", line)
        rows.append((mid, len(got), c, lean_m.group(0) if lean_m else "?"))
        print(f"#{mid}: {len(got)} pickups, {lean_m.group(0) if lean_m else ''}, {mix_line(c, max(1, len(got)))}")
    n = sum(total.values())
    print(f"\n{len(rows)} dungeons, {n} pickups")
    print("overall  " + mix_line(total, n))
    print("base     " + " ".join(f"{k}={v}%" for k, v in BASE.items()))
    print("powerups " + " ".join(f"{k}={total[k]}" for k in ["berserk", "invisibility", "visor", "soulsphere", "megasphere", "invulnerability"]))
    # Fixed seeds: convert the first three again and compare every thing.
    same = 0
    for mid in list(lumps)[:3]:
        folder = OUT / "maps" / f"{mid}-again"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        run([f"#{mid}", "--out", str(folder)])
        same += things(folder) == lumps[mid]
    print(f"second conversion identical: {same}/{min(3, len(lumps))}")


def markers():
    """Each marker class on DOOM.WAD E1M1 (no bridge), stock and with the DRLA set: which item it becomes."""
    import time
    import zipfile
    review = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeonpickups")  # Made by tools/housepickups/housepickups.py assemble.
    game = Path(r"D:\dev\DoomDaggerfall\GameResources")
    mods = game.parent / "GameMods"
    runs = review / "run"
    runs.mkdir(parents=True, exist_ok=True)
    harness = runs / "markers_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "markers.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PMHarness" }\n')
    drla = [mods / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    for label, files in (("stock", [review / "doomerfall.pk3"]), ("drla", drla + [review / "doomerfall.pk3", review / "doomerfall-drla.pk3"])):
        log, ini = runs / f"log-markers-{label}.txt", runs / f"markers-{label}.ini"
        log.unlink(missing_ok=True)
        ini.unlink(missing_ok=True)
        command = [sys.executable, r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py", "--timeout", "30", "--cwd", str(runs), "--",
                   str(review / "uzdoom" / "uzdoom.exe"), "-iwad", str(game / "wads" / "DOOM.WAD"), "-config", str(ini), "-noautoload", "-skill", "3",
                   "-file", *map(str, files), str(harness), "+logfile", f"markers-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                   "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1"]
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.time() + 33
        while time.time() < end and proc.poll() is None and "PMDONE" not in (log.read_text(errors="replace") if log.exists() else ""):
            time.sleep(0.25)
        time.sleep(0.5)
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
        body = log.read_text(errors="replace") if log.exists() else ""
        print(f"[{label}]")
        for line in body.splitlines():
            if line.startswith("PM") or "Script error" in line or "FATAL" in line or "aborted" in line:
                print("  " + line[:200])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lean"
    if cmd in ("lean", "convert"):
        build()
    if cmd == "lean":
        lean()
    elif cmd == "convert":
        ids = [int(a[1:]) for a in sys.argv[2:] if a.startswith("#")]  # convert #ID ... converts those map ids
        convert(int(sys.argv[2]) if len(sys.argv) > 2 and not ids else 40, ids)
    elif cmd == "markers":
        markers()
    else:
        print(__doc__)
