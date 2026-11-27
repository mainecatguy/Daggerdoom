"""Screenshots of the distant terrain view (hw_ddhorizon.cpp) on the overworld and on a location exterior map.

usage: horizon_shots.py NAME [--map DDOVER01|DDT07154] [--exe uzdoom.exe] [--data DIR] [--pitch 0] [--drla]

Overworld: the camera stands at a world point exactly 3072 units east of the window centre, the treadmill's shift line.
It takes four views (east, north, west, south), walks east until the window shifts, comes back to the same world point
(the window stays shifted, since the point is exactly on the line), and takes the four views again. Then it turns the
distant view off (dd_horizon 0) for a before/after view. The two shifted sets are compared pixel by pixel: the horizon
should not move when the window does.
Location map: the four views from the map's start spot, with and without the distant view.
Game data comes from a review folder's data directory (read only; its town cache is copied). Output stays outside the repo.
"""
import argparse, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "overworld"))
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
WORK = r"D:\dev\DoomDaggerfall-build\distantlod-tests"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")

ZS = """version "4.14"
class HorizonShot : EventHandler
{
	static const double YAWS[] = { 0, 90, 180, 270 };
	int view, phase, ox, oy;
	bool have;
	Vector2 start;

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "hzview") view = e.Args[0];
		else if (e.Name == "hzphase") phase = e.Args[0];
	}

	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p || level.maptime < 5) return;
		bool over = level.MapName == "DDOVER01";
		int cx = over ? CVar.FindCVar("dd_tm_originx").GetInt() : 0, cy = over ? CVar.FindCVar("dd_tm_originy").GetInt() : 0;
		if (!have) { have = true; ox = cx; oy = cy; start = p.pos.xy; }
		Vector2 at = start;
		if (@ATX@ != 0) { at = (@ATX@, @ATY@); p.angle = @ATYAW@; }
		if (over)	// world tile (ox + 80, oy + 64): 3072 units east of the first window's centre
		{
			at = ((ox + 80 - cx) * 192.0 - 12288, (oy + 64 - cy) * 192.0 - 12288);
			if (phase == 1) at.x += 2000;
		}
		p.SetOrigin((at.x, at.y, p.GetZAt(at.x, at.y, 0, GZF_ABSOLUTEPOS)), false);
		p.vel = (0, 0, 0);
		if (@ATX@ == 0) p.angle = YAWS[view];
		p.pitch = @PITCH@;
		if (level.maptime % 35 == 5) Console.Printf("HZPOS map=%s phase=%d view=%d local=%.1f,%.1f,%.1f origin=%d,%d", level.MapName, phase, view, p.pos.x, p.pos.y, p.pos.z, cx, cy);
	}
}
"""


def compare(a, b):
    """Mean absolute difference (0-255) and the share of pixels off by more than 32, over the upper 2/3 of the view."""
    from PIL import Image, ImageChops
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    box = (0, 0, ia.width, ia.height * 2 // 3)
    d = ImageChops.difference(ia.crop(box), ib.crop(box)).convert("L")
    hist = d.histogram()
    n = sum(hist)
    return f"mean {sum(i * c for i, c in enumerate(hist)) / n:.2f}/255, off by >32: {100 * sum(hist[33:]) / n:.2f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--map", default="DDOVER01")
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-distantlod\Release\uzdoom.exe")
    ap.add_argument("--data", default=r"D:\dev\DoomDaggerfall-loop\review\arrival-spawn\data")
    ap.add_argument("--pitch", default="0")
    ap.add_argument("--at", help="X,Y,YAW: a fixed local spot and facing on a location map (all four shots use it)")
    ap.add_argument("--drla", action="store_true")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    os.makedirs(WORK, exist_ok=True)
    cache = os.path.join(WORK, "cache")
    if not os.path.isdir(cache):
        shutil.copytree(os.path.join(args.data, "cache"), cache)
    at = [v + ".0" for v in args.at.split(",")] if args.at else ["0.0", "0.0", "0.0"]
    harness = os.path.join(WORK, "horizon_shot.pk3")
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", ZS.replace("@PITCH@", args.pitch + ".0").replace("@ATX@", at[0]).replace("@ATY@", at[1]).replace("@ATYAW@", at[2]))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "HorizonShot" }\n')
    ini = os.path.join(WORK, f"{args.name}.ini")
    with open(ini, "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth=1280\nvid_defheight=720\nwin_w=1280\nwin_h=720\nvid_scalefactor=1\n")

    over = args.map == "DDOVER01"
    shots = []
    lines = []

    def views(tag):
        for i in range(4):
            shot = os.path.join(WORK, f"{args.name}_{tag}_{i}.png").replace("\\", "/")
            shots.append(shot)
            lines.append(f'netevent hzview {i}; wait 25; screenshot \\"{shot}\\"; wait 4')

    views("a")
    if over:
        lines.append("netevent hzphase 1; wait 70; netevent hzphase 2; wait 40")
        views("b")
    lines.append("dd_horizon 0; wait 4")
    views("off")
    lines.append("dd_horizon 1; quit")
    cfg = os.path.join(WORK, f"{args.name}.cfg")
    with open(cfg, "w", newline="\n") as f:
        for i, l in enumerate(lines):
            f.write(f'alias hzstep{i} "{l}; hzstep{i + 1}"\n')
        f.write(f'alias hzstep{len(lines)} "quit"\nwait 140; hzstep0\n')

    log = os.path.join(WORK, f"log-{args.name}.txt")
    if os.path.exists(log):
        os.remove(log)
    files = ([os.path.join(MODS, m) for m in DRLA] if args.drla else []) + [os.path.join(args.data, "ddruntime.pk3"), os.path.join(args.data, "overworld.pk3"), harness]
    command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", WORK, "--", args.exe, "-iwad", IWAD, "-file", *files,
               "-config", ini, "-noautoload", "-nomonsters", "-skill", "3", "-width", "1280", "-height", "720",
               "-ddtowncache", cache, "-ddconverter", os.path.join(args.data, "converter", "DungeonConverter.exe"), "-ddarena2", ARENA2,
               "+vid_fullscreen", "0", "+wipetype", "0", "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720",
               "+screenblocks", "12", "+crosshair", "0", "+r_drawplayersprites", "0", "+screenshot_type", "png", "+show_messages", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+logfile", args.name, "+map", args.map, "+exec", cfg]
    code = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).returncode
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    print("exit", code)
    for l in body.splitlines():
        if "DDHORIZON" in l or "DDTM active" in l or any(k in l for k in FATAL):
            print(" ", l[:220])
    pos = [l for l in body.splitlines() if "HZPOS" in l]
    for l in pos[-3:]:
        print(" ", l)
    missing = [s for s in shots if not os.path.exists(s)]
    print("shots", len(shots) - len(missing), "of", len(shots), "in", WORK)
    if over and not missing:
        for i in range(4):
            print(f"view {i}: shifted vs unshifted window, same world point: {compare(shots[i], shots[4 + i])}")


if __name__ == "__main__":
    main()
