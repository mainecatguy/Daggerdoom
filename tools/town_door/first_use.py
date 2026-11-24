"""Presses Use once on a town door whose interior is not converted yet, in UZDoom alone, minimized.

Usage: first_use.py NAME --exe UZDOOM [--scenario still|walkaway|left|busy] [--timeout 30]
still:    stands at the door after the press.
walkaway: steps 300 units away right after the press, and waits there. It never presses again.
left:     goes 1000 units away after the press. The door must be dropped with a message.
busy:     converts door B, presses door A while B runs, then stands closer to door C. A must convert before C.
Every run starts from a cache holding only the town. Generated files stay in the review folder.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

REVIEW = Path(os.environ.get("DD_REVIEW", r"D:\dev\DoomDaggerfall-loop\review\connected-transitions"))
ROOT = REVIEW.parent / "town-door"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")

HARNESS = r'''version "4.14"
class FUHarness : EventHandler
{
	const TICS = 35 * @WAIT@;
	int timer, pressedAt;
	bool done;
	void Hold(PlayerPawn p, Vector2 at, double z, Vector2 normal)
	{
		p.SetOrigin((at, z), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
	}
	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (level.MapName.Left(3) ~== "DDS")
		{
			Console.Printf("FUDONE entered map=%s tics_after_press=%d", level.MapName, gametic - CVar.FindCVar("dd_fu_press").GetInt());
			done = true;
			return;
		}
		Vector3 door = (@X@, @Y@, @Z@);
		Vector2 normal = (@NX@, @NY@);
		timer++;
		Vector2 first = (@BX@, @BY@), closer = (@CX@, @CY@);
		bool busy = "@SCENARIO@" == "busy";
		if (busy && timer < 24) { Hold(p, first, door.z, normal); return; }	// Long enough for door B's conversion to start.
		if (timer < (busy ? 26 : 12)) { Hold(p, door.xy + normal * 48, door.z, normal); return; }
		if (timer == (busy ? 26 : 12))
		{
			Hold(p, door.xy + normal * 48, door.z, normal);
			CVar.FindCVar("dd_fu_press").SetInt(gametic);
			CVar.FindCVar("dd_tm_use").SetInt(1);
			Console.Printf("FUPRESS");
			return;
		}
		if (busy) Hold(p, closer, door.z, normal);
		else
		{
			double away = timer <= 16 ? 48 : "@SCENARIO@" == "walkaway" ? 300 : "@SCENARIO@" == "left" ? 1000 : 48;
			Hold(p, door.xy + normal * away, door.z, normal);
		}
		if (timer > TICS)
		{
			Console.Printf("FUDONE not-entered after one press");
			done = true;
		}
	}
}
'''


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--exe", required=True)
ap.add_argument("--group", type=int, default=9183)
ap.add_argument("--scenario", default="still", choices=("still", "walkaway", "left", "busy"))
ap.add_argument("--timeout", type=int, default=30)
args = ap.parse_args()

run = ROOT / args.name
if run.exists():
    shutil.rmtree(run)
cache = run / "cache"
cache.mkdir(parents=True)
town = f"T{args.group:05d}.ddt"
shutil.copy2(REVIEW / "test-cache" / town, cache / town)
doors = [l.split() for l in lumps(cache / town)["DDDOORS"].decode().splitlines() if l.strip()]
buildings = [d for d in doors if d[0] == "0"]
door = buildings[0]
spot_b = spot_c = (0.0, 0.0)
if args.scenario == "busy":  # A has two neighbors with other interiors, and C is within the old 160-unit limit.
    def near(a, b):
        return ((float(a[3]) - float(b[3])) ** 2 + (float(a[4]) - float(b[4])) ** 2) ** 0.5
    for a in buildings:
        others = sorted((d for d in buildings if d[1] != a[1] and near(a, d) < 600), key=lambda d: near(a, d))
        distinct = list({d[1]: d for d in others}.values())
        if len(distinct) >= 2 and near(a, distinct[0]) < 290:
            door, c, b = a, distinct[0], distinct[1]
            break
    else:
        sys.exit("no door with two close neighbors")
    spot_b = (float(b[3]) + float(b[6]) * 8, float(b[4]) + float(b[7]) * 8)
    # 150 units from A toward C: inside the old limit, and closer to C than to A.
    share = 150 / near(door, c)
    spot_c = (float(door[3]) + (float(c[3]) - float(door[3])) * share, float(door[4]) + (float(c[4]) - float(door[4])) * share)
    print("running first:", b[1], "closer:", c[1], "A to C:", round(near(door, c)))
print("door interior:", door[1])

text = HARNESS
for key, value in (("@X@", door[3]), ("@Y@", door[4]), ("@Z@", door[5]), ("@NX@", door[6]), ("@NY@", door[7]), ("@SCENARIO@", args.scenario), ("@WAIT@", str(max(5, args.timeout - 8))),
                   ("@BX@", str(spot_b[0])), ("@BY@", str(spot_b[1])), ("@CX@", str(spot_c[0])), ("@CY@", str(spot_c[1]))):
    text = text.replace(key, value)
harness = run / "harness.pk3"
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "FUHarness" }\n')
    z.writestr("cvarinfo.txt", "user int dd_fu_press = 0;\n".replace("user", "server"))

command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", str(run), "--", args.exe, "-iwad", str(GAME / "wads" / "DOOM2.WAD"), "-noactivate",
           "-config", str(run / "uz.ini"), "-nosound", "-ddtowncache", str(cache), "-ddconverter", str(REVIEW / "converter" / "DungeonConverter.exe"),
           "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "-noautoload", "-skill", "3", "-file"]
command += [str(REVIEW / m) for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")] + [str(harness)]
command += ["+logfile", "console", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{args.group:05d}"]
console = run / "log-console.txt"
proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason, end = "timeout", time.time() + args.timeout + 3
log = ""
while time.time() < end:
    time.sleep(0.25)
    log = console.read_text(errors="replace") if console.exists() else ""
    if any(k in log for k in FATAL):
        reason = "fatal"
        break
    if "FUDONE" in log:
        reason = "finished"
        break
    if proc.poll() is not None:
        reason = "exited"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
print("stopped:", reason)
for line in log.splitlines():
    if line.startswith(("FU", "DDTCONV", "DDTRANSITION")) or "Opening" in line or "will not open" in line or any(k in line for k in FATAL):
        print(line[:150])
sys.exit(0 if re.search(r"FUDONE entered", log) else 1)
