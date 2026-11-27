"""Shotguns perks in Doom (mods/doomerfall/src/zscript/DoomerfallShotguns.zs) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/shotguns/shotguns_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The peer is Daggerfall's side of the bridge: it writes the character sheet with the DFB_SHEET_SHOT_* rule set the
harness (shotguns_test.zs) asks for. The perk code logs what it changed (+set dd_perklog 1). DOOM.WAD E1M1:
  stock    doomerfall.pk3 only: the stock Shotgun (DOOM.WAD has no Super Shotgun).
  drla     play_drlax.bat's DRLA set: RLShotgun, RLDoubleShotgun, RLAssaultShotgun, RLAutoshotgun (and the stock classes).
  nobridge doomerfall.pk3 only, no bridge session: nothing changes.
"""
import ctypes as C, math, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402

IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SHEET_INTS, SHEET_FORMAT_VERSION = 181, 11
RULES = {  # 167 damage, 168 reload cut, 169 pellets, 170 knock, 171 slam, 172 collide
    "off": {}, "dmg": {167: 7500}, "reload": {168: 3500}, "reloadheld": {168: 3500}, "p50": {169: 5000}, "p100": {169: 10000},
    "knock": {170: 10000, 171: 200}, "knock100": {169: 10000, 170: 20000, 171: 400}, "collide": {170: 10000, 171: 200, 172: 200}, "switch": {167: 7500}}
