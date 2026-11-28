"""Energy Weapons perks with plasma burn, Daggerfall and Doom together: Daggerfall's skill decides the rules, Doom applies
them, and Daggerfall shows each level's perk window.

usage: energy_paired.py <play folder> assemble <base play folder> <uzdoom build Release dir> <bridge dll> <launcher exe>
       energy_paired.py <play folder> run [map, default MAP01]

  assemble  as tools/shotguns/shotguns_paired.py (this repo's Unity build, this branch's UZDoom, doomerfall.pk3, bridge
            DLL and launcher).
  run       Daggerfall (its city save) with Doom on MAP01, -dfperktest EnergyWeapons -dfperksteps 20,26,50,75,100 twice.
            The Doom harness (energy_paired.zs) fires DRLA's Plasma Rifle 3 times per cycle at a target with a monster
            beside it.
Checks: Doom read the rules DoomerfallRules.zs gives for each skill; every hit gets the skill's damage bonus; the
projectiles fly at the skill's speed; from 25 the neighbour takes splash, below 25 it takes nothing; Daggerfall showed
the 25/50/75/100 perk text with all of each level's effects, burn included; hits burn for the level's share (50/100/125/150%),
from 50 later hits convert 20% / 40% of the burn, at 100 conversions burst into the neighbour. Wrap the whole script in quiet_run.py.
Output goes to <play folder>/../energy-paired.
"""
import math
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

TIMEOUT = 480  # burn cycles log more; 260 ended before the second 20/26 steps (run 20261127-143552)
MAP = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "run" else "MAP01"
STEPS = "20,26,50,75,100,20,26,50,75,100"
HIT = re.compile(r"energy: hit (\S+) (direct|explosion): (\d+) -> (\d+) \(x([\d.]+)\)")
BURNL = re.compile(r"energy: burn (\S+) hit (\d+): \+([\d.]+) burn")
CONV = re.compile(r"energy: convert (\S+): took ([\d.]+) of its burn ([\d.]+), dealt (\d+); burst (\d+) enemies")
SPLASH = re.compile(r"energy: splash from (\S+) hit (\d+) by (\S+): (\d+) enemies within (\d+) took (\d+)")
# What each level's window must say (DoomerfallPerks.cs): its burn, its splash (25) and its projectile speed.
POPUP = {25: ["Plasma burn", "hit directly", "50%", "20% of their damage", "15% faster"], 50: ["100%", "20% of the enemy's remaining burn", "30% faster"],
         75: ["125%", "40%", "45% faster"], 100: ["150%", "40% of it", "60% faster"]}


def rules(skill):
    s = max(0, min(skill, 100))
    lv = s // 25
    return {"dmg": 5000 * s // 100, "splash": 2000 if skill >= 25 else 0, "radius": 64 if skill >= 25 else 0, "speed": 1500 * lv,
            "burn": [0, 5000, 10000, 12500, 15000][lv], "convert": [0, 0, 2000, 4000, 4000][lv],
            "burst": 4000 if lv == 4 else 0, "burstradius": 128 if lv == 4 else 0}


