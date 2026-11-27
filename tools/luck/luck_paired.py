"""Luck in Doom (owner 2026-11-27): every kill has a Luck/2 percent chance to drop ammo, on its own hash stream.

usage (wrap the whole script in quiet_run.py, as tools/fixed_drops/paired.py):
  python tools/luck/luck_paired.py <play folder> <dfu build folder> <work folder> [luck ...] [--area N] [--stock]

<play folder> is an assembled play folder with this checkout's UZDoom, bridge and launcher. It is copied once to
<work folder>/play, gets <dfu build folder> (with -dflucktest) and a fresh doomerfall.pk3. Then
tools/fixed_drops/paired.py's "fresh" run plays once per Luck value (default 1 20 60 100; the test hook cannot set 0, which Daggerfall treats as death): a real New Game, Daggerfall
sets Luck (-dflucktest), the player arrives in Privateer's Hold, the harness kills the monsters near the start and lists
every drop (PDDROP). Doom logs every Luck roll (DFAMMO luck kill ... roll R drop|none) and every Luck drop.

Checks, per Luck: the fixed-drops harness passed (with --stock, only that it finished and listed the drops, since its
summoned-monster phase needs DRLA); Daggerfall set Luck; every roll names that Luck; a kill drops exactly when
roll < Luck/200; one single-pickup Luck drop per "drop" roll, and exactly one pickup per Luck drop missing from the
drop list once they are taken away (no jackpot); the drop rate is within 3 standard deviations of Luck/2 percent
(binomial); Luck 0 rolls nothing. Across Lucks: the same kills, the same rolls, and with the Luck drops taken away the
same drops (the monsters' own fixed loot does not move). Pooled over every run with Luck above 0: drops within 3
standard deviations of the summed expectation.
"""
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "fixed_drops"))
import paired as fd  # noqa: E402

KILL = re.compile(r"DFAMMO luck kill (\S+) luck (\d+) roll ([\d.]+) (drop|none)")
# One Luck drop: exactly one pickup of one type and tier (no jackpot).
LUCKDROP = re.compile(r"DFAMMO luck drop (\w+) tier (\d+) at (-?\d+) (-?\d+) luck (\d+)")


def copy_over(src, dst):
    for f in Path(src).rglob("*"):
        if f.is_file():
            t = dst / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)


def within(k, n, p):
    """k successes of n within 3 standard deviations of n*p; also the z score."""
    if n == 0:
        return k == 0, 0.0
    sd = math.sqrt(n * p * (1 - p))
    if sd == 0:
        return k == round(n * p), 0.0
    z = (k - n * p) / sd
    return abs(z) <= 3, z


