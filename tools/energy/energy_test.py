"""Energy Weapons perks (mods/doomerfall/src/zscript/DoomerfallEnergy.zs, DoomerfallEnergyBurn.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/energy/energy_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The peer is Daggerfall's side of the bridge: it writes the character sheet with the DFB_SHEET_ENERGY_* rule set the
harness (energy_test.zs) asks for. The harness fires each gun a few times at a target with two monsters beside it
(inside the splash radius) and one further off, and logs all damage and every projectile; the perk code logs what it
changed (+set dd_perklog 1). Runs DOOM.WAD E1M1:
  stock    doomerfall.pk3 only: stock PlasmaRifle and BFG9000.
  drla     play_drlax.bat's DRLA set: RLPlasmaRifle and RLLaserRifle (hitscan), and the stock classes.
  nobridge doomerfall.pk3 only, no bridge session: nothing changes.
Rule sets: off, dmg (+50%), splash (20% within 64), speed25 (+15%), speed (+60%), and the four burn levels (card 08):
burn25 (burn 50%), burn50 (100%, convert 20%), burn75 (125%, convert 40%), burn100 (150%, convert 40%, burst 40% within
128), then stress (burn100 rules, a burning 400-monster pack hit by burst-making volleys; checks the time they take).
"""
import ctypes as C, math, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402

IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SHEET_INTS, SHEET_FORMAT_VERSION = 194, 12
RULES = {  # 173 damage, 174/175 splash bp/radius, 176 speed
    "off": {}, "dmg": {173: 5000}, "splash": {174: 2000, 175: 64}, "speed25": {176: 1500}, "speed": {176: 6000},
    # 177 burn, 178 convert, 179/180 burst bp/radius (DoomerfallEnergyRules.cs at skills 25/50/75/100)
    "burn25": {177: 5000}, "burn50": {177: 10000, 178: 2000}, "burn75": {177: 12500, 178: 4000},
    "burn100": {177: 15000, 178: 4000, 179: 4000, 180: 128}}
