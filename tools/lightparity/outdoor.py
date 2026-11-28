"""Outdoor sprites and monsters against the ground, by day, at night and on a snowy night (lightparity 01).

usage: outdoor.py --exe UZDOOM --out DIR --data PLAYFOLDER\\data [--case NAME ...] [--spot "gx gy"]

Doom only, through quiet_run, on DDOVER01 with hand-fed Daggerfall sky lines (the cases of tools/weatherseam). The
treadmill's own monster packs are off (-nomonsters); the harness places frozen Doom monsters on the ground straight
ahead at 192, 512, 1024, 2048 and 3072 units (spread left and right), so they stand among the nature flats (trees) at known distances. Views:
  ahead     level, toward the monsters: near and far monsters and trees against the ground
  lit       pitched down at the nearest monster, with an orange dynamic light attached beside it (it must still light
            sprites and ground on top of the daylight)
  amp       the same view with light-amp (a fullbright view)
Screenshots: OUT/<case>/<view>.png and a brightness table OUT/<case>/probe.txt. Keep OUT outside the repository.
"""
import argparse
import os
import subprocess
import sys
import time
import zipfile

from PIL import Image, ImageStat

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "weatherseam"))
import seam_shots  # noqa: E402  (QUIET, IWAD, ARENA2, CASES, FATAL)

DISTANCES = (192, 512, 1024, 2048, 3072)

HARNESS = r'''version "4.10"
class LPHarness : EventHandler
{
	int view;
	double baseZ;
	Array<Actor> placed;

	override void WorldLoaded(WorldEvent e) { view = -1; }

	override void NetworkProcess(ConsoleEvent e)
	{
		let p = players[0].mo;
		if (!p) return;
		if (e.Name == "lp_place")
		{
			baseZ = p.floorz;
			static const double dist[] = { @DIST@ };
			for (int i = 0; i < dist.Size(); i++)
			{
				vector2 at = p.pos.xy + (dist[i], (i % 2 ? 1 : -1) * dist[i] * 0.18);	// spread so none hides another
				let m = Actor.Spawn(i % 2 ? "DoomImp" : "ZombieMan", (at, 0), NO_REPLACE);
				if (!m) continue;
				m.SetOrigin((at, m.floorz), false);
				m.angle = 180;
				m.bDORMANT = true;
				m.tics = -1;
				placed.Push(m);
			}
			return;
		}
		if (e.Name == "lp_light" && placed.Size())
		{
			placed[0].A_AttachLight("lplight", DynamicLight.PointLight, 0xff8020, 160, 0, 0, (0, 48, 32));
			return;
		}
		if (e.Name == "lp_view") view = e.Args[0];
	}

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE | CF_NOCLIP | CF_FLY | CF_TOTALLYFROZEN | CF_NOTARGET;
		p.bNOTARGET = true;
		foreach (m : placed) if (m) { m.vel = (0, 0, 0); m.tics = -1; }
		if (view < 0) return;
		p.SetOrigin((p.pos.x, p.pos.y, baseZ), false);
		p.vel = (0, 0, 0);
		p.angle = 0;
		p.pitch = view == 0 ? 0 : 18;
	}
}
'''


def probe(path):
    """Mean brightness of the whole picture and of its lower third (mostly ground)."""
    im = Image.open(path).convert("L")
    w, h = im.size
    return ImageStat.Stat(im).mean[0], ImageStat.Stat(im.crop((0, h * 2 // 3, w, h))).mean[0]


def run_case(args, name, lines):
    out = os.path.join(os.path.abspath(args.out), name)
    os.makedirs(out, exist_ok=True)
    harness = os.path.join(out, "lp_harness.pk3")
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", HARNESS.replace("@DIST@", ", ".join(str(d) for d in DISTANCES)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LPHarness" }\n')
    shots = {v: os.path.join(out, v + ".png").replace("\\", "/") for v in ("ahead", "lit", "amp")}
    for s in shots.values():
        if os.path.exists(s):
            os.remove(s)
    with open(os.path.join(out, "lp.cfg"), "w", newline="\n") as f:
        f.write(f'wait 70; dd_tm_warp "{args.spot}"; wait {args.settle}; netevent lp_place; wait 10; '
                f'netevent lp_view 0; wait 30; screenshot "{shots["ahead"]}"; wait 5; '
                f'netevent lp_light; netevent lp_view 1; wait 30; screenshot "{shots["lit"]}"; wait 5; '
                f'give infrared; wait 10; screenshot "{shots["amp"]}"; wait 5; quit\n')
    with open(os.path.join(out, "lp.ini"), "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth=960\nvid_defheight=540\n")
    log = os.path.join(out, "log-lp.txt")
    if os.path.exists(log):
        os.remove(log)
    sky = [a for line in lines for a in ("+dd_sky", line)]
    command = [sys.executable, seam_shots.QUIET, "--timeout", str(args.timeout), "--cwd", out, "--", args.exe, "-iwad", seam_shots.IWAD,
               "-noautoload", "-config", os.path.join(out, "lp.ini"), "-nomonsters", "-skill", "3", "-stdout",
               "-file", os.path.join(args.data, "ddruntime.pk3"), os.path.join(args.data, "overworld.pk3"), harness,
               "-ddtowncache", os.path.join(args.out, "cache"), "-ddconverter", os.path.join(args.data, "converter", "DungeonConverter.exe"),
               "-ddarena2", seam_shots.ARENA2,
               "+vid_fullscreen", "0", "+vid_scalemode", "5", "+vid_scale_customwidth", "960", "+vid_scale_customheight", "540",
               "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png", "+show_messages", "0", "+r_drawplayersprites", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+wipetype", "0",
               "+logfile", "log-lp.txt", *sky, "+map", "DDOVER01", "+exec", "lp.cfg"]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=open(os.path.join(out, "lp.stdout"), "w"), stderr=subprocess.STDOUT)
    end, reason, text = time.time() + args.timeout + 5, "timeout", ""
    while time.time() < end:
        time.sleep(0.5)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        if any(k in text for k in seam_shots.FATAL):
            reason = "fatal"
            break
        if proc.poll() is not None:
            reason = "exited"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    rows = [f"{v}\t" + ("\t".join(f"{x:.1f}" for x in probe(s)) if os.path.exists(s) else "missing") for v, s in shots.items()]
    with open(os.path.join(out, "probe.txt"), "w") as f:
        f.write("view\tmean\tlower_third\n" + "\n".join(rows) + "\n")
    print(f"== {name}: {reason}; " + "; ".join(rows))
    return reason == "exited" and all(os.path.exists(s) for s in shots.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", required=True, help="a play folder's data folder (ddruntime.pk3, overworld.pk3 with DDNATURE, converter)")
    ap.add_argument("--spot", default="26200 36672", help="overworld pixel, outside any town's mesh square")
    ap.add_argument("--settle", type=int, default=140)
    ap.add_argument("--timeout", type=int, default=40)
    ap.add_argument("--case", nargs="*", default=["summer-noon", "winter-snow", "winter-snow-night", "winter-night"])
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "cache"), exist_ok=True)
    ok = True
    for name in args.case:
        ok = run_case(args, name, seam_shots.CASES[name]) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
