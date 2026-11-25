"""Paired route for dropped piles and dropped Doom items in the location record (piles.zs), in paired.py's folder.

usage: piles.py run NAME [--load] | report NAME

DRLA is loaded and Daggerfall runs with -dfpilestest, which drops as the inventory window would: a pile in town, then
in Privateer's Hold a pile and a modded DRLA shotgun (sent to Doom as its own pickup). A first run walks two map pixels
away and back in between, leaves and re-enters the dungeon, takes the gun with Use and saves inside. A --load run loads
that save, waits, and leaves to town. `report` prints what each side logged about piles and the gun.
"""
import inspect
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402

l2 = paired.ledger2
md, base, pickup, REVIEW = l2.md, l2.base, l2.pickup, paired.REVIEW

# md.run with a longer limit: this route travels and enters the dungeon twice.
_source = inspect.getsource(md.run).replace("timeout = 75", "timeout = 170")
assert "timeout = 170" in _source
exec(compile(_source, md.__file__, "exec"), md.__dict__)
md.EXTRA_DF = ["-dfpilestest"]


def route(mode):
    folder = REVIEW / "route_piles"
    folder.mkdir(parents=True, exist_ok=True)
    text = (HERE / "piles.zs").read_text().replace("@ROUTE@", mode).replace("@TOWN@", f"DDT{pickup.GROUP:05d}")
    (folder / "harness.zs").write_text(text)
    md.HERE = folder


def report(name):
    for line in l2.log(name).splitlines():
        if line.startswith(("LR", "MD", "dfg drop", "DDLOC report", "DDLOC", "DDTM saved", "DDTM corpse")) or "doomitems:" in line:
            print(" ", line[:230])
    for line in base.read(REVIEW / "run" / f"{name}-df.log").splitlines():
        if any(k in line for k in ("piles:", "pilestest:", "doomitems: drop", "doomitems: take", "doomitems: dropped", "hotkeys:", "locations: ledger")):
            print("  df", line[:230])


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "run":
        load = "--load" in sys.argv
        route("load" if load else "first")
        if load:
            shutil.copyfile(REVIEW / "run" / "piles.zds", REVIEW / "run" / "saves" / "resume.zds")
        md.run(sys.argv[2], load, drla=True)
        if not load:
            saves = REVIEW / "run" / "saves"
            newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
            if newest:
                shutil.copy2(newest, REVIEW / "run" / "piles.zds")
                print("kept", newest.name, "as piles.zds")
        report(sys.argv[2])
    elif command == "report":
        report(sys.argv[2])
    else:
        sys.exit(__doc__)
