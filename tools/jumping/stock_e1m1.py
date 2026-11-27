"""Stock DOOM.WAD E1M1 with a play folder's UZDoom and doomerfall.pk3, without and with DRLA (play_drlax.bat's set).
Runs each for a short while on a private desktop, then prints the log's errors and any DFJUMP line (there must be none:
the jumping code stays off on stock maps). usage: stock_e1m1.py <play folder> <out dir>"""
import os, re, shutil, subprocess, sys, zipfile

# A map or mod changing the player's JumpZ (here to 20 at tic 10) must keep it on a stock map.
PROBE = """class JumpZProbe : StaticEventHandler
{
	override void WorldTick()
	{
		let mo = players[consoleplayer].mo;
		if (!mo) return;
		if (level.maptime == 10) mo.JumpZ = 20;
		if (level.maptime == 100) Console.Printf("JUMPZPROBE %.3f", mo.JumpZ);
	}
}
"""

play, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
MODS = r"D:\dev\DoomDaggerfall\GameMods"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
drla = [os.path.join(MODS, m) for m in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
bad = 0
for name, extra in (("plain", []), ("drla", drla)):
    run = os.path.join(out, name)
    shutil.rmtree(run, ignore_errors=True)
    os.makedirs(run)
    probe = os.path.join(run, "jumpz_probe.pk3")
    with zipfile.ZipFile(probe, "w") as z:
        z.writestr("zscript/probe.zs", PROBE)
        z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
        z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "JumpZProbe" }\n')
    cmd = [sys.executable, QUIET, "--timeout", "30", "--cwd", run, "--", os.path.join(play, "uzdoom", "uzdoom.exe"), "-iwad", IWAD,
           "-file", *extra, os.path.join(play, "doomerfall.pk3"), probe, "-config", os.path.join(run, "u.ini"), "-skill", "3", "+map", "E1M1",
           "+logfile", "log", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
           "+dd_debugmessages", "1"]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logs = [f for f in os.listdir(run) if f.startswith("log")]  # UZDoom names +logfile's file log-<name>.txt in its folder
    log = open(os.path.join(run, logs[0]), errors="replace").read() if logs else ""
    entered = "E1M1" in log
    errs = [l for l in log.splitlines() if (re.search(r"doomerfall\.pk3.*(error|Attempt)|DFJUMP", l, re.I) or re.search(r"FATAL|VM execution aborted", l))]
    jz = re.search(r"JUMPZPROBE ([\d.]+)", log)
    if not jz or jz.group(1) != "20.000": errs.append("a JumpZ change was not kept: " + (jz.group(1) if jz else "no probe line"))
    print(f"{name}: entered E1M1={entered}, problems={len(errs)}, JumpZ after a change={jz.group(1) if jz else None}")
    for l in errs[:10]:
        print("   ", l)
    bad += (not entered) or bool(errs)
print("STOCK E1M1", "PASS" if not bad else "FAIL")
sys.exit(1 if bad else 0)
