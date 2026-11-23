"""Check converted city roofs in the real engine.

Usage: python tools/dungeon_converter/roof_check.py <dir with <slug>.wad> --slug daggerfall_city [--drops 40]

Compares the engine's floor with the mesh height at every roof sample, walks the player's collision box between
samples on each building, and drops the real player onto a spread of roofs. Output is derived from game data, so
keep it outside the repo.
"""
import argparse
import os
import re
import subprocess
import sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

ZSCRIPT = """version "4.10"
class DFRoofCheck : EventHandler
{
	Array<int> owner;
	Array<double> xs, ys, zs;
	Array<int> drops;
	int phase, at, wait;
	double startZ, landedOff, landedSlide;
	Vector2 uphill;

	override void WorldLoaded(WorldEvent e)
	{
		String body = Wads.ReadLump(Wads.CheckNumForName("DFROOFS", Wads.ns_global));
		Array<String> rows;
		body.Split(rows, "\\n", TOK_SKIPEMPTY);
		for (int i = 0; i < rows.Size(); i++)
		{
			Array<String> f;
			rows[i].Split(f, " ");
			owner.Push(f[0].ToInt());
			xs.Push(f[1].ToDouble());
			ys.Push(f[2].ToDouble());
			zs.Push(f[3].ToDouble());
		}
		// An even spread of roofs from each pitch: flat, up to 30, 30 to 45, and over 45 degrees.
		int each = %d / 4;
		for (int bucket = 0; bucket < 4; bucket++)
		{
			Array<int> members;
			for (int i = 0; i < xs.Size(); i++)
				if (Bucket(level.PointInSector((xs[i], ys[i])).floorplane.Normal.z) == bucket) members.Push(i);
			int step = max(1, members.Size() / max(1, each));
			for (int i = step / 2, n = 0; i < members.Size() && n < each; i += step, n++) drops.Push(members[i]);
		}
	}

	static int Bucket(double nz) { return nz >= 0.9999 ? 0 : nz >= cos(30) ? 1 : nz >= cos(45) ? 2 : 3; }

	void Surfaces()
	{
		int within1 = 0, within4 = 0, sloped = 0, unstandable = 0;
		double worst = 0, total = 0, steepest = 1;
		for (int i = 0; i < xs.Size(); i++)
		{
			Sector s = level.PointInSector((xs[i], ys[i]));
			double z = s.floorplane.ZatPoint((xs[i], ys[i])), off = abs(z - zs[i]), nz = s.floorplane.Normal.z;
			total += off;
			worst = max(worst, off);
			if (off <= 1) within1++;
			if (off <= 4) within4++;
			if (nz < 0.9999) sloped++;
			if (nz < 0.7) unstandable++;
			steepest = min(steepest, nz);
		}
		Console.Printf("DFROOF surface samples %%d within1 %%d within4 %%d mean %%.2f worst %%.1f sloped %%d steeperthan45 %%d steepestdeg %%.1f", xs.Size(), within1, within4, total / max(1, xs.Size()), worst, sloped, unstandable, acos(steepest));
	}

	void Walks(PlayerPawn mo)
	{
		int pairs = 0, crossed = 0, fell = 0;
		for (int i = 0; i + 1 < xs.Size(); i++)
		{
			if (owner[i] != owner[i + 1]) continue;
			pairs++;
			mo.SetOrigin((xs[i], ys[i], zs[i] + 1), false);
			mo.FindFloorCeiling();
			mo.SetZ(mo.floorz);
			Vector2 to = (xs[i + 1], ys[i + 1]) - mo.pos.xy;
			int steps = int(ceil(to.Length() / 8));
			bool ok = true;
			double low = 1e9;
			for (int n = 1; n <= steps && ok; n++)
			{
				Vector2 p = (xs[i], ys[i]) + to * (double(n) / steps);
				ok = mo.TryMove(p, true);
				if (ok) { mo.SetZ(mo.floorz); low = min(low, mo.pos.z); }
			}
			if (ok) crossed++;
			if (ok && low < min(zs[i], zs[i + 1]) - 32) fell++;
		}
		Console.Printf("DFROOF walks pairs %%d crossed %%d crossedbutdropped %%d", pairs, crossed, fell);
	}

	override void WorldTick()
	{
		let mo = players[0].mo;
		if (!mo || phase == 3) return;
		if (phase == 0)
		{
			Surfaces();
			Walks(mo);
			phase = 1;
			Place(mo);
			return;
		}
		++wait;
		if (wait < 13) return;
		Sector s = level.PointInSector((xs[drops[at]], ys[drops[at]]));
		if (wait == 13)
		{
			// Landed: measure against the surface under the player, then run straight uphill at running speed.
			landedOff = mo.pos.z - mo.floorz;
			landedSlide = (mo.pos.xy - (xs[drops[at]], ys[drops[at]])).Length();
			startZ = mo.pos.z;
			uphill = (-s.floorplane.Normal.x, -s.floorplane.Normal.y);
			if (s.floorplane.Normal.z < 0) uphill = -uphill;
			if (uphill.Length() > 0.001) uphill = uphill.Unit();
		}
		if (wait < 33) { mo.vel.xy = uphill * 12; return; }
		Console.Printf("DFDROP owner %%d bucket %%d deg %%.1f off %%.1f slid %%.1f rise %%.1f", owner[drops[at]], Bucket(s.floorplane.Normal.z), acos(s.floorplane.Normal.z), landedOff, landedSlide, mo.pos.z - startZ);
		if (++at >= drops.Size()) { phase = 3; Console.Printf("DFROOF done"); return; }
		Place(mo);
	}

	void Place(PlayerPawn mo)
	{
		wait = 0;
		mo.SetOrigin((xs[drops[at]], ys[drops[at]], zs[drops[at]] + 24), false);
		mo.vel = (0, 0, 0);
	}
}
"""

