"""Converts a sample of dungeons chosen from the trapdoor census and checks their hinged tiles in the running game.

Usage: python tools/dungeon_converter/trapdoor_regress.py --converter <DungeonConverter.exe> --overworld <overworld.pk3> --out <dir outside the repo> [--only <map id> ...]
The sample is one example dungeon per hinged kind in --list-trapdoors, plus the known hard cases.
A tile must hold the player closed, then fire through its real trigger and finish its move. A tile nothing can trigger must stay closed.
Whether the body can walk out is reported for the original 7 tiles, not required.
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
# Tiles that already worked, which must keep the stricter walk-on result.
ORIGINAL = {"630439035": 5, "207828842": 2}
# Known hard cases: Mantellan Crux, Orsinium, and Direnni Tower.
KNOWN = {"1001", "19021260", "43196334"}
BAD = ("Script error", "VM execution aborted", "FatalError")
LIMIT = 30
SLICE = 6

parser = argparse.ArgumentParser()
parser.add_argument("--converter", required=True)
parser.add_argument("--overworld", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--only", nargs="*", default=None)
args = parser.parse_args()
failures = 0


def census():
    text = subprocess.run([args.converter, "--list-trapdoors"], capture_output=True, text=True, errors="replace", check=True).stdout
    kinds = []
    for line in text.splitlines():
        m = re.match(r"KIND placed=(\d+) dungeons=\d+ (.*flag=(\d+) .*) eg (\d+) (.*) record=(\d+)$", line)
        if m and m.group(3) in ("8", "18", "20"):
            kinds.append((m.group(2), m.group(4), int(m.group(6)), int(m.group(1))))
    return kinds


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


def field(row, name):
    m = re.search(r"\b" + name + r"=(-?\d+)", row)
    return int(m.group(1)) if m else None


def tile_problem(row, strict):
    if field(row, "held") != 1:
        return "not held"
    if field(row, "inert") == 1:
        return "inert tile moved" if field(row, "fired") != 0 else None
    if field(row, "fired") != 1 or field(row, "end") != 1 or field(row, "stalled") != 0:
        return "did not finish"
    # Walking on is judged only for walk-on tiles. Others are reached by walking but fire from their chain.
    if field(row, "trig") == 1 and (field(row, "walkOn") == 0 or (strict and field(row, "walkOn") != 1)):
        return "walk-on failed"
    return None


def run_dungeon(map_id):
    """Every tile in the dungeon, a slice per launch. Returns the rows, or None if a launch failed."""
    rows, first = [], 0
    flood = ["+set", "td_flood", "1"] if map_id in ORIGINAL else []
    while True:
        tag = f"trapdoor_{first}"
        text = launch(map_id, tag, "trapdoor_check", "TDDONE", ["+set", "td_first", str(first), "+set", "td_count", str(SLICE), *flood, "+map", "MAP01"])
        got = [l for l in text.splitlines() if l.startswith("TD ") and " record=" in l]
        errors = [l for l in text.splitlines() if any(b in l for b in BAD)]
        start = re.search(r"TDSTART tiles=(\d+)", text)
        if "TDDONE" not in text or errors or not start:
            print(f"  LAUNCH FAILED at tile {first}: {(errors or ['no TDDONE'])[0][:200]}")
            return rows, False
        rows += got
        first += SLICE
        if first >= int(start.group(1)):
            return rows, len(rows) == int(start.group(1))


kinds = census()
sample = sorted({k[1] for k in kinds} | KNOWN | set(ORIGINAL))
if args.only:
    sample = [s for s in sample if s in args.only]
print(f"Census: {len(kinds)} hinged kinds, {sum(k[3] for k in kinds)} placed. Sample: {len(sample)} dungeons")
seen = {}
for map_id in sample:
    convert(map_id)
    rows, complete = run_dungeon(map_id)
    strict = map_id in ORIGINAL
    bad = [(r, tile_problem(r, strict)) for r in rows if tile_problem(r, strict)]
    ok = complete and rows and not bad and (not strict or len(rows) == ORIGINAL[map_id])
    failures += 0 if ok else 1
    seen[map_id] = {field(r, "record") for r in rows}
    noside = sum(field(r, "walkOn") == -1 for r in rows)
    inert = sum(field(r, "inert") == 1 for r in rows)
    nodrop = sum(field(r, "inert") != 1 and float(re.search(r"drop=(-?[\d.]+)", r).group(1)) < 8 for r in rows)
    bumps = sum("bump=none" not in r for r in rows)
    print(f"{map_id}: {'PASS' if ok else 'FAIL'} {len(rows)} tiles, {len(bad)} bad, {noside} with no level side, {inert} inert, {nodrop} did not drop the body, {bumps} with a bump on the way on")
    with open(os.path.join(args.out, map_id, "rows.txt"), "w") as f:
        f.write("\n".join(rows))
    for r, why in bad[:6]:
        print(f"  {why}: {r}")

if not args.only:
    for desc, map_id, record, placed in kinds:
        if record not in seen.get(map_id, ()):
            failures += 1
            print(f"KIND NOT TESTED ({placed} placed): {desc} in {map_id} record {record}")

# Save and load with an action 18 and an action 8 tile open. Only Wayrest has both.
map_id = "630439035"
if map_id in sample:
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
print(f"RESULT {'PASS' if not failures else 'FAIL'} failures={failures}")
sys.exit(1 if failures else 0)
