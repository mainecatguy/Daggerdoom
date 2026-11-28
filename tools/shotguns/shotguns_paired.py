"""Shotguns perks, Daggerfall and Doom together: Daggerfall's skill decides the rules, Doom applies them, and a knocked
enemy slams into a wall.

usage: shotguns_paired.py <play folder> assemble <base play folder> <uzdoom build Release dir> <bridge dll> <launcher exe>
       shotguns_paired.py <play folder> run [map, default MAP01]

  assemble  as tools/automatics/automatics_paired.py (this repo's Unity build, this branch's UZDoom, doomerfall.pk3 and
            bridge DLL), plus this branch's launcher.
  run       Daggerfall (its city save) with Doom on MAP01, -dfperktest Shotguns -dfperksteps 20,26,50,75,100 twice. The Doom harness
            (shotguns_paired.zs) fires DRLA's Double Shotgun once per cycle at a target 40 units from a wall.
Checks: Doom read the rules DoomerfallRules.zs gives for each skill; below 75 no knockback; at 75 and 100 the
target is knocked, staggers and slams into the wall once for up to 200 / 400. Wrap the whole script in quiet_run.py.
Output goes to <play folder>/../shotguns-paired.
"""
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "automatics"))
import automatics_paired as ap  # noqa: E402
pp, ng = ap.pp, ap.ng

TIMEOUT = 200
# DDOVER01 (the Daggerfall city) was tried first: no wall was reachable from its start before the town loaded, and
# the far wall the probe found was the edge of the loaded overworld window, which moves when the treadmill recenters
# (work/notes/20261127-033904.md). Doom 2 MAP01 has real walls next to the start.
MAP = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "run" else "MAP01"
STEPS = "20,26,50,75,100,20,26,50,75,100"  # twice: the town (and its walls) loads well after the first steps
KNOCK = re.compile(r"shotguns: knock (\S+) pellets (\d+) share ([\d.]+) size ([\d.]+) speed ([\d.]+)( stagger)?")
SLAM = re.compile(r"shotguns: slam (\S+) speed share ([\d.]+) damage (\d+) \(most (\d+)\)")


def rules(skill):
    s = max(0, min(skill, 100))
    most, knock = skill >= 100, skill >= 75
    return {"dmg": 7500 * s // 100, "reload": 3500 if skill >= 25 else 0, "pellets": 10000 if most else 5000 if skill >= 50 else 0,
            "knock": 20000 if most else 10000 if knock else 0, "slam": 400 if most else 200 if knock else 0, "collide": 0}


