"""Doom's shared rules (mods/doomerfall/src/zscript/DoomerfallRules.zs) give the same numbers as the formulas they
replaced: Daggerfall's perk rule files (DoomerfallAutomaticsRules.cs, DoomerfallExplosivesRules.cs,
DoomerfallShotgunsRules.cs, DoomerfallEnergyRules.cs before 2026-11-27, and skillperks 05's DoomerfallPistolsRules.cs,
ported below line for line), and the old Doom
formulas in DoomerfallAttributes.zs, DoomerfallAgility.zs and DoomerfallJump.zs.

usage: python quiet_run.py --timeout 120 -- python tools/rules/rules_test.py <uzdoom.exe> <work folder>
Runs DOOM.WAD E1M1 with doomerfall.pk3 and a harness that prints every rule over its whole input range, no bridge.
"""
import math, re, subprocess, sys, time, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
BAD = re.compile(r'Script error|zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)


def old_perks(skill):
    """The five C# Fill(values, skill) methods, in DoomerfallRules.ERule order (the old sheet slots 155-193)."""
    c = 0 if skill < 0 else 100 if skill > 100 else skill
    v = []
    # Automatics
    burst = skill >= 25
    v += [6000 * c // 100, 3000 if burst else 0, 3 if burst else 0, 300 if burst else 0,
          4 if skill >= 100 else 2 if skill >= 50 else 1,
          200 if skill >= 100 else 100 if skill >= 75 else 0, 3000 if skill >= 100 else 1500 if skill >= 75 else 0]  # skillperks 09
    # Explosives
    chain = skill >= 100
    v += [6000 * c // 100, 9900 if skill >= 75 else 9500 if skill >= 25 else 0, 5000 if skill >= 50 else 0,  # perknumbers 01: Explosives 50 +50%
          2500 if chain else 0, 128 if chain else 0]
    # Shotguns
    most, knock = skill >= 100, skill >= 75
    v += [7500 * c // 100, 3500 if skill >= 25 else 0, 10000 if most else 5000 if skill >= 50 else 0,
          20000 if most else 10000 if knock else 0, 400 if most else 200 if knock else 0, 0]
    # Energy Weapons
    lv = c // 25
    v += [5000 * c // 100, 2000 if skill >= 25 else 0, 64 if skill >= 25 else 0, 1500 * (c // 25),
          [0, 5000, 10000, 12500, 15000][lv], [0, 0, 2000, 4000, 4000][lv], 4000 if lv == 4 else 0, 128 if lv == 4 else 0]
    # Pistols
    spray, deadeye, pool, shrapnel = skill >= 25, skill >= 75, skill >= 50, skill >= 100
    steps = (1 if skill >= 75 else 0) + (1 if skill >= 50 else 0) + (1 if skill >= 25 else 0)
    v += [25000 if spray else 0, 15000 if spray else 0, 15000 if deadeye else 0, 30000 if deadeye else 0,
          3 if spray else 0, 8 if spray else 0, 2000 * steps, 1 if skill >= 50 else 0, 100 if pool else 0,
          500 if pool else 0, 3 if shrapnel else 0, 3300 if shrapnel else 0, 250 if shrapnel else 0]
    # More Automatics: skillperks 09's DoomerfallAutomaticsRules.cs Fill (agent/skillperks-20261128-011753), slots 194-202
    per = 4 if skill >= 100 else 2 if skill >= 50 else 1
    bands, suppress = skill >= 50, skill >= 75
    v += [3 if skill >= 25 and per == 1 else 0, 25 if bands else 0, 1 if bands else 0, 7 if bands else 0, 1 if bands else 0,
          1000 if bands else 0, 500 if suppress else 0, 4000 if suppress else 0, 5000 if suppress else 0]
    return v


def old_attr(v):
    # Strength melee, Speed, Agility handling (old DoomerfallAttributes.zs and DoomerfallAgility.zs), then attributes
    # 08's DoomerfallAttributes.zs curves: Strength guns, Agility firearms, Agility rifles and pistols, Luck crit chance.
    c = max(0, min(100, v))
    return (1.0 if v < 0 else 1.0 + v / 100.0, 1.0 if v < 0 else 0.75 + v / 200.0,
            0.0 if v <= 0 else 0.40 * v / 100.0,
            1.0 if v < 0 else 0.8 + c * 0.004, 1.0 if v < 0 else 1.0 + (c - 50) * 0.002,
            1.0 if v < 0 else 1.0 + (c - 50) * 0.004, 0.0 if v <= 50 else min(v - 50, 50) * 0.001)


def old_jump(s):
    k = max(0, min(100, s))
    f = 1.0 + k / 100.0 + (0.25 if k >= 25 else 0.0)
    return f, 2 if s >= 100 else 1 if s >= 50 else 0, 1.5 * sim_height(8 * math.sqrt(f), 1)


def sim_height(v, g):
    """The apex of a jump by stepping Doom's physics: move by the speed, then lose gravity (P_ZMovement)."""
    z = top = 0.0
    while v > 0:
        z += v
        top = max(top, z)
        v -= g
    return top


def new_fall(units, safe):
    """Falling damage since jumpfollowup 01 (owner, Q&A item 6): 5 HP per metre past 1.5 jump heights."""
    m = (units - safe) / 30.0
    return int(5.0 * m) if m > 0 else 0


def main():
    exe, work = Path(sys.argv[1]), Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "rulestest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("rules_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "RulesTest" }\n')
    out = work / "rules.out"
    args = [str(exe), "-iwad", str(IWAD), "-file", str(mod), str(harness), "-config", str(work / "rules.ini"), "-nosound",
            "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200", "+map", "E1M1"]
    with open(out, "wb") as f:
        p = subprocess.Popen(args, cwd=work, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        try:
            while p.poll() is None and time.monotonic() < deadline:
                time.sleep(0.2)
                text = out.read_text(errors="replace")
                if "RULESTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    lines = out.read_text(errors="replace").splitlines()
    bad, counts = [l for l in lines if BAD.search(l)][:5], {}
    def fail(msg):
        bad.append(msg)
    for l in lines:
        t = l.split()
        if len(t) < 2 or t[0] != "RULESTEST":
            continue
        kind = t[1]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "perk":
            r, s, got = map(int, t[2:5])
            if old_perks(s)[r] != got:
                fail(f"perk rule {r} at skill {s}: {got}, was {old_perks(s)[r]}")
        elif kind == "get" and int(t[3]) != 0:
            fail(f"rule {t[2]} is {t[3]} without a Daggerfall character")
        elif kind == "attr":
            v = int(t[2])
            if any(abs(float(a) - b) > 1e-6 for a, b in zip(t[3:10], old_attr(v))):
                fail(f"attributes at {v}: {t[3:10]}, was {old_attr(v)}")
        elif kind == "jump":
            s = int(t[2])
            want = old_jump(s)
            if abs(float(t[3]) - want[0]) > 1e-6 or int(t[4]) != want[1] or abs(float(t[5]) - want[2]) > 1e-4:
                fail(f"jumping at {s}: {t[3:6]}, want {want}")
        elif kind == "fall":
            u, got = int(t[2]), (int(t[3]), int(t[4]))
            if (new_fall(u, 54), new_fall(u, 117)) != got:
                fail(f"fall of {u} units: {got}, want {(new_fall(u, 54), new_fall(u, 117))}")
        elif kind == "height":
            v, g, got = float(t[2]), float(t[3]), float(t[4])
            if abs(sim_height(v, g) - got) > 1e-4:
                fail(f"jump height for JumpZ {v} gravity {g}: {got}, want {sim_height(v, g)}")
        elif kind == "luck":
            luck = int(t[2])
            want = "".join("1" if luck > 0 and (k / 1000.0) * 200 < min(luck, 100) else "0" for k in range(601))
            if t[3] != want:
                fail(f"luck {luck}: drop pattern differs")
        elif kind == "stat" and t[2:4] != ["-1", "0"]:
            fail(f"without a Daggerfall character Agility reads {t[2]} and HasCharacter {t[3]}")
    rules = len(old_perks(0))  # 48: 39, plus skillperks 09's nine
    want_counts = {"perk": rules * 111, "get": rules, "attr": 102, "jump": 111, "fall": 401, "height": 5, "luck": 9, "stat": 1, "done": 1}
    if counts != want_counts:
        fail(f"line counts {counts}, want {want_counts}")
    for b in bad[:20]:
        print("FAIL", b)
    print(f"{sum(counts.values())} values compared")
    print("RESULT", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
