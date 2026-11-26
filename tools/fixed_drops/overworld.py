"""Fixed drops on the overworld with DRLA, with Daggerfall and Doom together, against the play folder paired.py uses.

usage: overworld.py <play folder> <run name> [--area N] [--out <results folder name>]
The test start (Daggerfall city, DDOVER01, skill 3): list the overworld's seeded packs, kill the nearest pack, warp far
away and back, list what came back, kill the rest. Prints the PO lines and a summary: deaths with and without a loot
seed, drops, the census at each step. Uses paired.py's runner. Wrap the whole script in quiet_run.py.
"""
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402


def make_harness(out, name, play=None):
    harness = out / f"overworld-{name}.pk3"
    text = (HERE / "overworld.zs").read_text().replace('Printf("PODONE', 'Printf("PDDONE').replace('"PO', '"PDPO')
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "POHarness" }\n')
    return harness


def summary(out, name):
    text = (out / f"result-{name}.txt").read_text()
    uz = (out / f"log-{name}.txt").read_text(errors="replace") if (out / f"log-{name}.txt").exists() else ""
    print(text.splitlines()[0])
    for line in re.findall(r"^PDPOCENSUS .*$", text, re.M):
        print(" ", line)
    # A blow kills at once (phase 1 or 4); the drops land in the next tics (phase 2 or 5).
    for label, phases in (("first", "12"), ("second", "45")):
        died = re.findall(rf"^PDPODIED (\S+) seed (\S+) phase [{phases}]$", text, re.M)
        drops = re.findall(rf"^PDPODROP (\S+) seed (\S+) phase [{phases}]$", text, re.M)
        unseeded = [d for d in died if d[1] == "00000000"]
        counters = sum(1 for d in drops if "Counter" in d[0] or "Incrementer" in d[0])
        print(f"  {label} kill: {len(died)} died, {len(unseeded)} without a seed, {len(drops)} drops "
              f"({sum(1 for d in drops if d[1] == '00000000')} unseeded, {counters} kill counters)")
        print("   ", sorted(d[0] for d in drops if "Counter" not in d[0] and "Incrementer" not in d[0]))
    print("  DDMON spawner gave:", len(re.findall(r"DDMON spawner", uz)), " DDLOOT summoned:", len(re.findall(r"DDLOOT summoned", uz)))


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[2] == "summary":  # overworld.py <play> summary <run name>: no run, just the summary.
        summary(Path(sys.argv[1]).resolve().parent / "overworld-drops", "travel" + sys.argv[3])
        sys.exit()
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play = Path(sys.argv[1]).resolve()
    out = play.parent / "overworld-drops"
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        out = play.parent / sys.argv[i + 1]
        del sys.argv[i:i + 2]
    out.mkdir(exist_ok=True)
    area = int(sys.argv[sys.argv.index("--area") + 1]) if "--area" in sys.argv else 10
    name = "travel" + sys.argv[2]  # paired.py starts a "travel*" run at the test start on DDOVER01.
    paired.make_harness = make_harness
    paired.TIMEOUT = 180
    paired.run(play, out, name, area)
    summary(out, name)
