"""Why does a move fail? Puts the player at x,y,z and tries TryMove to tx,ty; prints the opening, the sector under each
box corner (with its 3D floor count), nearby things, and the blocking line. Doom runs alone on quiet_run.py's private
desktop with the play folder's UZDoom and data (like floor_check.py), about 15 seconds.
usage: move_probe.py <play folder> <wad> "x,y,z,tx,ty;..."
"""
import subprocess, sys, tempfile, zipfile
from pathlib import Path
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ZS = r'''version "4.14"
class MPProbe : EventHandler
{
	static const double PTS[] = { @PTS@ };
	override void WorldTick()
	{
		if (level.maptime != 10) return;
		Actor mo = players[0].mo;
		Console.Printf("MP radius %.2f height %.2f maxstep %.1f", mo.radius, mo.height, mo.MaxStepHeight);
		for (int i = 0; i + 4 < PTS.Size(); i += 5)
		{
			mo.SetOrigin((PTS[i], PTS[i+1], PTS[i+2]), false);
			mo.floorz = PTS[i+2];
			FCheckPosition tm;
			bool here = mo.CheckPosition((PTS[i], PTS[i+1]), false, tm);
			Console.Printf("MP at %.2f %.2f %.2f: fits %d floorz %.2f ceilz %.2f dropoff %.2f", PTS[i], PTS[i+1], PTS[i+2], here, tm.floorz, tm.ceilingz, tm.dropoffz);
			for (int c = 0; c < 5; c++)
			{
				double cx = PTS[i] + (c == 4 ? 0 : (c & 1 ? 10.5 : -10.5)), cy = PTS[i+1] + (c == 4 ? 0 : (c & 2 ? 10.5 : -10.5));
				Sector cs = level.PointInSector((cx, cy));
				Console.Printf("MP   corner %.1f %.1f sector %d floor %.2f ceil %.2f 3dfloors %d", cx, cy, cs.Index(), cs.floorplane.ZatPoint((cx, cy)), cs.ceilingplane.ZatPoint((cx, cy)), cs.Get3DFloorCount());
			}
			let it = BlockThingsIterator.Create(mo, 64);
			while (it.Next()) if (it.thing != mo) Console.Printf("MP   thing %s at %.1f %.1f %.1f r %.1f h %.1f solid %d", it.thing.GetClassName(), it.thing.pos.x, it.thing.pos.y, it.thing.pos.z, it.thing.radius, it.thing.height, it.thing.bSolid);
			FCheckPosition tm2;
			bool there = mo.CheckPosition((PTS[i+3], PTS[i+4]), false, tm2);
			Console.Printf("MP   check to %.2f %.2f: fits %d floorz %.2f ceilz %.2f", PTS[i+3], PTS[i+4], there, tm2.floorz, tm2.ceilingz);
			mo.BlockingLine = null;
			bool moved = mo.TryMove((PTS[i+3], PTS[i+4]), true);
			Line l = mo.BlockingLine;
			if (l)
			{
				string s1 = l.frontsector ? String.Format("%d", l.frontsector.Index()) : "-";
				string s2 = l.backsector ? String.Format("%d", l.backsector.Index()) : "-";
				Console.Printf("MP   trymove %d now %.2f %.2f %.2f, blocking line %d (%.1f,%.1f)-(%.1f,%.1f) sectors %s|%s", moved, mo.pos.x, mo.pos.y, mo.pos.z, l.Index(), l.v1.p.x, l.v1.p.y, l.v2.p.x, l.v2.p.y, s1, s2);
			}
			else Console.Printf("MP   trymove %d now %.2f %.2f %.2f, no blocking line", moved, mo.pos.x, mo.pos.y, mo.pos.z);
		}
		Console.Printf("MPDONE");
	}
}
'''
play, wad, pts = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
flat = ", ".join(c for p in pts.split(";") for c in p.split(","))
data = play / "data"
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    with zipfile.ZipFile(tmp / "probe.pk3", "w") as z:
        z.writestr("zscript.txt", ZS.replace("@PTS@", flat))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "MPProbe" }\n')
    subprocess.run([sys.executable, QUIET, "--timeout", "40", "--cwd", str(tmp), "--", str(play / "uzdoom" / "uzdoom.exe"), "-iwad", IWAD,
                    "-file", str(data / "ddruntime.pk3"), str(wad), str(data / "privateershold_mesh.pk3"), str(data / "privateershold_doors.pk3"),
                    str(tmp / "probe.pk3"), "-config", str(tmp / "probe.ini"), "-nomonsters", "+map", "MAP01", "+logfile", "probe",
                    "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = (tmp / "log-probe.txt").read_text(errors="replace") if (tmp / "log-probe.txt").exists() else ""
print("\n".join(l for l in log.splitlines() if l.startswith("MP") or "Script error" in l))
