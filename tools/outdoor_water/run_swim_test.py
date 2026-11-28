"""Paired test of Daggerfall's outdoor swimming in Doom (dd_bridge.cpp DD_BridgeOutdoorSwimming, DoomerfallSwim.zs,
DoomerfallSwimState.cs). Runs a play folder made by scripts/play/install.py like the fall exemption test (overworld
DDOVER01, DRLA, Daggerfall's sync test character) with swim_probe.zs. Checks:
  - on Daggerfall's water tile the player swims (Actor.DD_OutdoorSwimming), Daggerfall says so (df.log "swim state:
    swimming 1");
  - speed in water / on land = 1/4 + Swimming / 200 (PlayerSpeedChanger.GetSwimSpeed), within 2%;
  - the eye is at Daggerfall's swimming share, 0.21 / 1.71 of the standing eye, within 2%;
  - a jump in the water does not rise;
  - while in the water Daggerfall tallies Swimming (skill uses rise) and breath stays unchanged (no drowning outdoors);
  - back on land swimming ends and the eye height is restored.

usage: run_swim_test.py <play folder> <run dir> [--water DX DY] [--stay TICS]   (the run folder is deleted and recreated)"""
import argparse, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r"D:\dev\DoomDaggerfall\GameResources"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("play")
    ap.add_argument("run")
    ap.add_argument("--water", nargs=2, type=float, default=[-13749, 4537])
    ap.add_argument("--stay", type=int, default=35 * 45)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--map", default="DDOVER01")
    a = ap.parse_args()
    play, run = os.path.abspath(a.play), os.path.abspath(a.run)
    if os.path.isdir(run):
        shutil.rmtree(run)
    os.makedirs(os.path.join(run, "saves"))
    pk3 = os.path.join(run, "probe.pk3")
    dx, dy = a.water
    text = open(os.path.join(HERE, "swim_probe.zs")).read().replace("@WATER_DX@", f"{dx:.1f}") \
        .replace("@WATER_DY@", f"{dy:.1f}").replace("@STAY_TICS@", str(a.stay))
    with zipfile.ZipFile(pk3, "w") as z:
        z.writestr("zscript/probe.zs", text)
        z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
        z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "DoomerfallSwimTest" }\n')
    data = os.path.join(play, "data")
    mods = [os.path.join(MODS, m) for m in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    mods += [os.path.join(data, m) for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3",
                                             "privateershold_doors.pk3")]
    mods += [os.path.join(play, "dfitems.pk3"), os.path.join(play, "doomerfall.pk3"), pk3]
    uz = ["-config", os.path.join(run, "uzdoom.ini"), "-savedir", os.path.join(run, "saves"), "-dfbridgelog", os.path.join(run, "uz.log"),
          "-ddtowncache", os.path.join(data, "cache"), "-ddconverter", os.path.join(data, "converter", "DungeonConverter.exe"),
          "-ddarena2", os.path.join(GAME, "DAGGER", "ARENA2"), "-skill", "3", "+map", a.map, "+vid_fullscreen", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+logfile", "console.log"]
    df = ["-dfbridgelog", os.path.join(run, "df.log"), "-dfsynctest", os.path.join(GAME, "DAGGER"), 
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

    lines, swim = [], []
    for name in ("log-console-log.txt", "uz.log", "df.log"):
        p = os.path.join(run, name)
        if not os.path.exists(p):
            continue
        for l in open(p, errors="replace"):
            if re.search(r"SWIMTEST|DFSWIM|FATAL|Script error|swim state|fall state", l):
                print(name, ":", l.rstrip())
            if name == "log-console-log.txt" and "SWIMTEST" in l:
                lines.append(l)
            if name == "df.log" and "swim state:" in l:
                swim.append(l)
    sys.exit(check(lines, swim))


def num(pattern, text, cast=float):
    m = re.search(pattern, text)
    return cast(m.group(1)) if m else None


def check(lines, swim):
    fails = []
    text = "".join(lines)
    if "SWIMTEST done" not in text:
        fails.append("the probe did not finish")
    land = next((l for l in lines if "SWIMTEST land" in l), "")
    water = next((l for l in lines if "SWIMTEST water speed" in l), "")
    jump = next((l for l in lines if "SWIMTEST jump" in l), "")
    back = next((l for l in lines if "SWIMTEST back" in l), "")
    skill = num(r"Swimming=(-?\d+)", water, int)
    if num(r"swimming=(\d)", land, int) != 0:
        fails.append(f"swimming on dry land: {land.strip()}")
    if not water or num(r"swimming=(\d)", water, int) != 1:
        fails.append(f"not swimming in the water: {water.strip() or 'no water line'}")
    else:
        want = 0.25 + max(0, skill) / 200
        ratio = num(r"ratio=([\d.]+)", water)
        if abs(ratio - want) > 0.02 * want:
            fails.append(f"speed ratio {ratio} want {want:.4f} (Swimming {skill})")
        eye = num(r"eye_ratio=([\d.]+)", water)
        if abs(eye - 0.21 / 1.71) > 0.02 * 0.21 / 1.71:
            fails.append(f"eye ratio {eye} want {0.21 / 1.71:.4f}")
    if not jump or num(r"rise=(-?[\d.]+)", jump) > 0.5:
        fails.append(f"jumped in the water: {jump.strip() or 'no jump line'}")
    if not back or num(r"swimming=(\d)", back, int) != 0 or abs(num(r" eye=([\d.]+)", back) - num(r"land_eye=([\d.]+)", back)) > 0.01:
        fails.append(f"back on land: {back.strip() or 'no back line'}")
    on = [l for l in swim if "swimming 1" in l]
    off = [l for l in swim if "swimming 0" in l]
    if not on or not off:
        fails.append("Daggerfall did not see swimming start and stop")
    else:
        u0, u1 = num(r"uses (-?\d+)", on[0], int), num(r"uses (-?\d+)", off[-1], int)
        b0, b1 = num(r"breath (-?\d+)", on[0], int), num(r"breath (-?\d+)", off[-1], int)
        print(f"Daggerfall: Swimming uses {u0} -> {u1}, breath {b0} -> {b1}")
        if u1 <= u0:
            fails.append("Swimming was not tallied in the water")
        if b1 != b0:
            fails.append("breath changed outdoors")
    for f in fails:
        print("FAIL", f)
    print("SWIM TEST", "PASS" if not fails else "FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    main()
