"""Takes the same screenshots from the same world point on the overworld and on the town map, then compares them.

Usage: stitch_shot.py NAME --world-point WX,WY [--yaws 180,135] [--pitch 0] [--start-tile X,Y]
WX and WY are Daggerfall world units. Output stays outside the repository.
"""
import argparse, os, struct, subprocess, sys, zipfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-stitch\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORK = r"D:\dev\DoomDaggerfall-build\stitch-tests\shots"

ZS = """version "4.14"
class StitchShot : EventHandler
{
	const S = 0.75;
	double townX, townY;
	int view;
	static const double YAWS[] = { @YAWS@ };

	override void NetworkProcess(ConsoleEvent e) { if (e.Name == "stitchview") view = e.Args[0]; }

	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p) return;
		if (townX == 0)
		{
			Array<String> rows;
			Wads.ReadLump(Wads.CheckNumForName("DDTOWN", Wads.ns_global)).Split(rows, "\\n", TOK_SKIPEMPTY);
			for (int i = 0; i < rows.Size(); i++)
			{
				Array<String> f;
				rows[i].Split(f, " ", TOK_SKIPEMPTY);
				if (f.Size() >= 3 && f[0] == "origin") { townX = f[1].ToDouble(); townY = f[2].ToDouble(); }
			}
		}
		double x, y;
		if (CVar.FindCVar("dd_tm_intown").GetInt()) { x = (@WX@ - townX) * S; y = (@WY@ - townY) * S; }
		else { x = @WX@ * S - CVar.FindCVar("dd_tm_originx").GetInt() * 192.0 - 12288; y = @WY@ * S - CVar.FindCVar("dd_tm_originy").GetInt() * 192.0 - 12288; }
		p.SetOrigin((x, y, p.GetZAt(x, y, 0, GZF_ABSOLUTEPOS)), false);
		p.vel = (0, 0, 0);
		p.angle = YAWS[view];
		p.pitch = @PITCH@;
		if (level.maptime % 35 == 5) Console.Printf("SHOTPOS map=%s z=%.2f floor=%.2f", level.MapName, p.pos.z, p.floorz);
	}
}
"""

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--world-point", required=True)
ap.add_argument("--yaws", default="180,135")
ap.add_argument("--pitch", default="0")
ap.add_argument("--start-tile", default="26560,36608")
ap.add_argument("--town", default=r"D:\dev\DoomDaggerfall-build\stitch-data\town")
ap.add_argument("--slug", default="daggerfall_city")
ap.add_argument("--world", default=r"D:\dev\DoomDaggerfall-build\stitch-data")
ap.add_argument("--town-map", default="DDTOWN01")
args = ap.parse_args()

os.makedirs(WORK, exist_ok=True)
wx, wy = args.world_point.split(",")
yaws = [y.strip() for y in args.yaws.split(",")]
mesh = os.path.join(args.town, args.slug + "_mesh.pk3")
over = os.path.join(WORK, args.name + "_over.pk3")
subprocess.check_call([sys.executable, os.path.join(HERE, "gen_overworld.py"), "--out", over, "--world-dir", args.world, "--ground-from", mesh,
                       "--start-tile", args.start_tile, "--packchance", "0"], stdout=subprocess.DEVNULL)
harness = os.path.join(WORK, args.name + "_shot.pk3")
text = ZS.replace("@YAWS@", ", ".join(y + ".0" for y in yaws)).replace("@WX@", wx + ".0").replace("@WY@", wy + ".0").replace("@PITCH@", args.pitch + ".0")
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "StitchShot" }\n')

ini = os.path.join(WORK, "shot.ini")
with open(ini, "w", newline="\n") as f:
    f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth=1280\nvid_defheight=720\nwin_w=1280\nwin_h=720\nvid_scalefactor=1\n")

results = {}
for label, game_map in (("over", "DDOVER01"), ("town", args.town_map)):
    cfg = os.path.join(WORK, f"{args.name}_{label}.cfg")
    with open(cfg, "w", newline="\n") as f:
        for i in range(len(yaws)):
            shot = os.path.join(WORK, f"{args.name}_{label}_{i}.png").replace("\\", "/")
            f.write(f'alias shotstep{i} "netevent stitchview {i}; wait 12; screenshot \\"{shot}\\"; wait 6; shotstep{i + 1}"\n')
        f.write(f'alias shotstep{len(yaws)} "quit"\nwait 90; shotstep0\n')
    log = os.path.join(WORK, f"log-{args.name}_{label}.txt")
    if os.path.exists(log):
        os.remove(log)
    command = [sys.executable, QUIET, "--timeout", "30", "--cwd", WORK, "--", EXE, "-iwad", IWAD, "-file", over, os.path.join(args.town, args.slug + ".wad"), mesh, harness,
               "-config", ini, "-noactivate", "-nosound", "-noautoload", "-nomonsters", "-skill", "3", "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+wipetype", "0",
               "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720", "+screenblocks", "12", "+crosshair", "0", "+r_drawplayersprites", "0",
               "+screenshot_type", "png", "+show_messages", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+logfile", f"{args.name}_{label}", "+map", game_map, "+exec", cfg]
    code = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).returncode
    body = open(log, errors="replace").read() if os.path.exists(log) else ""
    pos = [l for l in body.splitlines() if "SHOTPOS" in l]
    print(label, "exit", code, pos[-1] if pos else "no position", "| errors:", [l[:100] for l in body.splitlines() if "rror" in l or "FATAL" in l][:3])

def read_png(path):
    """Minimal reader for the engine's 8-bit, non-interlaced RGB and RGBA screenshots."""
    d = open(path, "rb").read()
    pos, idat, width, height, kind = 8, b"", 0, 0, 2
    while pos < len(d):
        size = struct.unpack(">I", d[pos:pos + 4])[0]
        tag = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + size]
        if tag == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
            kind = body[9]
        elif tag == b"IDAT":
            idat += body
        pos += 12 + size
    bpp = {2: 3, 6: 4}[kind]
    raw = zlib.decompress(idat)
    stride = width * bpp
    prev = bytearray(stride)
    rows = []
    at = 0
    for _ in range(height):
        f = raw[at]
        row = bytearray(raw[at + 1:at + 1 + stride])
        at += stride + 1
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1: row[i] = (row[i] + a) & 255
            elif f == 2: row[i] = (row[i] + b) & 255
            elif f == 3: row[i] = (row[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(row)
        prev = row
    return width, height, bpp, rows


for i in range(len(yaws)):
    w, h, bpp, a = read_png(os.path.join(WORK, f"{args.name}_over_{i}.png"))
    w2, h2, bpp2, b = read_png(os.path.join(WORK, f"{args.name}_town_{i}.png"))
    if (w, h) != (w2, h2):
        print("view", i, "sizes differ")
        continue
    total = off = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            d = (abs(a[y][x * bpp] - b[y][x * bpp2]) + abs(a[y][x * bpp + 1] - b[y][x * bpp2 + 1]) + abs(a[y][x * bpp + 2] - b[y][x * bpp2 + 2])) / 3
            total += d
            off += d > 32
    n = (h // 2 + h % 2) * (w // 2 + w % 2)
    print(f"view {i} yaw {yaws[i]}: mean difference {total / n:.2f}/255, pixels off by more than 32: {100 * off / n:.2f}%")
