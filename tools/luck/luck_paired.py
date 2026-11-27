"""Attributes in Doom (card 04): Luck makes monsters' ammo drops more frequent, on its own random stream.

usage (wrap the whole script in quiet_run.py, as tools/fixed_drops/paired.py):
  python tools/luck/luck_paired.py <play folder> <dfu build folder> <work folder> [luck ...] [--area N] [--stock]

<play folder> is an assembled play folder with this checkout's UZDoom, bridge and launcher (for example the one
tools/willpower/willpower_paired.py made). It is copied once to <work folder>/play, gets <dfu build folder> (with
-dflucktest) and a fresh doomerfall.pk3. Then tools/fixed_drops/paired.py's "fresh" run plays once per Luck value
(default 1 and 100): a real New Game, Daggerfall sets Luck (-dflucktest), the player arrives in Privateer's Hold, the
harness kills the monsters near the start and lists every drop (PDDROP).

Checks: every run passed the fixed-drops harness and killed the same monsters; Daggerfall set each Luck; every extra
drop Doom logged (DFAMMO luck drop) names that Luck; with the logged extra drops taken away, every run's drops are
identical (the fixed-seed loot does not move); the highest Luck got more extra drops than the lowest, and at least one;
a lower Luck's extra drops are all among a higher Luck's.
"""
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "fixed_drops"))
import paired as fd  # noqa: E402

LUCKLINE = re.compile(r"DFAMMO luck drop (\w+) tier (\d+) at (-?\d+) (-?\d+) luck (\d+)")
TYPES = {"Clip": "Clip", "Shell": "Shell", "Rocket": "Rocket", "Cell": "Cell"}


def copy_over(src, dst):
    for f in Path(src).rglob("*"):
        if f.is_file():
            t = dst / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)


def main():
    area = 10
    if "--area" in sys.argv:  # Daggerfall's area level (-dfarealevel): higher levels place the DRLA monsters that drop ammo.
        i = sys.argv.index("--area")
        area = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    stock = "--stock" in sys.argv  # Stock Doom monsters (no DRLA): Privateer's Hold's DRLA former humans drop guns, never ammo.
    if stock:
        sys.argv.remove("--stock")
        fd.DRLA[:] = []
        # The harness names DRLA classes in its last phase (summoned monsters); stock ones keep it compiling. That phase
        # is not part of this test.
        text = (fd.HERE / "paired.zs").read_text()
        for rl, doom in (("RLPainElemental", "PainElemental"), ("RLFormerOverwatch", "ChaingunGuy"), ("RLLostSoulPE", "LostSoul"), ("RLUACDefenceDrone", "LostSoul")):
            text = text.replace(f'"{rl}"', f'"{doom}"')
        patched = Path(sys.argv[3]).resolve() / "stock-harness"
        patched.mkdir(parents=True, exist_ok=True)
        (patched / "paired.zs").write_text(text)
        fd.HERE = patched
    source, dfu, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]).resolve()
    lucks = [int(a) for a in sys.argv[4:]] or [1, 100]
    play = work / "play"
    if not play.exists():
        shutil.copytree(source, play, ignore=shutil.ignore_patterns("run", "PortableAppdata"))
    copy_over(dfu, play / "dfu")
    fd.subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(play / "doomerfall.pk3")])
    out = work / ("results-stock" if stock else "results")
    out.mkdir(parents=True, exist_ok=True)
    runs = {}
    for luck in lucks:
        name = f"fresh{luck}"
        fd.EXTRA_DF[:] = ["-dflucktest", str(luck)]
        fd.run(play, out, name, area)
        s = fd.summary(out, name)
        con = fd.ng.read(out / f"log-{name}.txt")
        dfl = fd.ng.read(out / f"{name}-df.log")
        extras = [m.groups() for m in LUCKLINE.finditer(con)]
        extra = Counter(f"DFAmmo_{TYPES[t]}_{tier}" for t, tier, *_ in extras)
        # A drop's spot is physics; the harness lists class and seed (DFAmmo_ pickups have seed 0).
        base = Counter({k: v for k, v in s["drops"].items()})
        for cls, n in extra.items():
            key = f"{cls} seed 00000000"
            base[key] -= n
        dropped = len(re.findall(r"DFAMMO size \S+ \S+ dropped", con))
        listed = "PDDROPS " in (out / f"result-{name}.txt").read_text()
        runs[luck] = dict(s=s, extras=extras, extra=extra, base=base, df=f"luck test: luck {luck} " in dfl, dropped=dropped, listed=listed)
    checks = []
    lo, hi = min(lucks), max(lucks)
    for luck, r in runs.items():
        s = r["s"]
        print(f"luck {luck}: {s['result']}, {sum(s['kills'].values())} killed, {sum(s['drops'].values())} drops, "
              f"{r['dropped']} monster ammo drops, {len(r['extras'])} extra ({dict(r['extra'])}), {len(s['unseeded'])} unseeded")
        for line in s["unseeded"][:5]:
            print("   ", line)
        if stock:  # The harness's last phase (summoned monsters) spawns DRLA summoners, absent here: it must still list the drops.
            checks.append((f"luck {luck}: harness killed and listed the drops", r["listed"] and sum(s["kills"].values()) > 0))
        else:
            checks.append((f"luck {luck}: fixed-drops harness passed", s["result"] == "result: passed"))
        checks.append((f"luck {luck}: Daggerfall set Luck", r["df"]))
        checks.append((f"luck {luck}: every extra drop names Luck {luck}", all(int(e[4]) == luck for e in r["extras"])))
        checks.append((f"luck {luck}: extras subtract cleanly", all(v >= 0 for v in r["base"].values())))
    base = runs[lo]
    for luck, r in runs.items():
        if luck == lo:
            continue
        checks.append((f"luck {luck} vs {lo}: same kills", r["s"]["kills"] == base["s"]["kills"]))
        same = +r["base"] == +base["base"]
        if not same:
            print("  only low:", list((+base["base"] - +r["base"]).items())[:10], "\n  only high:", list((+r["base"] - +base["base"]).items())[:10])
        checks.append((f"luck {luck} vs {lo}: fixed loot identical apart from the extra ammo", same))
    checks.append((f"luck {hi} got more extra ammo drops than luck {lo}", len(runs[hi]["extras"]) > len(runs[lo]["extras"]) and runs[hi]["extras"]))
    lo_spots = Counter((e[0], e[1]) for e in runs[lo]["extras"])
    hi_spots = Counter((e[0], e[1]) for e in runs[hi]["extras"])
    checks.append((f"luck {lo}'s extra drops are among luck {hi}'s (by type and tier)", not (lo_spots - hi_spots)))
    for label, ok in checks:
        print("PASS" if ok else "FAIL", label)
    print("RESULT", "PASS" if all(ok for _, ok in checks) else "FAIL")


if __name__ == "__main__":
    main()
