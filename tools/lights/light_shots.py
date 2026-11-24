"""Screenshots and frame times at fixed viewpoints in a converted Daggerfall place, through quiet_run.

Usage: python light_shots.py --exe UZDOOM --out DIR --map MAP --views VIEWS [--files PK3 ...] [--doom-args ...]
VIEWS: one "id x y z yaw pitch" line per viewpoint, in Doom map units (z is the eye). Lines starting with # are skipped.
For each viewpoint the player is moved there and frozen, and after a settle time the harness counts rendered frames
for --measure seconds and logs "LTFPS id frames ms". A screenshot <id>.png is written first.
The frame rate is uncapped (vid_maxfps 0, no vsync). quiet_run keeps the window minimized on a private desktop, so
UZDoom renders at its minimized size unless the scene is scaled (vid_scalemode 5 with a custom size, the default here).
"""
import argparse
import os
import re
import subprocess
import sys
import time
import zipfile

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")

HARNESS = r'''version "4.10"
class LTHarness : EventHandler
{
	Array<double> views;	// x y z yaw pitch, five per view
	int current, changedAt;
	ui int uiView, frames, startMs;
	ui bool counting;

	override void WorldLoaded(WorldEvent e)
	{
		current = -1;
		int lump = Wads.CheckNumForFullName("LTVIEWS");
		if (lump < 0) return;
		Array<String> rows;
		Wads.ReadLump(lump).Split(rows, "\n", TOK_SKIPEMPTY);
		foreach (row : rows)
		{
			Array<String> f;
			row.Split(f, " ", TOK_SKIPEMPTY);
			if (f.Size() < 5) continue;
			for (int i = 0; i < 5; i++) views.Push(f[i].ToDouble());
		}
	}

	override void NetworkProcess(ConsoleEvent e)
	{
		if (e.Name != "lt_view") return;
		current = e.Args[0];
		changedAt = gametic;
	}

	override void WorldTick()
	{
		if (!playeringame[0] || !players[0].mo || current < 0 || current * 5 + 4 >= views.Size()) return;
		let p = players[0].mo;
		players[0].cheats |= CF_GODMODE | CF_NOCLIP | CF_FLY;
		p.bNOTARGET = true;
		p.SetOrigin((views[current * 5], views[current * 5 + 1], views[current * 5 + 2] - players[0].viewheight), false);
		p.vel = (0, 0, 0);
		p.angle = views[current * 5 + 3];
		p.pitch = views[current * 5 + 4];
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (current != uiView) { uiView = current; counting = false; frames = 0; return; }
		if (current < 0) return;
		int since = gametic - changedAt;
		if (since == @SETTLE@ && !counting) { counting = true; frames = 0; startMs = MSTime(); }
		else if (counting) frames++;
		if (counting && since >= @SETTLE@ + @MEASURE@)
		{
			Console.Printf("LTFPS %d %d %d", current, frames, MSTime() - startMs);
			counting = false;
			uiView = -2;
		}
	}
}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--views", required=True)
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--doom-args", nargs="*", default=[])
    ap.add_argument("--measure", type=float, default=3, help="seconds of frame counting per view")
    ap.add_argument("--size", default="960x720", help="scene size (vid_scalemode 5); 'window' renders at the window size")
    ap.add_argument("--start-wait", type=int, default=140, help="tics before the first view")
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("--cache", help="runtime town cache folder (-ddtowncache), for generated towns and interiors")
    ap.add_argument("--converter", help="DungeonConverter.exe the engine runs for uncached places (-ddconverter)")
    args = ap.parse_args()
    if args.cache:
        args.doom_args = ["-ddtowncache", os.path.abspath(args.cache), "-ddarena2", r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"] + \
            (["-ddconverter", os.path.abspath(args.converter)] if args.converter else []) + args.doom_args

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    views = [l.split() for l in open(args.views) if l.strip() and not l.startswith("#")]
    settle, measure = 35, int(args.measure * 35)
    harness = os.path.join(out, "lt_harness.pk3")
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", HARNESS.replace("@SETTLE@", str(settle)).replace("@MEASURE@", str(measure)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LTHarness" }\n')
        z.writestr("LTVIEWS", "".join(" ".join(v[1:6]) + "\n" for v in views))
    with open(os.path.join(out, "lt.cfg"), "w", newline="\n") as f:
        for i, v in enumerate(views):
            shot = os.path.join(out, v[0] + ".png").replace("\\", "/")
            f.write(f'alias ltstep{i} "netevent lt_view {i}; wait {settle - 5}; screenshot \\"{shot}\\"; wait {measure + 15}; ltstep{i + 1}"\n')
        f.write(f'alias ltstep{len(views)} "quit"\nwait {args.start_wait}; dd_lights_status; ltstep0\n')
    width, height = (960, 720) if args.size == "window" else map(int, args.size.split("x"))
    with open(os.path.join(out, "lt.ini"), "w", newline="\n") as f:
        f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth={width}\nvid_defheight={height}\n"
                f"win_w={width}\nwin_h={height}\nvid_scalefactor=1\n")
    scale = [] if args.size == "window" else ["+vid_scalemode", "5", "+vid_scale_customwidth", str(width), "+vid_scale_customheight", str(height)]
    log = os.path.join(out, "log-lt.txt")
    if os.path.exists(log):
        os.remove(log)
    timeout = args.timeout or int(30 + len(views) * (args.measure + 2.5))
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--cwd", out, "--", args.exe, "-iwad", IWAD, "-noautoload",
               "-config", os.path.join(out, "lt.ini"), "-nomonsters", "-skill", "3", "-stdout", "-file", *[os.path.abspath(p) for p in args.files], harness,
               "+vid_fullscreen", "0", "+vid_maxfps", "0", "+vid_vsync", "0", "+cl_capfps", "0", *scale, "+screenblocks", "12", "+crosshair", "0",
               "+screenshot_type", "png", "+show_messages", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
               "+wipetype", "0", "+logfile", "lt", *args.doom_args, "+map", args.map, "+exec", "lt.cfg"]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=open(os.path.join(out, "lt.stdout"), "w"), stderr=subprocess.STDOUT)
    end, reason, text = time.time() + timeout + 5, "timeout", ""
    while time.time() < end:
        time.sleep(0.5)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        if any(k in text for k in FATAL):
            reason = "fatal"
            break
        if proc.poll() is not None:
            reason = "exited"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in text.splitlines():
        if line.startswith(("DFDLIGHTS", "DDLIGHTS", "DFDFLATS", "DDTOWN")) or any(k in line for k in FATAL):
            print(line[:200])
    for m in re.finditer(r"LTFPS (\d+) (\d+) (\d+)", text):
        i, frames, ms = (int(g) for g in m.groups())
        print(f"{views[i][0]}: {frames} frames in {ms} ms = {frames * 1000 / max(ms, 1):.0f} fps, {ms / max(frames, 1):.2f} ms/frame")
    return 0 if reason == "exited" else 1


if __name__ == "__main__":
    sys.exit(main())
