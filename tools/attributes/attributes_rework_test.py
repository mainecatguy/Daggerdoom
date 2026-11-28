"""Attribute rework (owner, 2026-11-27; gamedesign/decisions/20261127-attribute-rework-owner.md) against a fake Daggerfall peer.

usage: python quiet_run.py --timeout 900 -- python tools/attributes/attributes_rework_test.py <uzdoom.exe> <doomerfall_bridge.dll> <work folder>

The peer is Daggerfall's side of the bridge: it writes a character sheet with the Strength, Agility and Luck of each
config in turn (Willpower 50, so hits on the player are unscaled). The harness (attributes_rework.zs) measures each
config once its stats arrive and prints "ATTRRW measured"; then the peer moves on. Runs DOOM.WAD E1M1:
  stock     doomerfall.pk3: Fist, Chainsaw, Shotgun, RocketLauncher, Chaingun, Pistol.
  drla      play_drlax.bat's DRLA set plus doomerfall-drla.pk3: RLFist, RLChainsaw, RLCombatShotgun, RLRocketLauncher,
            RLChaingun, RLPistol, RLMarksmanRifle (rifle), RLGrammatonClericBeretta (pistol and automatic).
  nobridge  doomerfall.pk3 without a bridge session: no effects item, no change.
Checks (analyse): every weapon's hitscan damage, and an explosive's blast, follow the rule's factor at 0, 50 and 100
against the all-50 config; dodge never happens; Luck 100 crits about 5% of 2500 pistol and fist hits, Luck 50 never;
every blast crits all of its targets or none, some blasts at Luck 100 crit; burn ticks never crit.
"""
import math, re, subprocess, sys, time, zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "automatics"))
import automatics_test as at  # noqa: E402

