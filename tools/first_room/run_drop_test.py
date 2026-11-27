"""Checks that the start room's battle rifle Former Humans drop battle rifles with the DRLA set from play_drlax.bat.

usage: run_drop_test.py <uzdoom.exe> <output folder>
Packs drop_test.zs into a pk3, runs DOOM2 MAP01 with DRLA Arsenal, Monsters and DRLAX on a private desktop (quiet_run),
and passes when all three kinds died and three RLBattleRiflePickup lie on the floor."""
import re
import time
import subprocess
import sys
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
MODS = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]

uz, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
pk3 = out / "first_room_drop_test.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("drop_test.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { AddEventHandlers = "FirstRoomDropTest" }\n')
log = out / "log-drop-test-log.txt"  # UZDoom names +logfile drop-test.log this way
log.unlink(missing_ok=True)
cmd = [sys.executable, QUIET, "--timeout", "40", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *map(str, MODS), str(pk3),
       "-config", str(out / "drop-test.ini"), "+logfile", "drop-test.log", "-warp", "1", "-skill", "3",
       "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd)
deadline = time.time() + 45
while time.time() < deadline and proc.poll() is None:
    text = log.read_text(errors="replace") if log.exists() else ""
    # Not plain "Fatal": DRLA's own Midas_Statue_Fatality warnings contain it.
    if "FIRSTROOM done" in text or "Fatal error" in text or "VM execution aborted" in text:
        break
    time.sleep(0.5)
subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
text = log.read_text(errors="replace") if log.exists() else ""
for line in text.splitlines():
    if line.startswith("FIRSTROOM"):
        print(line)
m = re.search(r"FIRSTROOM killed (\d+) [^\n]*floor: (\d+)", text)
ok = bool(m) and m.group(1) == "3" and m.group(2) == "3"
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
