"""Makes a real character, then follows the route in harness.zs and a real fast travel.

The locprobe lines need a Daggerfall build with probe.patch applied (git apply), which is test-only and never committed
to the game code. Stage with stage.py after building.

usage: run_location.py [list row for fast travel] [label]   A label keeps the logs in review/reported-location/evidence-<label>.
Uses private config, saves, and the portable Daggerfall build. Stops at once on a fatal error.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "new_game"))
import run_new_game as ng  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\reported-location")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
TIMEOUT = 150  # Character creation with the full mod set (30-55 s), then the whole route. Fatal errors still stop it at once.
ROW_HEIGHT = 6
# The DRLA set always logs a harmless "Script error" for one translation, so only real stops count here.
ng.FATAL = ("VM execution aborted", "Execution could not continue", "Fatal error")


def wait(path, text, deadline, proc, console):
    while time.time() < deadline and proc.poll() is None:
        if text in ng.read(path):
            return True
        if any(k in ng.read(console) for k in ng.FATAL):
            return False
        time.sleep(0.05)
    return False


def travel(hwnd, row, df_log, uz_log, deadline, proc, console):
    while ng.read(uz_log).count("Daggerfall opened menu") < 2:  # The first was character creation.
        if time.time() > deadline or proc.poll() is not None:
            return "menu did not open"
        time.sleep(0.05)
    menus = re.findall(r"opened menu \d+ at (\d+)x(\d+)", ng.read(uz_log))
    ng.SURFACE[:] = [int(menus[-1][0]), int(menus[-1][1])]
    time.sleep(1.0)
    ng.click(hwnd, 20, 190)  # I'm At.
    time.sleep(0.7)
    ng.key(hwnd, 0x0D)  # Open the region.
    time.sleep(0.7)
    ng.key(hwnd, 0x4C)  # The location list.
    time.sleep(0.6)
    boxes = ng.read(df_log).count("top window is DaggerfallMessageBox")  # Earlier boxes must not count.
    for _ in range(3):  # A double click that lands while the list is still opening is lost, so try again.
        ng.click(hwnd, 100, 64 + row * ROW_HEIGHT, 2)
        retry_at = time.time() + 3
        while ng.read(df_log).count("top window is DaggerfallMessageBox") <= boxes and time.time() < min(deadline, retry_at) and proc.poll() is None:
            time.sleep(0.05)
        if ng.read(df_log).count("top window is DaggerfallMessageBox") > boxes:
            break
    time.sleep(0.3)
    ng.key(hwnd, 0x59)  # Yes.
    if wait(df_log, "top window is DaggerfallTravelPopUp", deadline, proc, console):
        time.sleep(0.4)
        ng.key(hwnd, 0x42)  # Begin.
    if wait(df_log, "travel: Doom reached", deadline, proc, console):
        time.sleep(3.0)
        return "arrived"
    return "arrival not seen"


def main():
    row = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    label = sys.argv[2] if len(sys.argv) > 2 else ""
    run = REVIEW / "test-run"
    (run / "saves").mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = run / "uz.log", run / "df.log", run / "log-route.txt", run / "launcher.log"  # +logfile route writes log-route.txt
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = REVIEW / "data"
    uz_args = ["-noactivate", "-config", str(run / "test.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-dfflow",
               "-dfnewgametest", "once", "-dfuitest", "1", "-nosound", "-ddtowncache", str(data / "cache"),
               "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
               "+logfile", "route", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfflow", ng.DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, ng.QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD,
               "--uzdoom-cwd", str(run), "--log", str(launcher)]
    mods = [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3", data / "ddruntime.pk3", data / "overworld.pk3",
            data / "privateershold.wad", data / "privateershold_mesh.pk3", data / "privateershold_doors.pk3", REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "test-harness"]
    for mod in mods:
        command += ["--mod", str(mod)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT
    result, hwnd, tries, last = "timeout", None, 0, ""
    try:
        while time.time() < deadline and proc.poll() is None:
            uz = ng.read(uz_log)
            if any(k in ng.read(console) for k in ng.FATAL):
                result = "fatal"
                break
            if "both games running" in uz:
                result = "route did not finish"
                hwnd = hwnd or ng.doom_window(launcher)
                if wait(console, "ready for the fast travel menu", deadline, proc, console):
                    result = travel(hwnd, row, df_log, uz_log, deadline, proc, console)
                break
            size = re.search(r"opened menu 4 at (\d+)x(\d+)", uz)
            if not size or "ui: closed" in uz[uz.rfind("opened menu 4"):]:
                time.sleep(0.05)
                continue
            ng.SURFACE[:] = [int(size.group(1)), int(size.group(2))]
            hwnd = hwnd or ng.doom_window(launcher)
            if not hwnd:
                continue
            top = ng.top_window(df_log)
            tries = tries + 1 if top == last else 0
            last = top
            ng.act(hwnd, top, tries)
            time.sleep(0.15)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    if label:  # Keeps this run's logs, so a later run cannot overwrite the evidence.
        kept = REVIEW / f"evidence-{label}"
        kept.mkdir(exist_ok=True)
        for path in (uz_log, df_log, console, launcher):
            if path.exists():
                shutil.copy2(path, kept / path.name)
        print("kept logs in", kept)
    print("result:", result, "| last wizard window:", last)
    for line in ng.read(console).splitlines():
        if line.startswith("LOCSTEP") or any(k in line for k in ng.FATAL):
            print(line[:180])
    for line in ng.read(df_log).splitlines():
        if "locprobe" in line or "error" in line or "travel:" in line:
            print(line[:270])


if __name__ == "__main__":
    main()
