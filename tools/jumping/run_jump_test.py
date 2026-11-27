"""Paired jumping test: runs a play folder made by scripts/play/install.py with Daggerfall's sync test character, starting
in town (DDT07154) with DRLA, adds jump_probe.zs as its own pk3, and checks the probe's JUMPTEST lines:
  - jumping in place (with mid-air jumps) never does falling damage at any level and lands where it started;
  - mid-air jumps: 0 below 50, 1 at 50 to 99, 2 at 100;
  - the first rise grows with Jumping as the height factor 1 + s/100 + (s >= 25 ? 0.25 : 0) says (within 10%);
  - a 9 m drop and a walk off a real ledge do Daggerfall's falling damage (5 HP per metre past 5) below 75, none from 75;
  - Daggerfall's HP drops by that damage (hp before and after).

usage: run_jump_test.py <play folder> <run dir>      (the run folder is deleted and recreated)"""
import os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r"D:\dev\DoomDaggerfall\GameResources"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"


def main():
    play, run = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    if os.path.isdir(run):
        shutil.rmtree(run)
    os.makedirs(os.path.join(run, "saves"))
    pk3 = os.path.join(run, "probe.pk3")
    with zipfile.ZipFile(pk3, "w") as z:
        z.write(os.path.join(HERE, "jump_probe.zs"), "zscript/probe.zs")
        z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
        z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "DoomerfallJumpTest" }\n')
    data = os.path.join(play, "data")
    mods = [os.path.join(MODS, m) for m in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    mods += [os.path.join(data, m) for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3",
                                             "privateershold_doors.pk3")]
    mods += [os.path.join(play, "dfitems.pk3"), os.path.join(play, "doomerfall.pk3"), pk3]
    uz = ["-config", os.path.join(run, "uzdoom.ini"), "-savedir", os.path.join(run, "saves"), "-dfbridgelog", os.path.join(run, "uz.log"),
          "-ddtowncache", os.path.join(data, "cache"), "-ddconverter", os.path.join(data, "converter", "DungeonConverter.exe"),
          "-ddarena2", os.path.join(GAME, "DAGGER", "ARENA2"), "-skill", "3", "+map", "DDT07154", "+vid_fullscreen", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+logfile", "console.log"]
    df = ["-dfbridgelog", os.path.join(run, "df.log"), "-dfsynctest", os.path.join(GAME, "DAGGER"), "-screen-fullscreen", "0",
          "-screen-width", "1280", "-screen-height", "800"]
    cmd = [sys.executable, QUIET, "--timeout", "260", "--", os.path.join(play, "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", os.path.join(play, "uzdoom", "uzdoom.exe"), "--dfu", os.path.join(play, "dfu", "DaggerfallUnity.exe"),
           "--iwad", os.path.join(GAME, "wads", "DOOM2.WAD")]
    for m in mods:
        cmd += ["--mod", m]
    cmd += ["--uzdoom-cwd", run, "--log", os.path.join(run, "launcher.log")]
    for a in uz:
        cmd += ["--uzdoom-arg", a]
    for a in df:
        cmd += ["--dfu-arg", a]
    print(" ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    print("exit", r.returncode, "(124 is the expected timeout: the launcher keeps running)")

    lines = []
    for name in ("log-console-log.txt", "console.log", "uz.log", "df.log"):
        p = os.path.join(run, name)
        if os.path.exists(p):
            for l in open(p, errors="replace"):
                if re.search(r"JUMPTEST|DFJUMP|FATAL|Script error", l):
                    print(name, ":", l.rstrip())
                    if name in ("log-console-log.txt", "console.log") and "JUMPTEST" in l:
                        lines.append(l)
    sys.exit(check(lines))


def factor(s):
    s = max(0, min(100, s))
    return 1 + s / 100 + (0.25 if s >= 25 else 0)


def check(lines):
    fails = []
    jumps = {int(m.group(1)): m for m in (re.search(r"jump level=(\d+) firstrise=([\d.-]+) totalrise=([\d.-]+) airjumps=(\d+) landdz=([\d.-]+) falldamage=(\d+)", l) for l in lines) if m}
    falls = [m for m in (re.search(r"(drop|ledge) level=(\d+) fell=([\d.-]+) falldamage=(\d+) expected=(\d+) hp=(-?\d+)->(-?\d+)", l) for l in lines) if m]
    if not any("JUMPTEST done" in l for l in lines):
        fails.append("the probe did not finish")
    for s in (0, 25, 50, 75, 100):
        m = jumps.get(s)
        if not m:
            fails.append(f"no jump line at {s}")
            continue
        air, dmg, dz = int(m.group(4)), int(m.group(6)), float(m.group(5))
        want_air = 2 if s >= 100 else 1 if s >= 50 else 0
        if dmg != 0: fails.append(f"jumping in place hurt at {s}: {dmg}")
        if abs(dz) > 0.5: fails.append(f"jump at {s} landed {dz} from where it started")
        if air != want_air: fails.append(f"{air} mid-air jumps at {s}, want {want_air}")
        if 0 in jumps and s:
            ratio = float(m.group(2)) / float(jumps[0].group(2))
            if abs(ratio / factor(s) - 1) > 0.10: fails.append(f"rise at {s} is {ratio:.2f}x skill 0, want {factor(s):.2f}x")
    for m in falls:
        kind, s, fell, dmg, want, hp0, hp1 = m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(7))
        rule = 0 if s >= 75 else max(0, int(5 * (fell / 30 - 5)))
        if dmg != want or want != rule: fails.append(f"{kind} at {s}: fell {fell}, damage {dmg}, expected {want}, rule {rule}")
        if hp0 - hp1 != dmg: fails.append(f"{kind} at {s}: HP went {hp0}->{hp1}, not down by {dmg}")
    if sum(1 for m in falls if m.group(1) == "drop") != 5: fails.append("missing drop lines")
    if not any(m.group(1) == "ledge" and int(m.group(4)) > 0 for m in falls): fails.append("no ledge fall that hurt")
    for f in fails:
        print("FAIL", f)
    print("JUMP TEST", "PASS" if not fails else "FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    main()