RULES["stress"] = RULES["burn100"]
BURN = {"burn25": (0.5, 0, 0), "burn50": (1.0, 0.2, 0), "burn75": (1.25, 0.4, 0), "burn100": (1.5, 0.4, 0.4)}
BURN_BONUS_BP = -2500  # Daggerfall's damage bonus during the burn sets (a -25% character)
STRESS_VOLLEY_MS = 8.0  # a 40-hit volley, every hit converting and bursting into ~100 neighbours, must fit in this
SPEED = {"speed25": 1.15, "speed": 1.6}
BAD = re.compile(r'Script error, "(doomerfall|entest)\.pk3|(doomerfall|entest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
HIT = re.compile(r"energy: hit (\S+) (direct|explosion): (\d+) -> (\d+) \(x([\d.]+)\) tic (\d+) by (\S+)")
SPLASH = re.compile(r"energy: splash from (\S+) hit (\d+) by (\S+): (\d+) enemies within (\d+) took (\d+) \((\d+) bp each\)")
SPEEDL = re.compile(r"energy: speed (\S+) x([\d.]+) ([\d.]+) -> ([\d.]+)")
DMG = re.compile(r"ENTEST dmg (\S+) (\d+) by (\S+) flags (\d+)")
BURNL = re.compile(r"energy: burn (\S+) hit (\d+): \+([\d.]+) burn, pool ([\d.]+)")
CONV = re.compile(r"energy: convert (\S+): took ([\d.]+) of its burn ([\d.]+), dealt (\d+); burst (\d+) enemies ([\d.]+) burn each")
STRESS = re.compile(r"ENTEST stress end hits (\d+) max volley ms ([\d.]+) max single ms ([\d.]+) max tic gap ms ([\d.]+) burning (\d+)")
MISSILE = re.compile(r"ENTEST missile (\S+) vel ([\d.]+) speed ([\d.]+) default ([\d.]+) gen (-?\d+)")


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.id = "dfen" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
        self.sheet("off")

    def sheet(self, cfg):
        v = [0] * SHEET_INTS
        v[0], v[1], v[2], v[159] = SHEET_FORMAT_VERSION, 1, 1, 1
        v[24 + 2] = 50  # live Willpower 50: neutral
        for k, x in RULES[cfg].items():
            v[k] = x
        # Burn sets run with a Daggerfall damage penalty, so a second application of the player's outgoing multipliers to
        # burn ticks or converted damage would show (they must be exactly the stated shares of the modified hit).
        self.state.damage_bonus_bp = BURN_BONUS_BP if cfg.startswith("burn") else 0
        data = struct.pack(f"<{SHEET_INTS}i", *v)
        version = C.c_uint32()
        rc = self.b.dfb_bulk_write(self.s, 0, data, len(data), C.byref(version))
        print(f"peer: sheet {cfg} rc {rc} v{version.value}", flush=True)

    def close(self):
        self.b.dfb_close(self.s)
        self.b.dfb_close(self.host)

    def pump(self):
        event = Event()
        while self.b.dfb_receive(self.s, C.byref(event)) == 1:
            pass
        self.state.heartbeat += 1
        self.b.dfb_publish_state(self.s, C.byref(self.state), C.sizeof(DfState))
        self.b.dfb_flush(self.s)


def launch(exe, work, files, peer, name, timeout):
    out = work / f"{name}.out"
    args = [str(exe), "-iwad", str(IWAD), "-file", *map(str, files), "-config", str(work / f"{name}.ini"), "-nosound",
            "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200", "-skill", "3",
            "+set", "dd_perklog", "1", "+map", "E1M1"]
    if peer:
        args += ["-dfbridge", peer.id, "-dfbridgelog", str(work / f"{name}-bridge.log")]
    asked = 0
    with open(out, "wb") as f:
        p = subprocess.Popen(args, cwd=work, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while p.poll() is None and time.monotonic() < deadline:
                if peer:
                    peer.pump()
                time.sleep(0.004)
                text = out.read_text(errors="replace")
                wants = re.findall(r"ENTEST want (\w+)", text)
                if peer and len(wants) > asked:
                    peer.sheet(wants[-1])
                    asked = len(wants)
                if "ENTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def cases_of(lines):
    cases, cur = [], None
    for l in lines:
        if m := re.search(r"ENTEST case (\w+) (\w+) slot=(-?\d+)", l):
            cur = {"cfg": m.group(1), "gun": m.group(2), "slot": int(m.group(3)), "hits": [], "splash": [], "speed": [],
                   "dmg": [], "missiles": [], "fires": 0, "ended": False, "burn": [], "conv": []}
            cases.append(cur)
        elif cur is None:
            continue
        elif "ENTEST end " in l:
            cur["ended"] = True
            cur = None
        elif h := HIT.search(l):
            cur["hits"].append(h)
        elif b := BURNL.search(l):
            cur["burn"].append(b)
        elif cv := CONV.search(l):
            cur["conv"].append(cv)
        elif s := SPLASH.search(l):
            cur["splash"].append(s)
        elif v := SPEEDL.search(l):
            cur["speed"].append(v)
        elif d := DMG.search(l):
            cur["dmg"].append((d.group(1), int(d.group(2)), d.group(3), int(d.group(4))))
        elif mi := MISSILE.search(l):
            cur["missiles"].append(mi)
        elif "ENTEST fire " in l:
            cur["fires"] += 1
    return cases


def rounded(d, f):
    return {max(0, math.floor(d * f + 1e-9)), math.ceil(d * f - 1e-9)}


def analyse(name, lines, checks, report):
    def check(label, ok, detail=""):
        checks.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {'' if ok else detail}", flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("ENTEST done" in l for l in lines))
    sights = [l for l in lines if "ENTEST sight " in l]
    check("the target sees both near monsters and the far one (so radius, not walls, keeps the far one out)",
          sights and all(l.strip().endswith("near1 1 near2 1 far 1") for l in sights), sights[:2])
    stress = [STRESS.search(l) for l in lines if STRESS.search(l)]
    if name != "nobridge":
        check("stress ran", stress, [l for l in lines if "ENTEST stress" in l][-3:])
        for m in stress:
            vol = float(m.group(2))
            check(f"stress: a 40-hit burst volley into a burning 400 pack takes under {STRESS_VOLLEY_MS} ms ({vol:.2f})", vol < STRESS_VOLLEY_MS)
            # The first burn ends after 3 s; at the 6 s end only burn from bursts is left. Pack members spawned inside walls
            # cannot be seen by their neighbours and stop burning, so not all 400.
            check("stress: bursts keep most of the pack burning after the first burn ran out", int(m.group(5)) >= 300, m.group(0))
            report.append(f"{name} stress: {m.group(0)[13:]}; volleys: " + ", ".join(
                re.search(r"ms ([\d.]+)", l).group(1) for l in lines if "ENTEST stress volley" in l))
    if name != "nobridge":
        lethal = [l for l in lines if "ENTEST lethal neighbours" in l]
        check("a direct hit that kills a burning enemy still bursts at 100 (both neighbours catch fire)",
              lethal and "burning 2 of 2" in lethal[0], lethal + [l for l in lines if "ENTEST lethal victim" in l or "convert EnTestMonster" in l][:3])
        report.append(f"{name} lethal: {lethal[:1]}")
    base = {}
    for c in cases_of(lines):
        tag = f"{c['cfg']} {c['gun']}"
        if not c["ended"]:
            check(f"{tag}: case ended", False)
            continue
        check(f"{tag}: the gun is an Energy Weapons gun (slot 9)", c["slot"] == 9, c["slot"])
        lost = {}
        for who, amount, inf, _ in c["dmg"]:
            lost[who] = lost.get(who, 0) + amount
            if who.startswith("near"):
                lost["near"] = lost.get("near", 0) + amount
        own = [d for d in c["dmg"] if d[2] != "EnergySplash" and d[2] != "DoomerfallEnergySplash"]
        spl = [d for d in c["dmg"] if d[2] == "DoomerfallEnergySplash"]
        check(f"{tag}: the target was hit", lost.get("target", 0) > 0, c["dmg"][:4])
        check(f"{tag}: nothing ever splashes the player", not any(d[0] == "player" for d in spl), spl[:3])
        hitscan = c["gun"] == "RLLaserRifle"
        shots = [m for m in c["missiles"] if int(m.group(5)) == (0 if name != "nobridge" else -1)]
        if not hitscan:
            check(f"{tag}: the gun's projectiles were seen", shots, c["missiles"][:2])
        if c["cfg"] == "off":
            base[c["gun"]] = lost.get("target", 0) / max(1, c["fires"])
            check(f"{tag}: no perk changes with the rules off", not c["hits"] and not c["splash"] and not c["speed"] and not spl,
                  (c["hits"][:2], c["splash"][:2], c["speed"][:2]))
            bad = [m.group(0) for m in shots if abs(float(m.group(2)) - float(m.group(4))) > 0.05 * float(m.group(4))]
            check(f"{tag}: projectiles fly at their normal speed", not bad, bad[:2])
            report.append(f"{name} {tag}: target lost {lost.get('target', 0)} over {c['fires']} shots, near {lost.get('near', 0)}, far {lost.get('far', 0)}, "
                          f"speeds {sorted({round(float(m.group(2)), 2) for m in shots})}")
        elif c["cfg"] == "dmg":
            fs = {round(float(h.group(5)), 4) for h in c["hits"]}
            check(f"{tag}: every hit x1.5", c["hits"] and fs == {1.5}, fs)
            bad = [h.group(0) for h in c["hits"] if int(h.group(4)) not in rounded(int(h.group(3)), 1.5)]
            check(f"{tag}: rounding", not bad, bad[:3])
            tgt = sum(int(h.group(4)) for h in c["hits"] if h.group(1) == "EnTestTarget")
            check(f"{tag}: the target lost what the hit lines say", tgt == lost.get("target", 0), (tgt, lost))
            check(f"{tag}: no splash without the splash rule", not spl and not c["splash"])
            per = lost.get("target", 0) / max(1, c["fires"])
            report.append(f"{name} {tag}: target lost {lost.get('target', 0)} over {c['fires']} shots ({per:.0f} a shot; rules off {base.get(c['gun'], 0):.0f})")
        elif c["cfg"] == "splash":
            check(f"{tag}: splash happened", c["splash"] and spl, c["dmg"][:4])
            check(f"{tag}: both near monsters took splash", {d[0] for d in spl if d[0].startswith("near")} == {"near1", "near2"}, spl[:4])
            # The BFG's rays also hit the near monsters directly, and the far one is within 64 of near1, so it may be splashed
            # from those hits; a hit on the target must still reach exactly the two near monsters.
            if c["gun"] != "BFG9000":
                check(f"{tag}: the far monster took no splash", not any(d[0] == "far" for d in spl), spl)
            from_target = [s for s in c["splash"] if s.group(1) == "EnTestTarget"]
            check(f"{tag}: a hit on the target splashes exactly the two near monsters (not the far one)",
                  from_target and all(int(s.group(4)) == 2 for s in from_target), [s.group(0) for s in from_target][:3])
            check(f"{tag}: the hit enemy takes no splash from its own hit", not any(d[0] == "target" for d in spl) or c["gun"] == "BFG9000", spl[:4])
            bad = []
            for s in c["splash"]:
                n, hit, total = int(s.group(4)), int(s.group(2)), int(s.group(6))
                lo, hi = min(rounded(hit, 0.2)), max(rounded(hit, 0.2))
                if not (n * lo <= total <= n * hi) or int(s.group(5)) != 64 or int(s.group(7)) != 2000:
                    bad.append(s.group(0))
            check(f"{tag}: each splash is 20% of the hit to each enemy within 64", not bad, bad[:3])
            check(f"{tag}: splash never splashes again", not any(s.group(3) == "DoomerfallEnergySplash" for s in c["splash"]))
            check(f"{tag}: no damage bonus without the damage rule", not c["hits"])
            report.append(f"{name} {tag}: {len(c['splash'])} splashes; near took {sum(d[1] for d in spl if d[0].startswith('near'))}, "
                          f"far took {sum(d[1] for d in spl if d[0] == 'far')}; e.g. {[s.group(0)[8:] for s in c['splash'][:2]]}")
        elif c["cfg"] in BURN:
            burn_case(c, tag, check, report, name)
        elif c["cfg"] in SPEED:
            f = SPEED[c["cfg"]]
            if hitscan:
                check(f"{tag}: hitscan gun: no projectiles, no speed change", not c["speed"], c["speed"][:2])
                continue
            fs = {round(float(v.group(2)), 4) for v in c["speed"]}
            check(f"{tag}: every shot sped up x{f}", c["speed"] and fs == {f} and len(c["speed"]) >= len(shots), (fs, len(c["speed"]), len(shots)))
            bad = [m.group(0) for m in shots if abs(float(m.group(2)) - f * float(m.group(4))) > 0.05 * f * float(m.group(4))]
            check(f"{tag}: projectiles fly at x{f} their normal speed", not bad, bad[:2])
            report.append(f"{name} {tag}: speeds {sorted({round(float(m.group(2)), 2) for m in shots})} (default {sorted({float(m.group(4)) for m in shots})})")


def burn_case(c, tag, check, report, name):
    f, conv, burst = BURN[c["cfg"]]
    spl = [d for d in c["dmg"] if d[2] == "DoomerfallEnergySplash"]
    check(f"{tag}: no damage bonus or splash without those rules", not c["hits"] and not c["splash"] and not spl)
    check(f"{tag}: hits set burning", c["burn"], c["dmg"][:4])
    bad = [b.group(0) for b in c["burn"] if abs(float(b.group(3)) - f * int(b.group(2))) > 0.006]
    check(f"{tag}: each hit burns {f:.0%} of its damage", not bad, bad[:3])
    if not conv:
        check(f"{tag}: no conversion below 50", not c["conv"], [x.group(0) for x in c["conv"][:2]])
    else:
        check(f"{tag}: later hits convert burn", c["conv"])
        bad = [x.group(0) for x in c["conv"] if abs(float(x.group(2)) - conv * float(x.group(3))) > 0.002 + 0.001 * float(x.group(3))]
        check(f"{tag}: each conversion takes {conv:.0%} of the remaining burn", not bad, bad[:3])
        bad = [x.group(0) for x in c["conv"] if int(x.group(4)) not in rounded(float(x.group(2)), 1)]
        check(f"{tag}: converted burn is dealt at once (chance rounding)", not bad, bad[:3])
    if burst:
        check(f"{tag}: conversions burst into the monsters nearby", any(int(x.group(5)) >= 1 for x in c["conv"]), [x.group(0) for x in c["conv"][:3]])
        bad = [x.group(0) for x in c["conv"] if abs(float(x.group(6)) - burst * float(x.group(2))) > 0.006]
        check(f"{tag}: burst burn is {burst:.0%} of the converted amount", not bad, bad[:3])
        nearfire = sum(d[1] for d in c["dmg"] if d[0] in ("near1", "near2", "far") and d[2] == "None")
        check(f"{tag}: monsters near the target burned", nearfire > 0)
    else:
        check(f"{tag}: no bursts below 100", not any(int(x.group(5)) for x in c["conv"]))
    # The target's books: burn ticks (inflictor None) pay what was added minus what was converted, +-1 for the last fraction.
    added = sum(float(b.group(3)) for b in c["burn"] if b.group(1) == "EnTestTarget")
    taken = sum(float(x.group(2)) for x in c["conv"] if x.group(1) == "EnTestTarget")
    ticks = sum(d[1] for d in c["dmg"] if d[0] == "target" and d[2] == "None")
    check(f"{tag}: the target's burn paid out in full (added {added:.2f} - converted {taken:.2f} = ticks {ticks})", abs(ticks - (added - taken)) <= 1.5)
    dealt = sum(int(x.group(4)) for x in c["conv"] if x.group(1) == "EnTestTarget")
    got = sum(d[1] for d in c["dmg"] if d[0] == "target" and d[2] == "DoomerfallEnergyBurst")
    check(f"{tag}: the target took exactly the converted damage ({dealt} / {got})", dealt == got)
    check(f"{tag}: the player never took burn or burst damage", not any(d[0] == "player" and d[2] in ("None", "DoomerfallEnergyBurst") for d in c["dmg"]))
    report.append(f"{name} {tag}: {len(c['burn'])} burns ({added:.1f} on the target), {len(c['conv'])} conversions ({taken:.1f} taken, {dealt} dealt), "
                  f"target burn ticks {ticks}, bursts {sum(int(x.group(5)) for x in c['conv'])}; e.g. {[x.group(0)[8:] for x in c['conv'][:2]]}")


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "entest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("energy_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "EnPerkTest" }\n')
    checks, report = [], []
    only = sys.argv[4:]
    drla = [MODS / n for n in DRLA] + [mod, harness]
    for name, files, bridged, timeout in (("stock", [mod, harness], True, 480), ("drla", drla, True, 700),
                                          ("nobridge", [mod, harness], False, 90)):
        if only and name not in only:
            continue
        peer = Peer(dll) if bridged else None
        try:
            lines = launch(exe, work, files, peer, name, timeout)
        finally:
            if peer:
                peer.close()
        if name == "nobridge":
            checks.append(not any("energy:" in l for l in lines))
            print(f"{'PASS' if checks[-1] else 'FAIL'} nobridge: no perk activity without a Daggerfall character")
        analyse(name, lines, checks, report)
        if bridged:
            blog = (work / f"{name}-bridge.log").read_text(errors="replace") if (work / f"{name}-bridge.log").exists() else ""
            ok = f"({BURN_BONUS_BP} bp)" in blog
            checks.append(ok)
            print(f"{'PASS' if ok else 'FAIL'} {name}: Daggerfall's damage bonus {BURN_BONUS_BP} bp was applied to hits during the burn sets")
    print("\n" + "\n".join(report))
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
