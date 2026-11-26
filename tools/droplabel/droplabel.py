"""Drop labels (test only): Doom guns on the floor show their Daggerfall material in the look label before pickup, and
the inventory gets the same name.

usage: droplabel.py <play folder> assemble|save|load|check [--out <results folder name>]
  assemble  tools/fixed_drops/paired.py's play folder (this lane's UZDoom, bridge and launcher; Unity must be built).
  save      a real New Game in Privateer's Hold: a dropped gun (A), a script-spawned gun (C) and a gun dropped from
            Daggerfall's inventory (D, by Daggerfall's -dfgundroptest) are each looked at and taken; D and a second
            dropped gun (B) are looked at, left on the floor, autosaved, and looked at again after leaving the dungeon
            and coming back; then D is taken.
  load      the save run's autosave in fresh copies of both games: B and D looked at again, D taken.
  check     compares the labels with the inventory names and across the runs; prints DROP LABELS PASS or FAIL.
Runs through paired.py's launcher driver. Wrap the whole script in quiet_run.py.
"""
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "fixed_drops"))
import paired  # noqa: E402

PLAY = None


def make_harness(out, name, play=None):
    harness = out / f"droplabel-{name}.pk3"
    bpos, dpos = "0, 0, 0", "0, 0, 0"
    if name == "load":
        pos = re.search(r"^PDLPOS B (.*?) D (.*)$", (out / "log-save.txt").read_text(errors="replace"), re.M)
        if not pos:
            sys.exit("no PDLPOS line in the save run's log")
        bpos, dpos = pos.group(1), pos.group(2)
    text = (HERE / "droplabel.zs").read_text().replace("@MODE@", "1" if name == "load" else "0")
    text = text.replace("@DOOR@", paired.door_spot(PLAY)).replace("@BPOS@", bpos).replace("@DPOS@", dpos)
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PDLabels" }\n')
    return harness


def labels(out, name):
    """Each look window's last label (the engine's own look: lines between PDLAT and PDLEND), and each take's name."""
    text = (out / f"log-{name}.txt").read_text(errors="replace")
    looks, current, seen = {}, None, ""
    for line in text.splitlines():
        m = re.match(r"PDLAT (\S+)", line)
        if m:
            current, seen = m.group(1), ""
            continue
        m = re.match(r'look: "(.*)"$', line)
        if m and current:
            seen = m.group(1)
        if line.startswith("PDLEND") and current:
            looks[current] = seen
            current = None
    df = (out / f"{name}-df.log").read_text(errors="replace")
    takes = re.findall(r'doomitems: take \d+ "([^"]+)".*?status 0.*?named "([^"]*)" material (\w+).*?floor id (\w+)(, material carried from a drop)?', df)
    answers = re.findall(r"look: request \d+ target 6 id (\w+): \[(.*)\]", df)
    result = re.search(r"^result: (.*)$", (out / f"result-{name}.txt").read_text(), re.M)
    return looks, takes, answers, result.group(1) if result else "none"


def check(out):
    ok = True
    runs = {}
    for name in ("save", "load"):
        if not (out / f"log-{name}.txt").exists():
            print(name, "missing")
            ok = False
            continue
        looks, takes, answers, result = runs[name] = labels(out, name)
        print(f"{name}: result {result}")
        print("  looks:", looks)
        for t in takes:
            print("  take:", t)
        print("  Daggerfall's gun answers:", len(answers), sorted(set(a[1] for a in answers)))
        ok &= result == "passed"
    if "save" in runs:
        looks, takes, _, _ = runs["save"]
        guns = [t for t in takes if t[0] != "RLPistolPickup"]
        # Takes in order: A, C, D. Each look label before a take equals the inventory name it got.
        for tag, take in zip(("A", "C", "D2"), guns):
            good = looks.get(tag) == take[1] and take[1].split(" ")[0] != take[1]
            print(f"  {tag}: label {looks.get(tag)!r}, inventory {take[1]!r}: {'ok' if good else 'MISMATCH'}")
            ok &= good
        # D carries C's material: taken as C, dropped from the inventory, taken again.
        if len(guns) >= 3:
            same = guns[1][1] == guns[2][1] and guns[2][4] != ""
            print(f"  D keeps C's material through the inventory drop: {'ok' if same else 'NO'}")
            ok &= same
        else:
            ok = False
        for tag in ("B", "D", "E"):
            same = looks.get(tag + "1") and looks.get(tag + "1") == looks.get(tag + "2")
            print(f"  {tag} before and after leaving and coming back: {looks.get(tag + '1')!r} / {looks.get(tag + '2')!r}: {'ok' if same else 'NO'}")
            ok &= bool(same)
    if "save" in runs and "load" in runs:
        s, l = runs["save"][0], runs["load"][0]
        for tag in ("B", "D"):
            same = s.get(tag + "1") and s.get(tag + "1") == l.get(tag + "2")
            print(f"  {tag} after the load: {l.get(tag + '2')!r} (saved {s.get(tag + '1')!r}): {'ok' if same else 'NO'}")
            ok &= bool(same)
        lt = [t for t in runs["load"][1] if t[0] != "RLPistolPickup"]
        same = bool(lt) and lt[-1][1] == l.get("D2")
        print(f"  D taken after the load: {lt[-1][1] if lt else None!r}: {'ok' if same else 'NO'}")
        ok &= same
    print("DROP LABELS", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    PLAY = Path(sys.argv[1]).resolve()
    out = PLAY.parent / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "droplabel-results")
    out.mkdir(parents=True, exist_ok=True)
    paired.make_harness = make_harness
    paired.EXTRA_DF = ["-dfgundroptest"]
    paired.TIMEOUT = 360
    paired.TRY[:] = [
        "Drop labels (branch agent/droplabel). Saves and settings go to this folder's run folder.",
        " 1. New Game, kill the gunners at the Privateer's Hold start. Look at a gun they dropped: the label names its material.",
        " 2. Take it (E) and open the inventory (I): the same name.",
        " 3. Drop a gun from the inventory, look at it on the floor: the same name it had in the inventory.",
        " 4. Save, load, leave the dungeon and come back: guns on the floor keep their names.",
    ]
    if sys.argv[2] == "assemble":
        paired.assemble(PLAY)
    elif sys.argv[2] == "check":
        check(out)
    else:
        paired.run(PLAY, out, sys.argv[2], int(sys.argv[sys.argv.index("--area") + 1]) if "--area" in sys.argv else 10)
