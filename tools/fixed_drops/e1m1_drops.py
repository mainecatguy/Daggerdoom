"""Stock drop check for the summoned-drops rule: DOOM.WAD E1M1, stock and with the DRLA set, no bridge session.
A tiny harness kills every monster at tic 35 (credited to the player), waits 5 s and lists the new loose items.
Stock E1M1's ZombieMen and ShotgunGuys always drop, so stock counts must match between builds exactly.

usage: e1m1_drops.py <uzdoom.exe> <label>
"""
import re
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
OUT = Path(r"D:\dev\DoomDaggerfall-loop\review\summoned-e1m1")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
HARNESS = """version "4.14"
class EDHarness : EventHandler
{
	int timer;
	Array<Actor> before;
	override void WorldTick()
	{
		timer++;
		if (!players[0].mo) return;
		players[0].cheats |= CF_GODMODE;
		if (timer == 35)
		{
			let it = ThinkerIterator.Create("Actor");
			Actor a;
			int n = 0;
			while (a = Actor(it.Next())) if (a is "Inventory" && !Inventory(a).Owner) before.Push(a);
			it = ThinkerIterator.Create("Actor");
			while (a = Actor(it.Next()))
				if (a.bISMONSTER && a.health > 0) { a.DamageMobj(players[0].mo, players[0].mo, 100000, 'None', DMG_FORCED); n++; }
			Console.Printf("EDKILLED %d", n);
		}
		if (timer == 35 * 6)
		{
			let it = ThinkerIterator.Create("Inventory");
			Inventory a;
			while (a = Inventory(it.Next())) if (!a.Owner && before.Find(a) == before.Size()) Console.Printf("EDDROP %s", a.GetClassName());
			Console.Printf("EDDONE");
		}
	}
}
"""

uz, label = sys.argv[1], sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
harness = OUT / "e1m1-drops.pk3"
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", HARNESS)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "EDHarness" }\n')
for name, files in (("stock", []), ("drla", [str(MODS / f) for f in DRLA])):
    tag = f"{label}-{name}"
    log = OUT / f"log-{tag}.txt"
    log.unlink(missing_ok=True)
    args = [uz, "-iwad", r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD", "-file", *files, str(harness),
            "-noautoload", "-config", str(OUT / "e1m1.ini"), "-skill", "3", "+logfile", tag, "+vid_fullscreen", "0",
            "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "E1M1", "+wait 300;quit"]
    code = subprocess.call([sys.executable, QUIET, "--timeout", "40", "--cwd", str(OUT), "--", *args],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    bad = [k for k in ("VM execution aborted", "Unhandled exception", "FATAL", "Script error") if k in body]
    drops = Counter(re.findall(r"^EDDROP (\S+)", body, re.M))
    killed = re.findall(r"^EDKILLED (\d+)", body, re.M)
    print(f"{tag}: exit {code}, killed {killed}, done {'EDDONE' in body}, errors {bad or 'none'}, DDLOOT lines {body.count('DDLOOT')}, "
          f"{sum(drops.values())} drops {dict(sorted(drops.items()))}")
