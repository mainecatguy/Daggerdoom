"""Door and gate access check for a converted exterior, in UZDoom alone: does the collision map still let the player reach
and use every building door and dungeon entrance, and walk through every gate frame?

Usage: python tools/dungeon_converter/exterior_doors.py <dir> --slug <slug> [--map DDT09183]
The dir is the --out of a runtime conversion: DungeonConverter --group <id> --ddt <file> --out <dir> --fidelity, which
keeps <slug>.wad, <slug>.doors.txt and <slug>.gates.txt there.

<slug>.doors.txt is written by the converter with --fidelity (the DDDOORS lines: kind target index x y z nx ny). Gate
leaves come from DFGATES in the mesh package (only the data is read; the package is not loaded, because its script no
longer compiles against the current engine and the gate leaves are door objects that do not depend on the map).
For each door, on either side of the door plane: the player (radius 10.5) must fit 96 units out, walk with the engine's
TryMove to 20 units from the door, and a Use-height trace from there must reach the door before any wall.
For each gate: the player must walk the engine's TryMove from 96 units on one side of the frame to 96 on the other.
Run it on the maps before and after a collision change and compare. Output is derived from game data; keep it outside
the repo.
"""
import argparse
import glob
import os
import subprocess
import sys
import zipfile

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

ZSCRIPT = """version "4.10"
class DFDoorCheck : EventHandler
{
	bool Walk(PlayerPawn mo, Vector2 from, Vector2 to, double z)
	{
		mo.SetOrigin((from, z), false);
		mo.SetZ(mo.floorz);
		mo.vel = (0, 0, 0);
		if (!mo.TestMobjLocation()) return false;
		Vector2 d = to - from;
		int steps = int(d.Length() / 4);
		for (int s = 1; s <= steps; s++)
		{
			mo.SetZ(mo.floorz);
			if (!mo.TryMove(from + d * (double(s) / steps), 1)) return false;
		}
		return true;
	}
	bool Door(PlayerPawn mo, Vector2 at, double z, Vector2 n)
	{
		if (!Walk(mo, at + n * 96, at + n * 20, z)) return false;
		FLineTraceData t;
		Vector2 to = at - mo.pos.xy;
		mo.LineTrace(atan2(to.y, to.x), 64, 0, TRF_THRUACTORS, 41, data: t);
		return t.HitType != TRACE_HitWall || t.Distance >= to.Length() - 6;
	}
	override void WorldTick()
	{
		if (level.maptime != 5) return;
		let mo = players[0].mo;
		mo.A_SetSize(10.5, mo.height);
		mo.bNOGRAVITY = true;
		Array<String> rows;
		Wads.ReadLump(Wads.CheckNumForName("DFDOORS", Wads.ns_global)).Split(rows, "\\n", TOK_SKIPEMPTY);
		int doors = 0, doorsOk = 0, gates = 0, gatesOk = 0;
		String failed = "";
		for (int i = 0; i < rows.Size(); i++)
		{
			Array<String> f;
			rows[i].Split(f, " ");
			if (f[0] == "gate")
			{
				Vector2 c = (f[1].ToDouble(), f[2].ToDouble()), n = (f[4].ToDouble(), f[5].ToDouble());
				double z = f[3].ToDouble() + 8;
				gates++;
				if (Walk(mo, c - n * 96, c + n * 96, z) || Walk(mo, c + n * 96, c - n * 96, z)) gatesOk++; else failed.AppendFormat(" gate%d", i);
				continue;
			}
			Vector2 at = (f[3].ToDouble(), f[4].ToDouble()), n = (f[6].ToDouble(), f[7].ToDouble());
			double z = f[5].ToDouble();
			doors++;
			if (Door(mo, at, z, n) || Door(mo, at, z, -n)) doorsOk++; else failed.AppendFormat(" door%d", i);
		}
		Console.Printf("DFDOORS result doors %d ok %d gates %d ok %d failed%s", doors, doorsOk, gates, gatesOk, failed);
	}
}
"""

parser = argparse.ArgumentParser()
parser.add_argument("dir")
parser.add_argument("--slug", required=True)
parser.add_argument("--timeout", type=int, default=40)
parser.add_argument("--map", default="MAP01")
args = parser.parse_args()
base = os.path.abspath(args.dir)
work = os.path.join(base, "doors")
harness = os.path.join(work, "harness")
os.makedirs(harness, exist_ok=True)
rows = [l.strip() for l in open(os.path.join(base, args.slug + ".doors.txt")) if l.strip()]
gate_file = os.path.join(base, args.slug + ".gates.txt")  # written beside the map by a --group --fidelity conversion
gate_text = open(gate_file).read() if os.path.exists(gate_file) else zipfile.ZipFile(os.path.join(base, args.slug + "_mesh.pk3")).read("DFGATES").decode()
gates = [l.split() for l in gate_text.splitlines() if l.strip()]
for a, b in zip(gates[0::2], gates[1::2]):  # slot pivotX pivotY pivotZ ...; the two leaves of a gate are consecutive
    ax, ay, bx, by = float(a[1]), float(a[2]), float(b[1]), float(b[2])
    dx, dy = bx - ax, by - ay
    length = (dx * dx + dy * dy) ** 0.5 or 1
    rows.append(f"gate {(ax + bx) / 2:.2f} {(ay + by) / 2:.2f} {float(a[3]):.2f} {-dy / length:.4f} {dx / length:.4f}")
with open(os.path.join(harness, "DFDOORS"), "w", newline="\n") as f:
    f.write("\n".join(rows) + "\n")
with open(os.path.join(harness, "zscript.zs"), "w", newline="\n") as f:
    f.write(ZSCRIPT)
with open(os.path.join(harness, "MAPINFO"), "w", newline="\n") as f:
    f.write('GameInfo\n{\n\tAddEventHandlers = "DFDoorCheck"\n}\n')
with open(os.path.join(work, "doom.ini"), "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
with open(os.path.join(work, "run.cfg"), "w", newline="\n") as f:
    f.write("wait 40; quit\n")
for old in glob.glob(os.path.join(work, "*doors*.txt")):
    os.remove(old)
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", work, "--", UZDOOM,
           "-iwad", IWAD, "-file", os.path.join(base, args.slug + ".wad"), harness,
           "-config", os.path.join(work, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
           "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
           "+logfile", "doors.log", "+map", args.map, "+exec", "run.cfg"]
code = subprocess.run(command, capture_output=True).returncode
found = sorted(glob.glob(os.path.join(work, "*doors*.txt")), key=os.path.getmtime)[-1:]
lines = [l.strip() for l in open(found[0], errors="replace")] if found else []
for l in lines:
    if l.startswith("DFDOORS") or l.startswith("Script error"):
        print(l)
print(f"exit {code}")
sys.exit(0 if any(l.startswith("DFDOORS result") for l in lines) else 2)