parser = argparse.ArgumentParser()
parser.add_argument("dir")
parser.add_argument("--slug", default="daggerfall_city")
parser.add_argument("--drops", type=int, default=40)
parser.add_argument("--map", default="MAP01")
args = parser.parse_args()
base = os.path.abspath(args.dir)
work = os.path.join(base, "roofcheck")
harness = os.path.join(work, "harness")
os.makedirs(harness, exist_ok=True)
with open(os.path.join(base, args.slug + ".roofs.txt")) as source, open(os.path.join(harness, "DFROOFS"), "w", newline="\n") as out:
    out.write(source.read())
with open(os.path.join(harness, "zscript.zs"), "w", newline="\n") as f:
    f.write(ZSCRIPT % args.drops)
with open(os.path.join(harness, "MAPINFO"), "w", newline="\n") as f:
    f.write('GameInfo\n{\n\tAddEventHandlers = "DFRoofCheck"\n}\n')
with open(os.path.join(work, "doom.ini"), "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
with open(os.path.join(work, "run.cfg"), "w", newline="\n") as f:
    f.write(f"wait {args.drops * 33 + 90}; quit\n")
log = os.path.join(work, "log-roof.txt")
if os.path.exists(log):
    os.remove(log)
command = [sys.executable, QUIET, "--timeout", "30", "--cwd", work, "--", UZDOOM, "-iwad", IWAD,
           "-file", os.path.join(base, args.slug + ".wad"), os.path.join(base, args.slug + "_mesh.pk3"), harness,
           "-config", os.path.join(work, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
           "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
           "+logfile", "roof", "+map", args.map, "+exec", "run.cfg"]
code = subprocess.run(command, capture_output=True).returncode
lines = [l.strip() for l in open(log, errors="replace")] if os.path.exists(log) else []
print("exit", code)
for line in lines:
    if line.startswith("DFROOF") or re.search(r"FATAL|Script error|VM execution", line):
        print(line[:220])
drops = []
for l in lines:
    m = re.match(r"DFDROP owner \d+ bucket (\d) deg ([\d.]+) off (-?[\d.]+) slid ([\d.]+) rise (-?[\d.]+)", l)
    if m:
        drops.append((int(m[1]), float(m[2]), float(m[3]), float(m[4]), float(m[5])))
names = ["flat", "up to 30 deg", "30 to 45 deg", "over 45 deg"]
for bucket, name in enumerate(names):
    group = [d for d in drops if d[0] == bucket]
    if group:
        landed = sum(1 for d in group if abs(d[2]) <= 1)
        climbed = sum(1 for d in group if d[4] >= 16)
        print(f"{name}: {len(group)} drops, on the surface {landed}, slide after landing max {max(d[3] for d in group):.1f}, climbed 16+ units running uphill {climbed}, rise {min(d[4] for d in group):.1f} to {max(d[4] for d in group):.1f}")
sys.exit(0 if drops and any("DFROOF done" in l for l in lines) else 1)
