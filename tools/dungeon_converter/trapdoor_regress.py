"""Converts the dungeons with trapdoor tiles and checks each tile in the running game.

Usage: python tools/dungeon_converter/trapdoor_regress.py --converter <DungeonConverter.exe> --overworld <overworld.pk3> --out <dir outside the repo>
A tile must hold the player closed, fire through its real trigger, finish its move, and drop the body. Whether the body can walk out is reported, not required.
"""
import argparse
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
# The dungeons whose trapdoors are enabled (TrapdoorDungeons in ActionExport.cs).
DUNGEONS = {"Wayrest": ("630439035", 5), "Lysandus' Tomb": ("207828842", 2)}
BAD = ("Script error", "VM execution aborted", "FatalError")
LIMIT = 30

parser = argparse.ArgumentParser()
parser.add_argument("--converter", required=True)
parser.add_argument("--overworld", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
failures = 0


def convert(map_id):
    folder = os.path.join(args.out, map_id)
    os.makedirs(folder, exist_ok=True)
    for extra in ([], ["--export-mesh"]):
        subprocess.run([args.converter, "#" + map_id, "--out", folder, *extra], capture_output=True, check=True)
    return folder


def launch(map_id, tag, package, marker, start):
    folder = os.path.join(args.out, map_id)
    out, ini = os.path.join(folder, tag + ".out"), os.path.join(folder, tag + ".ini")
    with open(ini, "w") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    files = [os.path.join(folder, map_id + s) for s in (".wad", "_mesh.pk3", "_doors.pk3")] + [args.overworld, os.path.join(HERE, package)]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7
    with open(out, "w") as sink:
        process = subprocess.Popen([EXE, "-iwad", IWAD, "-file", *files, "-config", ini, "-savedir", folder, "-noactivate", "-nosound", "-stdout", "-skill", "3", "-nomonsters",
                                    "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                    *start], cwd=folder, startupinfo=startup, stdout=sink, stderr=subprocess.STDOUT)
        began = time.time()
        while time.time() - began < LIMIT and process.poll() is None:
            time.sleep(0.25)
            text = open(out, errors="replace").read()
            if marker in text or "TSFAILED" in text or any(b in text for b in BAD):
                time.sleep(0.2)
                break
        if process.poll() is None:
            process.kill()
        process.wait()
    return open(out, errors="replace").read()


for name, (map_id, expected) in DUNGEONS.items():
    convert(map_id)
    text = launch(map_id, "trapdoor", "trapdoor_check", "TDDONE", ["+map", "MAP01"])
    rows = [l for l in text.splitlines() if l.startswith("TD record=")]
    needed = ("held=1", "walkOn=1", "fired=1", "end=1", "stalled=0")
    bad = [r for r in rows if not all(k in r for k in needed)]
    errors = [l for l in text.splitlines() if any(b in l for b in BAD)]
    ok = "TDDONE" in text and len(rows) == expected and not bad and not errors
    failures += 0 if ok else 1
    print(f"{name}: {'PASS' if ok else 'FAIL'} {len(rows)}/{expected} tiles")
    for r in rows:
        print("  " + r)
    for e in errors[:5]:
        print("  ERROR " + e[:200])

# Save and load with an action 18 and an action 8 tile open. Only Wayrest has both.
map_id = DUNGEONS["Wayrest"][0]
folder = os.path.join(args.out, map_id)
for old in glob.glob(os.path.join(folder, "*.zds")):
    os.remove(old)
first = launch(map_id, "save_a", "trapdoor_save_check", "Game saved", ["+map", "MAP01"])
saves = glob.glob(os.path.join(folder, "*.zds"))
before = [l for l in first.splitlines() if l.startswith("TSBEFORE")]
second = launch(map_id, "save_b", "trapdoor_save_check", "TSDONE", ["-loadgame", os.path.basename(saves[0])]) if saves else ""
rows = [l for l in second.splitlines() if l.startswith(("TSLOADED", "TSDROP", "TSFAILED"))]
ok = bool(before) and "TSDONE" in second and "TSFAILED" not in second and not any(b in first + second for b in BAD)
failures += 0 if ok else 1
print(f"Save and load: {'PASS' if ok else 'FAIL'}")
for r in before + rows:
    print("  " + r)
sys.exit(1 if failures else 0)
