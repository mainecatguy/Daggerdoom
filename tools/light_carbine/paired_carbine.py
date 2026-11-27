"""Light Carbine on a Daggerfall map (test only): a carbine that replaced a dropped Battle Rifle keeps the rifle's loot
identity, so its Daggerfall material is fixed.

usage: paired_carbine.py <play folder> run <name> | check <name> <name> [--out <results folder name>]
  run    a real New Game in Privateer's Hold with DRLA, through tools/fixed_drops/paired.py's launcher driver: kill the
         start's monsters, list the Battle Rifles and carbines they dropped with their loot seeds, take one carbine.
  check  compares two runs: every carbine seeded, the same drops and the same seeds, and the taken carbine got the same
         Daggerfall name, material and floor id (a lasting one) in both. Prints LIGHT CARBINE PAIRED PASS or FAIL.
The play folder is scripts/play/install.py's layout (uzdoom, dfu, data, dfitems.pk3, doomerfall.pk3, launcher).
Wrap the whole script in quiet_run.py.
"""
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "fixed_drops"))
import paired  # noqa: E402


def make_harness(out, name, play=None):
    harness = out / f"carbine-{name}.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "paired_carbine.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PDCarbine" }\n')
    return harness


def summary(out, name):
    text = (out / f"result-{name}.txt").read_text(errors="replace")
    drops = Counter(re.findall(r"^PDCDROP (.*)$", text, re.M))
    counts = re.search(r"^PDCDROPS rifles (\d+) carbines (\d+) unseeded (\d+)$", text, re.M)
    take = re.findall(r"^PDCTAKE (.*)$", text, re.M)
    df = re.findall(r'doomitems: take \d+ "(DoomerfallLightCarbine)".*?status 0.*?named "([^"]*)" material (\w+).*?floor id (\w+)', text)
    return text.splitlines()[0], drops, counts.groups() if counts else None, take, df


def check(out, names):
    ok = True
    runs = {n: summary(out, n) for n in names}
    for n, (result, drops, counts, take, df) in runs.items():
        print(f"{n}: {result}; rifles, carbines, unseeded: {counts}; take {take}; Daggerfall {df}")
        good = result == "result: passed" and counts is not None and int(counts[1]) > 0 and counts[2] == "0" and len(df) == 1
        if df:
            lasting = (int(df[0][3], 16) >> 58) & 1
            print(f"  floor id {df[0][3]} has the lasting mark: {bool(lasting)}; name has a material: {df[0][1].split(' ')[0] == df[0][2]}")
            good &= bool(lasting) and df[0][1].split(" ")[0] == df[0][2]
        ok &= good
    a, b = (runs[n] for n in names[:2])
    for i, label in ((1, "drops and seeds"), (3, "taken carbine"), (4, "Daggerfall name, material and floor id")):
        same = a[i] == b[i]
        print(f"same {label} in both runs: {same}")
        ok &= same
    print("LIGHT CARBINE PAIRED", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "carbine-paired")
    out.mkdir(parents=True, exist_ok=True)
    paired.make_harness = make_harness
    paired.TIMEOUT = 300
    if sys.argv[2] == "run":
        paired.run(play, out, sys.argv[3], 10)
    else:
        check(out, [a for a in sys.argv[3:] if not a.startswith("--")][:2])
