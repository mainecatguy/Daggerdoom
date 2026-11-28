"""Explosives perks in Doom (mods/doomerfall/src/zscript/DoomerfallExplosives.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/explosives/explosives_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The peer is Daggerfall's side of the bridge: it writes the character sheet with the DFB_SHEET_EXPL_* rule set the
harness (explosives_test.zs) asks for. The harness fires one rocket per case and logs what everyone lost; the perk code
logs what it changed (+set dd_perklog 1). Runs DOOM.WAD E1M1:
  stock    doomerfall.pk3 only: the stock RocketLauncher.
  drla     play_drlax.bat's DRLA set: RLRocketLauncher (and the stock RocketLauncher class).
  nobridge doomerfall.pk3 only, no bridge session: nothing changes.
Rule sets: off, dmg (+60%), self25 / self75 (own splash cut 95% / 99%), direct (+50% on the direct hit: a test value,
the owner has not set the amount), chain (Inpulsa's Broken Heart: 25% of max health, radius 128).
Cases: shot, pointblank, switch (another gun up while the slowed rocket flies: still the launcher's hit), chain (A kills B kills an imp) and pack (a grid of up to 400 monsters a rocket cannot kill, 130 health left).
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
RULES = {  # 162 damage, 163 self cut, 164 direct, 165/166 chain bp/radius
    "off": {}, "dmg": {162: 6000}, "self25": {163: 9500}, "self75": {163: 9900}, "direct": {164: 5000},
    "chain": {165: 2500, 166: 128}}
SPAWN_HEALTH = {"ExpTestMonster": 1000, "ExpPackMonster": 4000, "DoomImp": 60}
BAD = re.compile(r'Script error, "(doomerfall|exptest)\.pk3|(doomerfall|exptest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
HIT = re.compile(r"explosives: hit (\S+) (direct|splash): (\d+) -> (\d+) \(x([\d.]+)\) tic (\d+) by (\S+)")
SELF = re.compile(r"explosives: self (\d+) -> (\d+) \(cut (\d+) bp\) by (\S+)")
BLAST = re.compile(r"explosives: blast (\S+) gen (\d+) damage (\d+) radius (\d+) hit (\d+) tic (\d+)")
WORST = re.compile(r"explosives: chain worst tic ([\d.]+) ms for (\d+) blasts, queue peak (\d+)")


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.id = "dfexpl" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
        self.sheet("off")

    def sheet(self, cfg):
        v = [0] * SHEET_INTS
        v[0], v[1], v[2], v[159] = SHEET_FORMAT_VERSION, 1, 1, 1
        v[24 + 2] = 50  # live Willpower 50: the Willpower rule leaves the damage the player takes unchanged (x1)
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
                wants = re.findall(r"EXPTEST want (\w+)", text)
                if peer and len(wants) > asked:
                    peer.sheet(wants[-1])
                    asked = len(wants)
                if "EXPTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def cases_of(lines):
    cases, cur = [], None
    for l in lines:
        if m := re.search(r"EXPTEST case (\w+) (\w+) (\w+) cat=(\w+) slot=(-?\d+)", l):
            cur = {"cfg": m.group(1), "kind": m.group(2), "gun": m.group(3), "cat": m.group(4), "slot": int(m.group(5)),
                   "hits": [], "self": [], "blasts": [], "kills": [], "phurt": [], "tags": [], "held": [], "worst": [], "lines": []}
            cases.append(cur)
        elif cur is None:
            continue
        elif m := re.search(r"EXPTEST end \w+ \w+ \w+ target=(\d+)/(\d+) player=(\d+) blasthurt=(\d+) dead=(\d+)/(\d+) gap=([\d.]+)", l):
            cur["end"] = dict(zip(("thits", "tlost", "plost", "blasthurt", "dead", "size", "gap"), map(float, m.groups())))
            cur = None
        else:
            cur["lines"].append(l)
            if h := HIT.search(l):
                cur["hits"].append(h)
            elif s := SELF.search(l):
                cur["self"].append(s)
            elif b := BLAST.search(l):
                cur["blasts"].append(b)
            elif w := WORST.search(l):
                cur["worst"].append(w)
            elif k := re.search(r"EXPTEST killed (\S+) by (\S+) tic (\d+)", l):
                cur["kills"].append((k.group(1), k.group(2), int(k.group(3))))
            elif ph := re.search(r"EXPTEST player hurt (\d+) by (\S+)", l):
                cur["phurt"].append((int(ph.group(1)), ph.group(2)))
            elif hd := re.search(r"EXPTEST target hit held (\S+) slot (-?\d+)", l):
                cur["held"].append((hd.group(1), int(hd.group(2))))
            elif "shots: tag " in l:
                cur["tags"].append(l)
    return cases


def rounded(d, f):
    return {max(0, math.floor(d * f + 1e-9)), math.ceil(d * f - 1e-9)}


def analyse(name, lines, checks, report):
    def check(label, ok, detail=""):
        checks.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {'' if ok else detail}", flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("EXPTEST done" in l for l in lines))
    base_self = {}
    for c in cases_of(lines):
        tag = f"{c['cfg']} {c['kind']} {c['gun']}"
        e = c.get("end")
        if not e:
            check(f"{tag}: case ended", False)
            continue
        check(f"{tag}: the gun is an Explosives gun (slot 6)", c["slot"] == 6, c["cat"])
        rocket_hurt = sum(d for d, inf in c["phurt"] if inf != "DoomerfallChainBlast")
        if c["kind"] in ("shot", "pointblank", "switch"):
            check(f"{tag}: the target was hit", e["thits"] > 0 and e["tlost"] > 0, e)
            check(f"{tag}: the shot's splash reached the player", rocket_hurt > 0 or c["self"], c["phurt"])
        if c["cfg"] == "off":
            base_self[(c["gun"], c["kind"])] = rocket_hurt
            check(f"{tag}: no perk changes with the rules off", not c["hits"] and not c["self"] and not c["blasts"], c["hits"][:2])
        elif c["cfg"] == "dmg":
            fs = {round(float(h.group(5)), 4) for h in c["hits"]}
            kinds = {h.group(2) for h in c["hits"]}
            check(f"{tag}: every hit x1.6, direct and splash", fs == {1.6} and kinds == {"direct", "splash"}, (fs, kinds))
            bad = [h.group(0) for h in c["hits"] if int(h.group(4)) not in rounded(int(h.group(3)), 1.6)]
            check(f"{tag}: rounding", not bad, bad[:3])
            check(f"{tag}: the target lost what the hit lines say", sum(int(h.group(4)) for h in c["hits"] if h.group(1) == "ExpTestTarget") == e["tlost"],
                  (e["tlost"], [h.group(0) for h in c["hits"]]))
            if c["kind"] == "switch":
                check(f"{tag}: another gun was up when the rocket hit", c["held"] and all(s != 6 for _, s in c["held"]), c["held"])
                report.append(f"{name} {tag}: held at the hit {sorted(set(h for h, _ in c['held']))}, hits {[h.group(0)[12:] for h in c['hits']]}")
            else:
                check(f"{tag}: no cut to the player's own splash", not c["self"] and rocket_hurt > 0, c["self"][:2])
        elif c["cfg"] in ("self25", "self75"):
            cut = RULES[c["cfg"]][163]
            f = 1 - cut / 10000
            bad = [s.group(0) for s in c["self"] if int(s.group(3)) != cut or int(s.group(2)) not in rounded(int(s.group(1)), f)]
            check(f"{tag}: the player's own splash is cut by {cut / 100:g}%", c["self"] and not bad, (bad[:3], c["phurt"]))
            # The harness takes DRLA's random starting armor away first (it absorbs, or adds to, a hit after the perk).
            cut_sum = sum(int(s.group(2)) for s in c["self"])
            check(f"{tag}: the player lost what the self lines say", cut_sum == rocket_hurt, (rocket_hurt, [s.group(0) for s in c["self"]], c["phurt"]))
            off = base_self.get((c["gun"], "shot"))
            if c["kind"] == "shot" and off:
                check(f"{tag}: about {cut / 100:g}% less own splash than with the rules off ({off})",
                      abs(rocket_hurt - off * f) <= max(2, 0.02 * off), rocket_hurt)
            check(f"{tag}: no damage bonus to the target", not c["hits"], c["hits"][:2])
            base = base_self.get((c["gun"], "shot"))
            report.append(f"{name} {tag}: own splash {sum(int(s.group(1)) for s in c['self'])} -> {rocket_hurt} (rules off: {base})")
            if c["kind"] == "pointblank":
                check(f"{tag}: the point-blank rocket was recognised", any(" skill 6 gen 0 " in t for t in c["tags"]), c["tags"])
        elif c["cfg"] == "direct":
            fs = {(h.group(2), round(float(h.group(5)), 4)) for h in c["hits"]}
            check(f"{tag}: only the direct hit gets +50%", fs == {("direct", 1.5)}, fs)
            check(f"{tag}: the target lost what the hit lines say plus unboosted splash", sum(int(h.group(4)) for h in c["hits"]) <= e["tlost"], e)
        elif c["cfg"] == "chain":
            bad = []
            for b in c["blasts"]:
                want = int(SPAWN_HEALTH.get(b.group(1), -1) * 0.25 / (1 << int(b.group(2))))
                if int(b.group(3)) != want or int(b.group(4)) != 128:
                    bad.append(b.group(0))
            check(f"{tag}: blasts are 25% of max health halved each generation, radius 128", c["blasts"] and not bad, bad[:3])
            check(f"{tag}: blasts never hurt the player", e["blasthurt"] == 0, e)
            check(f"{tag}: no damage bonus on blasts", not any(h.group(7) == "DoomerfallChainBlast" for h in c["hits"]))
            gens = sorted({int(b.group(2)) for b in c["blasts"]})
            if c["kind"] == "chain":
                imp = [k for k in c["kills"] if k[0] == "DoomImp"]
                check(f"{tag}: A, B and the imp all died, the imp by a chained blast", e["dead"] == 3 and imp and imp[0][1] == "DoomerfallChainBlast", (c["kills"], gens))
                check(f"{tag}: at least two generations", len(gens) >= 2 and gens[0] == 0, gens)
                report.append(f"{name} {tag}: kills {c['kills']} generations {gens}")
            else:
                worst = max((float(w.group(1)) for w in c["worst"]), default=0)
                peak = max((int(w.group(3)) for w in c["worst"]), default=0)
                tics = [b_ for b_ in (int(b.group(6)) for b in c["blasts"])]
                span = (max(tics) - min(tics) + 1) if tics else 0
                per_tic = max((tics.count(x) for x in set(tics)), default=0)
                check(f"{tag}: the chain killed the pack", e["size"] >= 100 and e["dead"] >= 0.9 * e["size"], e)
                check(f"{tag}: at most 16 blasts per tic", per_tic <= 16, per_tic)
                check(f"{tag}: the worst tic of blasts stays under one tic (28.6 ms)", worst < 28.6, worst)
                report.append(f"{name} {tag}: pack {int(e['size'])}, dead {int(e['dead'])}, blasts {len(c['blasts'])} over {span} tics "
                              f"(max {per_tic} per tic), generations {gens[0] if gens else '-'}..{gens[-1] if gens else '-'}, "
                              f"worst blast tic {worst:.2f} ms, queue peak {peak}, worst wall gap between tics {e['gap']:.1f} ms")


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "exptest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("explosives_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ExpPerkTest" }\n')
    checks, report = [], []
    only = sys.argv[4:]
    drla = [MODS / n for n in DRLA] + [mod, harness]
    for name, files, bridged, timeout in (("stock", [mod, harness], True, 180), ("drla", drla, True, 300),
                                          ("nobridge", [mod, harness], False, 60)):
        if only and name not in only:
            continue
        peer = Peer(dll) if bridged else None
        try:
            lines = launch(exe, work, files, peer, name, timeout)
        finally:
            if peer:
                peer.close()
        if name == "nobridge":
            checks.append(not any("explosives:" in l for l in lines))
            print(f"{'PASS' if checks[-1] else 'FAIL'} nobridge: no perk activity without a Daggerfall character")
        analyse(name, lines, checks, report)
    print("\n" + "\n".join(report))
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
