"""Automatics perks in Doom (mods/doomerfall/src/zscript/DoomerfallAutomatics.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/automatics/automatics_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder>

The peer is Daggerfall's side of the bridge: it writes the character sheet with the DFB_SHEET_AUTO_* rule set the
harness (automatics_test.zs) asks for. The harness fires each sample gun at a target and logs every shot; the perk code
logs what it changed (+set dd_perklog 1). Runs DOOM.WAD E1M1:
  stock    doomerfall.pk3 only: the stock Chaingun.
  drla     play_drlax.bat's DRLA set: RLChaingun, RLBattleRifle, RLUzi, RLMinigun (and the stock Chaingun class).
  nobridge doomerfall.pk3 only, no bridge session: nothing changes.
Rule sets: off, dmg (+60%), burst (+30% on the first 3 shots, 0.3 s reset), ammo2 / ammo4 (one ammo per 2 / 4 shots),
sunder (+1% per hit up to +15%), full (all of skill 100's rules). Whole script must run under quiet_run.py.
"""
import ctypes as C, math, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402

IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SHEET_INTS, SHEET_FORMAT_VERSION = 162, 7
# DRLA guns that spin up: the harness cannot hold a real trigger (a console +attack does not reach a game on the
# private desktop), so each pull fires only a short string of shots. They are checked with fewer shots.
SPINUP = {"RLChaingun", "RLMinigun"}
RULES = {  # 155 damage, 156/157/158 burst bp/shots/reset ms, 159 shots per ammo, 160/161 sunder bp/max
    "off": {}, "dmg": {155: 6000}, "burst": {156: 3000, 157: 3, 158: 300}, "ammo2": {159: 2}, "ammo4": {159: 4},
    "sunder": {160: 100, 161: 1500}, "full": {155: 6000, 156: 3000, 157: 3, 158: 300, 159: 4, 160: 100, 161: 1500}}
