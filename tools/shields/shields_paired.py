"""No shields for now (goal noshields, owner 2026-11-26): a paired run with a new character checks that shields are
out of the game.

usage (wrap the whole script in quiet_run.py, as tools/fixed_drops/paired.py):
  python tools/shields/shields_paired.py <play folder> <dfu build folder> <work folder>

<play folder> is an assembled play folder with this checkout's UZDoom, bridge and launcher (for example the one
tools/luck/luck_paired.py used). It is copied once to <work folder>/play and gets <dfu build folder> and a fresh
doomerfall.pk3. Then tools/fixed_drops/paired.py's "fresh" run plays once: a real New Game, the player arrives in
Privateer's Hold, and Daggerfall's -dfshieldtest (DoomerfallShieldsTest) surveys loot and shop stock, tries to equip a
shield, and saves and loads a game holding an equipped shield. The fixed-drops harness result does not matter here.

Checks (from the Daggerfall bridge log): the ban is active; the new character, every survey and every enemy roll hold
no shield, with armor present in the armor-bearing surveys; equipping is refused; the save loads, the shield is still
carried, the left hand is empty, and the armor values lost the shield's bonus.
"""
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "fixed_drops"))
import paired as fd  # noqa: E402

SURVEY = re.compile(r"shield test: survey (.+?): (\d+) items, (\d+) armor, (\d+) shields")
ARMORED = ("random armor", "magic items", "shop shelves", "every loot table", "every enemy type")


def copy_over(src, dst):
    for f in Path(src).rglob("*"):
        if f.is_file():
            t = dst / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)


def main():
    source, dfu, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]).resolve()
    play = work / "play"
    if not play.exists():
        shutil.copytree(source, play, ignore=shutil.ignore_patterns("run", "PortableAppdata"))
    copy_over(dfu, play / "dfu")
    fd.subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(play / "doomerfall.pk3")])
    out = work / "results"
    out.mkdir(parents=True, exist_ok=True)
    fd.EXTRA_DF[:] = ["-dfshieldtest"]
    fd.run(play, out, "shields", 10)
    log = fd.ng.read(out / "shields-df.log")
    lines = [l for l in log.splitlines() if "shield test:" in l]
    for l in lines:
        print(l[l.index("shield test:"):])
    checks = [("ban active in the bridge session", "shield test: active True" in log)]
    surveys = SURVEY.findall(log)
    checks.append(("all six surveys ran", len(surveys) == 6))
    for what, n, armor, shields in surveys:
        checks.append((f"{what}: no shields", shields == "0"))
        if what.startswith(ARMORED):
            checks.append((f"{what}: armor present ({armor} of {n})", int(armor) > 0))
    checks.append(("no shield found anywhere", "FOUND SHIELD" not in log))
    checks.append(("quest random armor rerolls the 4 shield indexes", "4 of the armor group indexes" in log))
    checks.append(("equipping a shield is refused", "shield test: equip refused True" in log))
    before = re.search(r"before save: equipped (\w+), armor ([-\d,]+)", log)
    after = re.search(r"after load: loaded (\w+), shields carried (\d+), left hand (\w+), armor ([-\d,]+)", log)
    checks.append(("the older-save shield was equipped before saving", bool(before) and before.group(1) == "True"))
    checks.append(("the save loaded", bool(after) and after.group(1) == "True"))
    checks.append(("the shield is still carried after load", bool(after) and int(after.group(2)) >= 1))
    checks.append(("the left hand is empty after load", bool(after) and after.group(3) == "empty"))
    checks.append(("armor values lost the shield's bonus", bool(before and after) and before.group(2) != after.group(4)))
    checks.append(("Daggerfall took the shield off on load", "shields: took off" in log))
    errors = [l for l in log.splitlines() if "Exception" in l]
    checks.append(("no exceptions in the bridge log", not errors))
    for label, ok in checks:
        print("PASS" if ok else "FAIL", label)
    print("RESULT", "PASS" if all(ok for _, ok in checks) else "FAIL")


if __name__ == "__main__":
    main()
