"""The owner's perk numbers (perknumbers 01), live from a real character sheet.

usage: python quiet_run.py --timeout 600 -- python tools/perknumbers/perknumbers_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder> [stock|drla|nobridge ...]

The fake Daggerfall peer writes a character sheet with live skills and attributes only (no hand-picked rule set, no
dd_ruletest), so Doom's rules (DoomerfallRules.Compute) produce every number checked here:
  e49 / e50  Explosives 49 / 50: the direct rocket hit gets x(1 + skill bonus) and, from 50, x1.5 more; splash only
             the skill bonus.
  e100       Explosives 100 and every attribute 100: Inpulsa's blast from a 1000-health monster is 250 at the centre,
             falls off over radius 128 like a rocket's (damage x (1 - distance / 128)), with no bonus of any kind.
  s74 / s75 / s100  Shotguns: no slam below 75; a wall slam of at most 200 at 75 and 400 at 100, scaled by the
             target's speed against the strongest launch. The target stands 4 units from the wall, so it slams at full
             speed: exactly 200 / 400 with DRLA's Double Shotgun (every pellet hits); stock Doom's Shotgun is logged.
Runs DOOM.WAD E1M1: stock (doomerfall.pk3), drla (play_drlax.bat's DRLA set) and nobridge (no Daggerfall: nothing).
"""
import ctypes as C, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402

