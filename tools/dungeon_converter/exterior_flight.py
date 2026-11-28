"""Flight test for exterior collision: fly the real player just above model tops and see what stops it.

Usage: python tools/dungeon_converter/exterior_flight.py <dir with <slug>.wad and <slug>.tops.txt> --slug <slug> [--timeout 30]

The converter writes <slug>.tops.txt with --fidelity: cells that got a model top at least a body above the street.
For each one the player (radius 10.5, as in Doomerfall towns) is put 2 units above the top with gravity off and moved
48 units in each of four directions with the engine's own TryMove. Each move ends:
  clear   moved the whole way,
  finite  stopped by a two-sided line (a higher model top nearby: real geometry with a finite height) or a thing,
  sky     stopped by a one-sided line, which Doom treats as a wall of unlimited height: an invisible wall above the model,
  start   the start position itself did not fit (skipped).
Passes when no move ends at a one-sided line and some moves are clear. Output is derived from game data, so keep it
outside the repo.
"""
import argparse
import glob
import os
import subprocess
import sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

ZSCRIPT = """version "4.10"
class DFFlight : EventHandler
{
	override void WorldTick()
	{
		if (level.maptime != 5) return;
		let mo = players[0].mo;
		mo.A_SetSize(10.5, mo.height);
		mo.bNOGRAVITY = true;
		String body = Wads.ReadLump(Wads.CheckNumForName("DFTOPS", Wads.ns_global));
		Array<String> rows;
		body.Split(rows, "\\n", TOK_SKIPEMPTY);
		int clear = 0, finite = 0, sky = 0, start = 0;
		static const double dx[] = { 1, -1, 0, 0 };
		static const double dy[] = { 0, 0, 1, -1 };
		for (int i = 0; i < rows.Size(); i++)
		{
			Array<String> f;
			rows[i].Split(f, " ");
			Vector3 p = (f[0].ToDouble(), f[1].ToDouble(), f[2].ToDouble() + 2);
			for (int d = 0; d < 4; d++)
			{
				mo.SetOrigin(p, false);
				mo.vel = (0, 0, 0);
				if (!mo.TestMobjLocation() || mo.floorz > p.z + 1) { start++; continue; }
				String outcome = "clear";
				for (int s = 1; s <= 12; s++)
				{
					mo.SetZ(max(mo.pos.z, mo.floorz));
					if (mo.TryMove(p.xy + (dx[d], dy[d]) * 4 * s, 1)) continue;
					Line l = mo.BlockingLine;
					outcome = (l && !(l.flags & Line.ML_TWOSIDED)) ? "sky" : "finite";
					break;
				}
				if (outcome == "clear") clear++; else if (outcome == "finite") finite++; else
				{
					sky++;
					if (sky <= 10) Console.Printf("DFFLIGHT sky at %.0f %.0f z %.0f dir %d line %d", p.x, p.y, p.z, d, mo.BlockingLine.Index());
				}
			}
		}
		Console.Printf("DFFLIGHT result samples %d clear %d finite %d sky %d start %d", rows.Size(), clear, finite, sky, start);
	}
}
"""

parser = argparse.ArgumentParser()
parser.add_argument("dir")
parser.add_argument("--slug", required=True)
parser.add_argument("--timeout", type=int, default=30)
args = parser.parse_args()
base = os.path.abspath(args.dir)
work = os.path.join(base, "flight")
harness = os.path.join(work, "harness")
os.makedirs(harness, exist_ok=True)
with open(os.path.join(harness, "zscript.zs"), "w", newline="\n") as f:
    f.write(ZSCRIPT)
with open(os.path.join(harness, "MAPINFO"), "w", newline="\n") as f:
    f.write('GameInfo\n{\n\tAddEventHandlers = "DFFlight"\n}\n')
with open(os.path.join(base, args.slug + ".tops.txt")) as src, open(os.path.join(harness, "DFTOPS"), "w", newline="\n") as dst:
    dst.write(src.read())
with open(os.path.join(work, "doom.ini"), "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
with open(os.path.join(work, "run.cfg"), "w", newline="\n") as f:
    f.write("wait 40; quit\n")
log = os.path.join(work, "flight.log")
for old in [log] + glob.glob(os.path.join(work, "*flight*.txt")):
    if os.path.exists(old):
        os.remove(old)
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", work, "--", UZDOOM,
           "-iwad", IWAD, "-file", os.path.join(base, args.slug + ".wad"), harness,
           "-config", os.path.join(work, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
           "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
           "+logfile", "flight.log", "+map", "MAP01", "+exec", "run.cfg"]
code = subprocess.run(command, capture_output=True).returncode
import glob
found = [log] if os.path.exists(log) else sorted(glob.glob(os.path.join(work, "*flight*.txt")), key=os.path.getmtime)[-1:]  # quiet_run may rename the log
lines = [l.strip() for l in open(found[0], errors="replace")] if found else []
for l in lines:
    if l.startswith("DFFLIGHT") or l.startswith("Script error"):
        print(l)
result = next((l for l in lines if l.startswith("DFFLIGHT result")), None)
print(f"exit {code}")
if result is None:
    sys.exit(2)
fields = result.split()
values = {fields[i]: int(fields[i + 1]) for i in range(2, len(fields) - 1, 2)}
sys.exit(0 if values["sky"] == 0 and values["clear"] > 0 else 1)
