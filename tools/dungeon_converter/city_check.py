"""Load-test a converted city in UZDoom through quiet_run, take screenshots, and record frame times.

Usage: python tools/dungeon_converter/city_check.py <dir with daggerfall_city.wad> [--views "x,y,z,yaw,pitch;..."] [--timeout 30]
Writes check/<n>.png and check/console.txt in that directory. Output is derived from game data, so keep it outside the repo.
"""
import argparse
import os
import re
import subprocess
import sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DEFAULT_VIEWS = "S,S,41,90,0;S,S,41,0,0;S,S,41,180,0;S,S,41,270,0;0,-3000,1400,90,25;0,-11500,500,90,5;-11000,-11000,1200,45,10"

ZSCRIPT = """version "4.10"
class DFCheck : EventHandler
{
	Vector3 pos; double yaw, tilt; bool hold;
	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name != "dfview") return;
		static const double data[] = { %s };
		int at = e.Args[0] * 5;
		pos = (data[at], data[at + 1], data[at + 2]); yaw = data[at + 3]; tilt = data[at + 4]; hold = true;
		Place();
	}
	void Place()
	{
		let mo = players[0].mo;
		mo.bNOGRAVITY = true;
		mo.SetOrigin((pos.x, pos.y, pos.z - 41), false);
		mo.vel = (0, 0, 0);
		mo.angle = yaw; mo.pitch = tilt;
	}
	override void WorldTick() { if (hold) Place(); }
	override void WorldLoaded(WorldEvent e)
	{
		let mo = players[0].mo;
		Console.Printf("DFSTART %%.1f %%.1f %%.1f floor %%.1f radius %%.1f sectors %%d lines %%d", mo.pos.x, mo.pos.y, mo.pos.z, mo.floorz, mo.radius, level.sectors.Size(), level.lines.Size());
	}
}
"""

parser = argparse.ArgumentParser()
parser.add_argument("dir")
parser.add_argument("--views", default=DEFAULT_VIEWS)
parser.add_argument("--timeout", type=int, default=30)
parser.add_argument("--slug", default="daggerfall_city")
parser.add_argument("--collider", action="store_true", help="capture the Doom collider view instead of the mesh")
parser.add_argument("--size", default="1280x720", help="3D render size")
args = parser.parse_args()
render_width, render_height = args.size.split("x")
base = os.path.abspath(args.dir)
check = os.path.join(base, "check")
harness = os.path.join(check, "harness")
os.makedirs(harness, exist_ok=True)

stats = open(os.path.join(base, args.slug + ".stats.txt")).read()
sx, sy = re.search(r"start (-?[\d.]+),(-?[\d.]+)", stats).groups()
views = [v.split(",") for v in args.views.split(";")]
views = [[sx if v[0] == "S" else v[0], sy if v[1] == "S" else v[1], v[2], v[3], v[4]] for v in views]
with open(os.path.join(harness, "zscript.zs"), "w", newline="\n") as f:
    f.write(ZSCRIPT % ", ".join(str(float(n)) for v in views for n in v))
with open(os.path.join(harness, "MAPINFO"), "w", newline="\n") as f:
    f.write('GameInfo\n{\n\tAddEventHandlers = "DFCheck"\n}\n')

with open(os.path.join(check, "run.cfg"), "w", newline="\n") as f:
    for i in range(len(views)):
        shot = os.path.join(check, f"{i}.png").replace("\\", "/")
        f.write(f'alias dfstep{i} "netevent dfview {i}; wait 8; screenshot \\"{shot}\\"; wait 4; dfstep{i + 1}"\n')
    f.write(f'alias dfstep{len(views)} "netevent dfview 0; wait 4; dfmesh_bench 1; wait 140; dfmesh_bench 0; dfmesh_status; quit"\n')
    f.write('wait 70; dfstep0\n')
with open(os.path.join(check, "doom.ini"), "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth=1280\nvid_defheight=720\nwin_w=1280\nwin_h=720\nvid_scalefactor=1\n")

console = os.path.join(check, "console.txt")
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", check, "--", UZDOOM,
           "-iwad", IWAD, "-file", os.path.join(base, args.slug + ".wad"), os.path.join(base, args.slug + "_mesh.pk3"), harness,
           "-config", os.path.join(check, "doom.ini"), "-stdout", "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
           "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+dfmesh_view", "0" if args.collider else "1",
           # A minimized window is 320x200. The custom scale mode renders the scene at a useful size anyway.
           "+vid_scalemode", "5", "+vid_scale_customwidth", render_width, "+vid_scale_customheight", render_height, "+screenblocks", "12", "+crosshair", "0",
           "+screenshot_type", "png", "+show_messages", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
           "+vid_lowerinbackground", "0", "+logfile", "game", "+map", "MAP01", "+exec", "run.cfg"]
game_log = os.path.join(check, "log-game.txt")  # UZDoom names the log file log-<name>.txt
if os.path.exists(game_log):
    os.remove(game_log)
with open(console, "w") as log:
    code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
text = open(game_log, errors="replace").read() if os.path.exists(game_log) else open(console, errors="replace").read()
print("exit code", code)
for line in text.splitlines():
    if re.search(r"DFMesh:|DFSTART|DFCITY|DFBENCH|DFSTATUS|error|Error|FATAL|Script warning|missing texture", line):
        print(line[:220])
sys.exit(code)
