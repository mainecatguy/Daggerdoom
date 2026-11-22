"""Walk the real player along a converted city's test routes, using forward input and the engine's own collision.

Usage: python tools/dungeon_converter/city_walk.py <dir with daggerfall_city.wad> [--routes north,east,south,west] [--seconds 30]
Each route is one quiet launch. Output is derived from game data, so keep it outside the repo.
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
class DFWalk : EventHandler
{
	Array<double> xs, ys;
	int next, best, stuck, jumps;
	double bestDistance, topSpeed, lowest;
	Vector3 last;
	bool started, finished;

	override void WorldLoaded(WorldEvent e)
	{
		String body = Wads.ReadLump(Wads.CheckNumForName("DFROUTE", Wads.ns_global));
		Array<String> rows;
		body.Split(rows, "\\n", TOK_SKIPEMPTY);
		for (int i = 0; i < rows.Size(); i++)
		{
			Array<String> f;
			rows[i].Split(f, " ");
			xs.Push(f[0].ToDouble());
			ys.Push(f[1].ToDouble());
		}
		bestDistance = 1e9;
		lowest = 1e9;
	}

	override void WorldTick()
	{
		let mo = players[0].mo;
		if (!mo || finished) return;
		if (!started)
		{
			started = true;
			int resume = Wads.ReadLump(Wads.CheckNumForName("DFRESUME", Wads.ns_global)).ToInt();
			if (resume > 0) { next = resume; mo.SetOrigin((xs[resume], ys[resume], mo.floorz), false); mo.vel = (0, 0, 0); }
			last = mo.pos;
		}
		double moved = (mo.pos.xy - last.xy).Length();
		if (moved > 64) jumps++;
		topSpeed = max(topSpeed, moved);
		lowest = min(lowest, mo.pos.z - mo.floorz);
		last = mo.pos;
		Vector2 to = (xs[next] - mo.pos.x, ys[next] - mo.pos.y);
		double distance = to.Length();
		if (distance < 48 && next + 1 < xs.Size()) { next++; bestDistance = 1e9; stuck = 0; return; }
		if (distance < 24 && next + 1 == xs.Size())
		{
			finished = true;
			Console.Printf("DFWALK done waypoints %d/%d tics %d at %.0f %.0f z %.1f jumps %d topspeed %.1f belowfloor %.2f", next + 1, xs.Size(), level.maptime, mo.pos.x, mo.pos.y, mo.pos.z, jumps, topSpeed, lowest);
			return;
		}
		if (distance < bestDistance - 1) { bestDistance = distance; stuck = 0; }
		else if (++stuck > 175)
		{
			finished = true;
			Console.Printf("DFWALK stuck waypoints %d/%d tics %d at %.0f %.0f z %.1f target %.0f %.0f jumps %d", next, xs.Size(), level.maptime, mo.pos.x, mo.pos.y, mo.pos.z, xs[next], ys[next], jumps);
			return;
		}
		mo.angle = atan2(to.y, to.x);
		mo.pitch = 0;
		if (level.maptime % 175 == 0)
			Console.Printf("DFWALK at %.0f %.0f z %.1f waypoint %d/%d", mo.pos.x, mo.pos.y, mo.pos.z, next, xs.Size());
	}
}
"""

parser = argparse.ArgumentParser()
parser.add_argument("dir")
parser.add_argument("--routes", default="north,east,south,west")
parser.add_argument("--seconds", type=int, default=30)
parser.add_argument("--slug", default="daggerfall_city")
parser.add_argument("--resume", default="", help="start routes at a waypoint, as name=index,name=index, to keep each launch short")
args = parser.parse_args()
resume = {k: v for k, v in (pair.split("=") for pair in args.resume.split(",") if pair)}
base = os.path.abspath(args.dir)
work = os.path.join(base, "walk")
harness = os.path.join(work, "harness")
os.makedirs(harness, exist_ok=True)

routes = {}
for line in open(os.path.join(base, args.slug + ".routes.txt")):
    if line.startswith("route"):
        current = line.split()[1]
        routes[current] = []
    else:
        routes[current].append(line.strip())

with open(os.path.join(harness, "zscript.zs"), "w", newline="\n") as f:
    f.write(ZSCRIPT)
with open(os.path.join(harness, "MAPINFO"), "w", newline="\n") as f:
    f.write('GameInfo\n{\n\tAddEventHandlers = "DFWalk"\n}\n')
with open(os.path.join(work, "doom.ini"), "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
tics = args.seconds * 35
with open(os.path.join(work, "run.cfg"), "w", newline="\n") as f:
    f.write(f'alias dfgo "+forward; +speed; wait {tics}; -forward; -speed; quit"\nwait 35; dfgo\n')

failed = False
for name in args.routes.split(","):
    with open(os.path.join(harness, "DFROUTE"), "w", newline="\n") as f:
        f.write("\n".join(routes[name]) + "\n")
    with open(os.path.join(harness, "DFRESUME"), "w", newline="\n") as f:
        f.write(resume.get(name, "0") + "\n")
    log =os.path.join(work, f"log-{name}.txt")
    if os.path.exists(log):
        os.remove(log)
    command = [sys.executable, QUIET, "--timeout", str(args.seconds + 15), "--cwd", work, "--", UZDOOM,
               "-iwad", IWAD, "-file", os.path.join(base, args.slug + ".wad"), os.path.join(base, args.slug + "_mesh.pk3"), harness,
               "-config", os.path.join(work, "doom.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
               "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+logfile", name, "+map", "MAP01", "+exec", "run.cfg"]
    code = subprocess.run(command, capture_output=True).returncode
    lines = [l.strip() for l in open(log, errors="replace")] if os.path.exists(log) else []
    walk = [l for l in lines if l.startswith("DFWALK")]
    result = next((l for l in walk if " done " in l or " stuck " in l), walk[-1] if walk else "no walk output")
    print(f"{name}: exit {code}, {len(routes[name])} waypoints: {result}")
    failed = failed or " done " not in result
sys.exit(1 if failed else 0)
