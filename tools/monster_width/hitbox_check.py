"""Hitbox verification on a converted dungeon: narrowed monsters (Zombieman, Imp, Demon) take bullets, melee and
projectiles at their full stock radius, in open space and while squeezed in a doorway (hitbox/zscript.zs), and the
doorway check (tools/dungeon_converter/door_check) walks each of the three through the open doorways.

Every launch is private, minimized and time limited; wrap the whole script in quiet_run.py.
Usage: python tools/monster_width/hitbox_check.py --exe <uzdoom.exe> --ph <dir with privateershold.wad, _mesh.pk3, _doors.pk3> --out <dir>
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = [os.path.join(MODS, n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
MOD = os.path.join(REPO, "mods", "doomerfall", "src")
FATAL = ("VM execution aborted", "FatalError", "Execution could not continue")

ap = argparse.ArgumentParser()
ap.add_argument("--exe", required=True)
ap.add_argument("--ph", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--only", help="run one case")
args = ap.parse_args()
args.out = os.path.abspath(args.out)
os.makedirs(args.out, exist_ok=True)
ph = [os.path.abspath(os.path.join(args.ph, "privateershold" + s)) for s in (".wad", "_mesh.pk3", "_doors.pk3")]
runtime = os.path.abspath(os.path.join(args.ph, "ddruntime.pk3"))  # newer conversions share the door runtime
if os.path.exists(runtime):
    ph.insert(0, runtime)


def launch(name, files, extra, marker, limit):
    out = os.path.join(args.out, name + ".log")
    config = os.path.join(args.out, name + ".ini")
    with open(config, "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    with open(out, "w") as sink:
        p = subprocess.Popen([args.exe, "-iwad", os.path.join(WADS, "DOOM2.WAD"), "-file", *files, "-config", config, "-noactivate",
                              "-nosound", "-stdout", "-skill", "3", "+vid_fullscreen", "0", "+wipetype", "0",
                              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                              *extra, "+map", "MAP01"], cwd=args.out, stdout=sink, stderr=subprocess.STDOUT)
        started = time.time()
        while time.time() - started < limit and p.poll() is None:
            time.sleep(0.5)
            text = open(out, errors="replace").read()
            if marker in text or any(b in text for b in FATAL):
                time.sleep(0.5)
                break
        if p.poll() is None:
            p.kill()
        p.wait()
    return open(out, errors="replace").read()


def fields(line):
    return dict(kv.split("=", 1) for kv in line.split() if "=" in kv)


failures = 0


def report(name, ok, detail):
    global failures
    failures += 0 if ok else 1
    print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}", flush=True)


for name, mods in (("hit_stock", []), ("hit_drla", DRLA)):
    if args.only and args.only != name:
        continue
    text = launch(name, [*mods, *ph, MOD, os.path.join(HERE, "hitbox")], [], "HBDONE", 75)
    done = "HBDONE" in text and not any(b in text for b in FATAL)
    opens = [l for l in text.splitlines() if l.startswith("HBOPEN ")]
    squeezes = [l for l in text.splitlines() if l.startswith("HBSQUEEZE ")]
    report(name, done and len(opens) >= 3, f"finished={done} monsters={len(opens)}")
    for line in opens:
        f = fields(line)
        counts = {k: [int(v) for v in f[k].split("/")] for k in ("bullet", "melee", "projectile")}  # ok/wrong/hits/misses
        ok = float(f["squeeze"]) < float(f["radius"]) and all(c[1] == 0 and c[2] > 0 and c[3] > 0 for c in counts.values())
        report(f"  {name} open {line.split()[1]}", ok, line.split(" ", 2)[2] + "  (ok/wrong/hits/misses)")
    for line in squeezes:
        f = fields(line)
        counts = {k: [int(v) for v in f[k].split("/")] for k in ("bullet", "melee", "projectile")}  # hit/wrong/blocked
        wrong = int(f["radiusChanged"]) + sum(c[1] for c in counts.values())
        # A monster that fits no doorway never squeezes, so it has nothing to hit there; that is reported, not failed.
        ok = wrong == 0 and (int(f["squeezedDoors"]) == 0 or all(c[0] > 0 for c in counts.values()))
        report(f"  {name} squeeze {line.split()[1]}", ok, line.split(" ", 2)[2] + "  (hit/wrong/blocked)")

dead_ends = {21, 23, 24, 25, 27, 28, 31, 34, 37, 41, 49, 53}  # as action_regress.py: no dungeon on their far side
for kind in ("ZombieMan", "DoomImp", "Demon"):
    name = "doors_" + kind
    if args.only and args.only != name:
        continue
    text = launch(name, [*ph, MOD, os.path.join(REPO, "tools", "dungeon_converter", "door_check")],
                  ["-nomonsters", "+set", "dt_monster", kind], "DTDONE", 90)
    marks = {}
    for line in text.splitlines():
        if line.startswith("DT door="):
            f = fields(line[3:])
            if int(f["door"]) not in dead_ends:
                marks[int(f["door"])] = f.get("monster", "?")
    size = next((l for l in text.splitlines() if l.startswith("DTMONSTER")), "DTMONSTER none")
    by = {m: sorted(d for d, v in marks.items() if v == m) for m in ("1", "0", "n")}
    report(name, "DTDONE" in text and len(marks) == 46 and not by["0"],
           f"{size}: {len(by['1'])} of {len(marks)} doorways pass, shut only by the open leaf {by['0']}, "
           f"too narrow even without the leaf {len(by['n'])}")
sys.exit(1 if failures else 0)
