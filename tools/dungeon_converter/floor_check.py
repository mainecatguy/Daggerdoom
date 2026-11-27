"""Floor heights in a converted dungeon: the engine's collision floors next to the visible mesh's floors.

  floor_check.py points <play folder> --out FILE [--wad WAD] --at x,y;x,y;...   floors at each point (engine + mesh)
  floor_check.py path   <play folder> --out FILE [--wad WAD] --from x,y --to x,y [--step 8]
  floor_check.py scan   <play folder> --out FILE [--wad WAD] --deg LO,HI [--radius 24] [--grid 16]
        every grid point whose floor, and the floor `radius` units around it, is one plane between LO and HI degrees

Uses the play folder's UZDoom, ddruntime.pk3 and privateershold_mesh/_doors.pk3; --wad swaps the map. Doom runs alone on
quiet_run.py's private desktop with a private config, about 40 seconds. The mesh floor at a point is every upward-facing
(normal z over 0.3) triangle of DFMESH above it, read in Python (vertices are x, height, y, as hw_dfmesh.cpp reads them).
"""
import math
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

PROBE = r'''version "4.14"
class FCProbe : EventHandler
{
	static const double PTS[] = { @PTS@ };
	vector3 nrm;
	bool Ramp(double x, double y, double lo, double hi)
	{
		Sector s = level.PointInSector((x, y));
		nrm = s.floorplane.Normal;
		return nrm.z > lo && nrm.z < hi && s.ceilingplane.ZatPoint((x, y)) - s.floorplane.ZatPoint((x, y)) >= 56;
	}
	override void WorldTick()
	{
		if (level.maptime != 10) return;
		for (int i = 0; i + 1 < PTS.Size(); i += 2)
		{
			double x = PTS[i], y = PTS[i + 1];
			Sector s = level.PointInSector((x, y));
			Console.Printf("FCPT %.1f %.1f sector %d floor %.1f ceiling %.1f slope %.1f", x, y, s.Index(),
				s.floorplane.ZatPoint((x, y)), s.ceilingplane.ZatPoint((x, y)), acos(s.floorplane.Normal.z));
		}
		if (@SCAN@)
		{
			double lo = cos(@HI@), hi = cos(@LO@);
			int found = 0;
			for (double y = @Y0@; y <= @Y1@; y += @GRID@)
			for (double x = @X0@; x <= @X1@; x += @GRID@)
			{
				if (!Ramp(x, y, lo, hi)) continue;
				vector3 n = nrm;
				bool all = true;
				for (int k = 0; k < 4 && all; k++)
					all = Ramp(x + cos(k * 90) * @R@, y + sin(k * 90) * @R@, lo, hi) && (nrm - n).Length() < 0.01;
				if (!all) continue;
				Console.Printf("FCRAMP %d %d z %.1f slope %.1f uphill %.0f", x, y, level.PointInSector((x, y)).floorplane.ZatPoint((x, y)), acos(n.z), atan2(-n.y, -n.x));
				found++;
			}
			Console.Printf("FCSCAN %d points", found);
		}
		Console.Printf("FCDONE");
	}
}
'''


