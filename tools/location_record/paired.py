"""Paired runs for the location record, reusing the location ledger harness (tools/location_ledger).

usage: paired.py setup | uzdoom | run NAME [--load] [--notable] | report NAME [FIRST] | plans NAME

setup:  copies card 2's review folder (locledger2, game data stays outside the repo) to review\\locrecord\\paired,
        without its runs, then copies this worktree's UZDoom build in.
uzdoom: copies this worktree's UZDoom build in again (after a rebuild).
run / report: ledger2.py's dungeon route (Privateer's Hold, area level 30, a real kill quest) in that folder.
plans:  the encounter plans of a run: each request's digest and what it spawned, so visits can be compared.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "location_ledger"))
import ledger2  # noqa: E402

SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger2")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\locrecord\paired")
UZ_TREE = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-locrecord\Release")

ledger2.REVIEW = REVIEW
for module in (ledger2.ef, ledger2.md, ledger2.pickup, ledger2.base):
    module.REVIEW = REVIEW
ledger2.base.BUILD, ledger2.base.RUN = REVIEW / "build", REVIEW / "run"


def copy_uzdoom():
    for item in UZ_TREE.iterdir():
        if item.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(item, REVIEW / "uzdoom" / item.name)
    print("uzdoom from", UZ_TREE)


def setup():
    if REVIEW.exists():
        shutil.rmtree(REVIEW)
    shutil.copytree(SOURCE, REVIEW, ignore=shutil.ignore_patterns("run", "route", "route3"))
    copy_uzdoom()


def plans(name):
    for line in ledger2.log(name).splitlines():
        if re.match(r"DDENC (facts|planned|spawned|timing|all)|DDLOC|DDTM (left|place)|LLSIG \w+ begin", line):
            print(" ", line[:230])


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        setup()
    elif command == "uzdoom":
        copy_uzdoom()
    elif command == "plans":
        plans(sys.argv[2])
    elif command in ("run", "report"):
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        if command == "run":
            if "--notable" in sys.argv:
                ledger2.EXTRA_UZ.append("-ddlocnotable")
            load = "--load" in sys.argv
            ledger2.route("load" if load else "first")
            if load:
                ledger2.stage_first_save()
            ledger2.md.run(sys.argv[2], load)
            if not load:
                ledger2.keep_first_save()
            ledger2.report(sys.argv[2])
            plans(sys.argv[2])
        else:
            ledger2.report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        sys.exit(__doc__)
