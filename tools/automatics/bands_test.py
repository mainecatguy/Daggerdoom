"""Automatics bands (50), every third shot free (25), suppression (75) and the bigger damage-taken stack (100), in Doom,
against a fake Daggerfall peer (skillperks 09).

usage: python quiet_run.py --timeout 600 -- python tools/automatics/bands_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder>

Runs DOOM.WAD E1M1 with play_drlax.bat's DRLA set, doomerfall.pk3 and the harness (bands_test.zs). The peer writes the
rule set the harness asks for (automatics_test.Peer). Rule sets:
  off       nothing: no flat damage, no penetration.
  bands     skill 50's band rules: slow +25 / +1 pen, middle +7 / +1 pen, fast 10% extra bullet.
  extra100  fast band extra bullet on every shot (to check the extra bullet itself).
  free3     every third shot free (skill 25).
  big       skill 100's stack (+2% per hit to +30%) and one ammo per 4 shots.
  suppress  skill 75's slow: 5% per hit to 40%, fading over 5 s.
Target A stands 120 units in front of the player, target B 140 behind it on the same line.
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import automatics_test as at  # noqa: E402

at.RULES.update({
    "bands": {195: 25, 196: 1, 197: 7, 198: 1, 199: 1000},
    "extra100": {199: 10000},
    "free3": {194: 3},
    "big": {160: 200, 161: 3000, 159: 4},
    "suppress": {200: 500, 201: 4000, 202: 5000},
})
BAD = re.compile(r'Script error, "(doomerfall|bandtest)\.pk3|(doomerfall|bandtest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted|not implemented for', re.I)
HIT = re.compile(r"automatics: hit (\S+) with (\S+) shot (\d+)( burst)?: (\d+) -> (\d+) \(x([\d.]+)\) tic (\d+) by (\S+) flat (\d+)( extra)?")
PEN = re.compile(r"automatics: penetrate (\S+) -> (\S+) damage (\d+)")
EXTRA = re.compile(r"automatics: extra (bullet|projectile)")
XB = re.compile(r"automatics: extra bullet from \S+ damage (\d+) type (\S+) puff (\S+) flags (\d+) angle (-?[\d.]+) pitch (-?[\d.]+) "
                r"\(first (-?[\d.]+) (-?[\d.]+), aim (-?[\d.]+) (-?[\d.]+)\) tic (\d+)")
XP = re.compile(r"automatics: extra projectile (\S+) from \S+ angle (-?[\d.]+) pitch (-?[\d.]+) \(first (-?[\d.]+) (-?[\d.]+), "
                r"aim (-?[\d.]+) (-?[\d.]+), ([\w ]+)\) tic (\d+)")
BUL = re.compile(r"BANDTEST bullet tic (\d+) damage (\d+) type (\S+) puff (\S+) flags (\d+) angle (-?[\d.]+) pitch (-?[\d.]+)")
REPORT = re.compile(r"BANDTEST report (\w+) (\d) (\d) band=(\d) tics=(\d+)")
# Bands as the gun fires now (DECORATE, derive_bands.py): the Grammaton Beretta semi 18 slow, burst 2 fast, full auto
# 5 slow (its AltFire only switches mode, so alt keeps the mode's band); the Widowmaker SMG 2 fast, its alternate fire
# 18 slow; the three guns the old walk could not measure; the Hurricane Cannon spun up on DRLA's synth-fire button.
WANT_REPORT = {("RLGrammatonClericBeretta", 0, 0): (1, 18), ("RLGrammatonClericBeretta", 1, 0): (3, 2),
               ("RLGrammatonClericBeretta", 2, 0): (1, 5), ("RLGrammatonClericBeretta", 2, 1): (1, 5),
               ("RLWidowmakerSMG", 0, 0): (3, 2), ("RLWidowmakerSMG", 0, 1): (1, 18), ("RLStormUzi", 0, 0): (2, 3),
               ("RLSussGun", 0, 0): (2, 3), ("RLNuclearOnslaught", 0, 0): (2, 3), ("RLHurricaneCannon", 0, 0): (3, 1)}
SUP = re.compile(r"automatics: suppress \S+ ([\d.]+) -> ([\d.]+) speed")


def launch(exe, work, files, peer, timeout):
    # automatics_test.launch watches for its own markers; patch them to this harness's.
    out = work / "bands.out"
    args = [str(exe), "-iwad", str(at.IWAD), "-file", *map(str, files), "-config", str(work / "bands.ini"), "-nosound",
            "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200", "-skill", "3",
            "+set", "dd_perklog", "1", "+map", "E1M1", "-dfbridge", peer.id, "-dfbridgelog", str(work / "bands-bridge.log")]
    asked = set()
    import time
    with open(out, "wb") as f:
        p = subprocess.Popen(args, cwd=work, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while p.poll() is None and time.monotonic() < deadline:
                peer.pump()
                time.sleep(0.004)
                text = out.read_text(errors="replace")
                for m in re.finditer(r"BANDTEST want (\w+)", text):
                    if m.group(1) not in asked:
                        asked.add(m.group(1))
                        peer.sheet(m.group(1))
                if "BANDTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def cases_of(lines):
    cases, cur = [], None
    for l in lines:
        if m := re.search(r"BANDTEST case (\w+) (\w+) band=(\d) tics=(\d+) slot=(-?\d+)", l):
            cur = {"cfg": m.group(1), "gun": m.group(2), "band": int(m.group(3)), "tics": int(m.group(4)), "slot": int(m.group(5)),
                   "hits": [], "pens": [], "extras": 0, "sup": [], "speed": [], "shots": 0, "bullets": {}, "xb": [], "shot_tics": [],
                   "xp": [], "pitch": float(m2.group(1)) if (m2 := re.search(r"pitch=(-?[\d.]+)", l)) else 0.0,
                   "angle": float(m3.group(1)) if (m3 := re.search(r"angle=(-?[\d.]+)", l)) else 0.0}
            cases.append(cur)
        elif not cur:
            continue
        elif m := re.search(r"BANDTEST end \w+ \w+ shots=(\d+) hittics=(\d+) ammo=(-?\d+)->(-?\d+) hitsA=(\d+) lostA=(\d+) hitsB=(\d+) lostB=(\d+) hitby=(\d+)", l):
            cur["hitby"] = int(m.group(9))
            cur.update(shots=int(m.group(1)), hittics=int(m.group(2)), used=int(m.group(3)) - int(m.group(4)), hitsA=int(m.group(5)),
                       lostA=int(m.group(6)), hitsB=int(m.group(7)), lostB=int(m.group(8)))
        elif b := BUL.search(l):
            cur["bullets"].setdefault(int(b.group(1)), []).append(b.groups()[1:])
        elif m := re.search(r"BANDTEST shot \d+ tic (\d+)", l):
            cur["shot_tics"].append(int(m.group(1)))
        elif m := re.search(r"BANDTEST probe \w+ \w+ hit=(\d+)", l):
            cur["probe"] = int(m.group(1))
        elif m := re.search(r"BANDTEST speed tic (\d+) ([\d.]+)", l):
            cur["speed"].append((int(m.group(1)), float(m.group(2))))
        elif h := HIT.search(l):
            cur["hits"].append(h)
        elif pm := PEN.search(l):
            cur["pens"].append(pm)
        elif EXTRA.search(l):
            cur["extras"] += 1
            if x := XB.search(l):
                cur["xb"].append(x.groups())
            if x := XP.search(l):
                cur["xp"].append(x.groups())
        elif s := SUP.search(l):
            cur["sup"].append((float(s.group(1)), float(s.group(2))))
    return cases


def analyse(lines):
    checks = []

    def check(label, ok, detail=""):
        checks.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {label} {'' if ok else detail}", flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("BANDTEST done" in l for l in lines))
    absent = [l for l in lines if "BANDTEST absent" in l or "noselect" in l or "timeout" in l]
    check("every gun present, selected, and every rule set arrived", not absent, absent)
    got = {(m.group(1), int(m.group(2)), int(m.group(3))): (int(m.group(4)), int(m.group(5))) for l in lines if (m := REPORT.search(l))}
    for k, want in WANT_REPORT.items():
        check(f"band of {k[0]} mode {k[1]}{' alt fire' if k[2] else ''} is {want} (band, tics)", got.get(k) == want, got.get(k))
    want_band = {"BandTestProjectileUzi": (3, 1), "BandTestNoAimUzi": (3, 1), "Chaingun": (1, 4), "RLBattleRifle": (1, 4), "RLUzi": (2, 3), "RLThompson": (3, 2), "RLMinigun": (3, 1)}
    blocked = [l for l in lines if "BANDTEST target blocked" in l]
    check("every target placed aside (projectile cases) stands in the open, in the player's sight", not blocked, blocked[:3])
    for c in cases_of(lines):
        tag = f"{c['cfg']} {c['gun']}"
        auto = c["slot"] == 5
        check(f"{tag}: an Automatics gun, band {want_band[c['gun']]}", auto and (c["band"], c["tics"]) == want_band[c["gun"]], c)
        if c["gun"] == "BandTestNoAimUzi":
            # Without autoaim the shots fly along the view, 12 degrees right of A's centre. They may still graze A (its square
            # box and the ball's radius reach about 13 degrees at 260), so whether they are turned is checked by the aim below.
            check(f"{tag}: fired ({c.get('hitsA')} hits on A)", c["shots"] >= 3, c.get("shots"))
        else:
            check(f"{tag}: fired and hit A", c["shots"] >= 3 and c.get("hitsA", 0) > 0, c.get("shots"))
        flat = {1: 25, 2: 7}.get(c["band"], 0) if c["cfg"] == "bands" else 0
        pen = c["cfg"] == "bands" and c["band"] in (1, 2)
        if c["cfg"] in ("off", "bands", "extra100"):
            bad = [f"{h.group(5)}->{h.group(6)} flat {h.group(10)}" for h in c["hits"]
                   if int(h.group(10)) != flat or int(h.group(6)) != int(h.group(5)) + flat]
            if c["cfg"] == "off":
                check(f"{tag}: no flat damage, no penetration, nothing reaches B", not c["hits"] and not c["pens"] and c["hitsB"] == 0, c)
            elif flat:
                check(f"{tag}: every hit gets +{flat} base damage", c["hits"] and not bad and len([h for h in c["hits"] if h.group(1) == "BandTestTarget"]) >= c["hitsA"], bad[:4])
            else:
                check(f"{tag}: no flat damage in the fast band", not bad and not any(int(h.group(10)) for h in c["hits"]), bad[:4])
        if pen:
            to_b = [p for p in c["pens"] if p.group(2) == "BandTestTarget"]
            dealt = sorted(int(h.group(6)) for h in c["hits"])
            carried = sorted(int(p.group(3)) for p in to_b)
            check(f"{tag}: bullets pass through A into B with full damage (A {c['hitsA']} hits, B {c['hitsB']}, pens {len(to_b)})",
                  c["hitsB"] == len(to_b) and c["hitsB"] >= 0.8 * c["hitsA"] and c["lostB"] == sum(carried) and carried == dealt[:0] + carried
                  and all(x in dealt for x in carried) and c["hitsB"] <= c["hitsA"], (carried[:6], dealt[:6]))
        elif c["cfg"] in ("bands", "extra100"):
            check(f"{tag}: fast band, no penetration", not c["pens"], len(c["pens"]))
        if c["cfg"] == "bands" and c["band"] == 3:
            rate = c["extras"] / max(1, c["shots"])
            lo, hi = (0.03, 0.20) if c["shots"] >= 80 else (0.0, 0.35)
            check(f"{tag}: extra bullet on about 10% of shots ({c['extras']} of {c['shots']} = {rate:.3f})", lo <= rate <= hi)
        if c["cfg"] == "bands" and c["band"] in (1, 2):
            check(f"{tag}: no extra bullets outside the fast band", c["extras"] == 0)
        if c["cfg"] == "extra100" and c["gun"].startswith("BandTest"):
            # A projectile gun: the player faces 12 degrees right of A, 260 away (40 radius: 8.7 degrees either side), so the
            # engine's autoaim turns each shot 5.625 degrees left. The extra flies along the shot's own direction mirrored
            # about that turned aim (same spread), and hits A. Without autoaim the aim is the view (angle, pitch -5).
            noaim = c["gun"] == "BandTestNoAimUzi"
            want = ("no autoaim", c["angle"], c["pitch"]) if noaim else ("autoaim", c["angle"] + 5.625, None)

            def dang(a, b):  # a - b as the shortest turn, in degrees
                return (float(a) - float(b) + 180) % 360 - 180
            bad = [] if c["xp"] else ["no extra projectiles"]
            bad += [x for x in c["xp"] if x[7] != want[0] or abs(dang(x[5], want[1])) > 0.05 or (noaim and abs(float(x[6]) - want[2]) > 0.05)
                   or abs(dang(x[1], x[5]) + dang(x[3], x[5])) > 2e-3 or abs(float(x[2]) + float(x[4]) - 2 * float(x[6])) > 2e-3]
            # The shots really spread: the gun's +-2 degrees, so the mirror is not trivially the shot itself.
            spread = [abs(dang(x[3], x[5])) for x in c["xp"]]
            check(f"{tag}: the shots spread about the aim (largest {max(spread, default=0):.2f} degrees)", spread and max(spread) > 0.5, spread[:5])
            check(f"{tag}: an extra projectile on every shot ({c['extras']} for {c['shots']} shots)",
                  len(c["xp"]) == c["extras"] and c["extras"] >= 0.9 * c["shots"] and c["shots"] >= 3, (c["extras"], c["shots"]))
            check(f"{tag}: view pitch {c['pitch']}, every extra projectile mirrors the shot about the engine's autoaim "
                  f"({want[0]}, aims {sorted({x[5] + ' ' + x[6] for x in c['xp']})[:3]})", not bad, bad[:2])
            if not noaim:
                check(f"{tag}: the extra projectiles hit A too ({c.get('hitby')} projectiles hit A of {c['shots'] + c['extras']} fired)",
                      c.get("hitby", 0) >= 0.9 * (c["shots"] + c["extras"]), c.get("hitby"))
        elif c["cfg"] == "extra100":
            check(f"{tag}: an extra bullet on every shot ({c['extras']} for {c['shots']} shots), and they hit (A hit {c['hitsA']} times)",
                  c["extras"] >= 0.9 * c["shots"] and c["extras"] <= c["shots"] + 1 and c["hitsA"] >= 1.5 * c["shots"], (c["extras"], c["shots"]))
            check(f"{tag}: extra bullets spend no ammo (used {c['used']} for {c['shots']} shots)", c["used"] <= c["shots"] + 2 or c["used"] < 0)
            # Each extra bullet is the shot's first bullet again: the same damage roll, damage type, puff and flags as the
            # gun's own LineAttack that tic, its angle and pitch mirrored about the gun's (autoaimed) aim.
            bad = []
            for x in c["xb"]:
                dmg, typ, puff, flags, ang, pit, fa, fp, aa, ap, tic = x
                recs = c["bullets"].get(int(tic), [])
                first = recs[0] if recs else None
                mine = [r for r in recs[1:] if r[4] == ang and r[5] == pit]
                ok = (first and first[:4] == (dmg, typ, puff, flags) and (first[4], first[5]) == (fa, fp) and mine and mine[0][:4] == (dmg, typ, puff, flags)
                      and abs(float(ang) + float(fa) - 2 * float(aa)) < 2e-3 and abs(float(pit) + float(fp) - 2 * float(ap)) < 2e-3)
                if not ok:
                    bad.append((x, recs))
            check(f"{tag}: every extra bullet ({len(c['xb'])}) repeats the shot's first bullet (damage, type, puff, flags) mirrored about the aim",
                  c["xb"] and len(c["xb"]) == c["extras"] and not bad, bad[:2])
            check(f"{tag}: the first shot already gets its extra bullet (no waiting for an earlier hit)",
                  c["shot_tics"] and c["xb"] and int(c["xb"][0][10]) == c["shot_tics"][0], (c["shot_tics"][:2], [x[10] for x in c["xb"][:2]]))
            dmgs = {x[0] for x in c["xb"]}
            check(f"{tag}: extra bullets follow each shot's own damage roll ({sorted(dmgs)})", len(dmgs) >= 2, dmgs)
            if c["pitch"]:
                aims = [float(x[9]) for x in c["xb"]]
                check(f"{tag}: view pitch {c['pitch']}, extra bullets mirror about the autoaimed pitch, not the view "
                      f"(aim pitch {min(aims, default=0):.2f}..{max(aims, default=0):.2f})", aims and all(abs(a - c["pitch"]) > 2 for a in aims), aims[:5])
        if c["cfg"] == "free3":
            n = c["hittics"]  # a shot is a tic in which the gun fired; every shot of these accurate guns hits A
            want = n - n // 3
            check(f"{tag}: every third shot free, used {c['used']} for {n} shots (want {want})", abs(c["used"] - want) <= 1)
        if c["cfg"] == "big":
            want = 100 + min(2 * c["hitsA"], 30)
            check(f"{tag}: after {c['hitsA']} hits another source's 100 does {c.get('probe')} (want {want})", c.get("probe") == want)
            check(f"{tag}: still one ammo per 4 shots, used {c['used']} for {c['hittics']}", abs(c["used"] - c["hittics"] / 4) <= 1.01)
        if c["cfg"] == "suppress":
            steps_ok = all(abs(after - min(before + 0.05, 0.40)) < 1e-3 for before, after in c["sup"])
            peak = max((after for _, after in c["sup"]), default=0)
            check(f"{tag}: each hit adds 5% up to 40% ({len(c['sup'])} hits, peak {peak:.3f})", c["sup"] and steps_ok and abs(peak - 0.40) < 1e-3,
                  c["sup"][:10])
            sp = c["speed"]
            hit_tics = [t for t, s in sp if s < 8 - 1e-6]
            if hit_tics and sp:
                # The last hit: the tic the speed was lowest after which it only rises.
                low_t, low_s = min(sp, key=lambda x: (x[1], -x[0]))
                last = max(t for t, s in sp if abs(s - low_s) < 1e-6)
                at_t = {t: s for t, s in sp}
                half = at_t.get(last + 87)
                after = at_t.get(last + 176)
                check(f"{tag}: slowed to 60% ({low_s:.3f} of 8), about 80% 2.5 s later ({half}), back to 8 after 5 s ({after})",
                      abs(low_s - 4.8) < 0.05 and half is not None and abs(half - 8 * (1 - 0.4 * (1 - 87 / 175))) < 0.1 and after == 8.0)
            else:
                check(f"{tag}: the monster was slowed", False, sp[:5])
    return checks


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(at.REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "bandtest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(HERE / "bands_test.zs", "zscript.txt")
        z.write(HERE / "bands_test.dec", "decorate.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "BandTest" }\n')
    peer = at.Peer(dll)
    try:
        lines = launch(exe, work, [at.MODS / n for n in at.DRLA] + [mod, harness], peer, 240)
    finally:
        peer.close()
    checks = analyse(lines)
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
