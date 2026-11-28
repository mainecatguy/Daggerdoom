"""Paired jumping test: runs a play folder made by scripts/play/install.py with Daggerfall's sync test character, starting
in town (DDT07154) with DRLA, adds jump_probe.zs as its own pk3, and checks the probe's JUMPTEST lines:
  - jumping in place (with mid-air jumps) never does falling damage at any level and lands where it started;
  - mid-air jumps: 0 below 50, 1 at 50 to 99, 2 at 100;
  - the first rise grows with Jumping as the height factor 1 + s/100 + (s >= 25 ? 0.25 : 0) says (within 10%);
  - the safe fall height is 1.5 times the measured jump height (first rise) at every level (jumpfollowup 01, owner Q&A
    item 6); a drop just under it does no damage, a drop 1.1 m over it does 5 HP, and a 9 m drop and a
    walk off a real ledge do 5 HP per metre past it;
  - Daggerfall's HP drops by that damage (hp before and after);
  - walking off the ledge without jumping still allows the double jump at 75 (none at 0) (Q&A item 8);
  - every jump, from the ground or in mid-air, adds one Jumping use in Daggerfall (Q&A item 7): Daggerfall's
    "skillxp: ... 1 uses of skill 3" lines match the jumps the probe made;
  - with a high-jump power (Strength 2, as DRLA's Antigrav boots) at Jumping 0, the safe fall is still 1.5 times the
    measured (about 4 times higher) jump, with the same edge drops.

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
    cmd = [sys.executable, QUIET, "--timeout", "330", "--", os.path.join(play, "doomerfall-launcher.exe"), "--minimized", "--nodraw",
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
    global all_lines
    for name in ("log-console-log.txt", "console.log", "uz.log", "df.log"):
        p = os.path.join(run, name)
        if os.path.exists(p):
            for l in open(p, errors="replace"):
                if name == "df.log" and re.search(r"skillxp: .*uses of skill 3,", l):
                    all_lines.append(l)
                if re.search(r"JUMPTEST|DFJUMP|FATAL|Script error", l):
                    print(name, ":", l.rstrip())
                    all_lines.append(l)
                    if name in ("log-console-log.txt", "console.log") and "JUMPTEST" in l:
                        lines.append(l)
    sys.exit(check(lines))


all_lines = []


def factor(s):
    s = max(0, min(100, s))
    return 1 + s / 100 + (0.25 if s >= 25 else 0)


def check(all_test_lines):
    fails = []
    lines = [l for l in all_test_lines if "JUMPTEST boots" not in l]
    boots = [l.replace("JUMPTEST boots", "JUMPTEST") for l in all_test_lines if "JUMPTEST boots" in l]
    fails += check_boots(boots)
    jumps = {int(m.group(1)): m for m in (re.search(r"jump level=(\d+) firstrise=([\d.-]+) totalrise=([\d.-]+) airjumps=(\d+) landdz=([\d.-]+) falldamage=(\d+)", l) for l in lines) if m}
    falls = [m for m in (re.search(r"(drop|edge|ledge) level=(\d+) fell=([\d.-]+) falldamage=(\d+) expected=(\d+) hp=(-?\d+)->(-?\d+) safe=([\d.]+)", l) for l in lines) if m]
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
    edges = {}
    for m in falls:
        kind, s, fell, dmg, want, hp0, hp1, safe = m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(7)), float(m.group(8))
        rule = max(0, int(5 * ((fell - safe) / 30)))
        if dmg != want or want != rule: fails.append(f"{kind} at {s}: fell {fell}, safe {safe}, damage {dmg}, expected {want}, rule {rule}")
        if hp0 - hp1 != dmg: fails.append(f"{kind} at {s}: HP went {hp0}->{hp1}, not down by {dmg}")
        if s in jumps and abs(safe - 1.5 * float(jumps[s].group(2))) > 1.0:
            fails.append(f"{kind} at {s}: safe fall {safe}, not 1.5 x the jump height {jumps[s].group(2)}")
        if kind == "edge":
            edges.setdefault(s, []).append((fell, safe, dmg))
        if kind != "edge" and dmg == 0: fails.append(f"{kind} at {s}: fell {fell} past the safe {safe} and did no damage")
    for s in (0, 25, 50, 75, 100):
        e = edges.get(s, [])
        if len(e) != 2 or e[0][2] != 0 or e[0][0] >= e[0][1] or e[1][2] != 5:
            fails.append(f"safe fall edge at {s}: {e}, want no damage just under and 5 HP 1.1 m over")
    if sum(1 for m in falls if m.group(1) == "drop") != 5: fails.append("missing drop lines")
    for l in lines:
        m = re.search(r"ledge level=(\d+) .* airjumps=(\d+)", l)
        if m and int(m.group(2)) != (1 if int(m.group(1)) >= 50 else 0):
            fails.append(f"walked off a ledge at {m.group(1)}: {m.group(2)} mid-air jumps")
    tot = [int(m.group(1)) for m in (re.search(r"jumps total=(\d+)", l) for l in lines) if m]
    tallies = sum(1 for l in all_lines if re.search(r"skillxp: .*; 1 uses of skill 3,", l))
    if not tot or tot[0] != tallies or tallies < 10:
        fails.append(f"Jumping uses: Daggerfall tallied {tallies} jumps, the probe made {tot}")
    mj = [re.search(r"modjumpz got=([\d.]+)", l) for l in lines]
    mj = [m for m in mj if m]
    if not mj or abs(float(mj[0].group(1)) - 15) > 0.01: fails.append("a mod's JumpZ change was not kept and scaled")
    if not any(m.group(1) == "ledge" and int(m.group(4)) > 0 for m in falls): fails.append("no ledge fall that hurt")
    for f in fails:
        print("FAIL", f)
    print("JUMP TEST", "PASS" if not fails else "FAIL")
    return 1 if fails else 0


def check_boots(lines):
    """The high-jump pass at Jumping 0: jump about 4x the plain 36 units, safe fall 1.5x the measured jump."""
    fails = []
    if not any("power=1" in l for l in lines):
        return ["the boots pass did not get its high-jump power"]
    j = [m for m in (re.search(r"jump level=0 firstrise=([\d.-]+)", l) for l in lines) if m]
    if not j:
        return ["no boots jump line"]
    rise = float(j[0].group(1))
    if rise < 3.5 * 36:
        fails.append(f"boots jump rose {rise}, want about 4 x 36")
    falls = [m for m in (re.search(r"(drop|edge) level=0 fell=([\d.-]+) falldamage=(\d+) expected=(\d+) hp=(-?\d+)->(-?\d+) safe=([\d.]+)", l) for l in lines) if m]
    edges = []
    for m in falls:
        kind, fell, dmg, want, hp0, hp1, safe = m.group(1), float(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), float(m.group(7))
        rule = max(0, int(5 * ((fell - safe) / 30)))
        if dmg != want or want != rule: fails.append(f"boots {kind}: fell {fell}, safe {safe}, damage {dmg}, expected {want}, rule {rule}")
        if hp0 - hp1 != dmg: fails.append(f"boots {kind}: HP went {hp0}->{hp1}, not down by {dmg}")
        if abs(safe - 1.5 * rise) > 1.0: fails.append(f"boots {kind}: safe fall {safe}, not 1.5 x the jump height {rise}")
        if kind == "edge": edges.append((fell, safe, dmg))
    if len(edges) != 2 or edges[0][2] != 0 or edges[0][0] >= edges[0][1] or edges[1][2] != 5:
        fails.append(f"boots safe fall edge: {edges}, want no damage just under and 5 HP 1.1 m over")
    return fails


if __name__ == "__main__":
    main()
