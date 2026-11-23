"""Regression launches for the action system: stock E1M1, E1M1 with DRLA, E1M1 beside the action package,
the Privateer's Hold door check, and Scourg Barrow save and load. Each launch is minimized, private, and time limited.

Usage: python tools/dungeon_converter/action_regress.py <scourg dir> <privateer's hold dir>
"""
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
if "--exe" in sys.argv:  # test a private build
    at = sys.argv.index("--exe")
    EXE = sys.argv[at + 1]
    del sys.argv[at:at + 2]
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = [os.path.join(MODS, n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
BAD = ("Script error", "VM execution aborted", "FatalError", "Unknown class", "Execution could not continue")
scourg, holds = (os.path.abspath(a) for a in sys.argv[1:3])
run_dir = os.path.join(scourg, "regress")
os.makedirs(run_dir, exist_ok=True)
failures = 0


def launch(name, iwad, files, extra, marker, limit=30, tolerate_mod_errors=False):
    log = os.path.join(run_dir, name + ".log")
    out = os.path.join(run_dir, name + ".stdout")
    for path in (log, out):
        if os.path.exists(path):
            os.remove(path)
    config = os.path.join(run_dir, name + ".ini")
    with open(config, "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7
    with open(out, "w") as sink:
        process = subprocess.Popen([EXE, "-iwad", os.path.join(WADS, iwad), *(["-file", *files] if files else []), "-config", config,
                                    "-savedir", run_dir, "-noactivate", "-nosound", "-stdout", "-skill", "3",
                                    "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                    "+logfile", name + ".log", *extra], cwd=run_dir, startupinfo=startup, stdout=sink, stderr=subprocess.STDOUT)
        started = time.time()
        text = ""
        while time.time() - started < limit and process.poll() is None:
            time.sleep(0.5)
            text = open(out, errors="replace").read()
            if marker in text or (not tolerate_mod_errors and any(b in text for b in BAD)):
                time.sleep(0.5)
                break
        if process.poll() is None:
            process.kill()
        process.wait()
    text = open(out, errors="replace").read()
    if os.path.exists(log):
        text += open(log, errors="replace").read()
    return text


def report(name, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")


def clean(text):
    return not any(b in text for b in BAD)


only_load = len(sys.argv) > 3 and sys.argv[3] == "load"  # reuses the existing save
package = os.path.join(scourg, "scourgbarrow_doors.pk3")
for name, files in () if only_load else (("e1m1_stock", []), ("e1m1_drla", DRLA), ("e1m1_package", [package])):
    # The DRLA set prints a translation error and optional DoomRPG class warnings by itself, with none of our files loaded.
    drla = files is DRLA
    text = launch(name, "DOOM.WAD", files, ["+map", "E1M1"], "E1M1 - ", 30 if files else 12, tolerate_mod_errors=drla)
    entered = "E1M1" in text
    inactive = "DFACTIONS loaded" not in text and "DFDOORS spawned" not in text
    fatal = any(b in text for b in BAD if b not in ("Script error", "Unknown class")) if drla else not clean(text)
    report(name, not fatal and entered and inactive, f"entered={entered} actions inactive={inactive}")

ph = [os.path.join(holds, "privateershold" + s) for s in (".wad", "_mesh.pk3", "_doors.pk3", "_player.pk3")]
if not only_load:
    text = launch("ph_doors", "DOOM2.WAD", [*ph, os.path.join(HERE, "door_check")], ["-nomonsters", "+map", "MAP01"], "DTDONE", 60)
    rows = [l for l in text.splitlines() if l.startswith("DT door=")]
    rows = rows[:len(rows) // 2] if len(rows) >= 116 and rows[:58] == rows[58:116] else rows
    checked = ("use", "closed", "walk", "trace", "ball", "swing", "openpass", "traceopen", "ballopen", "solid", "through", "hold")
    dead_ends = {21, 23, 24, 25, 27, 28, 31, 34, 37, 41, 49, 53}  # no dungeon on their far side; see work/notes/door-objects.md
    bad = [l for l in rows if int(l.split()[1][5:]) not in dead_ends
           and any(f.split("=")[0] in checked and "0" in f.split("=")[1] for f in l.split()[2:])]
    report("privateers_doors", "DTDONE" in text and clean(text) and len(rows) == 58 and not bad, f"{len(rows)} doors, {len(bad)} rows with a failed test")
    for l in bad[:4]:
        print("  " + l[:170])
    bodies = next((l for l in text.splitlines() if l.startswith("DTPLAYERSTALL")), "")
    report("door_bodies", "through+passable+solid" in bodies and not any(w in bodies for w in ("FAILED", "NOTPASSABLE", "NOTSOLID")), bodies)
    for old in glob.glob(os.path.join(run_dir, "*.zds")):
        os.remove(old)
files = [*(os.path.join(scourg, "scourgbarrow" + s) for s in (".wad", "_mesh.pk3", "_doors.pk3")), os.path.join(HERE, "action_save_check")]
if not only_load:
    first = launch("save_a", "DOOM2.WAD", files, ["-nomonsters", "+map", "MAP01"], "Game saved", 20)
    before = [l for l in first.splitlines() if l.startswith("ASBEFORE")]
    report("save", clean(first) and bool(glob.glob(os.path.join(run_dir, "*.zds"))) and bool(before), before[0] if before else "no state line")
saves = glob.glob(os.path.join(run_dir, "*.zds"))
saved = bool(saves)
if saved:
    second = launch("save_b", "DOOM2.WAD", files, ["-nomonsters", "-loadgame", os.path.basename(saves[0])], "ASDONE", 25)
    loaded = [l for l in second.splitlines() if l.startswith("ASLOADED")]
    report("load", clean(second) and "ASDONE" in second and bool(loaded), loaded[0] if loaded else "no state line")
sys.exit(1 if failures else 0)
