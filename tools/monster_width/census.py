"""Census: which encounter-pool monsters still fit no open doorway of a converted dungeon at the Daggerfall-map width.

Dumps the encounter pool (Doomerfall mod, +set dd_encounter_pooldump 1) with the stock monsters and with the DRLA set,
reads the door check's doorway measurements (DT rows: wide=a/b/c, c = widest monster radius past the solid open leaf)
and the door heights (DFDOORS in <slug>_doors.pk3), and sorts every monster by how many open doorways it fits through.

Usage: python tools/monster_width/census.py --exe <uzdoom.exe> --doors-log <door check stdout> --doors-pk3 <slug>_doors.pk3 --out <dir>
Wrap it in quiet_run.py. Writes census.txt in --out.
"""
import argparse
import os
import re
import subprocess
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = [os.path.join(MODS, n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
MOD = os.path.join(REPO, "mods", "doomerfall", "src")
SCALE = 10.5 / 16  # DD_MonsterMoveScale (dd_monsters.cpp): monsters move at the player's 16 -> 10.5

ap = argparse.ArgumentParser()
ap.add_argument("--exe", required=True)
ap.add_argument("--doors-log", required=True)
ap.add_argument("--doors-pk3", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)


def dump(name, files):
    out = os.path.join(args.out, name + ".log")
    config = os.path.join(args.out, name + ".ini")
    with open(config, "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7
    with open(out, "w") as sink:
        p = subprocess.Popen([args.exe, "-iwad", os.path.join(WADS, "DOOM2.WAD"), "-file", *files, MOD, "-config", config, "-noactivate", "-nosound",
                              "-stdout", "-skill", "3", "-nomonsters", "+set", "dd_encounter_pooldump", "1", "+i_pauseinbackground", "0",
                              "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "MAP01"],
                             cwd=args.out, startupinfo=startup, stdout=sink, stderr=subprocess.STDOUT)
        started = time.time()
        while time.time() - started < 40 and p.poll() is None:
            time.sleep(0.5)
            if "ENCPOOL done" in open(out, errors="replace").read():
                break
        if p.poll() is None:
            p.kill()
        p.wait()
    rows = re.findall(r"ENCPOOL monster (\S+) kind=(\S+) tier=(\d+) .*? radius=(\d+) height=(\d+)", open(out, errors="replace").read())
    return [(c, k, int(t), float(r), float(h)) for c, k, t, r, h in rows]


doorways = [int(m.split("/")[2]) for m in re.findall(r"wide=(\d+/\d+/\d+)", open(args.doors_log, errors="replace").read())]
doorways = [w for w in doorways[:58] if w > 0]  # dead ends (no room beyond) report 0
heights = []
with zipfile.ZipFile(args.doors_pk3) as z:
    for line in z.read("DFDOORS").decode().splitlines():
        f = line.split()
        if len(f) >= 11:
            heights.append(float(f[10]) - float(f[9]))
door_height = min(heights)
lines = [f"Doorways with a room on both sides: {len(doorways)}; widest monster radius past the solid open leaf per doorway: "
         + ", ".join(f"{w}: {doorways.count(w)}" for w in sorted(set(doorways), reverse=True)) + f". Lowest door opening {door_height:.1f}.",
         f"Daggerfall-map monster radius = class radius x {SCALE:.5f}. Heights are stock.", ""]
for name, files in (("stock", []), ("drla", DRLA)):
    pool = dump("pool_" + name, files)
    lines.append(f"== {name}: {len(pool)} pool monsters")
    nowhere, some, most = [], [], 0
    for cls, kind, tier, r, h in sorted(pool, key=lambda m: (-m[3], m[0])):
        narrow = r * SCALE
        fits = sum(narrow <= w for w in doorways) if h <= door_height else 0
        why = "too tall" if h > door_height else "too wide" if fits == 0 else ""
        if fits == 0:
            nowhere.append(f"  {cls} ({kind}, tier {tier}) radius {r:.0f} -> {narrow:.2f}, height {h:.0f}: {why}")
        elif fits < len(doorways):
            some.append(f"  {cls} ({kind}, tier {tier}) radius {r:.0f} -> {narrow:.2f}, height {h:.0f}: {fits} of {len(doorways)}")
        else:
            most += 1
    lines.append(f"fits every measured doorway: {most}")
    lines.append(f"fits some doorways: {len(some)}")
    lines += some
    lines.append(f"fits no open doorway: {len(nowhere)}")
    lines += nowhere
    lines.append("")
open(os.path.join(args.out, "census.txt"), "w").write("\n".join(lines))
print("\n".join(lines))
