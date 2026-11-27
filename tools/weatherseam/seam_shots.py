"""Overworld ground and light in winter: screenshots where the open ground meets a town's mesh, and across open ground.

usage: seam_shots.py --exe UZDOOM --out DIR --runtime DDRUNTIME.pk3 --overworld OVERWORLD.pk3 --converter EXE
                     [--spot "gx gy"] [--case NAME ...]

Doom only, monsters off, through quiet_run. The player is warped (dd_tm_warp) to --spot on DDOVER01 (default: 18 tiles
west of the City of Daggerfall, the nature-flats demo's spot), then stands frozen while the harness turns the view:
  east      level, toward the town: the town's mesh ground against the overworld's ground
  eastdown  pitched down toward the town edge: tile patterns on both sides of the seam
  high      raised 1500 units, pitched down toward the town: the whole seam
  west      level, away from the town: open ground into the distance (distance darkening)
  down      raised 2500 units, straight down: dirt, grass and stone transitions join up if tile rotations are right
Each case is a set of hand-fed Daggerfall lines (+dd_sky): winter noon clear, winter snow, winter night, summer noon.
Screenshots: OUT/<case>/<view>.png, log OUT/<case>/log-ws.txt. Game-derived output: keep OUT outside the repository.
"""
import argparse
import os
import subprocess
import sys
import time
import zipfile

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")

# Daggerfall's lines as the bridge sends them (sky: index frame stars night ambient weather loop sun elevation winter).
# Winter noon clear is Daggerfall's own (work/notes/20261126-145333.md). Snow is scaled from it by WeatherManager's
# SnowSunlightScale / WinterSunlightScale (0.45 / 0.65) with weather 6 and SnowyFogSettings' 0.005/m: an estimate.
CASES = {
    "winter-noon": ["sky 19 32 0 0 91 0 0 62 90 1", "fog 1 2 0.0005 0 0 168 176 198 0"],
    "winter-snow": ["sky 19 32 0 0 63 6 0 43 90 1", "fog 1 2 0.005 0 0 128 128 128 0"],
    "winter-night": ["sky 19 0 1 1 20 0 0 0 -60 1", "fog 1 2 0.0005 0 0 20 20 20 0"],
    "summer-noon": ["sky 18 31 0 0 214 0 0 106 90 0", "fog 1 2 0.0005 0 0 168 176 198 0"],
}
VIEWS = [("east", 0, 0, 0), ("eastdown", 0, 35, 0), ("high", 0, 25, 1500), ("west", 180, 0, 0),
         ("down", 0, 90, 2500)]  # name, angle, pitch, raise; down: straight down, tile transitions (north is up)
LIT = ("lit", 180, 40, 128)  # --lights: pitched down at the ground ahead, where a dynamic light is attached

HARNESS = r'''version "4.10"
class WSHarness : EventHandler
{
	Array<double> views;	// angle pitch raise
	int current;
	double baseZ;

	override void WorldLoaded(WorldEvent e) { current = -1; }

	bool walking;

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name == "ws_walk") { walking = true; current = -1; return; }
		if (e.Name == "ws_light" && players[0].mo)	// an orange dynamic light 300 units ahead, on the ground (a stand-in for a muzzle flash or rocket)
		{
			players[0].mo.A_AttachLight("wslight", DynamicLight.PointLight, 0xff8020, 320, 0, 0, (300, 0, -100));
			return;
		}
		if (e.Name != "ws_view") return;
		if ((current < 0 || walking) && players[0].mo) baseZ = players[0].mo.floorz;
		walking = false;
		current = e.Args[0];
	}

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo) return;
		static const double data[] = { @DATA@ };
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE | CF_NOCLIP | CF_FLY | CF_TOTALLYFROZEN;
		p.bNOTARGET = true;
		if (walking)	// west at 100 units a tic, on the ground: the treadmill shifts its window on the way
		{
			p.SetOrigin((p.pos.x - 100, p.pos.y, p.floorz), false);
			p.vel = (0, 0, 0);
			p.angle = 180;
			return;
		}
		if (current < 0) return;
		p.SetOrigin((p.pos.x, p.pos.y, baseZ + data[current * 3 + 2]), false);
		p.vel = (0, 0, 0);
		p.angle = data[current * 3];
		p.pitch = data[current * 3 + 1];
	}
}
'''