BAD = re.compile(r'Script error, "(doomerfall|shottest)\.pk3|(doomerfall|shottest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
CASE = re.compile(r"SHOTTEST case (\w+) (\w+) cat=(\w+) slot=(-?\d+) sub=(\d)")
SHOT = re.compile(r"SHOTTEST shot (\w+) (\w+) n=(\d+) hits=(\d+) lost=(\d+) cycle=(\d+)")
RELOAD = re.compile(r"SHOTTEST reload (\w+) (\w+) tics=(\d+) mag=(-?\d+)")
KNOCKT = re.compile(r"SHOTTEST knock (\w+) (\w+) sub=(\d) moved=([\d.]+) pain=(\d) hits=(\d+) lost=(\d+) lost2=(\d+)")
SHOTGUNS = {"Shotgun", "SuperShotgun", "RLShotgun", "RLDoubleShotgun", "RLAssaultShotgun", "RLAutoshotgun", "RLPlasmaShotgun"}
HIT = re.compile(r"shotguns: hit (\S+) with (\S+): (\d+) -> (\d+)")
PELLETS = re.compile(r"shotguns: pellets (\S+) (\d+) -> (\d+)")
RFRAME = re.compile(r"shotguns: reload (\S+) frame (\d+) -> (\d+) tics")
KNOCK = re.compile(r"shotguns: knock (\S+) pellets (\d+) share ([\d.]+) size ([\d.]+) speed ([\d.]+)( stagger)?")
SLAM = re.compile(r"shotguns: (slam|collide|collided) (\S+) speed share ([\d.]+) damage (\d+) \(most (\d+)\)")


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.id = "dfshot" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
        self.sheet("off")

    def sheet(self, cfg):
        v = [0] * SHEET_INTS
        v[0], v[1], v[2], v[159] = SHEET_FORMAT_VERSION, 1, 1, 1
        v[32 + 4] = v[67 + 4] = 50  # Shotguns above Energy Weapons, so the Plasma Shotgun uses Shotguns
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
                for m in re.finditer(r"SHOTTEST want (\w+)", text):
                    if peer and m.group(1) not in asked:
                        asked.add(m.group(1))
                        peer.sheet(m.group(1))
                if "SHOTTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def split_cases(lines):
    """Lines grouped by (cfg, gun, sub), in order."""
    cases, cur = {}, None
    for l in lines:
        if m := CASE.search(l):
            cur = (m.group(1), m.group(2), int(m.group(5)))
            cases[cur] = {"cat": m.group(3), "slot": int(m.group(4)), "lines": []}
        elif "SHOTTEST end" in l or "SHOTTEST want" in l:
            if cur and "SHOTTEST end" in l:
                cases[cur]["lines"].append(l)
            cur = None
        elif cur:
            cases[cur]["lines"].append(l)
    return cases


def shots_of(lines):
    """Per shot: the perk lines since its fire line, and the harness's shot line."""
    out, buf = [], []
    for l in lines:
        if "SHOTTEST fire" in l:
            buf = []
        elif m := SHOT.search(l):
            out.append((m, buf))
            buf = []
        else:
            buf.append(l)
    return out


def analyse(name, lines, checks, report):
    def check(label, ok, detail=""):
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {'' if ok else detail}", flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("SHOTTEST done" in l for l in lines) and not any("SHOTTEST nospot" in l for l in lines))
    check("no stuck or unselected guns", not any(re.search(r"SHOTTEST (stuck|noselect|timeout)", l) for l in lines),
          [l for l in lines if re.search(r"SHOTTEST (stuck|noselect|timeout)", l)][:3])
    cases = split_cases(lines)
    base = {}
    for (cfg, gun, sub), c in cases.items():
        tag = f"{cfg} {gun}{' heavy' if sub else ''} ({c['cat']}, slot {c['slot']})"
        check(f"{tag}: reads as Shotguns (slot 4)", c["slot"] == 4)
        L = c["lines"]
        perk = [l for l in L if "shotguns:" in l]
        shots = shots_of(L)
        if cfg == "switch":
            res = [m for l in L if (m := re.search(r"SHOTTEST switchres hits=(\d+) lost=(\d+) held=(\S+)", l))]
            held = [m for l in L if (m := re.search(r"SHOTTEST heldhit (\S+) tic=(\d+)", l))]
            hl = [HIT.search(l) for l in perk if HIT.search(l)]
            r = res[0] if res else None
            check(f"{tag}: the slowed pellets hit after the switch", bool(r and int(r.group(1)) > 0 and held), L[-6:])
            check(f"{tag}: another gun was up at every hit", bool(held) and all(h.group(1) not in SHOTGUNS for h in held), [h.group(0) for h in held][:3])
            bad = [h.group(0) for h in hl if int(h.group(4)) not in (max(1, math.floor(int(h.group(3)) * 1.75 + 1e-9)), math.ceil(int(h.group(3)) * 1.75 - 1e-9))]
            check(f"{tag}: every hit still +75% (one hit line per hit, the target lost what they say)",
                  bool(r and hl and not bad and len(hl) == int(r.group(1)) and sum(int(h.group(4)) for h in hl) == int(r.group(2))),
                  (bad[:3], len(hl), r and r.group(0)))
            if r:
                report.append(f"{gun} switch: held at the hits {sorted({h.group(1) for h in held})}, {r.group(1)} hits, lost {r.group(2)}")
            continue
        if cfg in ("off", "dmg", "reload", "reloadheld", "p50", "p100"):
            check(f"{tag}: 5 shots hit", len(shots) == 5 and all(int(m.group(4)) > 0 for m, _ in shots), len(shots))
            hits = [int(m.group(4)) for m, _ in shots]
            cycles = [int(m.group(6)) for m, _ in shots]
            rl = [RELOAD.search(l) for l in L if RELOAD.search(l)]
            if cfg == "off":
                base[gun] = {"hits": sum(hits) / max(1, len(hits)), "cycle": cycles, "reload": int(rl[0].group(3)) if rl else None}
                check(f"{tag}: no perk activity with every rule off", not perk, perk[:3])
                report.append(f"{gun}: {base[gun]['hits']:.1f} pellets per shot, shot-to-ready {cycles} tics"
                              + (f", empty-magazine reload {base[gun]['reload']} tics" if rl else ""))
            if cfg == "dmg":
                bad = []
                hl = [HIT.search(l) for l in perk if HIT.search(l)]
                for h in hl:
                    d, n = int(h.group(3)), int(h.group(4))
                    if n not in (max(1, math.floor(d * 1.75 + 1e-9)), math.ceil(d * 1.75 - 1e-9)):
                        bad.append(f"{d} -> {n}")
                total_hits, total_lost = sum(hits), sum(int(m.group(5)) for m, _ in shots)
                if len(hl) != total_hits:
                    bad.append(f"{len(hl)} hit lines for {total_hits} hits")
                if sum(int(h.group(4)) for h in hl) != total_lost:
                    bad.append(f"target lost {total_lost}, hit lines say {sum(int(h.group(4)) for h in hl)}")
                check(f"{tag}: every pellet does +75% and the target lost what the code logged", not bad and hl, bad[:4])
            if cfg == "reload":
                base.setdefault(gun, {})["rcycle"] = cycles
            if cfg == "reloadheld":
                # Same rule as "reload", but the reload key is held through every shot's recovery: nothing may change.
                want = base.get(gun, {}).get("rcycle")
                check(f"{tag}: holding reload after shots leaves the shot cycle as without it {cycles} vs {want}", cycles == want)
            if cfg in ("p50", "p100") and gun == "RLPlasmaShotgun":
                check(f"{tag}: projectile pellets are not multiplied (open question)", not any(PELLETS.search(l) for l in perk))
            elif cfg in ("p50", "p100"):
                f = 1.5 if cfg == "p50" else 2.0
                bad = []
                for m, buf in shots:
                    pl = [PELLETS.search(l) for l in buf if PELLETS.search(l)]
                    for x in pl:
                        a, b = int(x.group(2)), int(x.group(3))
                        if b not in (math.floor(a * f), math.ceil(a * f)):
                            bad.append(f"{a} -> {b}")
                    if not pl or sum(int(x.group(3)) for x in pl) != int(m.group(4)):
                        bad.append(f"shot {m.group(3)}: {int(m.group(4))} hits, pellet lines say {sum(int(x.group(3)) for x in pl)}")
                ratio = (sum(hits) / len(hits)) / base[gun]["hits"] if gun in base and hits else 0
                check(f"{tag}: x{f} pellets per call, all fired and hit; average x{ratio:.2f} over 'off'",
                      not bad and abs(ratio - f) <= 0.3, bad[:4])
                report.append(f"{gun} {cfg}: {sum(hits) / max(1, len(hits)):.1f} pellets per shot (x{ratio:.2f})")
            if cfg == "reload":
                b = base.get(gun, {})
                if b.get("reload") is not None:  # only the timed reload from an empty magazine
                    win = [i for i, l in enumerate(L) if "SHOTTEST reloadstart" in l or RELOAD.search(l)]
                    scope = L[win[0]:win[-1] + 1] if len(win) == 2 else []
                else:
                    scope = perk
                frames = [RFRAME.search(l) for l in scope if RFRAME.search(l)]
                cut = sum(int(x.group(2)) - int(x.group(3)) for x in frames)
                elig = sum(int(x.group(2)) for x in frames if int(x.group(2)) > 1)
                if b.get("reload") is not None:  # magazine gun: the timed reload from empty
                    got = int(rl[0].group(3)) if rl else None
                    measured, before = (b["reload"] - got if got is not None else None), b["reload"]
                    where = "empty-magazine reload"
                    rframes = [x for x in frames]
                else:
                    measured, before = sum(b.get("cycle", [])) - sum(cycles), sum(b.get("cycle", []))
                    where = "shot-to-ready cycles (pump/reload frames after the shot)"
                share = cut / elig if elig else 0
                ok = elig > 0 and 0.25 <= share <= 0.40 and measured is not None and abs(measured - cut) <= (1 if b.get("reload") is not None else 5)
                check(f"{tag}: {where} cut {cut} of {elig} tics ({share:.0%}); measured {measured} fewer tics", ok,
                      f"frames {[(x.group(2), x.group(3)) for x in frames][:12]}")
                if before:
                    report.append(f"{gun} reload: {where}: {before} -> {before - (measured or 0)} tics ({(measured or 0) / before:.0%} shorter)")
        else:
            km = [KNOCKT.search(l) for l in L if KNOCKT.search(l)]
            kl = [KNOCK.search(l) for l in perk if KNOCK.search(l)]
            sl = [SLAM.search(l) for l in perk if SLAM.search(l)]
            if not km or len(kl) != 1:
                check(f"{tag}: one knock per shot", False, f"{len(kl)} knock lines, harness {bool(km)}")
                continue
            k, h = kl[0], km[0]
            strength, slam_most = {"knock": (1, 200), "knock100": (2, 400), "collide": (1, 200)}[cfg]
            pm = 2 if cfg == "knock100" else 1
            share = min(1, int(k.group(2)) / (14 * pm))
            size = min(1, math.sqrt(100 / (1000 if sub else 100)))
            speed = 16 * strength * share * size
            ok = (abs(float(k.group(3)) - share) < 2e-3 and abs(float(k.group(4)) - size) < 2e-3 and abs(float(k.group(5)) - speed) < 0.02
                  and int(k.group(2)) == int(h.group(6)) - sum(1 for s in sl if s.group(1) in ("slam", "collide")))
            check(f"{tag}: knock speed 16 x {strength} x pellets {k.group(2)}/{14 * pm} x size {size:.3f} = {speed:.2f}", ok, k.group(0))
            check(f"{tag}: staggered {'(shove >= 4)' if speed >= 4 else '(no, shove < 4)'}" + ("" if cfg == "collide" else " and moved"),
                  (h.group(5) == "1") == (speed >= 4) and (cfg == "collide" or float(h.group(4)) > 3), h.group(0))
            pellet_dmg = int(h.group(7)) - sum(int(s.group(4)) for s in sl if s.group(1) in ("slam", "collide"))
            if cfg == "collide":
                kinds = sorted(s.group(1) for s in sl)
                ok = kinds == ["collide", "collided"] and all(abs(int(s.group(4)) - 200 * float(s.group(3))) <= 1 and float(s.group(3)) > 0 for s in sl)
                # The second target takes the collision amount times any outgoing boost on the player (items'
                # ModifyDamage, measured by the harness on 1000 at the same moment; DRLA can add one).
                boost = next((int(m.group(1)) for l in L if (m := re.search(r"SHOTTEST boost (\d+)", l))), 1000)
                items = [l.split("SHOTTEST boostitem ")[1] for l in L if "SHOTTEST boostitem " in l]
                collided = next((int(s.group(4)) for s in sl if s.group(1) == "collided"), 0)
                ok = ok and abs(int(h.group(8)) - collided * boost / 1000) <= 1
                if boost != 1000:
                    report.append(f"{gun}{' heavy' if sub else ''} collide: outgoing boost on the player x{boost / 1000:.3f} "
                                  f"({', '.join(items) or 'no single item'}): collision {collided}, second target lost {h.group(8)}")
                check(f"{tag}: knocked into the second target, both take collision damage once", ok, [s.group(0) for s in sl])
            elif sub and not sl:  # a heavy enemy may stop before the wall
                check(f"{tag}: heavy enemy stopped short of the wall, no slam (moved {h.group(4)})", float(h.group(4)) < 40, h.group(0))
                report.append(f"{gun} heavy {cfg}: {k.group(2)} pellets, speed {float(k.group(5)):.1f}, moved {h.group(4)}, no slam")
            else:
                ok = len(sl) == 1 and sl[0].group(1) == "slam" and int(sl[0].group(5)) == slam_most and float(sl[0].group(3)) > 0
                ok = ok and abs(int(sl[0].group(4)) - slam_most * float(sl[0].group(3))) <= 1 and pellet_dmg > 0
                check(f"{tag}: one wall slam, damage = {slam_most} x speed share", ok, [s.group(0) for s in sl])
                if sl:
                    report.append(f"{gun}{' heavy' if sub else ''} {cfg}: {k.group(2)} pellets, speed {float(k.group(5)):.1f}, moved {h.group(4)}, "
                                  f"slam {sl[0].group(4)} (share {sl[0].group(3)}), pellets did {pellet_dmg}")
    return cases


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "shottest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("shotguns_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "ShotPerkTest" }\n')
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
            checks.append(not any("shotguns:" in l for l in lines))
            print(f"{'PASS' if checks[-1] else 'FAIL'} nobridge: no perk activity without a Daggerfall character")
        analyse(name, lines, checks, report)
    print("\nREPORT\n" + "\n".join(report))
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