def run(play, out):
    harness = out / "shotpair-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(HERE / "shotguns_paired.zs", "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ShotPairHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-shotpair.txt", out / "launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / "shotpair.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "shotpair", "+vid_fullscreen", "0", "+wipetype", "0", "+set", "dd_perklog", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-skill", "3", "+map", MAP]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
          "-dfsynctest", ng.DAGGER, "-dfperktest", "Shotguns", "-dfperksteps", STEPS]
    command = [str(play / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD,
               "--uzdoom-cwd", str(out), "--log", str(launcher)]
    for mod in pp.DRLA + [data / n for n in pp.DATA] + [play / "dfitems.pk3", play / "doomerfall.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline, hwnd, clicked, fatal = time.time() + TIMEOUT, None, 0, False
    try:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.3)
            text, uzt, dft = ng.read(console), ng.read(uz_log), ng.read(df_log)
            if any(k in text for k in pp.FATAL) or re.search(r"Script error.*(shotpair-harness|doomerfall\.pk3)", text) or "PAIRED nospot" in text:
                fatal = True
                break
            hwnd = hwnd or ng.doom_window(launcher)
            opened = dft.count("ui: menu 7 opened")
            if hwnd and opened > clicked:
                time.sleep(1.0)
                size = re.findall(r"opened menu 7 at (\d+)x(\d+)", uzt)
                if size:
                    ng.SURFACE[:] = [int(size[-1][0]), int(size[-1][1])]
                ng.click(hwnd, 160, 100)
                clicked = opened
            whole = {int(x) for x in re.findall(r"PAIRED end \d+ skill=(\d+) ", text)}
            if {26, 50, 75, 100} <= whole and len(re.findall(r"PAIRED end \d+ skill=100 ", text)) >= 2:
                break
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    analyse(out, ng.read(console), ng.read(df_log), fatal)


def analyse(out, text, dft, fatal):
    report, checks = [], {}

    def check(name, ok, detail=""):
        checks[name] = checks.get(name, True) and bool(ok)
        if not ok:
            report.append(f"FAIL {name}: {detail}")

    check("no fatal or script error, wall found", not fatal)
    cycles, cur = [], None
    for l in text.splitlines():
        if m := re.search(r"PAIRED start (\d+) skill=(-?\d+) dmg=(-?\d+) reload=(-?\d+) pellets=(-?\d+) knock=(-?\d+) slam=(-?\d+) collide=(-?\d+)", l):
            keys = ("dmg", "reload", "pellets", "knock", "slam", "collide")
            cur = {"skill": int(m.group(2)), "read": {k: int(m.group(3 + i)) for i, k in enumerate(keys)}, "knock": [], "slam": []}
            cycles.append(cur)
        elif cur and (k := KNOCK.search(l)):
            cur["knock"].append(k)
        elif cur and (s := SLAM.search(l)):
            cur["slam"].append(s)
        elif cur and (e := re.search(r"PAIRED end \d+ skill=(-?\d+) moved=([\d.]+) pain=(\d) lost=(\d+)", l)):
            cur["end"] = {"skill": int(e.group(1)), "moved": float(e.group(2)), "pain": e.group(3) == "1", "lost": int(e.group(4))}
            cur = None
    done = [c for c in cycles if "end" in c and c["end"]["skill"] == c["skill"]]
    seen = sorted({c["skill"] for c in done})
    report.append(f"skills seen in whole cycles: {seen}")
    check("cycles at 26, 50, 75 and 100", all(s in seen for s in (26, 50, 75, 100)), seen)
    slams = 0
    for c in done:
        want = rules(c["skill"])
        check("Doom read Daggerfall's rules for the skill", c["read"] == want, f"skill {c['skill']}: read {c['read']} want {want}")
        e = c["end"]
        if want["knock"]:
            ok = len(c["knock"]) == 1 and len(c["slam"]) == 1 and e["pain"] and int(c["slam"][0].group(4)) == want["slam"]
            ok = ok and 0 < int(c["slam"][0].group(3)) <= want["slam"]
            check("75+: one knock, a stagger and one wall slam per shot", ok, f"skill {c['skill']}: {[k.group(0) for k in c['knock']]} "
                  f"{[s.group(0) for s in c['slam']]} {e}")
            slams += len(c["slam"])
            report.append(f"skill {c['skill']}: " + "; ".join(k.group(0) for k in c["knock"] + c["slam"]) + f"; moved {e['moved']} lost {e['lost']}")
        else:
            check("below 75: no knockback", not c["knock"] and not c["slam"], f"skill {c['skill']}: {[k.group(0) for k in c['knock']]}")
    check("a wall slam happened", slams > 0)
    report.append(f"perk windows: {dft.count('ui: menu 7 opened')} opened, {dft.count('ui: menu 7 closed')} closed")
    report += [l for l in text.splitlines() if "PAIRED spot" in l][:1]
    result = "SHOTGUNS PAIRED " + ("PASS" if checks and all(checks.values()) else "FAIL")
    lines = [result] + [f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()] + [""] + report
    (out / "result.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "shotguns-paired"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "assemble":
        ap.assemble(play, Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
        shutil.copy2(sys.argv[6], play / "doomerfall-launcher.exe")
    else:
        run(play, out)