def run(play, out):
    harness = out / "enpair-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(HERE / "energy_paired.zs", "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "EnPairHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-enpair.txt", out / "launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / "enpair.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "enpair", "+vid_fullscreen", "0", "+wipetype", "0", "+set", "dd_perklog", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-skill", "3", "+map", MAP]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
          "-dfsynctest", ng.DAGGER, "-dfperktest", "EnergyWeapons", "-dfperksteps", STEPS]
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
            if any(k in text for k in pp.FATAL) or re.search(r"Script error.*(enpair-harness|doomerfall\.pk3)", text) or "PAIRED nospot" in text:
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
            if {26, 50, 75, 100} <= whole and min(whole) < 25 and len(re.findall(r"PAIRED end \d+ skill=100 ", text)) >= 2:
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

    check("no fatal or script error, room found", not fatal)
    cycles, cur = [], None
    for l in text.splitlines():
        if m := re.search(r"PAIRED start (\d+) skill=(-?\d+) dmg=(-?\d+) splash=(-?\d+) radius=(-?\d+) speed=(-?\d+) burn=(-?\d+) convert=(-?\d+) burst=(-?\d+) burstradius=(-?\d+)", l):
            keys = ("dmg", "splash", "radius", "speed", "burn", "convert", "burst", "burstradius")
            cur = {"skill": int(m.group(2)), "read": {k: int(m.group(3 + i)) for i, k in enumerate(keys)}, "hits": [], "splash": [], "burn": [], "conv": []}
            cycles.append(cur)
        elif cur and (b := BURNL.search(l)):
            cur["burn"].append(b)
        elif cur and (cv := CONV.search(l)):
            cur["conv"].append(cv)
        elif cur and (h := HIT.search(l)):
            cur["hits"].append(h)
        elif cur and (s := SPLASH.search(l)):
            cur["splash"].append(s)
        elif cur and (e := re.search(r"PAIRED end \d+ skill=(-?\d+) shots=(\d+) lost=(\d+) near=(\d+) missiles=(\d+) vel=([\d.]+) default=([\d.]+)", l)):
            cur["end"] = {"skill": int(e.group(1)), "shots": int(e.group(2)), "lost": int(e.group(3)), "near": int(e.group(4)),
                          "missiles": int(e.group(5)), "vel": float(e.group(6)), "default": float(e.group(7))}
            cur = None
    done = [c for c in cycles if "end" in c and c["end"]["skill"] == c["skill"]]
    seen = sorted({c["skill"] for c in done})
    report.append(f"skills seen in whole cycles: {seen}")
    # Below 25: the character's starting skill or the 20 step (which lasts only a second before 26, so it rarely gets a
    # whole cycle).
    check("cycles below 25 and at 26, 50, 75 and 100", seen and seen[0] < 25 and all(s in seen for s in (26, 50, 75, 100)), seen)
    for c in done:
        want, e = rules(c["skill"]), c["end"]
        check("Doom read Daggerfall's rules for the skill", c["read"] == want, f"skill {c['skill']}: read {c['read']} want {want}")
        f = 1 + want["dmg"] / 10000
        fs = {round(float(h.group(5)), 4) for h in c["hits"]}
        check("every hit gets the skill's damage bonus", (not want["dmg"] and not c["hits"]) or (c["hits"] and fs == {round(f, 4)}),
              f"skill {c['skill']}: {fs} want {f}")
        sp = 1 + want["speed"] / 10000
        check("projectiles fly at the skill's speed", e["missiles"] > 0 and abs(e["vel"] - sp * e["default"]) <= 0.03 * sp * e["default"],
              f"skill {c['skill']}: {e}")
        check("the target was hit", e["lost"] > 0, f"skill {c['skill']}: {e}")
        if want["splash"]:
            check("from 25 the neighbour takes splash", e["near"] > 0 and c["splash"], f"skill {c['skill']}: {e}")
        else:
            check("below 25 no splash", e["near"] == 0 and not c["splash"], f"skill {c['skill']}: {e}")
        bf, cf = want["burn"] / 10000, want["convert"] / 10000
        if bf:
            check("hits burn for the level's share", c["burn"] and all(abs(float(b.group(3)) - bf * int(b.group(2))) <= 0.006 for b in c["burn"]),
                  f"skill {c['skill']}: {[b.group(0) for b in c['burn'][:3]]}")
        else:
            check("below 25 no burn", not c["burn"] and not c["conv"], f"skill {c['skill']}")
        if cf:
            check("from 50 later hits convert the level's share of the burn", c["conv"] and all(
                abs(float(x.group(2)) - cf * float(x.group(3))) <= 0.002 + 0.001 * float(x.group(3)) for x in c["conv"]),
                f"skill {c['skill']}: {[x.group(0) for x in c['conv'][:3]]}")
            # The character's Daggerfall damage bonus already sized the burn; converted damage must not get it again.
            check("converted burn is dealt as the converted amount (no second damage bonus)", all(
                int(x.group(4)) in {math.floor(float(x.group(2)) + 1e-9), math.ceil(float(x.group(2)) - 1e-9)} for x in c["conv"]),
                f"skill {c['skill']}: {[x.group(0) for x in c['conv'][:3]]}")
        elif bf:
            check("at 25 no conversion", not c["conv"], f"skill {c['skill']}")
        bursts = sum(int(x.group(5)) for x in c["conv"])
        if want["burst"]:
            check("at 100 conversions burst into the neighbour", bursts > 0, f"skill {c['skill']}: {[x.group(0) for x in c['conv'][:3]]}")
        else:
            check("below 100 no burst", bursts == 0, f"skill {c['skill']}")
        report.append(f"skill {c['skill']}: {len(c['burn'])} burns, {len(c['conv'])} conversions, {bursts} burst targets; e.g. "
                      f"{[x.group(0)[8:] for x in c['conv'][:1]]}")
        report.append(f"skill {c['skill']}: read {c['read']}; hits x{sorted(fs)}; vel {e['vel']:.2f} (default {e['default']:.2f}); "
                      f"target lost {e['lost']} over {e['shots']} shots, neighbour {e['near']}")
    popups = re.findall(r"perks: Energy Weapons rose from \d+ to \d+, perk at (\d+): (.*)", dft)
    got = {int(level): body for level, body in popups}
    for level, words in POPUP.items():
        body = got.get(level, "")
        check(f"perk window text at {level} lists all its effects", body and all(w in body for w in words), f"{level}: {body!r}")
        report.append(f"perk {level}: {body}")
    report.append(f"perk windows: {dft.count('ui: menu 7 opened')} opened, {dft.count('ui: menu 7 closed')} closed")
    check("perk windows opened", dft.count("ui: menu 7 opened") >= 4)
    result = "ENERGY PAIRED " + ("PASS" if checks and all(checks.values()) else "FAIL")
    lines = [result] + [f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()] + [""] + report
    (out / "result.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "energy-paired"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "assemble":
        ap.assemble(play, Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
        shutil.copy2(sys.argv[6], play / "doomerfall-launcher.exe")
    else:
        run(play, out)