def main():
    area = 10
    if "--area" in sys.argv:
        i = sys.argv.index("--area")
        area = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    if "--timeout" in sys.argv:  # Seconds per run (paired.py's default 240 can be short for area 30's ~1000 kills).
        i = sys.argv.index("--timeout")
        fd.TIMEOUT = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    stock = "--stock" in sys.argv  # Stock Doom monsters (no DRLA).
    if stock:
        sys.argv.remove("--stock")
        fd.DRLA[:] = []
        # The harness names DRLA classes in its last phase (summoned monsters); stock ones keep it compiling.
        text = (fd.HERE / "paired.zs").read_text()
        for rl, doom in (("RLPainElemental", "PainElemental"), ("RLFormerOverwatch", "ChaingunGuy"), ("RLLostSoulPE", "LostSoul"), ("RLUACDefenceDrone", "LostSoul")):
            text = text.replace(f'"{rl}"', f'"{doom}"')
        patched = Path(sys.argv[3]).resolve() / "stock-harness"
        patched.mkdir(parents=True, exist_ok=True)
        (patched / "paired.zs").write_text(text)
        fd.HERE = patched
    source, dfu, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]).resolve()
    lucks = [int(a) for a in sys.argv[4:]] or [1, 20, 60, 100]
    play = work / "play"
    if not play.exists():
        shutil.copytree(source, play, ignore=shutil.ignore_patterns("run", "PortableAppdata"))
    copy_over(dfu, play / "dfu")
    fd.subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(play / "doomerfall.pk3")])
    out = work / (f"results-stock-a{area}" if stock else f"results-drla-a{area}")
    out.mkdir(parents=True, exist_ok=True)
    runs = {}
    for luck in lucks:
        name = f"fresh{luck}"
        fd.EXTRA_DF[:] = ["-dflucktest", str(luck)]
        fd.run(play, out, name, area)
        s = fd.summary(out, name)
        con = fd.ng.read(out / f"log-{name}.txt")
        dfl = fd.ng.read(out / f"{name}-df.log")
        rolls = [(c, int(l), float(r), d == "drop") for c, l, r, d in KILL.findall(con)]
        drops = LUCKDROP.findall(con)
        # PDDROP lists class and seed; a Luck drop is a DFAmmo pickup, so the comparison drops the seed of DFAmmo pickups.
        base = Counter()
        for k, v in s["drops"].items():
            base[re.sub(r"^(DFAmmo_\w+) seed \w+", r"\1", k)] += v
        for t, tier, *_ in drops:
            base[f"DFAmmo_{t}_{tier}"] -= 1
        runs[luck] = dict(s=s, rolls=rolls, drops=drops, base=base, df=f"luck test: luck {luck} " in dfl,
                          listed="PDDROPS " in (out / f"result-{name}.txt").read_text(),
                          fatal=s["result"] in ("result: fatal", "result: timeout"))
    checks = []
    for luck, r in runs.items():
        s, rolls = r["s"], r["rolls"]
        n, k, p = len(rolls), sum(1 for x in rolls if x[3]), min(luck, 100) / 200
        ok, z = within(k, n, p)
        r.update(n=n, k=k, p=p)
        print(f"luck {luck}: {s['result']}, {sum(s['kills'].values())} killed, {n} Luck rolls, {k} drops "
              f"({100 * k / n if n else 0:.1f}%, expected {100 * p:.1f}%, z {z:+.2f}), {len(r['drops'])} logged drops, "
              f"types {dict(Counter(d[0] for d in r['drops']))}, {len(s['unseeded'])} unseeded")
        for line in s["unseeded"][:5]:
            print("   ", line)
        if stock:  # The harness's last phase (summoned monsters) spawns DRLA summoners, absent here: it must still list the drops.
            checks.append((f"luck {luck}: run finished and listed the drops", not r["fatal"] and r["listed"] and sum(s["kills"].values()) > 0))
        else:
            checks.append((f"luck {luck}: fixed-drops harness passed", s["result"] == "result: passed"))
        checks.append((f"luck {luck}: Daggerfall set Luck", r["df"]))
        if luck <= 0:
            checks.append((f"luck {luck}: no Luck rolls and no Luck drops", n == 0 and not r["drops"]))
            continue
        checks.append((f"luck {luck}: rolled for kills", n > 0))
        checks.append((f"luck {luck}: every roll names Luck {luck}", all(x[1] == luck for x in rolls)))
        checks.append((f"luck {luck}: a kill drops exactly when roll < Luck/200", all(x[3] == (x[2] < p) for x in rolls)))
        checks.append((f"luck {luck}: one single-pickup Luck drop per drop roll, naming Luck {luck}", len(r["drops"]) == k and all(int(d[4]) == luck for d in r["drops"])))
        checks.append((f"luck {luck}: drop rate {k}/{n} within 3 sd of {100 * p:.0f}%", ok))
        checks.append((f"luck {luck}: Luck drops subtract cleanly from the drop list", all(v >= 0 for v in r["base"].values())))
    lo = min(lucks)
    for luck, r in runs.items():
        if luck == lo:
            continue
        b = runs[lo]
        checks.append((f"luck {luck} vs {lo}: same kills", r["s"]["kills"] == b["s"]["kills"]))
        if b["rolls"]:
            checks.append((f"luck {luck} vs {lo}: same rolls per kill", sorted((c, x) for c, _, x, _ in r["rolls"]) == sorted((c, x) for c, _, x, _ in b["rolls"])))
        same = +r["base"] == +b["base"]
        if not same:
            print("  only low:", list((+b["base"] - +r["base"]).items())[:10], "\n  only high:", list((+r["base"] - +b["base"]).items())[:10])
        checks.append((f"luck {luck} vs {lo}: monsters' own drops identical apart from the Luck drops", same))
    pos = [r for l, r in runs.items() if l > 0]
    if pos:
        K, N = sum(r["k"] for r in pos), sum(r["n"] for r in pos)
        mean = sum(r["n"] * r["p"] for r in pos)
        var = sum(r["n"] * r["p"] * (1 - r["p"]) for r in pos)
        z = (K - mean) / math.sqrt(var) if var else 0
        print(f"pooled: {K} drops of {N} rolls, expected {mean:.1f}, z {z:+.2f}")
        checks.append(("pooled drop count within 3 sd of the Luck/2 expectation", abs(z) <= 3))
    for label, ok in checks:
        print("PASS" if ok else "FAIL", label)
    print("RESULT", "PASS" if all(ok for _, ok in checks) else "FAIL")


if __name__ == "__main__":
    main()
