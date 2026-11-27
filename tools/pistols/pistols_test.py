"""Pistols perks in Doom (mods/doomerfall/src/zscript/DoomerfallPistols.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/pistols/pistols_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The peer is Daggerfall's side of the bridge: it writes the character sheet with the DFB_SHEET_PIST_* rule set the
harness (pistols_test.zs) asks for. The perk code logs what it changed (+set dd_perklog 1). DOOM.WAD E1M1:
  stock    doomerfall.pk3 only: the stock Pistol.
  drla     play_drlax.bat's DRLA set: RLPistol, RLHandcannon, RLMarksmanPistol (and the stock Pistol).
  nobridge doomerfall.pk3 only, no bridge session: nothing changes.
The fire-rate multipliers are not built (open), so they are not tested.
"""
import ctypes as C, math, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402

IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SHEET_INTS, SHEET_FORMAT_VERSION = 186, 10
POOL = {181: 100, 182: 500}
FRAG = {183: 3, 184: 3300, 185: 5}
RULES = {  # must match RuleOf in pistols_test.zs
    "off": {}, "reload": {179: 2000}, "reload60": {179: 6000},
    "pool": POOL, "carry": {180: 1, **POOL}, "frag": FRAG, "turn": FRAG, "carryfrag": {180: 1, **POOL, **FRAG}}
BAD = re.compile(r'Script error, "(doomerfall|pisttest)\.pk3|(doomerfall|pisttest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted|not implemented for', re.I)
CASE = re.compile(r"PISTTEST case (\w+) (\w+) cat=(\w+) slot=(-?\d+)")
SHOT = re.compile(r"PISTTEST shot (\w+) (\w+) n=(\d+) hits=(\d+) lost=(\d+) cycle=(\d+)")
RELOAD = re.compile(r"PISTTEST reload (\w+) (\w+) tics=(\d+) mag=(-?\d+)")
LINE = re.compile(r"PISTTEST line (\w+) (\w+) hitsA=(\d+) lostA=(\d+)(.*)")
DMG = re.compile(r"PISTTEST damage (\w) (\d+) inflictor (\S+) health (-?\d+)")
HIT = re.compile(r"pistols: hit (\S+) with (\S+): (\d+) -> (\d+) \(pool \+(\d+)\)")
RFRAME = re.compile(r"pistols: reload (\S+) frame (\d+) -> (\d+) tics")
CARRY = re.compile(r"pistols: carry (\S+) -> (\S+) damage (\d+)")
FRAGL = re.compile(r"pistols: fragment (\S+) -> (\S+) damage (\d+) of (\d+)( turned)?")
TIC = re.compile(r"PISTTEST fire tic=(\d+)")
OUT = []  # every check line, also written to <work folder>/result.txt


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.id = "dfpist" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
        self.sheet("off")

    def sheet(self, cfg):
        v = [0] * SHEET_INTS
        v[0], v[1], v[2], v[159] = SHEET_FORMAT_VERSION, 1, 1, 1
        v[32 + 7] = v[67 + 7] = 50  # Pistols above the other gun skills, so a two-skill pistol uses Pistols
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
                for m in re.finditer(r"PISTTEST want (\w+)", text):
                    if peer and m.group(1) not in asked:
                        asked.add(m.group(1))
                        peer.sheet(m.group(1))
                if "PISTTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def split_cases(lines):
    cases, cur = {}, None
    for l in lines:
        if m := CASE.search(l):
            cur = (m.group(1), m.group(2))
            cases[cur] = {"cat": m.group(3), "slot": int(m.group(4)), "lines": []}
        elif "PISTTEST end" in l or "PISTTEST want" in l:
            cur = None
        elif cur:
            cases[cur]["lines"].append(l)
    return cases


def shots_of(lines):
    out, buf, tic = [], [], 0
    for l in lines:
        if m := TIC.search(l):
            buf, tic = [], int(m.group(1))
        elif m := SHOT.search(l):
            out.append((m, buf, tic))
            buf = []
        else:
            buf.append(l)
    return out


def r33(x):
    return max(1, int(math.floor(x * 0.33 + 0.5)))


