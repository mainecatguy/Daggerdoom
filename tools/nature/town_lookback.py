"""Town look-back check for wilderness nature flats.

Stands at one world point outside a generated town on the overworld, facing out into the wilderness, and records every
nature flat near it (position relative to the player, sprite). Then walks into the town's entry band, waits for the
handoff to the town map, goes back to the same world point on the town map and records again. The two lists are
compared: the town map must show the same flats at the same places on its ground.

    python tools/nature/town_lookback.py [--exe ...] [--data <make_data.py output>] [--out <dir>]

Defaults: City of Daggerfall (group rect x 26507-26612, y 36619-36724), look point 18 tiles west of it.
Output stays outside the repository.
"""
import argparse
import math
import re
import subprocess
import zipfile
from pathlib import Path

IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"

ZS = """version "4.14"
class LookBack : StaticEventHandler
{
	const TILE = 192.0;
	const HALF = 12288.0;
	int phase, timer;
	double lx, ly, ex, ey, tx, ty;	// look and entry points (overworld local), translation overworld -> town

	int CV(String n) { return CVar.FindCVar(n).GetInt(); }

	void Dump(String tag, PlayerPawn p)
	{
		Console.Printf("LBK %s map=%s player=%.2f,%.2f,%.2f angle=%.1f pitch=%.1f camera=%.2f,%.2f,%.2f origin=%d,%d", tag, level.MapName, p.pos.x, p.pos.y, p.pos.z, p.angle, p.pitch, players[0].camera.pos.x, players[0].camera.pos.y, players[0].camera.pos.z, CV("dd_tm_originx"), CV("dd_tm_originy"));
		let it = ThinkerIterator.Create("DFNatureFlat", Thinker.MAX_STATNUM + 1, true);
		Actor a;
		int n = 0;
		while (a = Actor(it.Next()))
		{
			Vector3 d = a.pos - p.pos;
			if (d.xy.Length() > @RADIUS@) continue;
			Console.Printf("LBKF %s %.2f %.2f %.2f %s %.3f %.3f", tag, d.x, d.y, d.z, TexMan.GetName(a.picnum), a.scale.x, a.scale.y);
			n++;
		}
		Console.Printf("LBK %s count=%d", tag, n);
	}

	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p) return;
		timer++;
		bool inTown = CV("dd_tm_intown") != 0;
		switch (phase)
		{
		case 0:	// warp near the town
			if (level.maptime < 5) break;
			CVar.FindCVar("dd_tm_warp").SetString("@START@");
			phase = 1; timer = 0;
			break;
		case 1:	// arrive, then wait until the town map is ready
		{
			p.vel = (0, 0, 0);
			if (timer < 10 || level.maptime < 3 || inTown) break;
			if (timer % 70 == 0) Console.Printf("LBK waiting nearest=%d state=%d", CV("dd_tm_nearest"), CV("dd_tm_neareststate"));
			if (CV("dd_tm_neareststate") != 3) { if (timer > 35 * 120) { Console.Printf("LBK FAIL town not ready"); phase = 9; } break; }
			lx = (@LX@ - CV("dd_tm_originx")) * TILE - HALF; ly = (@LY@ - CV("dd_tm_originy")) * TILE - HALF;
			ex = (@EX@ - CV("dd_tm_originx")) * TILE - HALF; ey = (@EY@ - CV("dd_tm_originy")) * TILE - HALF;
			p.SetOrigin((lx, ly, p.GetZAt(lx, ly, 0, GZF_ABSOLUTEPOS)), false);
			p.angle = @YAW@;
			phase = 2; timer = 0;
			break;
		}
		case 2:	// on the overworld at the look point
			p.vel = (0, 0, 0);
			if (timer == 20) Dump("over", p);
			if (timer == 20 || timer == 100) level.MakeScreenShot();
			if (timer == 110) { phase = 3; timer = 0; }
			break;
		case 3:	// into the entry band, standing still, until the handoff
			p.vel = (0, 0, 0);
			if (!inTown)
			{
				if (timer == 1) p.SetOrigin((ex, ey, p.GetZAt(ex, ey, 0, GZF_ABSOLUTEPOS)), false);
				if (timer > 35 * 20) { Console.Printf("LBK FAIL no handoff"); phase = 9; }
				break;
			}
			if (level.maptime < 3) break;
			tx = p.pos.x - ex; ty = p.pos.y - ey;
			Console.Printf("LBK handoff map=%s at=%.2f,%.2f translation=%.2f,%.2f", level.MapName, p.pos.x, p.pos.y, tx, ty);
			p.SetOrigin((lx + tx, ly + ty, p.GetZAt(lx + tx, ly + ty, 0, GZF_ABSOLUTEPOS)), false);
			p.angle = @YAW@;
			phase = 4; timer = 0;
			break;
		case 4:	// on the town map at the same world point
			p.vel = (0, 0, 0);
			if (timer == 20) { Dump("town", p); Console.Printf("LBK intown=%d", CV("dd_tm_intown")); }
			if (timer == 20 || timer == 100) level.MakeScreenShot();
			if (timer == 110) { phase = 9; timer = 0; }
			break;
		case 9:
			if (timer == 5) { Console.Printf("LBK DONE"); level.ExitLevel(0, false); }
			if (timer == 10) CVar.FindCVar("dd_tm_warp").SetString("");
			break;
		}
	}
}
"""