IWAD = Path(r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SHEET_INTS, SHEET_FORMAT_VERSION = 203, 13
STATS_LIVE, SKILLS_BASE, SKILLS_LIVE = 24, 32, 67
SHOTGUNS, EXPLOSIVES = 4, 6
SHEETS = {"e49": (49, 0, 50), "e50": (50, 0, 50), "e100": (100, 0, 100), "s74": (0, 74, 50), "s75": (0, 75, 50),
          "s100": (0, 100, 50)}  # Explosives, Shotguns, every attribute
BAD = re.compile(r'Script error, "(doomerfall|pntest)\.pk3|(doomerfall|pntest)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
HIT = re.compile(r"explosives: hit (\S+) (direct|splash): (\d+) -> (\d+) \(x([\d.]+)\)")
BLAST = re.compile(r"explosives: blast (\S+) gen (\d+) damage (\d+) radius (\d+) hit (\d+)")
BLASTHIT = re.compile(r"PNTEST blasthit len ([\d.]+) inz (\d) dmg (\d+)")
DUMMY = re.compile(r"PNTEST dummy len (\d+) fits (\d) sight (\d)")
KNOCK = re.compile(r"shotguns: knock (\S+) pellets (\d+) share ([\d.]+)")
SLAM = re.compile(r"shotguns: slam (\S+) speed share ([\d.]+) damage (\d+) \(most (\d+)\)")
LOST = re.compile(r"PNTEST target lost (\d+) by (\S+)")


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.id = "dfpn" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
        self.sheet("e49")

    def sheet(self, cfg):
        expl, shot, attr = SHEETS[cfg]
        v = [0] * SHEET_INTS
        v[0], v[1], v[2] = SHEET_FORMAT_VERSION, 1, 1
        for i in range(8):
            v[STATS_LIVE + i] = v[STATS_LIVE - 8 + i] = attr
        for base in (SKILLS_BASE, SKILLS_LIVE):
            v[base + SHOTGUNS], v[base + EXPLOSIVES] = shot, expl
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
                wants = re.findall(r"PNTEST want (\w+)", text)
                if peer and len(wants) > asked:
                    peer.sheet(wants[-1])
                    asked = len(wants)
                if "PNTEST done" in text or BAD.search(text):
                    break
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def cases_of(lines):
    cases, cur = [], None
    for l in lines:
        if m := re.search(r"PNTEST case (\w+) (\w+) (\w+) slot=(-?\d+)", l):
            cur = {"cfg": m.group(1), "kind": m.group(2), "gun": m.group(3), "slot": int(m.group(4)), "lines": []}
            cases.append(cur)
        elif cur is None:
            continue
        elif m := re.search(r"PNTEST end \w+ \w+ lost=(\d+)", l):
            cur["lost"] = int(m.group(1))
            cur = None
        else:
            cur["lines"].append(l)
    return cases


def found(rx, lines):
    return [m for m in map(rx.search, lines) if m]


def analyse(name, lines, checks, report):
    def check(label, ok, detail=""):
        checks.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}: {label} {'' if ok else detail}", flush=True)

    check("no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    check("finished", any("PNTEST done" in l for l in lines))
    cases = cases_of(lines)
    check("every case ran", sorted(c["cfg"] for c in cases) == sorted(SHEETS), [c["cfg"] for c in cases])
    for c in cases:
        tag = f"{c['cfg']} {c['gun']}"
        ls = c["lines"]
        if "lost" not in c:
            check(f"{tag}: case ended", False)
            continue
        if c["kind"] == "shot":
            expl = SHEETS[c["cfg"]][0]
            bonus = 1 + 6000 * expl // 100 / 10000
            direct = bonus * (1.5 if expl >= 50 else 1)
            hits = [h for h in found(HIT, ls) if h.group(1) == "PNTarget"]
            d = [h for h in hits if h.group(2) == "direct"]
            s = [h for h in hits if h.group(2) == "splash"]
            check(f"{tag}: one direct hit at x{direct:.4f}", len(d) == 1 and abs(float(d[0].group(5)) - direct) < 1e-4, [h.group(0) for h in hits])
            check(f"{tag}: splash at x{bonus:.4f} only", all(abs(float(h.group(5)) - bonus) < 1e-4 for h in s), [h.group(0) for h in s])
            if d:
                raw, got = int(d[0].group(3)), int(d[0].group(4))
                check(f"{tag}: direct damage {raw} -> {got} rounds from {raw * direct:.2f}", got in (int(raw * direct), int(raw * direct) + 1), d[0].group(0))
                report.append(f"{name} {tag}: direct {raw} -> {got} (x{float(d[0].group(5)):.4f} = skill x{bonus:.3f}"
                              f"{' x Explosives 50 1.5' if expl >= 50 else ''}); splash {[h.group(3) + '->' + h.group(4) for h in s]}")
        elif c["kind"] == "chain":
            blasts = found(BLAST, ls)
            check(f"{tag}: one blast of 250 (25% of 1000), radius 128", [(b.group(1), int(b.group(3)), int(b.group(4))) for b in blasts] == [("PNChainMonster", 250, 128)],
                  [b.group(0) for b in blasts])
            dummies = found(DUMMY, ls)
            seen = {int(m.group(1)) for m in dummies if m.group(3) == "1"}
            bh = found(BLASTHIT, ls)
            bad = [m.group(0) for m in bh if m.group(2) != "1" or int(m.group(3)) != int(250 * (1 - float(m.group(1)) / 128))]
            check(f"{tag}: each dummy took 250 x (1 - distance / 128), no bonus", bh and not bad, bad)
            check(f"{tag}: the dummy at the centre took exactly 250", any(float(m.group(1)) == 0 and int(m.group(3)) == 250 for m in bh), [m.group(0) for m in bh])
            near = [m for m in bh if 0 < float(m.group(1)) < 128]
            check(f"{tag}: at least 3 dummies between the centre and the edge took less", len(near) >= 3, (seen, [m.group(0) for m in bh]))
            hit_lens = {round(float(m.group(1))) for m in bh}
            check(f"{tag}: every dummy in sight and in reach was hit", {x for x in seen if x < 128} <= hit_lens, (seen, hit_lens))
            check(f"{tag}: nothing beyond 128 was hurt", all(float(m.group(1)) < 128 for m in bh), [m.group(0) for m in bh])
            check(f"{tag}: the blast never got the Explosives bonus", not any("DoomerfallChainBlast" in h.group(0) for h in found(HIT, lines)))
            report.append(f"{name} {tag}: blast {[b.group(3) for b in blasts]}; dummies (distance: damage) "
                          f"{[(round(float(m.group(1))), int(m.group(3))) for m in bh]}; in sight {sorted(seen)}")
        else:  # slam
            shot = SHEETS[c["cfg"]][1]
            most = 400 if shot >= 100 else 200 if shot >= 75 else 0
            knocks, slams = found(KNOCK, ls), found(SLAM, ls)
            if not most:
                check(f"{tag}: no knockback or slam below 75", not knocks and not slams, [m.group(0) for m in knocks + slams])
                continue
            ok = len(slams) == 1 and int(slams[0].group(4)) == most and 0 < int(slams[0].group(3)) <= most
            ok = ok and int(slams[0].group(3)) == round(most * float(slams[0].group(2)))
            check(f"{tag}: one wall slam of up to {most}, scaled by speed", ok, [m.group(0) for m in knocks + slams])
            lost_slam = [int(m.group(1)) for m in found(LOST, ls) if m.group(2) == "None"]
            check(f"{tag}: the target lost the slam damage", slams and lost_slam == [int(slams[0].group(3))], (lost_slam, [m.group(0) for m in slams]))
            if c["gun"] == "RLDoubleShotgun":
                check(f"{tag}: a slam at full speed is the full {most}", slams and int(slams[0].group(3)) == most, [m.group(0) for m in knocks + slams])
            report.append(f"{name} {tag}: {'; '.join(m.group(0) for m in knocks + slams)}")


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    mod = work / "doomerfall.pk3"
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(mod)], check=True)
    harness = work / "pntest.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("perknumbers_test.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PNTest" }\n')
    checks, report = [], []
    only = sys.argv[4:]
    drla = [MODS / n for n in DRLA] + [mod, harness]
    for name, files, bridged, timeout in (("stock", [mod, harness], True, 60), ("drla", drla, True, 120),
                                          ("nobridge", [mod, harness], False, 30)):
        if only and name not in only:
            continue
        peer = Peer(dll) if bridged else None
        try:
            lines = launch(exe, work, files, peer, name, timeout)
        finally:
            if peer:
                peer.close()
        if name == "nobridge":
            quiet = not any(re.search(r"(explosives|shotguns): ", l) for l in lines)
            checks.append(quiet and not any(BAD.search(l) for l in lines))
            print(f"{'PASS' if checks[-1] else 'FAIL'} nobridge: no perk activity and no errors without a Daggerfall character")
            continue
        analyse(name, lines, checks, report)
    print("\n" + "\n".join(report))
    failed = checks.count(False)
    print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
    print("RESULT", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
