"""Stands the player where the old overworld sank deepest under a town's drawn ground, in the real game.

Usage: height_proof.py --exe UZDOOM --runtime DIR --out DIR
DIR holds ddruntime.pk3, town-cache, and converter. Runs the old raw heights and the fixed heights,
reports feet against the drawn mesh, and takes ground-level screenshots. Output is derived from game data.
"""
import argparse, os, shutil, subprocess, sys, zipfile

import height_audit as audit

HERE = os.path.dirname(os.path.abspath(__file__))
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORLD = r"D:\dev\DoomDaggerfall-build\stitch-data"

ZS = """version "4.14"
class HeightProof : EventHandler
{
	int view;
	override void NetworkProcess(ConsoleEvent e) { if (e.Name == "proofview") view = e.Args[0]; }
	override void WorldTick()
	{
		let p = players[0].mo;
		if (!p) return;
		double x = (@GX@ - CVar.FindCVar("dd_tm_originx").GetInt()) * 192.0 - 12288;
		double y = (@GY@ - CVar.FindCVar("dd_tm_originy").GetInt()) * 192.0 - 12288;
		p.SetOrigin((x, y, p.GetZAt(x, y, 0, GZF_ABSOLUTEPOS)), false);
		p.vel = (0, 0, 0);
		p.angle = view * 120;
		p.pitch = 12;
		if (level.maptime % 35 == 5)
			Console.Printf("PROOF map=%s intown=%d lod=%d z=%.3f", level.MapName, CVar.FindCVar("dd_tm_intown").GetInt(), CVar.FindCVar("dd_tm_neareststate").GetInt(), p.pos.z);
	}
}
"""


def pick_point(cache):
    """The vertex with the deepest old sink that is well outside every town's entry zone."""
    raw = audit.World(__import__("gen_overworld").world_lump(open(audit.WOODS, "rb").read()))
    best = (0, None, None, None)
    for path in sorted(os.listdir(cache)):
        if not path.endswith(".ddt"):
            continue
        lumps = audit.read_ddt(os.path.join(cache, path))
        rects = [tuple(int(v) for v in l.split()[1:5]) for l in lumps["DDTOWN"].decode().splitlines() if l.startswith("rect ")]
        for (gx, gy), z in audit.ground_vertices(lumps).items():
            if any(r[0] - 20 <= gx < r[1] + 20 and r[2] - 20 <= gy < r[3] + 20 for r in rects):
                continue
            sink = z - raw.doom_z(gx, gy)
            if sink > best[0]:
                best = (sink, path, (gx, gy), z)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    sink, town, (gx, gy), mesh_z = pick_point(os.path.join(args.runtime, "town-cache"))
    print(f"point {town} tile {gx},{gy}: drawn ground z={mesh_z:.3f}, old floor is {sink:.3f} below it")
    cache = os.path.join(args.out, "cache")
    os.makedirs(cache, exist_ok=True)
    shutil.copy2(os.path.join(args.runtime, "town-cache", town), cache)
    harness = os.path.join(args.out, "proof.pk3")
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", ZS.replace("@GX@", str(gx)).replace("@GY@", str(gy)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "HeightProof" }\n')
    ini = os.path.join(args.out, "proof.ini")
    with open(ini, "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth=1280\nvid_defheight=720\nwin_w=1280\nwin_h=720\nvid_scalefactor=1\n")
    for label, extra in (("before", ["--raw-world"]), ("after", ["--world-dir", WORLD])):
        over = os.path.join(args.out, label + "_overworld.pk3")
        subprocess.check_call([sys.executable, os.path.join(HERE, "gen_overworld.py"), "--out", over, "--start-tile", f"{gx - 64},{gy - 64}", "--packchance", "0"] + extra, stdout=subprocess.DEVNULL)
        cfg = os.path.join(args.out, label + ".cfg")
        with open(cfg, "w", newline="\n") as f:
            for i in range(3):
                shot = os.path.join(args.out, f"{label}_{i}.png").replace("\\", "/")
                f.write(f'alias step{i} "netevent proofview {i}; wait 12; screenshot \\"{shot}\\"; wait 6; step{i + 1}"\n')
            f.write('alias step3 "quit"\nwait 280; step0\n')
        name = "proof_" + label
        log = os.path.join(args.out, f"log-{name}.txt")
        if os.path.exists(log):
            os.remove(log)
        code = subprocess.run([sys.executable, QUIET, "--timeout", "30", "--cwd", args.out, "--", args.exe, "-iwad", IWAD,
                               "-file", os.path.join(args.runtime, "ddruntime.pk3"), over, harness, "-config", ini, "-ddtowncache", cache,
                               "-ddconverter", os.path.join(args.runtime, "converter", "DungeonConverter.exe"), "-ddarena2", ARENA2,
                               "-noactivate", "-nosound", "-noautoload", "-nomonsters", "-skill", "3", "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+wipetype", "0",
                               "+vid_scalemode", "5", "+vid_scale_customwidth", "1280", "+vid_scale_customheight", "720", "+screenblocks", "12", "+crosshair", "0", "+r_drawplayersprites", "0",
                               "+screenshot_type", "png", "+show_messages", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                               "+logfile", name, "+map", "DDOVER01", "+exec", cfg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).returncode
        body = open(log, errors="replace").read() if os.path.exists(log) else ""
        rows = [l for l in body.splitlines() if "PROOF" in l]
        errors = [l[:120] for l in body.splitlines() if "rror" in l or "FATAL" in l]
        print(label, "exit", code, rows[-1] if rows else "no position", "errors:", errors[:3])
        if rows:
            z = float(rows[-1].split("z=")[1])
            print(f"  feet minus drawn ground: {z - mesh_z:.3f}")


if __name__ == "__main__":
    main()