IWAD, MODS, DRLA, BAD = at.IWAD, at.MODS, at.DRLA, re.compile(r'Script error, "(doomerfall|doomerfall-drla|attrrw)\.pk3|(doomerfall|attrrw)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
STR, AGI, WIL, LUCK = 0, 3, 2, 7
# name: (Strength, Agility, Luck)
CONFIGS = {"n": (50, 50, 0), "s0": (0, 50, 0), "s100": (100, 50, 0), "a0": (50, 0, 0), "a100": (50, 100, 0),
           "x0": (0, 0, 0), "x100": (100, 100, 0), "l50": (50, 50, 50), "l100": (50, 50, 100)}
ORDER = ["n", "s0", "s100", "a0", "a100", "x0", "x100", "l50", "l100"]


def rules():
    r = {"off": {}}
    for name, (s, a, l) in CONFIGS.items():
        d = {}
        for base in (16, 24):  # DFB_SHEET_STATS_BASE, DFB_SHEET_STATS_LIVE
            for i in range(8):
                d[base + i] = 50
            d[base + STR], d[base + AGI], d[base + LUCK] = s, a, l
        r[name] = d
    return r


at.RULES = rules()

CURVE = re.compile(r"ATTRRW curve (-?\d+) (-?\d+) (-?\d+) (\w+) (\w+) (\w+) (\d) hits=(-?\d+) boom=(-?\d+)")
LUCKL = re.compile(r"ATTRRW luck (-?\d+) (-?\d+) (-?\d+) (\w+) hits=(\d+) crits=(\d+)")
BLAST = re.compile(r"ATTRRW blast (-?\d+) blasts=(\d+) allcrit=(\d+) nocrit=(\d+) mixed=(\d+)")
BURN = re.compile(r"ATTRRW burn (-?\d+) ticks=(\d+) crits=(\d+)")
DODGE = re.compile(r"ATTRRW dodge (-?\d+) hits=(\d+) evaded=(\d+) modzero=(\d+) agiitem=(\d)")
MEASURED = re.compile(r"ATTRRW measured str=(-?\d+) agi=(-?\d+) luck=(-?\d+) drla=(\d) item=(\d)")


def factor(kind1, kind2, rifle, s, a):
    """The rule (DoomerfallAttributeEffects.AttackFactor) for one weapon's tags."""
    if kind1 in ("melee", "unarmed"):
        return 1 + s / 100
    f = 1.0
    if {kind1, kind2} & {"shotgun", "explosive", "automatic"}:
        f *= 0.8 + 0.004 * s
    rp = "pistol" in (kind1, kind2) or rifle
    f *= 1 + (a - 50) * (0.004 if rp else 0.002)
    return f


def harness_pk3(path):
    with zipfile.ZipFile(path, "w") as z:
        z.write(Path(__file__).with_name("attributes_rework.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AttrRework" }\n')
        z.writestr("cvarinfo.txt", "server bool attrrw_nohits = false;\n")
    return path


def launch(exe, work, files, peer, name, timeout):
    out = work / f"{name}.out"
    args = [str(exe), "-iwad", str(IWAD), "-file", *map(str, files), "-config", str(work / f"{name}.ini"), "-nosound",
            "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200", "-skill", "3", "+map", "E1M1"]
    if peer:
        args += ["-dfbridge", peer.id, "-dfbridgelog", str(work / f"{name}-bridge.log")]
    order = list(ORDER) if peer else []
    if peer:
        peer.sheet(order[0])
    with open(out, "wb") as f:
        p = subprocess.Popen(args, cwd=work, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        try:
            while p.poll() is None and time.monotonic() < deadline:
                if peer:
                    peer.pump()
                time.sleep(0.004)
                text = out.read_text(errors="replace")
                if BAD.search(text):
                    break
                done = [tuple(int(x) for x in m.groups()[:3]) for m in MEASURED.finditer(text)]
                if peer:
                    if order and CONFIGS[order[0]] in done:
                        order.pop(0)
                        if not order:
                            break
                        peer.sheet(order[0])
                elif "E1M1" in text and time.monotonic() > deadline - timeout + 12:
                    break  # no bridge: a few seconds of play is enough to see nothing changes
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
    return out.read_text(errors="replace").splitlines()


def analyse(name, lines, check, drla, configs=CONFIGS, order=ORDER, paired=False):
    base_cfg = configs[order[0]]
    curve_order = [c for c in order if configs[c][2] == base_cfg[2]]
    check(name, "no script errors", not any(BAD.search(l) for l in lines), [l for l in lines if BAD.search(l)][:3])
    measured = {tuple(int(x) for x in m.groups()[:3]): m for m in map(MEASURED.search, lines) if m}
    check(name, "every config measured", all(c in measured for c in configs.values()), sorted(measured))
    check(name, "effects item held", bool(measured) and all(m.group(5) == "1" for m in measured.values()))
    curves = {}
    for m in map(CURVE.search, lines):
        if m:
            s, a, l = (int(x) for x in m.groups()[:3])
            curves[(s, a, l, m.group(4))] = (m.group(5), m.group(6), m.group(7) == "1", int(m.group(8)), int(m.group(9)))
    weapons = sorted({k[3] for k in curves})
    want = 8 if drla else 6
    check(name, f"{want} weapons measured", len(weapons) == want, weapons)
    print(f"  {'weapon':28} tags                  " + " ".join(f"{c:>6}" for c in curve_order))
    for w in weapons:
        n = curves.get((*base_cfg, w))
        if not n:
            continue
        k1, k2, rifle, base_hits, base_boom = n
        row, ok = [], True
        for c in curve_order:
            s, a, l = configs[c]
            got = curves.get((s, a, l, w))
            if not got:
                ok = False
                continue
            f = factor(k1, k2, rifle, s, a) / factor(k1, k2, rifle, base_cfg[0], base_cfg[1])
            ratio = got[3] / base_hits
            row.append(f"{ratio:6.3f}")
            # Doom rounds to whole points; 1000-point hits keep that under 0.5%.
            if abs(ratio - f) > 0.006:
                ok = False
                print(f"    {w} {c}: hits ratio {ratio:.4f}, rule {f:.4f}")
            if base_boom > 0:
                bratio = got[4] / base_boom
                if abs(bratio - f) > 0.02:
                    ok = False
                    print(f"    {w} {c}: blast ratio {bratio:.4f}, rule {f:.4f}")
        tags = f"{k1}/{k2}{'/rifle' if rifle else ''}"
        print(f"  {w:28} {tags:21} " + " ".join(row) + (f"   blast at all-50: {base_boom}" if base_boom > 0 else ""))
        check(name, f"{w} ({tags}) follows the rule at 0, 50, 100", ok)
        if base_boom > 0:
            check(name, f"{w} blast measured", all(curves.get((*configs[c], w), (0,) * 5)[4] > 0 for c in curve_order))
    # The expected tag sets are present.
    tagsets = {w: curves[(*base_cfg, w)] for w in weapons if (*base_cfg, w) in curves}
    has = lambda pred: any(pred(t) for t in tagsets.values())
    for label, pred in [("melee", lambda t: t[0] == "melee"), ("fists", lambda t: t[0] == "unarmed"), ("shotgun", lambda t: "shotgun" in t[:2]),
                        ("explosive", lambda t: "explosive" in t[:2]), ("automatic", lambda t: "automatic" in t[:2]),
                        ("pistol", lambda t: "pistol" in t[:2])] + ([("rifle", lambda t: t[2]), ("pistol+automatic", lambda t: t[0] == "pistol" and t[1] == "automatic")] if drla else []):
        check(name, f"a {label} weapon was measured", has(pred))
    for m in map(DODGE.search, lines):
        if m:
            check(name, f"no dodge at Agility {m.group(1)} ({m.group(3)} of {m.group(2)} hits evaded, {m.group(4)} zeroed)",
                  m.group(3) == "0" and m.group(4) == "0" and (paired or int(m.group(2)) > 0))
    for m in map(LUCKL.search, lines):
        if m:
            l, hits, crits = int(m.group(3)), int(m.group(5)), int(m.group(6))
            chance = max(0, min(l, 100) - 50) * 0.001
            if chance == 0:
                check(name, f"Luck {l} {m.group(4)}: no crits ({crits} of {hits})", crits == 0)
            else:
                sd = math.sqrt(hits * chance * (1 - chance))
                check(name, f"Luck {l} {m.group(4)}: about {chance:.1%} crits ({crits} of {hits} = {crits / hits:.2%}, 4 sd {4 * sd:.0f})",
                      abs(crits - hits * chance) <= 4 * sd)
    for m in map(BLAST.search, lines):
        if m:
            l, n, all_, none, mixed = (int(x) for x in m.groups())
            check(name, f"Luck {l}: every blast crits all its targets or none ({all_} all, {none} none, {mixed} mixed of {n})", mixed == 0 and n > 0)
            if l >= 100:
                check(name, f"Luck {l}: some blasts are lucky ({all_} of {n}, about 5% expected)", 0 < all_ <= n * 0.12)
            if l <= 50:
                check(name, f"Luck {l}: no lucky blasts", all_ == 0)
    for m in map(BURN.search, lines):
        if m:
            check(name, f"Luck {m.group(1)}: burn ticks never crit ({m.group(3)} of {m.group(2)})", m.group(3) == "0" and int(m.group(2)) > 100)
    luck_lines = [m for m in map(LUCKL.search, lines) if m]
    check(name, "Luck measured at 50 and 100 for pistol and fists", len(luck_lines) >= 4)
    check(name, "burn measured", any(BURN.search(l) for l in lines))


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    mod, mod_drla, harn = work / "doomerfall.pk3", work / "doomerfall-drla.pk3", work / "attrrw.pk3"
    subprocess.run([sys.executable, str(build), str(mod)], check=True)
    subprocess.run([sys.executable, str(build), "--drla", str(mod_drla)], check=True)
    harness_pk3(harn)
    failures = []

    def check(name, label, ok, detail=None):
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {label}" + (f"  {detail}" if detail and not ok else ""), flush=True)
        if not ok:
            failures.append(f"{name}: {label}")

    runs = [("stock", [mod, harn], False), ("drla", [MODS / f for f in DRLA] + [mod, mod_drla, harn], True)]
    only = sys.argv[4:] or ["stock", "drla", "nobridge"]
    for name, files, drla in runs:
        if name not in only:
            continue
        peer = at.Peer(dll)
        try:
            lines = launch(exe, work, files, peer, name, 240)
        finally:
            peer.close()
        analyse(name, lines, check, drla)
    if "nobridge" in only:
        lines = launch(exe, work, [mod, harn], None, "nobridge", 25)
        check("nobridge", "no script errors", not any(BAD.search(l) for l in lines))
        check("nobridge", "started", any("E1M1" in l for l in lines))
        ms = [m for m in map(MEASURED.search, lines) if m]
        check("nobridge", "measured with no character (DD_SheetStat -1) and the effects item never given",
              bool(ms) and all(m.group(1) == "-1" and m.group(5) == "0" for m in ms))
        cs = [m for m in map(CURVE.search, lines) if m]
        check("nobridge", "every weapon's 1000-point hit deals exactly 1000", len(cs) == 6 and all(m.group(8) == "1000" for m in cs))
        ls = [m for m in map(LUCKL.search, lines) if m]
        check("nobridge", "no crits", bool(ls) and all(m.group(6) == "0" for m in ls))
        dg = [m for m in map(DODGE.search, lines) if m]
        check("nobridge", "no dodge", bool(dg) and all(m.group(3) == "0" for m in dg))
    print("RESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
