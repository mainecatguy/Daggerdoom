"""Energy Weapons perks before burn (mods/doomerfall/src/zscript/DoomerfallEnergy.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/energy/energy_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The peer is Daggerfall's side of the bridge: it writes the character sheet with the DFB_SHEET_ENERGY_* rule set the
harness (energy_test.zs) asks for. The harness fires each gun a few times at a target with two monsters beside it
(inside the splash radius) and one further off, and logs all damage and every projectile; the perk code logs what it
changed (+set dd_perklog 1). Runs DOOM.WAD E1M1:
  stock    doomerfall.pk3 only: stock PlasmaRifle and BFG9000.
  drla     play_drlax.bat's DRLA set: RLPlasmaRifle and RLLaserRifle (hitscan), and the stock classes.
  nobridge doomerfall.pk3 only, no bridge session: nothing changes.
Rule sets: off, dmg (+50%), splash (20% within 64), speed25 (+15%), speed (+60%).
"""
import ctypes as C, math, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402

IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SHEET_INTS, SHEET_FORMAT_VERSION = 177, 10
RULES = {  # 173 damage, 174/175 splash bp/radius, 176 speed
    "off": {}, "dmg": {173: 5000}, "splash": {174: 2000, 175: 64}, "speed25": {176: 1500}, "speed": {176: 6000}}
SPEED = {"speed25": 1.15, "speed": 1.6}
BAD = re.compile(r'Script error, "(doomerfall|entest)\.pk3|(doomerfall|entest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
HIT = re.compile(r"energy: hit (\S+) (direct|explosion): (\d+) -> (\d+) \(x([\d.]+)\) tic (\d+) by (\S+)")
SPLASH = re.compile(r"energy: splash from (\S+) hit (\d+) by (\S+): (\d+) enemies within (\d+) took (\d+) \((\d+) bp each\)")
SPEEDL = re.compile(r"energy: speed (\S+) x([\d.]+) ([\d.]+) -> ([\d.]+)")
DMG = re.compile(r"ENTEST dmg (\S+) (\d+) by (\S+) flags (\d+)")
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
                   "dmg": [], "missiles": [], "fires": 0, "ended": False}
            cases.append(cur)
        elif cur is None:
            continue
        elif "ENTEST end " in l:
            cur["ended"] = True
            cur = None
        elif h := HIT.search(l):
            cur["hits"].append(h)
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
    for name, files, bridged, timeout in (("stock", [mod, harness], True, 240), ("drla", drla, True, 400),
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
    print("\n" + "\n".join(report))
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
