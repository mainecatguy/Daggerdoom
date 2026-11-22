"""Checks that the treadmill stays inactive on stock and converted maps.

Runs DOOM.WAD E1M1, saves, reloads that save, and enters a converted dungeon demo if one is present.
"""
import glob, os, shutil, subprocess, sys, time, zipfile

EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-overworld\Release\uzdoom.exe"
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORK = r"D:\dev\DoomDaggerfall-build\overworld-tests\stock"
DOOR = r"D:\dev\DoomDaggerfall-loop\review\door-demo"
COMMON = ["-nosound", "-noautoload", "-noactivate", "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]


def run(name, args, seconds, until=None):
    log = os.path.join(WORK, f"log-{name}.txt")
    if os.path.exists(log):
        os.remove(log)
    cmd = [sys.executable, QUIET, "--timeout", str(seconds), "--", EXE, "-config", os.path.join(WORK, "stock.ini"), "-savedir", WORK] + COMMON + ["+logfile", name] + args
    proc = subprocess.Popen(cmd, cwd=WORK, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + seconds
    text = ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        if "FATAL" in text or (until and until(text)):
            break
    alive = proc.poll() is None
    if alive:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    return alive, text


os.makedirs(WORK, exist_ok=True)
doom = ["-iwad", os.path.join(WADS, "DOOM.WAD"), "-skill", "3"]
# A tiny script requests one save. It adds no overworld data, so the treadmill must stay off.
hook = os.path.join(WORK, "savehook.pk3")
with zipfile.ZipFile(hook, "w") as z:
    z.writestr("zscript.txt", '''version "4.14"
class SaveHook : EventHandler { bool saved; override void WorldTick() { if (!saved && level.maptime == 70) { saved = true; Level.MakeAutoSave(); } } }
''')
    z.writestr("mapinfo.txt", '''gameinfo { addeventhandlers = "SaveHook" }
''')
doom += ["-file", hook]
alive, text = run("e1m1", doom + ["+map", "E1M1"], 15, lambda t: False)
print(f"E1M1: ran to time limit={alive} entered={'E1M1' in text} fatal={'FATAL' in text} treadmill={'DDTM' in text}")
saves = sorted(glob.glob(os.path.join(WORK, "auto*.zds")), key=os.path.getmtime)
if saves:
    save = saves[-1]
    with zipfile.ZipFile(save) as z:
        blob = b"".join(z.read(n) for n in z.namelist())
    print(f"E1M1 save {os.path.basename(save)}: overworld key={b'ddoverworld' in blob} actor id key={b'ddrecordid' in blob}")
    alive, text = run("e1m1load", doom + ["-loadgame", os.path.basename(save)], 12, lambda t: False)
    print(f"E1M1 reload: ran to time limit={alive} fatal={'FATAL' in text} treadmill={'DDTM' in text}")
else:
    print("E1M1 save: the save command wrote no file")

files = [os.path.join(DOOR, f) for f in ("privateershold.wad", "privateershold_mesh.pk3", "privateershold_width.pk3", "privateershold_monsters.pk3", "privateershold_doors.pk3")]
if all(map(os.path.exists, files)):
    alive, text = run("dungeon", ["-iwad", os.path.join(WADS, "DOOM2.WAD"), "-file"] + files + ["-skill", "3", "+map", "MAP01"], 15, lambda t: False)
    print(f"Dungeon demo: ran to time limit={alive} entered={'MAP01' in text} fatal={'FATAL' in text} treadmill={'DDTM' in text}")
