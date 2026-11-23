"""Controls for synchronized saving. Usage: run_controls.py plain|load|stock|drla

plain: a normal Daggerfall save through its own entry point.
load:  loads the Daggerfall half of a real bundle through Daggerfall's own loader.
stock: DOOM.WAD E1M1 with no bridge makes a menu save and an autosave.
drla:  the same with the DRLA set.
"""
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\synchronized-saving")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
RUNNER = str(HERE / "run_save.py")
mode = sys.argv[1]

STOCK_SCRIPT = '''version "4.10"
class StockSaveControl : EventHandler
{
	ui int ticks;
	ui bool done;
	override void UiTick()
	{
		if (done || gamestate != GS_LEVEL || ++ticks < 70) return;
		done = true;
		let saves = SavegameManager.GetManager();
		saves.ReadSaveStrings();
		saves.InsertNewSaveNode();
		saves.DoSave(0, "control");
		saves.RemoveNewSaveNode();
	}
	override void WorldTick()
	{
		if (level.maptime == 140) level.MakeAutoSave();
		if (level.maptime == 200) Console.Printf("STOCKDONE");
	}
}
'''


def stock(name, mods):
    run = REVIEW / "test" / f"control-{name}"
    shutil.rmtree(run, ignore_errors=True)
    (run / "saves").mkdir(parents=True)
    control = run / "control.pk3"
    with zipfile.ZipFile(control, "w") as z:
        z.writestr("zscript.txt", STOCK_SCRIPT)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "StockSaveControl" }\n')
    files = [str(m) for m in mods] + [str(control)]
    command = [sys.executable, QUIET, "--timeout", "35", "--cwd", str(run), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
               "-file", *files, "-config", str(run / "uz.ini"), "-savedir", str(run / "saves"), "-nosound", "-noautoload", "-skill", "3",
               "+logfile", "console", "+map", "E1M1", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log, end, result = run / "log-console.txt", time.time() + 38, "timeout"
    while time.time() < end and proc.poll() is None:
        time.sleep(0.3)
        text = log.read_text(errors="replace") if log.exists() else ""
        if "STOCKDONE" in text:
            result = "finished"
            time.sleep(0.5)
            break
        # Not "Script error": DRLAX prints one for an empty translation at every load, and the game runs on.
        if any(k in text for k in ("VM execution aborted", "DIED WITH FATAL", "Execution could not continue")):
            result = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print(name, result)
    names = sorted(p.name for p in (run / "saves").iterdir())
    print("files:", names)
    for path in sorted((run / "saves").glob("*.zds")):
        with zipfile.ZipFile(path) as z:
            print(path.name, "zip", z.testzip() or "ok", "doomerfall entries:", sum(n.startswith("doomerfall/") for n in z.namelist()),
                  "stock entries:", all(n in z.namelist() for n in ("info.json", "globals.json", "savepic.png")))
    text = log.read_text(errors="replace") if log.exists() else ""
    print("bridge lines in console:", text.count("[bridge]"))


if mode == "plain":
    sys.exit(subprocess.call([sys.executable, RUNNER, "control-plain", "--no-savetest", "--extra-df=-dfplainsavetest", "--until", "plain save test:", "--timeout", "30"]))
elif mode == "load":
    bundle = REVIEW / "test" / "real1" / "saves" / "bundle.zds"
    target = REVIEW / "dfu" / "PortableAppdata" / "Saves" / "SAVE900"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    with zipfile.ZipFile(bundle) as z:
        for entry in z.namelist():
            if entry.startswith("doomerfall/daggerfall/"):
                (target / entry.rsplit("/", 1)[1]).write_bytes(z.read(entry))
    try:
        code = subprocess.call([sys.executable, RUNNER, "control-load", "--no-savetest", "--extra-df=-dfloadsavetest", "--extra-df=Doomerfall", "--until", "load test:", "--timeout", "30"])
    finally:
        shutil.rmtree(target, ignore_errors=True)
    sys.exit(code)
elif mode == "stock":
    stock("stock", [])
elif mode == "drla":
    stock("drla", [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3"])
