"""Stock Doom still starts with the fist work: DOOM.WAD E1M1, stock and with the DRLA set (as play_drlax.bat), plus the
-norun startup check. Presses slot 1 and slot 2 so the fist and pistol are raised by Doom's own slot keys.

  python tools/fist/check_e1m1.py <stage>     (<stage>\\uzdoom\\uzdoom.exe; logs go to <stage>\\test-e1m1)
"""
import subprocess
import sys
from pathlib import Path

STAGE = Path(sys.argv[1])
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WADS = Path(r"D:\dev\DoomDaggerfall\GameResources\wads")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [str(MODS / n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
UZ = STAGE / "uzdoom" / "uzdoom.exe"
RUN = STAGE / "test-e1m1"
RUN.mkdir(exist_ok=True)
ok = True
for label, mods in (("stock", []), ("drla", DRLA)):
    log = RUN / f"log-e1m1-{label}.txt"
    log.unlink(missing_ok=True)
    cmd = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(RUN), "--", str(UZ), "-iwad", str(WADS / "DOOM.WAD"), "-config", str(RUN / f"{label}.ini"),
           "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"e1m1-{label}", "+i_pauseinbackground", "0",
           "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1",
           "+wait 70;slot 1;wait 70;slot 2;wait 70;quit"]  # One chain: a separate +quit would run before the map.
    code = subprocess.call(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lines = log.read_text(errors="replace").splitlines() if log.exists() else []
    fatal = [l for l in lines if any(k in l for k in FATAL)]
    bridge = [l for l in lines if "doomitems:" in l or "hotkeys:" in l or "dfg " in l]
    reached = any("E1M1" in l or "Hangar" in l for l in lines)
    print(label, "exit", code, "| log lines", len(lines), "| E1M1 seen", reached, "| fatal", len(fatal), "| bridge/hotkey lines", len(bridge))
    ok = ok and reached and not fatal and not bridge
code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(RUN), "--", str(UZ), "-iwad", str(WADS / "DOOM.WAD"), "-norun", "-stdout"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("-norun exit", code, "(1337 is success)")
print("RESULT", "PASS" if ok and code == 1337 else "FAIL")
