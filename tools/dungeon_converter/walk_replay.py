"""Doom-only replay of paired_walk.zs runs, with the line that blocked each tic.

usage: walk_replay.py <play folder> <wad> "x,y,heading16;..." [--tics 60] [--from x,y,z]
Same start search and movement as paired_walk.zs (speed 16 set every tic, the engine's own player move), without
Daggerfall. Prints per tic: position, z, and the blocking line (index, ends, sectors, and for a two-sided line the
floor and ceiling of each side at the line's middle). Doom runs on quiet_run.py's private desktop, about 15 seconds.
Check its positions against the paired run's log-walk.txt before trusting it for that run.
"""
import subprocess, sys, tempfile, zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ZS = r'''version "4.14"
class WRProbe : EventHandler
{
	static const double RUNS[] = { @RUNS@ };
	const TICS = @TICS@;
	int run, t;
	string Side(Sector s, vector2 m)
	{
		if (!s) return "-";
		return String.Format("%d(f %.1f c %.1f)", s.Index(), s.floorplane.ZatPoint(m), s.ceilingplane.ZatPoint(m));
	}
	void Start(PlayerPawn p)
	{
		double x0 = RUNS[run * 3], y0 = RUNS[run * 3 + 1];
		for (int r = 0; r <= 96; r += 8)
		{
			bool fits = false;
			for (int k = 0; k < (r ? 16 : 1) && !fits; k++)
			{
				double x = x0 + cos(k * 22.5) * r, y = y0 + sin(k * 22.5) * r;
				p.SetOrigin((x, y, p.GetZAt(x, y, 0, GZF_ABSOLUTEPOS)), false);
				p.FindFloorCeiling();
				p.SetZ(p.floorz);
				fits = p.TestMobjLocation();
			}
			if (fits) break;
		}
		p.vel = (0, 0, 0);
		p.angle = RUNS[run * 3 + 2] * 22.5;
	}
	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p || level.maptime < 10) return;
		if (level.maptime == 10)
		{
			players[0].cheats |= CF_GODMODE;
			p.bTHRUACTORS = true;
			Console.Printf("WR radius %.2f height %.2f", p.radius, p.height);
			if (@FROM@) { p.SetOrigin((@FX@, @FY@, @FZ@), false); p.FindFloorCeiling(); }
			run = 0; t = 0; Start(p);
			return;
		}
		if (run * 3 >= RUNS.Size()) return;
		t++;
		if (t <= 4) { p.vel = (0, 0, 0); return; }
		if (t == 5) Console.Printf("WRRUN %d heading %.1f from %.2f %.2f %.2f", run, RUNS[run * 3 + 2] * 22.5, p.pos.x, p.pos.y, p.pos.z);
		else
		{
			Line l = p.BlockingLine;
			string b = "none";
			if (l)
			{
				vector2 m = (l.v1.p + l.v2.p) / 2;
				b = String.Format("line %d (%.1f,%.1f)-(%.1f,%.1f) %s | %s", l.Index(), l.v1.p.x, l.v1.p.y, l.v2.p.x, l.v2.p.y, Side(l.frontsector, m), Side(l.backsector, m));
			}
			Console.Printf("WRT %d %.2f %.2f %.2f %d blocked by %s", t - 5, p.pos.x, p.pos.y, p.pos.z, p.pos.z <= p.floorz + 0.01, b);
		}
		p.BlockingLine = null;
		if (t <= 5 + TICS)
		{
			p.angle = RUNS[run * 3 + 2] * 22.5;
			p.vel.xy = (cos(p.angle), sin(p.angle)) * 16.0;
			return;
		}
		run++; t = 0;
		if (run * 3 < RUNS.Size()) Start(p); else Console.Printf("WRDONE");
	}
}
'''

play, wad, runs = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
tics = sys.argv[sys.argv.index("--tics") + 1] if "--tics" in sys.argv else "60"
# --from x,y,z: where the player is before the first start search (paired_walk arrives at the dungeon's entrance
# marker; the search picks the floor level nearest the player's height, so this matters where levels overlap).
fx, fy, fz = (sys.argv[sys.argv.index("--from") + 1].split(",") if "--from" in sys.argv else ("0", "0", "0"))
ZS = ZS.replace("@FROM@", "true" if "--from" in sys.argv else "false").replace("@FX@", fx).replace("@FY@", fy).replace("@FZ@", fz)
flat = ", ".join(c for r in runs.split(";") for c in r.split(","))
data = play / "data"
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    with zipfile.ZipFile(tmp / "probe.pk3", "w") as z:
        z.writestr("zscript.txt", ZS.replace("@RUNS@", flat).replace("@TICS@", tics))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "WRProbe" }\n')
    timeout = 30 + len(runs.split(";")) * (int(tics) + 6) // 35 + 10
    subprocess.run([sys.executable, QUIET, "--timeout", str(timeout), "--cwd", str(tmp), "--", str(play / "uzdoom" / "uzdoom.exe"), "-iwad", IWAD,
                    "-file", str(data / "ddruntime.pk3"), str(wad), str(data / "privateershold_mesh.pk3"), str(data / "privateershold_doors.pk3"),
                    str(tmp / "probe.pk3"), "-config", str(tmp / "probe.ini"), "-nomonsters", "+map", "MAP01", "+logfile", "probe",
                    "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = (tmp / "log-probe.txt").read_text(errors="replace") if (tmp / "log-probe.txt").exists() else ""
print(f"# walk_replay.py {wad} {runs}")
print("\n".join(l for l in log.splitlines() if l.startswith("WR") or "Script error" in l))
