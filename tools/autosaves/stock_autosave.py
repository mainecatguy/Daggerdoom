"""Stock Doom autosaves without Daggerfall: DOOM.WAD E1M1, then a level change to E1M2 (no intermission), which autosaves.
Stock and with the DRLA set, no bridge, minimized through quiet_run. Passes when each run writes an autosave on E1M2 and
logs no fatal error. A small test handler (written next to the logs) changes the level and prints SAVETEST lines.

usage: stock_autosave.py [--root INSTALL_FOLDER]   (default: the review folder of the autosave setup gate)
Logs and saves go to <root>/test/stock-autosave-<label>.
"""
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else Path(r"D:\dev\DoomDaggerfall-loop\review\autosave-setup")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
ZSCRIPT = """version "4.14"
class SaveTestHandler : StaticEventHandler
{
	override void WorldTick()
	{
		if (level.MapName ~== "E1M1" && level.maptime == 35) { Console.Printf("SAVETEST changing to E1M2"); level.ChangeLevel("E1M2", 0, CHANGELEVEL_NOINTERMISSION); }
		if (level.MapName ~== "E1M2" && level.maptime == 70) Console.Printf("SAVETEST on E1M2");
	}
}
"""

ok = True
for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
    runs = ROOT / "test" / f"stock-autosave-{label}"
    saves = runs / "saves"
    saves.mkdir(parents=True, exist_ok=True)
    for old in saves.glob("*.zds"):
        old.unlink()
    handler = runs / "savetest.pk3"
    with zipfile.ZipFile(handler, "w") as z:
        z.writestr("zscript.txt", ZSCRIPT)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SaveTestHandler" }\n')
    log = runs / f"log-{label}.txt"  # +logfile NAME writes log-NAME.txt in the working folder (as run_paired.py check)
    log.unlink(missing_ok=True)
    command = [sys.executable, QUIET, "--timeout", "40", "--cwd", str(runs), "--", str(ROOT / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
               "-config", str(runs / "uzdoom.ini"), "-savedir", str(saves), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(handler),
               "+logfile", label, "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
               "+disableautosave", "0", "+autosavecount", "4", "+map", "E1M1"]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + 40
    body = ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
        body = log.read_text(errors="replace") if log.exists() else ""
        if "SAVETEST on E1M2" in body or any(k in body for k in FATAL):
            time.sleep(1)
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    body = log.read_text(errors="replace") if log.exists() else ""
    autos = sorted(p.name for p in saves.glob("auto*.zds"))
    fatal = sum(any(k in l for k in FATAL) for l in body.splitlines())
    reached = "SAVETEST on E1M2" in body
    passed = bool(autos) and fatal == 0 and reached
    ok &= passed
    print(label, "PASS" if passed else "FAIL", "| autosaves", autos, "| fatal", fatal, "| reached E1M2", reached,
          "| script errors", sum("Script error" in l for l in body.splitlines()))
sys.exit(0 if ok else 1)
