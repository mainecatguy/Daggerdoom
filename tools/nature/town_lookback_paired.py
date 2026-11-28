"""Town look-back, paired: the town map side of town_lookback.py with Daggerfall Unity running through the launcher.

Daggerfall Unity starts at its -dfsynctest town, and position sync then moves it to wherever Doom is, so any town map
works. It loads the town map (--map, default DDT09183, the City of Daggerfall; Ruins of Gaerhart Manor is DDT06187) paired, stands at the look point town_lookback.py used (its town map coordinates, read from that
run's log), facing out, and records the nature flat actors and the distant view's flats. These are compared with the
overworld list from the unpaired run's log, which is the wilderness view of the same spot.

    python tools/nature/town_lookback_paired.py --exe <uzdoom.exe> --unpaired <town_lookback.py --out dir> [--out dir]

Uses the paired review folder review\\town-lookback (stage_lookback_demo.py: launcher, bridge, Daggerfall Unity, data)
read only, with the UZDoom given by --exe (default: the folder's own). Output stays outside the repository.
"""
import argparse
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import town_lookback as tl  # noqa: E402

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\town-lookback")
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
QUIET = tl.QUIET
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")

ZS = """version "4.14"
class LookBackPaired : StaticEventHandler
{
	int timer;
	bool placed;

	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p || level.MapName != "@MAP@") return;
		timer++;
		if (timer < @WAIT@) return;
		p.vel = (0, 0, 0);
		p.SetOrigin((@X@, @Y@, p.GetZAt(@X@, @Y@, 0, GZF_ABSOLUTEPOS)), false);
		p.angle = @YAW@;
		int t = timer - @WAIT@;
		if (t == 20)
		{
			Console.Printf("LBK town map=%s player=%.2f,%.2f,%.2f intown=%d", level.MapName, p.pos.x, p.pos.y, p.pos.z, CVar.FindCVar("dd_tm_intown").GetInt());
			let it = ThinkerIterator.Create("DFNatureFlat", Thinker.MAX_STATNUM + 1, true);
			Actor a;
			int n = 0;
			while (a = Actor(it.Next()))
			{
				Vector3 d = a.pos - p.pos;
				if (d.xy.Length() > @RADIUS@) continue;
				Console.Printf("LBKF town %.2f %.2f %.2f %s %.3f %.3f", d.x, d.y, d.z, TexMan.GetName(a.picnum), a.scale.x, a.scale.y);
				n++;
			}
			Console.Printf("LBK town count=%d", n);
		}
		if (t == 100)
		{
			let cv = CVar.FindCVar("dd_horizon_dump");
			if (cv) cv.SetString(String.Format("%.2f %.2f %.1f @OUT@/ring-town.txt", p.pos.x, p.pos.y, @RADIUS@));
			Console.Printf("LBK town ring player=%.2f,%.2f,%.2f", p.pos.x, p.pos.y, p.pos.z);
			level.MakeScreenShot();
		}
		if (t == 140) Console.Printf("LBK DONE");
	}
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(REVIEW / "uzdoom" / "uzdoom.exe"))
    ap.add_argument("--unpaired", required=True, help="town_lookback.py output folder for the same town")
    ap.add_argument("--map", default="DDT09183")
    ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-build\townlookback-tests\city-paired")
    ap.add_argument("--yaw", default="180")
    ap.add_argument("--radius", type=float, default=20 * 192.0)
    ap.add_argument("--wait", type=int, default=35 * 30, help="tics on the town map before standing at the look point (Daggerfall's season reaches the town within it)")
    a = ap.parse_args()
    out, unpaired = Path(a.out), Path(a.unpaired)
    out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob("*.png"), *out.glob("ring-*.txt"), out / "log-console.txt"]:
        old.unlink(missing_ok=True)
    over_flats, over_info = tl.parse((unpaired / "log-lookback.txt").read_text(errors="replace"))
    town_line = next(l for l in over_info if l.startswith("LBK town map="))
    x, y = re.search(r"player=([-\d.]+),([-\d.]+)", town_line).groups()
    harness = out / "lookback-paired.pk3"
    text = (ZS.replace("@X@", x).replace("@Y@", y).replace("@YAW@", a.yaw + ".0").replace("@RADIUS@", str(a.radius))
            .replace("@WAIT@", str(a.wait)).replace("@MAP@", a.map).replace("@OUT@", out.resolve().as_posix()))
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LookBackPaired" }\n')
    data = REVIEW / "data"
    command = [str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw", "--uzdoom", a.exe, "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(out), "--log", str(out / "launcher.log")]
    for mod in [data / "ddruntime.pk3", data / "overworld.pk3", REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", harness]:
        command += ["--mod", str(mod)]
    uz = ["-config", str(out / "uzdoom.ini"), "-dfbridgelog", str(out / "uz.log"), "-skill", "3", "-ddhorizontest",
          "-ddtowncache", str(out / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+map", a.map, "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+dd_debugmessages", "0",
          "+enablescriptscreenshot", "1", "+screenshot_type", "png", "+screenshot_dir", str(out), "+screenblocks", "12", "+r_drawplayersprites", "0",
          "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720"]
    df = ["-dfbridgelog", str(out / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-dfmute", "-dftownhour", "12",
          "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "720"]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    timeout = 150
    proc = subprocess.Popen([sys.executable, QUIET, "--timeout", str(timeout), "--"] + command,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    console, reason, end = out / "log-console.txt", "timeout", time.time() + timeout + 3
    try:
        while time.time() < end and proc.poll() is None:
            time.sleep(0.2)
            body = console.read_text(errors="replace") if console.exists() else ""
            if any(k in body for k in FATAL):
                reason = "fatal"
                break
            if "LBK DONE" in body:
                reason = "done"
                time.sleep(1.5)
                break
    finally:
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
    print("run ended:", reason)
    body = console.read_text(errors="replace") if console.exists() else ""
    town_flats, info = tl.parse(body)
    for line in info:
        print(line)
    uzlog = (out / "uz.log").read_text(errors="replace") if (out / "uz.log").exists() else ""
    print("bridge log lines:", len(uzlog.splitlines()), "| connected:", any(k in uzlog.lower() for k in ("connected", "handshake", "hello")))
    ring = tl.read_ring(out / "ring-town.txt", tl.player_z(info, "town"))
    if not town_flats["town"] or ring is None:
        print("RESULT: incomplete (see", console, ")")
        return
    print(f"ring town: complete={ring[0]} flats within radius {len(ring[1])}")
    # Daggerfall's date sets the season, so the paired town may use another climate archive (dfflat/F<archive>R<record>)
    # than the unpaired overworld. Positions and records do not depend on it: compare by record, and require one archive
    # for the town map's actors and its distant view.
    def archive(f):
        return re.sub(r"r\d+\.png$", "", f[3])
    def record(fs):
        return [(f[0], f[1], f[2], f[3][-7:]) for f in fs]
    archives = {"overworld": sorted({archive(f) for f in over_flats["over"]}), "town actors": sorted({archive(f) for f in town_flats["town"]}),
                "town distant view": sorted({archive(f) for f in ring[1]})}
    print("climate archives:", archives)
    one_archive = len(set(archives["town actors"]) | set(archives["town distant view"])) == 1
    over_r, town_r = record(over_flats["over"]), record(town_flats["town"] + ring[1])
    for r in (4, 6, 10, 20):
        no, nt, ng, miss, extra, dz = tl.compare(over_r, town_r, r * 192.0)
        print(f"paired town map (actors + distant view) vs unpaired overworld, within {r:2d} tiles: overworld {no}, town map {nt}, "
              f"same record within 1 unit {ng}, missing {len(miss)}, extra {len(extra)}, worst height difference {dz:.2f}")
    no, nt, ng, miss, extra, dz = tl.compare(over_r, town_r, a.radius)
    print("RESULT:", "PASS" if not miss and not extra and dz < 1.0 and ring[0] and one_archive else "FAIL")


if __name__ == "__main__":
    main()
