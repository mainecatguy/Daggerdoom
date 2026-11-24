"""Paired test for location state card 3: Daggerfall's location ledger for interiors, towns and the overworld.

usage: ledger3.py run NAME [--load] [--notable] | report NAME [FIRST]

Uses card 2's test folder (ledger2.py build / assemble). Route (ledger3.zs), a paired session through the launcher
with --minimized, starting in town group 7154: kill, wound, drop and take on a street, in a house (the building card 1
chose, review\\locledger\\interior.json) and in the wilderness south of town; travel 600 tiles away and back; walk back
into town and into the house; leave, travel away again and save there. A --load run loads that save and visits the
wilderness spot, the street and the house again. --notable adds UZDoom's -ddlocnotable test hook, which loads the save
as if it had no world table, so every place can only come back from Daggerfall's ledger.
`report NAME` compares the first visit of each place with the second; `report NAME FIRST` compares a load run with
the first run's first visits. Game data stays outside the repo.
"""
import inspect
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger2 as l2  # noqa: E402

md, base, pickup, REVIEW = l2.md, l2.base, l2.pickup, l2.REVIEW
INTERIOR = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger\interior.json")
PLACES = ("street", "house", "wild")

# md.run with a longer limit: this route visits three places twice and travels four times.
_source = inspect.getsource(md.run).replace("timeout = 75", "timeout = 150")
assert "timeout = 150" in _source
exec(compile(_source, md.__file__, "exec"), md.__dict__)


def route(mode):
    s = json.loads(INTERIOR.read_text())
    folder = REVIEW / "route3"
    folder.mkdir(parents=True, exist_ok=True)
    text = (HERE / "ledger3.zs").read_text().replace("@ROUTE@", mode).replace("@TOWN@", f"DDT{pickup.GROUP:05d}")
    text = text.replace("@HOUSEDOOR@", ", ".join(s["door"])).replace("@HOUSEEXIT@", ", ".join(s["exit"][:5]))
    (folder / "harness.zs").write_text(text)
    md.HERE = folder


def report(name, first=None):
    for place in PLACES:
        if first:
            l2.compare(l2.signature(first, place + "1"), l2.signature(name, place + "3"), f"{place}: {first} first visit vs {name} after the load")
        else:
            l2.compare(l2.signature(name, place + "1"), l2.signature(name, place + "2"), f"{place}: {name} first visit vs second")
    for line in l2.log(name).splitlines():
        if line.startswith(("DDLOC", "DDTM saved", "DDTM left", "DDTM place", "DDTRANSITION", "LL", "MD")) and not line.startswith(("LLSIG", "DDLOC sent")):
            print(" ", line[:230])
    for line in base.read(REVIEW / "run" / f"{name}-df.log").splitlines():
        if "locations:" in line:
            print("  df", line[:230])


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "run":
        if "--notable" in sys.argv:
            l2.EXTRA_UZ.append("-ddlocnotable")
        load = "--load" in sys.argv
        route("load" if load else "first")
        if load:
            shutil.copyfile(REVIEW / "run" / "first3.zds", REVIEW / "run" / "saves" / "resume.zds")  # a fresh mtime, so md.run picks it
        md.run(sys.argv[2], load)
        if not load:
            saves = REVIEW / "run" / "saves"
            newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
            if newest:
                shutil.copy2(newest, REVIEW / "run" / "first3.zds")
                print("kept", newest.name, "as first3.zds")
        report(sys.argv[2])
    elif command == "report":
        report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        sys.exit(__doc__)
