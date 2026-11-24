"""One paired session from a real New Game to town, against an installed play folder, minimized.

usage: walk.py <play folder> [--out DIR]
Uses play.bat's mods, plus walk.zs: makes a character with tools/new_game's driver, arrives in Privateer's Hold, leaves
by the exit, counts townspeople, presses Use on one (and closes Daggerfall's window with Esc), and opens the travel map.
Config, saves, and logs go to DIR (default <play folder>/../demo-walk), never to the play folder's run folder.
"""
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "new_game"))
import run_new_game as ng  # noqa: E402  (its window-message driver for Daggerfall's creation screens)

DRLA = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
TIMEOUT = 240


def main():
    play = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else play.parent / "demo-walk"
    shutil.rmtree(out, ignore_errors=True)
    (out / "saves").mkdir(parents=True)
    with zipfile.ZipFile(play / "data" / "privateershold_doors.pk3") as z:
        exit_row = next(l.split()[1:6] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit"))
    harness = out / "walk.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "walk.zs").read_text().replace("@EXIT@", ", ".join(exit_row)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DWHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-walk.txt", out / "launcher.log"
    data = play / "data"
    uz = ["-noactivate", "-config", str(out / "walk.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log), "-dfflow",
          "-dfnewgametest", "once", "-dfuitest", "0", "-nosound", "-ddtowncache", str(data / "cache"),
          "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "walk", "+vid_fullscreen", "0", "+wipetype", "0",
          "+bind", "k", "netevent df_fast_travel", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfflow", ng.DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, ng.QUIET, "--timeout", str(TIMEOUT), "--", str(play / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD,
               "--uzdoom-cwd", str(out), "--log", str(launcher)]
    for mod in DRLA + [data / n for n in DATA] + [play / "dfitems.pk3", play / "doomerfall.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline, result, hwnd, tries, last, closed, pressed = time.time() + TIMEOUT, "timeout", None, 0, "", 0, False
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.1)
            text, uzt, dft = ng.read(console), ng.read(uz_log), ng.read(df_log)
            if any(k in text for k in ("DIED WITH FATAL", "VM execution aborted")):
                result = "fatal"
                break
            if "DWDONE" in text:
                result = re.search(r"DWDONE (\w+)", text).group(1)
                time.sleep(1)
                break
            hwnd = hwnd or ng.doom_window(launcher)
            if not hwnd:
                continue
            if "both games running" not in uzt:  # Character creation.
                size = re.search(r"opened menu 4 at (\d+)x(\d+)", uzt)
                if not size or "ui: closed" in uzt[uzt.rfind("opened menu 4"):]:
                    continue
                ng.SURFACE[:] = [int(size.group(1)), int(size.group(2))]
                top = ng.top_window(df_log)
                tries = tries + 1 if top == last else 0
                last = top
                ng.act(hwnd, top, tries)
                time.sleep(0.15)
                continue
            # After DWTALK or DWTRAVEL, close each Daggerfall window that opens, after it has been shown a moment.
            opened = dft.count("opened, surface") - dft.count("closed, reason")
            if "DWTALK" in text and opened > 0 and closed < 4:
                time.sleep(1.5)
                ng.key(hwnd, 0x1B)
                closed += 1
                time.sleep(0.5)
            if "DWTRAVEL" in text and not pressed:  # The K binding goes through the engine's UI hook, as a player's key does.
                time.sleep(0.5)
                ng.key(hwnd, 0x4B)
                pressed = True
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    print("result:", result)
    for line in ng.read(console).splitlines():
        if line.startswith("DW") or "Script error" in line and "DoomRL" not in line and "translation" not in line:
            print(line[:200])
    for line in ng.read(df_log).splitlines():
        if re.search(r"new game:|talk:|townspeople|town:|ui: top window|transition|error", line):
            print("df", line[:200])


if __name__ == "__main__":
    main()
