"""Gun ammo route (gunammo.zs) in paired.py's folder: guns never give ammo, on any take or retake.

usage: gunammo.py run NAME [--stock] [--paths "1 3"] | report NAME

Runs in town with Daggerfall's -dfgundroptest hook. The DRLA set is loaded unless --stock is given (then the stock
Shotgun is used and DRLA's own drop path is skipped). The route prints the player's Doom ammo for the gun's types at
every step (LRAMMO): a map gun's first take, three drops and retakes for each drop path (Daggerfall's inventory window,
DRLA's weapon drop, Doom's weapdrop) and a monster-dropped gun's first take. The route needs about 2.5 minutes, so its
limit is 170 s rather than the usual 30 s; it ends at once when it finishes or a fatal error is logged.
"""
import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402

l2 = paired.ledger2
md, base, pickup, REVIEW = l2.md, l2.base, l2.pickup, paired.REVIEW

_source = inspect.getsource(md.run).replace("timeout = 75", "timeout = 170")
assert "timeout = 170" in _source
exec(compile(_source, md.__file__, "exec"), md.__dict__)
md.EXTRA_DF = ["-dfgundroptest"]


def route(drla, paths):
    folder = REVIEW / "route_gunammo"
    folder.mkdir(parents=True, exist_ok=True)
    text = (HERE / "gunammo.zs").read_text().replace("@SET@", "drla" if drla else "stock").replace("@PATHS@", paths).replace("@TOWN@", f"DDT{pickup.GROUP:05d}")
    (folder / "harness.zs").write_text(text)
    md.HERE = folder


def report(name):
    for line in l2.log(name).splitlines():
        if line.startswith(("LRAMMO", "LRSTEP", "MDDONE", "MDFAIL", "dfg drop", "dfg lost")) or "doomitems: took" in line:
            print(" ", line[:200])
    for line in base.read(REVIEW / "run" / f"{name}-df.log").splitlines():
        if any(k in line for k in ("gundroptest:", "doomitems: take", "doomitems: dropped", "hotkeys: key", "hotkeys: press", "hotkeys: took", "hotkeys: Doom dropped", "hotkeys: assigned", "hotkeys: cleared", "Nothing is assigned", "status 4")):
            print("  df", line[:200])


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "run":
        drla = "--stock" not in sys.argv
        paths = sys.argv[sys.argv.index("--paths") + 1] if "--paths" in sys.argv else "1 3"
        md.EXTRA_DF = ["-dfgundroptest"] if paths.split()[:1] == ["1"] else []  # the hook drops the first shotgun it sees
        route(drla, paths)
        md.run(sys.argv[2], False, drla=drla)
        report(sys.argv[2])
    elif command == "report":
        report(sys.argv[2])
    else:
        sys.exit(__doc__)