def analyse(name, lines, checks, report):
    def check(label, ok, detail=""):
        checks.append(bool(ok))
        OUT.append(f"{'PASS' if ok else 'FAIL'} {name}: {label} {'' if ok else detail}")
        print(OUT[-1], flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("PISTTEST done" in l for l in lines) and not any("PISTTEST nospot" in l for l in lines))
    check("no stuck or unselected guns", not any(re.search(r"PISTTEST (stuck|noselect|timeout)", l) for l in lines),
          [l for l in lines if re.search(r"PISTTEST (stuck|noselect|timeout)", l)][:3])
    base = {}
    for (cfg, gun), c in split_cases(lines).items():
        tag = f"{cfg} {gun} ({c['cat']}, slot {c['slot']})"
        check(f"{tag}: reads as Pistols (slot 7)", c["slot"] == 7)
        L = c["lines"]
        perk = [l for l in L if "pistols:" in l]
        hl = [HIT.search(l) for l in perk if HIT.search(l)]
        if cfg in ("off", "reload", "reload60", "pool"):
            shots = shots_of(L)
            hits = [int(m.group(4)) for m, _, _ in shots]
            lost = sum(int(m.group(5)) for m, _, _ in shots)
            cycles = [int(m.group(6)) for m, _, _ in shots]
            rl = [RELOAD.search(l) for l in L if RELOAD.search(l)]
            check(f"{tag}: 5 shots hit", len(shots) == 5 and all(h > 0 for h in hits), len(shots))
            if cfg == "off":
                base[gun] = {"cycle": cycles, "reload": int(rl[0].group(3)) if rl else None}
                check(f"{tag}: no perk activity with every rule off", not [l for l in perk], perk[:3])
                report.append(f"{gun}: trigger-to-ready {cycles}"
                              + (f", empty-magazine reload {base[gun]['reload']} tics" if rl else ", no reload"))
            if cfg == "pool":
                bad, prev = [], None
                for (m, buf, tic) in shots:
                    for h in [HIT.search(l) for l in buf if HIT.search(l)]:
                        bonus = int(h.group(5))
                        gap = tic - prev if prev is not None else 999
                        want = min(100, gap * 100 / 17.5)
                        if not (want - 6 <= bonus <= 100) or int(h.group(4)) != int(h.group(3)) + bonus:
                            bad.append(f"gap {gap} bonus {bonus} ({h.group(3)} -> {h.group(4)})")
                        prev = tic
                ok = hl and not bad and len(hl) == sum(hits) and sum(int(h.group(4)) for h in hl) == lost and int(hl[0].group(5)) == 100
                check(f"{tag}: first hit +100, each later hit + what refilled since the last (100 per 0.5 s)", ok, (bad[:3], len(hl), lost))
                report.append(f"{gun} pool: bonuses {[int(h.group(5)) for h in hl]}")
            if cfg in ("reload", "reload60"):
                share_want = 0.2 if cfg == "reload" else 0.6
                b = base.get(gun, {})
                frames = [RFRAME.search(l) for l in perk if RFRAME.search(l)]
                cut = sum(int(x.group(2)) - int(x.group(3)) for x in frames)
                elig = sum(int(x.group(2)) for x in frames if int(x.group(2)) > 1)
                if b.get("reload") is None:
                    check(f"{tag}: no reload to shorten, nothing changed (shot cycles {cycles})", not frames and cycles == b.get("cycle"), perk[:3])
                else:
                    got = int(rl[0].group(3)) if rl else None
                    measured = b["reload"] - got if got is not None else None
                    share = cut / elig if elig else 0
                    ok = elig > 0 and abs(share - share_want) <= 0.08 and measured is not None and abs(measured - cut) <= 1
                    check(f"{tag}: empty-magazine reload cut {cut} of {elig} tics ({share:.0%}); measured {measured} fewer", ok,
                          f"frames {[(x.group(2), x.group(3)) for x in frames][:12]}")
                    check(f"{tag}: shots between reloads unchanged ({cycles})", cycles == b.get("cycle"))
                    report.append(f"{gun} {cfg}: reload {b['reload']} -> {got} tics ({(measured or 0) / b['reload']:.0%} shorter)")
            continue

        lm = [LINE.search(l) for l in L if LINE.search(l)]
        if not lm:
            check(f"{tag}: line case finished", False, L[-5:])
            continue
        ln = lm[0]
        got = dict(re.findall(r"(\w)=(\d+)", ln.group(5)))
        got = {k: int(v) for k, v in got.items()}
        aHits = [DMG.search(l) for l in L if DMG.search(l) and DMG.search(l).group(1) == "A"]
        cl = [CARRY.search(l) for l in perk if CARRY.search(l)]
        fl = [FRAGL.search(l) for l in perk if FRAGL.search(l)]
        hit = int(aHits[0].group(2)) if aHits else 0
        # A hit line only where the pool is on (carry sets); frag and turn have no rule that changes the hit itself.
        pooled = cfg in ("carry", "carryfrag")
        check(f"{tag}: one pistol hit on A" + (" with the pool" if pooled else ", unchanged"),
              len(aHits) == 1 and (len(hl) == 1 and int(hl[0].group(4)) == hit if pooled else not hl), (len(hl), len(aHits)))
        if cfg == "carry":
            left1, left2 = hit - 20, hit - 50
            # A dies (20 health) and B dies (30): C takes exactly the rest, and the chain ends when C survives.
            ok = len(cl) == 2 and [int(x.group(3)) for x in cl] == [left1, left2] and got.get("B") == left1 and got.get("C") == left2
            check(f"{tag}: hit {hit} kills A (20) -> B takes {left1} and dies (30) -> C takes {left2}; nothing else", ok,
                  ([x.group(0) for x in cl], got))
            report.append(f"{gun} carry: hit {hit}, carried {[int(x.group(3)) for x in cl]}, B lost {got.get('B')}, C lost {got.get('C')}")
            check(f"{tag}: no fragments without the 100 perk", not fl)
        elif cfg == "frag":
            f = r33(hit)
            ok = len(fl) == 3 and all(int(x.group(3)) == f and int(x.group(4)) == hit for x in fl)
            ok = ok and got.get("B") == f and got.get("C") == f and int(ln.group(4)) == hit
            check(f"{tag}: 3 fragments of {f} (33% of {hit}): B behind and C on the fork take {f} each, A only its hit", ok,
                  ([x.group(0) for x in fl], got, ln.group(4)))
            check(f"{tag}: no carry-through without the kill rule", not cl)
            report.append(f"{gun} frag: hit {hit}, fragments {[x.group(2) + ('*' if x.group(5) else '') for x in fl]}, B {got.get('B')}, C {got.get('C')}")
        elif cfg == "turn":
            f = r33(hit)
            turned = [x for x in fl if x.group(5)]
            ok = len(fl) == 3 and got.get("D") == f and got.get("E") == 0 and len(turned) == 1 and turned[0].group(2) == "PistTestThin"
            check(f"{tag}: the middle fragment turns into D (4 degrees off), E (7.5 degrees off every line) untouched", ok,
                  ([x.group(0) for x in fl], got))
            report.append(f"{gun} turn: fragments {[x.group(2) + (' turned' if x.group(5) else '') for x in fl]}, D {got.get('D')}, E {got.get('E')}")
        elif cfg == "carryfrag":
            left = hit - 20
            fromA = [x for x in fl if int(x.group(4)) == hit]
            fromB = [x for x in fl if int(x.group(4)) == left and x not in fromA]
            ok = (len(cl) == 1 and int(cl[0].group(3)) == left and len(fl) == 6 and len(fromA) == 3 and len(fromB) == 3
                  and all(int(x.group(3)) == r33(hit) for x in fromA) and all(int(x.group(3)) == r33(left) for x in fromB)
                  and got.get("B") == left + r33(hit))
            check(f"{tag}: A dies, B takes the carry {left} + A's middle fragment {r33(hit)}; 3 fragments from A's hit, "
                  f"3 from B's carry-through hit (at 33% of {left}), none from fragments", ok, ([x.group(0) for x in cl + fl], got))
            report.append(f"{gun} carryfrag: hit {hit}, carry {left}, fragments {len(fl)}, B lost {got.get('B')}")


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "pisttest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("pistols_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PistPerkTest" }\n')
    checks, report = [], []
    only = sys.argv[4:]
    drla = [MODS / n for n in DRLA] + [mod, harness]
    for name, files, bridged, timeout in (("stock", [mod, harness], True, 150), ("drla", drla, True, 400),
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
            checks.append(not any("pistols:" in l for l in lines))
            print(f"{'PASS' if checks[-1] else 'FAIL'} nobridge: no perk activity without a Daggerfall character")
        analyse(name, lines, checks, report)
    print("\nREPORT\n" + "\n".join(report))
    failed = checks.count(False)
    summary = f"{len(checks) - failed} of {len(checks)} checks passed\nRESULT {'PASS' if not failed else 'FAIL'}"
    print("\n" + summary)
    (work / "result.txt").write_text("\n".join(OUT + ["", "REPORT"] + report + ["", summary]) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
