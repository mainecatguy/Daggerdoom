"""Frame cost of wilderness nature flats.

UZDoom sessions rendering at 1280x720 (vid_scalemode 5, which works on the private desktop), alternating flats on, off,
on, off (+dd_natureflats; scripts may not set it). Each session warps to the spot, stands still facing four directions
for 3 s each, then runs east for 15 s across chunk shifts. Every frame's time is taken in RenderOverlay; every tic's
time in WorldTick. Both go to the logs, summarised here.

    python tools/nature/frame_cost.py [--exe ...] [--data ...] [--out ...] [--tile 15632,31040]
"""
import argparse
import statistics
import subprocess
import zipfile
from pathlib import Path

IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
ROUNDS = [1, 0, 1, 0]

ZS = """version "4.14"
class FrameCost : StaticEventHandler
{
	const FLATS = @FLATS@;
	const ROUND = @ROUND@;
	int phase, timer;
	String label;	// what is being measured now; empty = nothing
	ui double lastFrame;
	ui String lastLabel;
	double lastTic;

	int CV(String n) { return CVar.FindCVar(n).GetInt(); }

	override void RenderOverlay(RenderEvent e)
	{
		double now = MSTimeF();
		if (label != "" && label == lastLabel && lastFrame > 0) Console.Printf("FCF %s %.3f", label, now - lastFrame);
		lastFrame = now;
		lastLabel = label;
	}

	int CountFlats()
	{
		let it = ThinkerIterator.Create("DFNatureFlat", Thinker.MAX_STATNUM + 1, true);
		int n = 0;
		while (it.Next()) n++;
		return n;
	}

	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p) return;
		double now = MSTimeF();
		if (label != "" && lastTic > 0) Console.Printf("FCT %s %.3f", label, now - lastTic);
		lastTic = now;
		timer++;
		switch (phase)
		{
		case 0:	// warp: a fresh layout of the whole window
			if (level.maptime < 5) break;
			CVar.FindCVar("dd_tm_warp").SetString("@TILE@");
			phase = 1; timer = 0;
			break;
		case 1:	// let the warp and layout settle
			p.vel = (0, 0, 0);
			if (timer < 140 || level.maptime < 70) break;
			Console.Printf("FC round=%d flats=%d actors=%d", ROUND, FLATS, CountFlats());
			phase = 2; timer = 0;
			break;
		case 2:	// four directions, 3 s each (the first second of each is not measured)
		{
			p.vel = (0, 0, 0);
			int view = timer / 105, t = timer % 105;
			if (view >= 4) { label = ""; phase = 3; timer = 0; break; }
			p.angle = view * 90.0;
			label = t >= 35 ? String.Format("r%d_f%d_still", ROUND, FLATS) : "";
			break;
		}
		case 3:	// run east across chunk shifts
			p.angle = 0;
			p.vel.xy = (20, 0);
			label = String.Format("r%d_f%d_run", ROUND, FLATS);
			if (timer >= 35 * 15)
			{
				label = "";
				p.vel = (0, 0, 0);
				Console.Printf("FC round=%d shifts=%d actors=%d", ROUND, CV("dd_tm_shifts"), CountFlats());
				phase = 9; timer = 0;
			}
			break;
		case 9:
			if (timer == 5) { Console.Printf("FC DONE"); level.ExitLevel(0, false); }
			break;
		}
	}
}
"""


def summary(values):
    v = sorted(values)
    if not v:
        return "no samples"
    p = lambda q: v[min(len(v) - 1, int(q * len(v)))]
    return f"n={len(v):5d} median {statistics.median(v):6.2f} ms  p95 {p(0.95):6.2f}  p99 {p(0.99):6.2f}  worst {v[-1]:7.2f}"


def run(a, out, data, cache, rnd, flats):
    text = ZS.replace("@FLATS@", str(flats)).replace("@ROUND@", str(rnd)).replace("@TILE@", a.tile.replace(",", " "))
    harness = out / "framecost.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "FrameCost" }\n')
    log = out / f"log-framecost{rnd}.txt"
    if log.exists():
        log.unlink()
    game = [a.exe, "-iwad", IWAD, "-file", str(data / "ddruntime.pk3"), str(data / "overworld.pk3"), str(harness), "-config", str(out / "test.ini"),
            "-nosound", "-noautoload", "-nomonsters", "-skill", "3", "-ddtowncache", str(cache),
            "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ARENA2, "+logfile", f"framecost{rnd}",
            "+" + a.toggle, str(flats),
            "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
            "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720", "+vid_vsync", "0", "+vid_maxfps", "0",
            "+map", "DDOVER01"]
    subprocess.run(["python", QUIET, "--cwd", str(out), "--timeout", "90", "--", *game])
    return log.read_text(errors="replace") if log.exists() else ""


def report(body):
    frames, tics = {}, {}
    for line in body.splitlines():
        f = line.split()
        if len(f) == 3 and f[0] in ("FCF", "FCT"):
            (frames if f[0] == "FCF" else tics).setdefault(f[1], []).append(float(f[2]))
        elif line.startswith("FC ") or "FATAL" in line or "Script error" in line or "aborted" in line:
            print(line)
    for label in frames:
        print(f"{label:14s} frame {summary(frames[label])}")
    for label in tics:
        print(f"{label:14s} tic   {summary(tics[label])}")
    for kind in ("still", "run"):
        for on in (1, 0):
            fr = [x for l, v in frames.items() if l.endswith(f"_f{on}_{kind}") for x in v]
            tc = [x for l, v in tics.items() if l.endswith(f"_f{on}_{kind}") for x in v]
            print(f"ALL flats {'on ' if on else 'off'} {kind:5s} frame {summary(fr)} | tic {summary(tc)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-nature\Release\uzdoom.exe")
    ap.add_argument("--data", default=r"D:\dev\DoomDaggerfall-build\nature-data")
    ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-build\nature-tests\framecost")
    ap.add_argument("--tile", default="15632,31040", help="global tile to stand on (default: woodland pixel 122,257)")
    ap.add_argument("--toggle", default="dd_natureflats", help="the CVAR switched on and off between sessions (dd_horizon for the distant view)")
    a = ap.parse_args()
    out, data = Path(a.out), Path(a.data)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    body = ""
    for rnd, flats in enumerate(ROUNDS):
        body += run(a, out, data, cache, rnd, flats)
    report(body)


if __name__ == "__main__":
    main()
