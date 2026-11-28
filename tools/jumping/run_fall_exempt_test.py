"""Paired test of Daggerfall's falling damage exemptions in Doom (DoomerfallFallState.cs -> dfb_df_state.player_flags ->
DoomerfallJump.zs). Runs a play folder made by scripts/play/install.py like run_jump_test.py (town DDT07154, DRLA,
Daggerfall's sync test character), with Daggerfall's -dffalltest (Slowfall on and off every 20 s, water tile reports)
and fall_exempt_probe.zs. Checks, at Jumping 0, for 9 m drops:
  - with Slowfall reported by Daggerfall: no damage;
  - after it ends: the falling damage rule (5 HP a metre past 1.5 jump heights: 36 HP at Jumping 0), and
    Daggerfall's HP drops by it;
  - with --water DX DY (an offset in Doom units from the start, from an earlier run's "fall test: ... nearest" line):
    over outdoor water, no damage.

usage: run_fall_exempt_test.py <play folder> <run dir> [--water DX DY]      (the run folder is deleted and recreated)"""
import argparse, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r"D:\dev\DoomDaggerfall\GameResources"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("play")
    ap.add_argument("run")
    ap.add_argument("--water", nargs=2, type=float)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--map", default="DDT07154", help="DDT07154 (town) or DDOVER01 (overworld)")
    a = ap.parse_args()
    play, run = os.path.abspath(a.play), os.path.abspath(a.run)
    if os.path.isdir(run):
        shutil.rmtree(run)
    os.makedirs(os.path.join(run, "saves"))
    pk3 = os.path.join(run, "probe.pk3")
    dx, dy = a.water or (0.0, 0.0)
    text = open(os.path.join(HERE, "fall_exempt_probe.zs")).read().replace("@WATER_DX@", f"{dx:.1f}") \
        .replace("@WATER_DY@", f"{dy:.1f}").replace("@HAVE_WATER@", "1" if a.water else "0")
    with zipfile.ZipFile(pk3, "w") as z:
        z.writestr("zscript/probe.zs", text)
        z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
        z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "DoomerfallFallExemptTest" }\n')
    data = os.path.join(play, "data")
    mods = [os.path.join(MODS, m) for m in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    mods += [os.path.join(data, m) for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3",
                                             "privateershold_doors.pk3")]
    mods += [os.path.join(play, "dfitems.pk3"), os.path.join(play, "doomerfall.pk3"), pk3]
    uz = ["-config", os.path.join(run, "uzdoom.ini"), "-savedir", os.path.join(run, "saves"), "-dfbridgelog", os.path.join(run, "uz.log"),
          "-ddtowncache", os.path.join(data, "cache"), "-ddconverter", os.path.join(data, "converter", "DungeonConverter.exe"),
          "-ddarena2", os.path.join(GAME, "DAGGER", "ARENA2"), "-skill", "3", "+map", a.map, "+vid_fullscreen", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+logfile", "console.log"]
    df = ["-dfbridgelog", os.path.join(run, "df.log"), "-dfsynctest", os.path.join(GAME, "DAGGER"), "-dffalltest",
          "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    cmd = [sys.executable, QUIET, "--timeout", str(a.timeout), "--", os.path.join(play, "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", os.path.join(play, "uzdoom", "uzdoom.exe"), "--dfu", os.path.join(play, "dfu", "DaggerfallUnity.exe"),
           "--iwad", os.path.join(GAME, "wads", "DOOM2.WAD")]
    for m in mods:
        cmd += ["--mod", m]
    cmd += ["--uzdoom-cwd", run, "--log", os.path.join(run, "launcher.log")]
    for x in uz:
        cmd += ["--uzdoom-arg", x]
    for x in df:
        cmd += ["--dfu-arg", x]
    r = subprocess.run(cmd)
    print("exit", r.returncode, "(124 is the expected timeout: the launcher keeps running)")

    lines, water = [], []
    for name in ("log-console-log.txt", "uz.log", "df.log"):
        p = os.path.join(run, name)
        if not os.path.exists(p):
            continue
        for l in open(p, errors="replace"):
            if re.search(r"FALLTEST|DFJUMP|FATAL|Script error|fall state|fall test", l):
                print(name, ":", l.rstrip())
            if name == "log-console-log.txt" and "FALLTEST" in l:
                lines.append(l)
            if name == "df.log" and "nearest" in l:
                water.append(l)
    sys.exit(check(lines, water, bool(a.water)))


def check(lines, water, want_water):
    fails = []
    got = {m.group(1): m for m in (re.search(r"FALLTEST (\w+) fell=([\d.-]+) falldamage=(\d+) rule=(\d+) flags_at_drop=(\d+) "
                                             r"flags_now=(\d+) hp=(-?\d+)->(-?\d+) safe=([\d.]+)", l) for l in lines) if m}
    if not any("FALLTEST done" in l for l in lines):
        fails.append("the probe did not finish")
    m = got.get("slowfall_on")
    if not m:
        fails.append("no Slowfall drop")
    elif not int(m.group(5)) & 1 or not int(m.group(6)) & 1 or int(m.group(3)) != 0 or int(m.group(7)) != int(m.group(8)):
        fails.append(f"Slowfall drop: {m.group(0)}")
    m = got.get("slowfall_off")
    if not m:
        fails.append("no drop after Slowfall")
    else:
        fell, dmg, rule, hp0, hp1 = float(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(7)), int(m.group(8))
        if int(m.group(5)) & 1 or dmg != rule or rule != max(0, int(5 * ((fell - float(m.group(9))) / 30))) or rule == 0 or hp0 - hp1 != dmg:
            fails.append(f"drop after Slowfall: {m.group(0)}")
    if want_water:
        m = got.get("water")
        if not m:
            fails.append("no water drop")
        elif not int(m.group(5)) & 2 or (int(m.group(5)) | int(m.group(6))) & 1 or int(m.group(3)) != 0 or int(m.group(4)) == 0 or int(m.group(7)) != int(m.group(8)):
            fails.append(f"water drop: {m.group(0)}")
    if water:
        print("last water report:", water[-1].strip())
    for f in fails:
        print("FAIL", f)
    print("FALL EXEMPT TEST", "PASS" if not fails else "FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    main()