def run_case(args, name, lines):
    out = os.path.join(os.path.abspath(args.out), name)
    os.makedirs(out, exist_ok=True)
    harness = os.path.join(out, "ws_harness.pk3")
    data = ", ".join(f"{a}, {p}, {r}" for _, a, p, r in VIEWS + [LIT])
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", HARNESS.replace("@DATA@", data))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "WSHarness" }\n')
    with open(os.path.join(out, "ws.cfg"), "w", newline="\n") as f:
        steps = [(i, view) for i, (view, *_rest) in enumerate(VIEWS)]
        if args.walk:  # then walk about 36 tiles west (window shifts) and take every view again as walked-<view>
            steps += [("walk", None)] + [(i, "walked-" + view) for i, view in steps]
        if args.flip:  # then a new Daggerfall season line arrives mid-game, and every view again as flipped-<view>
            steps += [("flip", None)] + [(i, "flipped-" + view) for i, (view, *_rest) in enumerate(VIEWS)]
        if args.lights:  # the ground with a dynamic light (dark by itself at night), then with light-amp (fullbright)
            lit = len(VIEWS)
            steps += [(lit, "nolight-lit"), ("light", None), (lit, "light-lit"), ("amp", None), (lit, "amp-lit"), (3, "amp-west")]
        for n, (i, view) in enumerate(steps):
            if i == "light":
                f.write(f'alias wsstep{n} "netevent ws_light; wait 5; wsstep{n + 1}"\n')
                continue
            if i == "amp":
                f.write(f'alias wsstep{n} "give infrared; wait 5; wsstep{n + 1}"\n')
                continue
            if i == "flip":
                f.write(f'alias wsstep{n} "dd_sky \\"{args.flip}\\"; wait 10; wsstep{n + 1}"\n')
                continue
            if i == "walk":
                f.write(f'alias wsstep{n} "netevent ws_walk; wait 70; wsstep{n + 1}"\n')
                continue
            shot = os.path.join(out, view + ".png").replace("\\", "/")
            f.write(f'alias wsstep{n} "netevent ws_view {i}; wait 30; screenshot \\"{shot}\\"; wait 5; wsstep{n + 1}"\n')
        f.write(f'alias wsstep{len(steps)} "quit"\n')
        f.write(f'wait 70; dd_tm_warp "{args.spot}"; wait {args.settle}; wsstep0\n')
    with open(os.path.join(out, "ws.ini"), "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth=960\nvid_defheight=540\n"
                "win_w=960\nwin_h=540\nvid_scalefactor=1\n")
    log = os.path.join(out, "log-ws.txt")
    for old_log in (log, os.path.join(out, "log-log-ws-txt.txt")):
        if os.path.exists(old_log):
            os.remove(old_log)
    sky = []
    for line in lines:
        sky += ["+dd_sky", line]
    command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--cwd", out, "--", args.exe, "-iwad", IWAD, "-noautoload",
               "-config", os.path.join(out, "ws.ini"), "-nomonsters", "-skill", "3", "-stdout",
               "-file", os.path.abspath(args.runtime), os.path.abspath(args.overworld), harness,
               "-ddtowncache", os.path.abspath(args.cache), "-ddconverter", os.path.abspath(args.converter), "-ddarena2", ARENA2,
               "+vid_fullscreen", "0", "+vid_scalemode", "5", "+vid_scale_customwidth", "960", "+vid_scale_customheight", "540",
               "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png", "+show_messages", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+wipetype", "0",
               "+logfile", "log-ws.txt", *sky, "+map", "DDOVER01", "+exec", "ws.cfg"]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=open(os.path.join(out, "ws.stdout"), "w"), stderr=subprocess.STDOUT)
    end, reason, text = time.time() + args.timeout + 5, "timeout", ""
    while time.time() < end:
        time.sleep(0.5)
        found = [p for p in (log, os.path.join(out, "log-log-ws-txt.txt")) if os.path.exists(p)]  # the engine may rename it
        text = open(found[0], errors="replace").read() if found else ""
        if any(k in text for k in FATAL):
            reason = "fatal"
            break
        if proc.poll() is not None:
            reason = "exited"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print(f"== {name}: {reason}")
    for line in text.splitlines():
        if line.startswith(("DDWEATHER exterior", "DDTM season", "DDTLOD", "DDTCACHE season")) or any(k in line for k in FATAL):
            print("  " + line[:220])
    return reason == "exited"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--runtime", required=True, help="ddruntime.pk3 (ground tile textures dfmesh/aNNNrRR.png)")
    ap.add_argument("--overworld", required=True, help="overworld.pk3, preferably with DDNATURE")
    ap.add_argument("--converter", required=True)
    ap.add_argument("--cache", help="town cache folder, default OUT/cache")
    ap.add_argument("--spot", default="26489 36672")
    ap.add_argument("--settle", type=int, default=420, help="tics after the warp before the first view (town conversion)")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--case", nargs="*", default=list(CASES))
    ap.add_argument("--walk", action="store_true", help="after the views, walk west about 36 tiles and take them again")
    ap.add_argument("--lights", action="store_true", help="after the views: a dynamic light on the ground, then light-amp")
    ap.add_argument("--flip", help="a sky line sent after the views (another season), then the views again")
    args = ap.parse_args()
    args.cache = args.cache or os.path.join(args.out, "cache")
    os.makedirs(args.cache, exist_ok=True)
    ok = True
    for name in args.case:
        ok &= run_case(args, name, CASES[name])
        if not ok:
            break  # stop on the first failure
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
