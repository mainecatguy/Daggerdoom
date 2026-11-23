"""Converts the two dungeons with secret door panels (non-door models on door actions) and checks all 3 in the running game.

Usage: python tools/dungeon_converter/special_door_regress.py --converter <DungeonConverter.exe> --overworld <overworld.pk3> --out <dir outside the repo>
Panels must block closed and pass open, and must not carry or trap a body. The 4 trapdoor tiles stay static, so they are not tested here.
"""
import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DUNGEONS = {"Orsinium": 2, "Lysandus' Tomb": 1}
BAD = ("Script error", "VM execution aborted", "FatalError")

parser = argparse.ArgumentParser()
parser.add_argument("--converter", required=True)
parser.add_argument("--overworld", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
census = subprocess.run([args.converter, "--list-door-actions"], capture_output=True, text=True, errors="replace").stdout
ids = {name: re.search(rf"DUNGEON (\d+) \S*/?{re.escape(name)} main=True", census.replace(" Area/", "/")) for name in DUNGEONS}
failures = 0


def run(name, map_id):
    folder = os.path.join(args.out, map_id)
    os.makedirs(folder, exist_ok=True)
    for extra in ([], ["--export-mesh"]):
        subprocess.run([args.converter, "#" + map_id, "--out", folder, *extra], capture_output=True, check=True)
    out, ini = os.path.join(folder, "check.out"), os.path.join(folder, "check.ini")
    with open(ini, "w") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    files = [os.path.join(folder, map_id + s) for s in (".wad", "_mesh.pk3", "_doors.pk3")] + [args.overworld, os.path.join(HERE, "special_door_check")]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7
    with open(out, "w") as sink:
        process = subprocess.Popen([EXE, "-iwad", IWAD, "-file", *files, "-config", ini, "-savedir", folder, "-noactivate", "-nosound", "-stdout", "-skill", "3", "-nomonsters",
                                    "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                    "+map", "MAP01"], cwd=folder, startupinfo=startup, stdout=sink, stderr=subprocess.STDOUT)
        began = time.time()
        while time.time() - began < 45 and process.poll() is None:
            time.sleep(0.5)
            text = open(out, errors="replace").read()
            if "SDDONE" in text or any(b in text for b in BAD):
                time.sleep(0.3)
                break
        if process.poll() is None:
            process.kill()
        process.wait()
    return open(out, errors="replace").read()


def row_ok(row):
    needed = ("closedSolid=1", "crossClosed=00", "started=1", "opened=1", "carried=0.0", "openSolid=1", "crossOpen=11", "closing=1", "closed=1", "endSolid=1")
    return all(k in row for k in needed)


for name, expected in DUNGEONS.items():
    if not ids[name]:
        print(f"{name}: FAIL not in the census")
        failures += 1
        continue
    text = run(name, ids[name].group(1))
    rows = [l for l in text.splitlines() if l.startswith("SD record=")]
    bad = [r for r in rows if not row_ok(r)]
    chains = [l for l in text.splitlines() if l.startswith("SDCHAIN")]
    bad += [c for c in chains if "fired=1" not in c]
    ok = "SDDONE" in text and len(rows) == expected and len(chains) == expected and not bad and not any(b in text for b in BAD)
    failures += 0 if ok else 1
    print(f"{name}: {'PASS' if ok else 'FAIL'} {len(rows)}/{expected} objects")
    for r in bad:
        print("  " + r)
sys.exit(1 if failures else 0)
