"""Pistols perks, Daggerfall and Doom together: Daggerfall's skill decides the rules, Doom applies them, and a pistol
shot carries through a kill and bursts into shrapnel.

usage: pistols_paired.py <play folder> assemble <base play folder> <uzdoom build Release dir> <bridge dll> <launcher exe>
       pistols_paired.py <play folder> run [map, default MAP01]

  assemble  as tools/shotguns/shotguns_paired.py (this repo's Unity build, this branch's UZDoom, doomerfall.pk3, bridge
            DLL and launcher).
  run       Daggerfall (its city save) with Doom on MAP01, -dfperktest Pistols -dfperksteps 20,26,50,75,100 twice. The Doom
            harness (pistols_paired.zs) fires DRLA's Pistol once per cycle through a line of targets.
Checks: Doom read the rules DoomerfallPistolsRules.cs gives for each skill; below 50 no carry-through and A (20 health)
survives; at 50 and 75 the shot gets the +100 pool, kills A and B takes exactly what was left; at 100 also 3 fragments
from A's hit and 3 from B's carry-through hit, C on the fork takes 33% of the hit. Wrap the whole script in quiet_run.py.
Output goes to <play folder>/../pistols-paired.
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
MAP = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == "run" else "MAP01"
STEPS = "20,26,50,75,100,20,26,50,75,100"
CARRY = re.compile(r"pistols: carry (\S+) -> (\S+) damage (\d+)")
FRAG = re.compile(r"pistols: fragment (\S+) -> (\S+) damage (\d+) of (\d+)( turned)?")
HIT = re.compile(r"pistols: hit (\S+) with (\S+): (\d+) -> (\d+) \(pool \+(\d+)\)")


def rules(skill):
    """DoomerfallPistolsRules.Fill, sheet 181..193."""
    steps = (skill >= 75) + (skill >= 50) + (skill >= 25)
    s50, s100 = skill >= 50, skill >= 100
    return [0, 0, 0, 0, 0, 0, 2000 * steps,
            1 if s50 else 0, 100 if s50 else 0, 500 if s50 else 0, 3 if s100 else 0, 3300 if s100 else 0, 5 if s100 else 0]


def r33(x):
    return max(1, int(x * 0.33 + 0.5))


def run(play, out):
    harness = out / "pistpair-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(HERE / "pistols_paired.zs", "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PistPairHarness" }\n')
    uz_log, df_log, console, launcher = out / "uz.log", out / "df.log", out / "log-pistpair.txt", out / "launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)
    data = play / "data"
    uz = ["-noactivate", "-nosound", "-config", str(out / "pistpair.ini"), "-savedir", str(out / "saves"), "-dfbridgelog", str(uz_log),
          "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
          "+logfile", "pistpair", "+vid_fullscreen", "0", "+wipetype", "0", "+set", "dd_perklog", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "-skill", "3", "+map", MAP]
    df = ["-dfbridgelog", str(df_log), "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800",
          "-dfsynctest", ng.DAGGER, "-dfperktest", "Pistols", "-dfperksteps", STEPS]
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
            if any(k in text for k in pp.FATAL) or re.search(r"Script error.*(pistpair-harness|doomerfall\.pk3)", text) or "PAIRED nospot" in text:
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
            if len(re.findall(r"PAIRED end \d+ skill=100 ", text)) >= 2 and {26, 50, 75} <= {int(x) for x in re.findall(r"PAIRED end \d+ skill=(\d+) ", text)}:
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

    check("no fatal or script error, line found", not fatal)
    cycles, cur = [], None
    for l in text.splitlines():
        if m := re.search(r"PAIRED start (\d+) skill=(-?\d+) rules((?: -?\d+){13})", l):
            cur = {"skill": int(m.group(2)), "read": [int(x) for x in m.group(3).split()], "carry": [], "frag": [], "hit": []}
            cycles.append(cur)
        elif cur and (x := CARRY.search(l)):
            cur["carry"].append(x)
        elif cur and (x := FRAG.search(l)):
            cur["frag"].append(x)
        elif cur and (x := HIT.search(l)):
            cur["hit"].append(x)
        elif cur and (e := re.search(r"PAIRED end \d+ skill=(-?\d+) hitA=(\d+) lostA=(\d+) lostB=(\d+) lostC=(\d+)", l)):
            cur["end"] = {"skill": int(e.group(1)), "hit": int(e.group(2)), "A": int(e.group(3)), "B": int(e.group(4)), "C": int(e.group(5))}
            cur = None
    done = [c for c in cycles if "end" in c and c["end"]["skill"] == c["skill"]]
    seen = sorted({c["skill"] for c in done})
    report.append(f"skills seen in whole cycles: {seen}")
    check("cycles at 26, 50, 75 and 100", all(s in seen for s in (26, 50, 75, 100)), seen)
    carried = frags = 0
    for c in done:
        s, e = c["skill"], c["end"]
        want = rules(s)
        check("Doom read Daggerfall's rules for the skill", c["read"] == want, f"skill {s}: read {c['read']} want {want}")
        hit = e["hit"]
        line = f"skill {s}: hit {hit}" + (f" (pool +{c['hit'][0].group(5)})" if c["hit"] else "") + f", A {e['A']}, B {e['B']}, C {e['C']}"
        line += "; " + "; ".join(x.group(0).replace("pistols: ", "") for x in c["carry"] + c["frag"])
        report.append(line)
        if s < 50:
            check("below 50: no pool, no carry-through, no fragments", not c["hit"] and not c["carry"] and not c["frag"] and e["B"] == 0, line)
            continue
        pooled = len(c["hit"]) == 1 and c["hit"][0].group(5) == "100" and int(c["hit"][0].group(4)) == hit
        left = hit - 20
        ok = pooled and len(c["carry"]) >= 1 and int(c["carry"][0].group(3)) == left and c["carry"][0].group(2) == "PistPairTarget"
        if s < 100:
            ok = ok and not c["frag"] and e["B"] == left and e["C"] == 0
            check("50 and 75: +100 pool, A dies, B takes exactly what was left, no fragments", ok, line)
        else:
            fromA = [x for x in c["frag"] if int(x.group(4)) == hit]
            fromB = [x for x in c["frag"] if int(x.group(4)) == left]
            ok = ok and len(c["frag"]) == 6 and len(fromA) == 3 and len(fromB) == 3 and all(int(x.group(3)) == r33(hit) for x in fromA)
            ok = ok and all(int(x.group(3)) == r33(left) for x in fromB) and e["C"] == r33(hit) and e["B"] == left + r33(hit)
            check("100: carry-through as at 50, 3 fragments from the hit and 3 from the carry-through hit, C on the fork takes 33%", ok, line)
            frags += len(c["frag"])
        carried += len(c["carry"])
    check("a carry-through happened", carried > 0)
    check("shrapnel happened", frags > 0)
    report.append(f"perk windows: {dft.count('ui: menu 7 opened')} opened, {dft.count('ui: menu 7 closed')} closed")
    report += [l for l in text.splitlines() if "PAIRED spot" in l][:1]
    result = "PISTOLS PAIRED " + ("PASS" if checks and all(checks.values()) else "FAIL")
    lines = [result] + [f"{'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()] + [""] + report
    (out / "result.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "pistols-paired"
    out.mkdir(parents=True, exist_ok=True)
    if sys.argv[2] == "assemble":
        ap.assemble(play, Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
        shutil.copy2(sys.argv[6], play / "doomerfall-launcher.exe")
    else:
        run(play, out)
