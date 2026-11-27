"""Loads a plain Daggerfall save (no Doom half) in a paired session through the launcher, minimized.

  run_plain_load.py <save> [save] [--root DIR] [--source FOLDER-OR-ZDS] [--play-mods]
  <save>: nogun or gun. With "save", Doom's load test then saves, changes, and reloads.
  --root: an install folder (scripts/play/install.py) to run instead of the plainsaves review folder.
  --source: the Daggerfall save to copy, a save folder or a Doomerfall .zds bundle. From a bundle only Daggerfall's own
  files are taken (no Doomerfall*.json), so it is a plain save. A New Game bundle gives one inside Privateer's Hold.
  --play-mods: also load what play.bat loads: the DRLA set, the root's dfitems.pk3 and doomerfall.pk3. Without
  doomerfall.pk3 nothing answers Daggerfall's gun requests (DoomerfallGuns.zs), so its "hotkeys: request 1" times out.

Both test saves are copies of one source save, written to the test folder's private portable saves; the source is only
read. "nogun" is the copy as it is. "gun" adds a DRLA shotgun (a Doom item) to the inventory. The test flags open
Daggerfall's Load window from Doom's title (-dfplainloadtest on both sides) and pick the save.
Run through tools/demo_combined/retarget.py <play folder> --play-mods. Stops at once on a fatal error.
"""
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REVIEW = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else Path(r"D:\dev\DoomDaggerfall-loop\review\plainsaves")
DATA = REVIEW / "data"
SOURCE = Path(sys.argv[sys.argv.index("--source") + 1]) if "--source" in sys.argv else \
    Path(r"C:\Users\Patrick\AppData\LocalLow\Daggerfall Workshop\Daggerfall Unity\Saves\SAVE0")  # read only
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
GAMEMODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]  # as play.bat
TIMEOUT = 90
SAVES = {"nogun": ("SAVE901", "PlainNoGun"), "gun": ("SAVE902", "PlainWithGun")}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def make_save(kind):
    folder, name = SAVES[kind]
    target = REVIEW / "dfu" / "PortableAppdata" / "Saves" / folder
    if target.exists():
        shutil.rmtree(target)
    if SOURCE.suffix.lower() == ".zds":
        target.mkdir(parents=True)
        prefix = "doomerfall/daggerfall/"
        with zipfile.ZipFile(SOURCE) as z:
            for entry in z.namelist():
                leaf = entry[len(prefix):]
                if entry.startswith(prefix) and leaf and not leaf.startswith("Doomerfall"):
                    (target / leaf).parent.mkdir(parents=True, exist_ok=True)
                    (target / leaf).write_bytes(z.read(entry))
            (target / "Screenshot.jpg").write_bytes(z.read("savepic.png"))  # the Load window reads one; PNG bytes load fine
    else:
        shutil.copytree(SOURCE, target)
    info = json.loads((target / "SaveInfo.txt").read_text())
    info["saveName"] = name
    (target / "SaveInfo.txt").write_text(json.dumps(info, indent=4))
    if kind == "gun":
        data = json.loads((target / "SaveData.txt").read_text())
        items = data["playerData"]["playerEntity"]["items"]
        gun = dict(items[0])
        gun.update(uid=max(i["uid"] for i in items) + 1000, shortName="RLShotgunPickup|gun|", itemGroup="MiscItems", groupIndex=9100,
                   className="DaggerfallWorkshop.Game.Doomerfall.DoomerfallDoomItem", weightInKg=2.0, value1=0, value2=0, stackCount=1,
                   message=0, nativeMaterialValue=0)
        items.append(gun)
        (target / "SaveData.txt").write_text(json.dumps(data, indent=4))
    return name


def main():
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in ("--root", "--source")]
    kind = args[0]
    load = args[1] if len(args) > 1 else ""
    save_name = make_save(kind)
    name = f"{kind}{'-' + load if load else ''}"
    run = REVIEW / "test-run"
    (run / "saves").mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = run / f"{name}-uz.log", run / f"{name}-df.log", run / f"log-{name}.txt", run / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)

    uz_args = ["-noactivate", "-config", str(run / "test.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-dfflow",
               "-dfplainloadtest", "once", "-dfuitest", "0", "-nosound", "-ddtowncache", str(DATA / "cache"),
               "-ddconverter", str(DATA / "converter" / "DungeonConverter.exe"), "-ddarena2", DAGGER + r"\ARENA2",
               "+logfile", f"log-{name}.txt", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    if "--loading-test" in sys.argv:  # the loading hold test (dd_loading_test.cpp)
        uz_args.append("-ddloadingtest")
    if load:
        uz_args += ["-dfloadtest", f"{load}:{run / 'saves' / (name + '.zds')}"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfflow", DAGGER, "-dfplainloadtest", save_name, "-dfmute",
                "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    if "--loading-test" in sys.argv:  # and Daggerfall's side of it (DoomerfallLoadingPauseTest.cs)
        dfu_args.append("-dfloadingpausetest")
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(launcher)]
    mods = [DATA / m for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    if "--play-mods" in sys.argv:
        mods = [GAMEMODS / m for m in DRLA] + mods + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]
    for mod in mods:
        command += ["--mod", str(mod)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT
    result = "timeout"
    try:
        while time.time() < deadline and proc.poll() is None:
            uz, df = read(uz_log), read(df_log)
            if any(k in read(console) for k in FATAL):
                result = "fatal"
                break
            if "FAILED" in uz:
                result = "failed"
                break
            if load and re.search(r"load test: (PASS|FAIL)", uz):
                result = re.search(r"load test: (PASS|FAIL)", uz).group(1)
                time.sleep(3)  # Daggerfall's after-load lines.
                break
            if not load and "plain load: both games running" in df and "flags 0 done" in df:
                result = "reached"
                time.sleep(4)  # Both games run together briefly; ammo settles.
                # The loading test watches for the poison's first tick after the hold (DoomerfallLoadingPauseTest.cs).
                while "--loading-test" in sys.argv and "poison after the release" not in read(df_log) and time.time() < deadline:
                    time.sleep(0.5)
                break
            time.sleep(0.2)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    print("result:", result)
    pattern = r"plain load|starter|hotkeys:|ammo: (plain|after load|add|equip)|load test|save \d+: wrote|FAILED|error|DDPLAINLOAD|DDNEWGAME|setup:|arrival|save:|committed"
    for path in (uz_log, df_log, console):
        lines = [l for l in read(path).splitlines() if re.search(pattern, l)]
        print(f"--- {path.name}: {len(lines)} lines")
        print("\n".join(lines[-40:]))


if __name__ == "__main__":
    main()