def option(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def wad_bounds(wad):
    import re
    data = Path(wad).read_bytes()
    n, off = struct.unpack("<ii", data[4:12])
    for i in range(n):
        o, s, name = struct.unpack("<ii8s", data[off + 16 * i: off + 16 * i + 16])
        if name.rstrip(b"\0") == b"TEXTMAP":
            text = data[o:o + s].decode(errors="replace")
    xy = [(float(a), float(b)) for a, b in re.findall(r"vertex\s*\{\s*x\s*=\s*([-\d.]+);\s*y\s*=\s*([-\d.]+)", text)]
    return min(p[0] for p in xy), min(p[1] for p in xy), max(p[0] for p in xy), max(p[1] for p in xy)


def mesh_floors(mesh_pk3, points):
    data = zipfile.ZipFile(mesh_pk3).read("DFMESH")
    textures, batches, vertices = struct.unpack("<iii", data[12:24])
    start = 24 + textures * 32 + batches * 12
    v = struct.unpack(f"<{vertices * 8}f", data[start:start + vertices * 32])
    tris = []
    for t in range(vertices // 3):
        a, b, c = [(v[(t * 3 + k) * 8], v[(t * 3 + k) * 8 + 2], v[(t * 3 + k) * 8 + 1]) for k in range(3)]  # x, y, height
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        wx, wy, wz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
        if abs(nz) / length > 0.3:
            tris.append((a, b, c, math.degrees(math.acos(abs(nz) / length))))
    result = {}
    for (x, y) in points:
        hits = []
        for a, b, c, slope in tris:
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-9:
                continue
            l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
            l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
            l3 = 1 - l1 - l2
            if min(l1, l2, l3) >= -1e-6:
                hits.append((l1 * a[2] + l2 * b[2] + l3 * c[2], slope))
        result[(x, y)] = sorted(set((round(h, 1), round(s, 1)) for h, s in hits))
    return result


def run_probe(play, wad, points, scan=None):
    data = play / "data"
    flat = ", ".join(f"{c:.1f}" for p in points for c in p) or "0"
    zs = PROBE.replace("@PTS@", flat).replace("@SCAN@", "true" if scan else "false")
    lo, hi, radius, grid = scan or (0, 0, 0, 16)
    x0, y0, x1, y1 = wad_bounds(wad)
    for key, value in (("@LO@", lo), ("@HI@", hi), ("@R@", radius), ("@GRID@", grid), ("@X0@", x0 + 8), ("@Y0@", y0 + 8), ("@X1@", x1 - 8), ("@Y1@", y1 - 8)):
        zs = zs.replace(key, str(value))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(tmp / "probe.pk3", "w") as z:
            z.writestr("zscript.txt", zs)
            z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "FCProbe" }\n')
        subprocess.run([sys.executable, QUIET, "--timeout", "40", "--cwd", str(tmp), "--", str(play / "uzdoom" / "uzdoom.exe"), "-iwad", IWAD,
                        "-file", str(data / "ddruntime.pk3"), str(wad), str(data / "privateershold_mesh.pk3"), str(data / "privateershold_doors.pk3"),
                        str(tmp / "probe.pk3"), "-config", str(tmp / "probe.ini"), "-nomonsters", "+map", "MAP01", "+logfile", "probe",
                        "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log = (tmp / "log-probe.txt").read_text(errors="replace") if (tmp / "log-probe.txt").exists() else ""
    lines = [l for l in log.splitlines() if l.startswith("FC") or "Script error" in l]
    if not any(l.startswith("FCDONE") for l in lines):
        raise SystemExit("the probe did not finish:\n" + "\n".join(lines[-5:]))
    return lines


def main():
    mode, play = sys.argv[1], Path(sys.argv[2]).resolve()
    wad = Path(option("--wad", play / "data" / "privateershold.wad"))
    out = []
    if mode == "scan":
        lo, hi = option("--deg").split(",")
        lines = run_probe(play, wad, [], (float(lo), float(hi), float(option("--radius", 24)), float(option("--grid", 16))))
        out = [l for l in lines if l.startswith(("FCRAMP", "FCSCAN"))]
    else:
        if mode == "points":
            points = [tuple(float(c) for c in p.split(",")) for p in option("--at").split(";")]
        else:
            (ax, ay), (bx, by) = [tuple(float(c) for c in option(k).split(",")) for k in ("--from", "--to")]
            n = max(1, int(math.hypot(bx - ax, by - ay) / float(option("--step", 8))))
            points = [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n + 1)]
        lines = run_probe(play, wad, points)
        mesh = mesh_floors(play / "data" / "privateershold_mesh.pk3", points)
        engine = [l for l in lines if l.startswith("FCPT")]
        for (x, y), line in zip(points, engine):
            out.append(f"{line[5:]} | mesh floors (height, slope): {mesh[(x, y)]}")
    text = f"# floor_check.py {' '.join(sys.argv[1:])}\n# map: {wad}\n" + "\n".join(out) + "\n"
    Path(option("--out")).write_text(text)
    print(text if len(text) < 6000 else text[:6000] + "...")


if __name__ == "__main__":
    main()
