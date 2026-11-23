"""Regression checks for the door work: stock E1M1, E1M1 with the DRLA set, and a standalone converted dungeon.

Usage: door_regress.py BUILD_DIR EXE. Generated files stay in BUILD_DIR.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
build, exe = sys.argv[1], sys.argv[2]
work = os.path.join(build, "tests", "regress")
os.makedirs(work, exist_ok=True)
COMMON = ["-config", os.path.join(work, "regress.ini"), "-savedir", work, "-nosound", "-noautoload", "-noactivate", "-width", "1280", "-height", "720", "+vid_fullscreen", "0",
          "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]


def run(name, args, seconds=25):
    log = os.path.join(work, f"log-{name}.txt")
    if os.path.exists(log):
        os.remove(log)
    proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(seconds), "--", exe] + COMMON + ["+logfile", name] + args, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end, text = time.time() + seconds, ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        if "FATAL" in text or "Execution could not continue" in text:
            break
    alive = proc.poll() is None
    if alive:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    bad = "FATAL" in text or "Execution could not continue" in text
    print(f"{name}: ran to limit={alive} exit={proc.returncode if not alive else '-'} entered={'E1M1' in text or 'MAP01' in text} fatal={bad} script messages={text.count('Script error')} door code={'DDDOORS' in text or 'DDTRANSITION' in text} treadmill={'DDTM' in text}")


doom = ["-iwad", os.path.join(WADS, "DOOM.WAD"), "-skill", "3"]
drla = doom + ["-file", os.path.join(MODS, "DoomRL_Arsenal_1.1.5.pk3"), os.path.join(MODS, "DoomRL_Monsters_Beta_7.3.pk3"), os.path.join(MODS, "drlax_1.2b.pk3"), "+map", "E1M1"]
if len(sys.argv) > 3:  # A DRLA-only run, for comparing another engine build.
    run("drla-" + sys.argv[3], drla, 30)
    sys.exit(0)
run("norun", doom + ["-norun"], 20)
run("e1m1", doom + ["+map", "E1M1"], 12)
run("drla", drla, 30)
stock = os.path.join(build, "dungeon-standalone")
converter = os.path.join(build, "converter", "DungeonConverter.exe")
for extra in ([], ["--export-mesh"]):
    subprocess.run([sys.executable, QUIET, "--timeout", "100", "--", converter, "Privateer's Hold", "--out", stock, "--world-scale", "0.75", *extra], stdout=subprocess.DEVNULL, check=True)
run("standalone", ["-iwad", os.path.join(WADS, "DOOM2.WAD"), "-file", *[os.path.join(stock, "privateershold" + s) for s in (".wad", "_mesh.pk3", "_doors.pk3")], "-skill", "3", "+map", "MAP01"], 12)