BAD = re.compile(r'Script error, "(doomerfall|autotest)\.pk3|(doomerfall|autotest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
HIT = re.compile(r"automatics: hit (\S+) with (\S+) shot (\d+)( burst)?: (\d+) -> (\d+) \(x([\d.]+)\) tic (\d+)")
SHOT = re.compile(r"AUTOTEST shot (\w+) (\w+) n=(\d+) burst=(\d+) tic=(\d+) ammo=(-?\d+)->(-?\d+) lost=(\d+)")


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.id = "dfauto" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
        self.sheet("off")

    def sheet(self, cfg):
        v = [0] * SHEET_INTS
        v[0], v[1], v[2], v[159] = SHEET_FORMAT_VERSION, 1, 1, 1
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
            if event.kind == 11:  # DFB_KIND_HP
                self.state.hp_applied = struct.unpack_from("<I", bytes(event.payload))[0]
        self.state.heartbeat += 1
        self.b.dfb_publish_state(self.s, C.byref(self.state), C.sizeof(DfState))
        self.b.dfb_flush(self.s)


def launch(exe, work, files, peer, name, timeout, extra=()):
    out = work / f"{name}.out"
    args = [str(exe), "-iwad", str(IWAD), "-file", *map(str, files), "-config", str(work / f"{name}.ini"), "-nosound",
            "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200", "-skill", "3",
            "+set", "dd_perklog", "1", "+map", "E1M1", *extra]
    if peer:
        args += ["-dfbridge", peer.id, "-dfbridgelog", str(work / f"{name}-bridge.log")]
    asked = set()
    with open(out, "wb") as f:
        p = subprocess.Popen(args, cwd=work, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while p.poll() is None and time.monotonic() < deadline:
                if peer:
                    peer.pump()
                time.sleep(0.004)
                text = out.read_text(errors="replace")
                for m in re.finditer(r"AUTOTEST want (\w+)", text):
                    if peer and m.group(1) not in asked:
                        asked.add(m.group(1))
                        peer.sheet(m.group(1))
                if "AUTOTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def analyse(name, lines, checks, held=False):
    def check(label, ok, detail=""):
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {detail if not ok else ''}", flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("AUTOTEST done" in l for l in lines))
    cases, per_shot = {}, {}
    cur, hits = None, []
    for l in lines:
        m = re.search(r"AUTOTEST case (\w+) (\w+) cat=(\w+) slot=(-?\d+)", l)
        if m:
            cur = (m.group(1), m.group(2))
            cases[cur] = {"cat": m.group(3), "slot": int(m.group(4)), "shots": [], "hitlines": 0, "hits": []}
            continue
        if "AUTOTEST fire" in l:
            hits = []
        elif (h := HIT.search(l)) and cur:
            hits.append(h)
            cases[cur]["hits"].append(h)
            cases[cur]["hitlines"] += 1
        elif (s := SHOT.search(l)) and cur:
            cases[cur]["shots"].append((s, hits))
            hits = []
        elif (e := re.search(r"AUTOTEST end (\w+) (\w+) shots=(\d+) ammo=(-?\d+)->(-?\d+) hits=(\d+) lost=(\d+)", l)) and cur:
            cases[cur]["end"] = (int(e.group(3)), int(e.group(4)) - int(e.group(5)))
            cases[cur]["target"] = (int(e.group(6)), int(e.group(7)))
        elif (pr := re.search(r"AUTOTEST probe (\w+) (\w+) hit=(\d+) fresh=(\d+)", l)) and cur:
            cases[cur]["probe"] = (int(pr.group(3)), int(pr.group(4)))
    for (cfg, gun), c in cases.items():
        tag = f"{cfg} {gun} ({c['cat']}, slot {c['slot']})"
        shots, used = c.get("end", (0, 0))
        spin = gun in SPINUP
        check(f"{tag}: fired and hit", shots >= (2 if spin else 8) and c.get("target", (0, 0))[0] > 0, f"shots {shots}")
        if cfg == "off":
            per_shot[gun] = used / shots if shots else 0
        auto = c["slot"] == 5
        rules = RULES[cfg] if auto else {}
        k = per_shot.get(gun, 1)
        # Damage factors. A shot is a tic in which the gun fired (one trigger pull of the stock Chaingun fires in two
        # tics); every hit line carries its tic, so shots and bursts are rebuilt from the tics here.
        bad = []
        target_hits, target_lost = c.get("target", (0, 0))
        tics = sorted({int(h.group(8)) for h in c["hits"]})
        index, last = {}, -1000
        for tic in tics:
            index[tic] = 1 if tic - last > 10 else index[last] + 1
            last = tic
        base_f = 1 + rules.get(155, 0) / 10000
        if base_f == 1 and not rules.get(157) and c["hits"]:
            bad.append(f"{len(c['hits'])} hit lines with no damage rule")
        for h in c["hits"]:
            k_ = index[int(h.group(8))]
            want = base_f * ((1 + rules[156] / 10000) if rules.get(157) and k_ <= rules[157] else 1)
            if abs(float(h.group(7)) - want) > 1e-3 or (rules.get(157) and int(h.group(3)) != k_):
                bad.append(f"tic {h.group(8)} shot {k_}: x{h.group(7)} counted {h.group(3)}, want x{want:.4f}")
            d, n = int(h.group(5)), int(h.group(6))
            if n not in (max(1, math.floor(d * want + 1e-9)), math.ceil(d * want - 1e-9)):
                bad.append(f"{d} -> {n} is not {d} x {want:.4f} rounded")
        if base_f != 1:  # every hit carries the bonus, and what the code logged is what the target lost
            if len(c["hits"]) != target_hits:
                bad.append(f"target was hit {target_hits} times, {len(c['hits'])} hit lines")
            if 160 not in rules and sum(int(h.group(6)) for h in c["hits"]) != target_lost:
                bad.append(f"target lost {target_lost}, hit lines say {sum(int(h.group(6)) for h in c['hits'])}")
        if rules.get(157) and base_f == 1:
            bonus = [h for h in c["hits"] if index[int(h.group(8))] <= rules[157]]
            if len(c["hits"]) != len(bonus):
                bad.append("a hit line outside the first 3 shots")
            if sum(int(h.group(6)) for h in c["hits"]) + 0 > target_lost:
                bad.append("hit lines exceed the damage taken")
        check(f"{tag}: damage x{'right' if auto else '1 (not Automatics)'} on every hit", not bad, bad[:4])
        if cfg == "burst" and auto:
            # Only bonus shots log in this rule set: 3 at the start, 3 after the long pause, none after the short one.
            got_idx = [index[t_] for t_ in tics]
            if spin:  # each harness pull is a short string of shots with long gaps between: every one starts a burst
                ok_idx = bool(got_idx) and max(got_idx) <= 3 and got_idx.count(1) >= 2
            else:
                ok_idx = got_idx == [1, 2, 3, 1, 2, 3]
            check(f"{tag}: bursts restart at the start and after the long pause only, not the short one", ok_idx,
                  f"burst indices {[index[t_] for t_ in tics]}")
        if not auto and gun == "RLUzi" and cfg == "full":
            check(f"{tag}: the Uzi is a Pistol, so no Automatics perks", c["hitlines"] == 0 and c["slot"] == 7, c)
        # Ammo.
        per = rules.get(159, 1)
        want_used = shots * k / per
        check(f"{tag}: ammo used {used} for {shots} shots, want about {want_used:.1f}", abs(used - want_used) <= 1.01 + (k - 1),
              f"(base {k:.2f} per shot)")
        # Sunder.
        hit, fresh = c.get("probe", (0, 0))
        want_hit = 100 + min(target_hits, 15) if 160 in rules and auto else 100
        check(f"{tag}: a 100 hit from elsewhere does {hit} (want {want_hit}), fresh target {fresh} (want 100)", hit == want_hit and fresh == 100)
    return cases


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "autotest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("automatics_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AutoPerkTest" }\n')
        z.writestr("cvarinfo.txt", "server noarchive bool autotest_hold = false;\n")
    checks = []
    only = sys.argv[4:]
    drla = [MODS / n for n in DRLA] + [mod, harness]
    for name, files, bridged, timeout in (("stock", [mod, harness], True, 120), ("drla", drla, True, 300),
                                          ("nobridge", [mod, harness], False, 60)):
        if only and name not in only:
            continue
        peer = Peer(dll) if bridged else None
        try:
            lines = launch(exe, work, files, peer, name, timeout, ("+set", "autotest_hold", "1", "+wait", "105", "++attack") if name == "drlaheld" else ())
        finally:
            if peer:
                peer.close()
        if name == "nobridge":
            checks.append(not any("automatics:" in l for l in lines))
            print(f"{'PASS' if checks[-1] else 'FAIL'} nobridge: no perk activity without a Daggerfall character")
        analyse(name, lines, checks, held=name == "drlaheld")
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