def parse(log):
    flats = {"over": [], "town": []}
    info = []
    for line in log.splitlines():
        if line.startswith("LBKF "):
            f = line.split()
            flats[f[1]].append((float(f[2]), float(f[3]), float(f[4]), f[5]))
        elif line.startswith("LBK "):
            info.append(line)
    return flats, info


def compare(over, town, radius):
    """Pairs each flat within radius with the nearest flat of the other list that has the same sprite."""
    def near(a, pool):
        best = None
        for b in pool:
            if b[3] != a[3]:
                continue
            d = math.hypot(a[0] - b[0], a[1] - b[1])
            if best is None or d < best[0]:
                best = (d, b)
        return best
    o = [f for f in over if math.hypot(f[0], f[1]) <= radius]
    t = [f for f in town if math.hypot(f[0], f[1]) <= radius]
    matched = [(a, near(a, t)) for a in o]
    good = [(a, m) for a, m in matched if m and m[0] < 1.0]
    missing_in_town = [a for a, m in matched if not m or m[0] >= 1.0]
    extra_in_town = [b for b in t if not (near(b, o) and near(b, o)[0] < 1.0)]
    dz = max((abs(a[2] - m[1][2]) for a, m in good), default=0.0)
    return len(o), len(t), len(good), missing_in_town, extra_in_town, dz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-nature\Release\uzdoom.exe")
    ap.add_argument("--data", default=r"D:\dev\DoomDaggerfall-build\nature-data")
    ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-build\nature-tests\lookback")
    ap.add_argument("--start", default="26480 36672", help="overworld warp tile, outside the entry band")
    ap.add_argument("--look", default="26489.5,36672.5", help="look point (global tiles), inside the town map's ground")
    ap.add_argument("--entry", default="26498.5,36672.5", help="point inside the entry band")
    ap.add_argument("--yaw", default="180", help="facing at the look point (180 = west, away from the city)")
    ap.add_argument("--radius", type=float, default=20 * 192.0, help="Doom units recorded around the look point")
    a = ap.parse_args()
    out, data = Path(a.out), Path(a.data)
    out.mkdir(parents=True, exist_ok=True)
    (lx, ly), (ex, ey) = a.look.split(","), a.entry.split(",")
    text = (ZS.replace("@START@", a.start).replace("@LX@", lx).replace("@LY@", ly).replace("@EX@", ex).replace("@EY@", ey)
            .replace("@YAW@", a.yaw + ".0").replace("@RADIUS@", str(a.radius)))
    harness = out / "lookback.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LookBack" }\n')
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    log = out / "log-lookback.txt"	# the engine names the file log-<name>.txt
    for old in [log, *out.glob("*.png")]:
        if old.exists():
            old.unlink()
    game = [a.exe, "-iwad", IWAD, "-file", str(data / "ddruntime.pk3"), str(data / "overworld.pk3"), str(harness), "-config", str(out / "test.ini"),
            "-nosound", "-noautoload", "-nomonsters", "-skill", "3", "-ddtowncache", str(cache),
            "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ARENA2, "+logfile", "lookback",
            "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
            "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720", "+screenblocks", "12", "+r_drawplayersprites", "0",
            "+enablescriptscreenshot", "1", "+screenshot_type", "png", "+screenshot_dir", str(out), "+map", "DDOVER01"]
    subprocess.run(["python", QUIET, "--cwd", str(out), "--timeout", "200", "--", *game])
    body = log.read_text(errors="replace") if log.exists() else ""
    flats, info = parse(body)
    for line in info:
        if not line.startswith("LBK waiting"):
            print(line)
    for l in body.splitlines():
        if "FATAL" in l or "Script error" in l or "aborted" in l:
            print("ERROR:", l)
    if not flats["over"] or not flats["town"]:
        print("RESULT: incomplete (see", log, ")")
        return
    for r in (4, 6, 10, 20):
        no, nt, ng, miss, extra, dz = compare(flats["over"], flats["town"], r * 192.0)
        print(f"within {r:2d} tiles: overworld {no}, town map {nt}, same sprite within 1 unit {ng}, "
              f"missing on town map {len(miss)}, extra on town map {len(extra)}, worst height difference {dz:.2f}")


if __name__ == "__main__":
    main()
