"""Civil War fixed drops with Daggerfall and Doom together, against the play folder paired.py uses.

usage: civilwar.py <play folder> series [--area N]
Runs, in order (each a real New Game arrival in Privateer's Hold, which rolls Civil War, unless noted):
  fresh       watch the war with the player out of it (god mode, no target), snapshot it at war time 6 s and 12 s,
              then stop the fighting and list the new loose items.
  save        the same, with a bundled autosave at war time 3 s.
  load        fresh copies of both games load that autosave and watch on.
  freshnoise  the same as fresh, but the player paces about and burns numbers from Doom's shared random streams.
  freshkill   the player kills, at war time 2 s, exactly the monsters the other army killed in fresh, then lists the
              drops.
Then compares: every watch run has the same deaths (war time, monster, seed), the same survivors (health and position)
and the same drops; freshkill's drops equal fresh's. Uses paired.py's runner. Wrap the whole script in quiet_run.py.
Output goes to <play folder>/../civilwar-paired.
"""
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402

MODES = {"fresh": 0, "save": 1, "load": 2, "freshnoise": 3, "freshkill": 4}
WATCH = ["fresh", "save", "load", "freshnoise"]


def kills_of(out):
    text = (out / "result-fresh.txt").read_text()
    return [m for m in re.findall(r"^PDCWDIED \d+ (\S+ \S+ \S+) seed \S+ war 1 by other$", text, re.M)]


def make_harness(out, name):
    base = name.rstrip("0123456789") if name.rstrip("0123456789") in MODES else name
    kills = ";".join(kills_of(out)) if base == "freshkill" else ""
    text = (HERE / "civilwar.zs").read_text().replace("@MODE@", str(MODES[base])).replace("@KILLS@", kills)
    text = text.replace('Printf("CW', 'Printf("PDCW').replace('"PDCWDONE', '"PDDONE')
    harness = out / f"civilwar-{name}.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "CWHarness" }\n')
    return harness


def summary(out, name):
    text = (out / f"result-{name}.txt").read_text()
    resumed = re.search(r"^PDCWRESUMED \S+ at war (\d+)", text, re.M)
    after = int(resumed.group(1)) if resumed else -1
    died = [l for l in re.findall(r"^PDCWDIED (\d+ .*)$", text, re.M) if int(l.split()[0]) > after]
    return {
        "result": text.splitlines()[0],
        "died": Counter(died),
        "mid": Counter(re.findall(r"^PDCW(?:ALIVE|DEAD) mid (.*)$", text, re.M)),
        "end": Counter(re.findall(r"^PDCW(?:ALIVE|DEAD) end (.*)$", text, re.M)),
        "drops": Counter(re.findall(r"^PDCWDROP (.*)$", text, re.M)),
        "snaps": re.findall(r"^PDCWSNAP .*$", text, re.M),
        "killed": re.findall(r"^PDCWKILLED .*$", text, re.M),
        "nf": re.findall(r"^PDCW(?:NOTFOUND|ALIVEAFTER) .*$", text, re.M),
        "noseed": [l for l in re.findall(r"^PDCWDIED (.*)$", text, re.M) if " seed 00000000 " in l],
    }


def diff(label, a, b, na, nb):
    if a == b:
        return True
    print(f"DIFF {label}: {na} vs {nb}")
    for side, d in ((na, a - b), (nb, b - a)):
        print(f"  only {side} ({sum(d.values())}):", list(d.items())[:12])
    return False


def compare(out, names):
    runs = {n: summary(out, n) for n in names}
    ok = True
    for n, s in runs.items():
        print(f"{n:10} {s['result']}, {sum(s['died'].values())} deaths, {sum(s['drops'].values())} drops; {'; '.join(s['snaps'])} {' '.join(s['killed'])}")
        for line in s["nf"][:10] + s["noseed"][:10]:
            print("           ", line)
        ok &= s["result"] == "result: passed" and not s["noseed"]
    base = runs["fresh"]
    ok &= sum(base["died"].values()) > 0 and sum(base["drops"].values()) > 0
    for n in names:
        if n == "fresh":
            continue
        if n == "freshkill":
            ok &= diff("drops (other army's kills vs the player's)", base["drops"], runs[n]["drops"], "fresh", n)
            ok &= not runs[n]["nf"] or all("NOTFOUND" in l for l in runs[n]["nf"])
            continue
        b = runs[n]
        died = Counter({k: v for k, v in base["died"].items() if n != "load" or int(k.split()[0]) > 105})
        for key, x in (("deaths", died), ("mid snapshot", base["mid"]), ("end snapshot", base["end"]), ("drops", base["drops"])):
            ok &= diff(key, x, b["died" if key == "deaths" else {"mid snapshot": "mid", "end snapshot": "end", "drops": "drops"}[key]], "fresh", n)
    print("CIVIL WAR FIXED DROPS", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "civilwar-paired"
    out.mkdir(exist_ok=True)
    area = int(sys.argv[sys.argv.index("--area") + 1]) if "--area" in sys.argv else 10
    paired.make_harness = make_harness
    paired.TIMEOUT = 300
    names = [a for a in sys.argv[3:] if not a.startswith("--") and not a.isdigit()] or ["fresh", "save", "load", "freshnoise", "freshkill"]
    if sys.argv[2] == "series":
        for name in names:
            paired.run(play, out, name, area)
        compare(out, names)
    elif sys.argv[2] == "compare":
        compare(out, names)
    else:
        paired.run(play, out, sys.argv[2], area)
