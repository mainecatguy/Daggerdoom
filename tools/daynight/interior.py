"""Doom-only check that a building interior gets Daggerfall's interior look and no sky, rain or daylight.

usage: interior.py UZDOOM OUT "<dd_sky line>" ["<another line, e.g. fog>"]
Starts Gothway Garden (DDT07154), walks through the tavern door with the dd_tm_use test
hook, screenshots inside and outside, and prints the DDWEATHER lines. Runs through quiet_run, about 25 s.
"""
import os
import subprocess
import sys
import zipfile

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DATA = r"D:\dev\DoomDaggerfall-loop\review\doom-items\data"
CACHE = r"D:\dev\DoomDaggerfall-loop\review\daynight\cache"  # copy of the Doom items demo cache; the tavern converts on first use
CONVERTER = r"D:\dev\DoomDaggerfall-build\converter-daynight\DungeonConverter.exe"  # built from this worktree, so its cache format matches
DOOR = (-125.25, -14400.0, 9969.616, 0.0, 1.0)  # tavern 8325716 in DDT07154's DDDOORS: x y z nx ny

HARNESS = '''version "4.10"
class DNInterior : EventHandler
{
	override void WorldTick()
	{
		if (!players[0].mo || level.MapName != "DDT07154") return;
		let p = players[0].mo;
		if (level.maptime >= 20 && level.maptime % 35 == 20) { p.SetOrigin((@X@ + @NX@ * 48, @Y@ + @NY@ * 48, @Z@), false); p.angle = atan2(-@NY@, -@NX@); }
		if (level.maptime >= 32 && level.maptime % 35 == 32) CVar.FindCVar("dd_tm_use").SetInt(1);
	}
}
'''


def main():
    exe, out, sky = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]
    os.makedirs(out, exist_ok=True)
    x, y, z, nx, ny = DOOR
    harness = os.path.join(out, "dn_interior.pk3")
    with zipfile.ZipFile(harness, "w") as zf:
        zf.writestr("zscript.txt", HARNESS.replace("@X@", str(x)).replace("@Y@", str(y)).replace("@Z@", str(z)).replace("@NX@", str(nx)).replace("@NY@", str(ny)))
        zf.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DNInterior" }\n')
    shot = lambda name: os.path.join(out, name + ".png").replace("\\", "/")
    with open(os.path.join(out, "dn.cfg"), "w", newline="\n") as f:
        f.write(f'wait 25; screenshot "{shot("outside")}"; wait 300; screenshot "{shot("inside")}"; wait 10; quit\n')
    log = os.path.join(out, "log-dn.txt")
    if os.path.exists(log):
        os.remove(log)
    subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", out, "--", exe, "-iwad", IWAD, "-noautoload", "-nomonsters", "-skill", "3",
                     "-file", os.path.join(DATA, "ddruntime.pk3"), os.path.join(DATA, "overworld.pk3"), harness,
                     "-ddtowncache", CACHE, "-ddconverter", CONVERTER,
                     "-ddarena2", r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2", "+vid_fullscreen", "0", "+screenshot_type", "png",
                     "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+wipetype", "0",
                     "+logfile", "dn", "+dd_sky", sky] + [a for line in sys.argv[4:] for a in ("+dd_sky", line)] + ["+map", "DDT07154", "+exec", "dn.cfg"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    for line in text.splitlines():
        if line.startswith(("DDWEATHER", "DDLIGHTS interior", "DDTOWN active")) or "FATAL" in line:
            print(line[:200])


if __name__ == "__main__":
    main()
