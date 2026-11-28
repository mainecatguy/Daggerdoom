"""Checks that no DDLOC line reaches the on-screen messages during paired.py's dungeon route, with screenshots.

usage: notify_check.py setup STAGE | uzdoom BUILD_RELEASE | run NAME
setup:  makes review\\locrecord\\paired from a play folder (scripts/play/install.py layout) and this mod source.
uzdoom: copies a UZDoom build over the folder's.
run:    paired.py's "run NAME", keeping every on-screen message up (cleared by UZDoom only at a map change) and taking a
        screenshot every 3 s into run\\shots\\NAME. Read the screenshots; the log's DDLOC lines are counted here.
"""
import shutil
import sys

import paired

ledger2, REVIEW = paired.ledger2, paired.REVIEW


def run(name):
    shots = REVIEW / "run" / "shots" / name
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir(parents=True)
    script = "".join(f"wait 105;screenshot {shots.as_posix()}/{i:02d}.png;" for i in range(24))
    ledger2.EXTRA_UZ += ["+con_notifytime", "600", "+con_notifylines", "40", "+" + script]
    ledger2.route("first")
    ledger2.md.run(name, False)
    ledger2.report(name)
    lines = ledger2.log(name).splitlines()
    print("DDLOC lines in the UZDoom log:", sum("DDLOC" in l for l in lines), "| screenshots:", len(list(shots.glob("*.png"))))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        shutil.rmtree(REVIEW, ignore_errors=True)
        shutil.copytree(sys.argv[2], REVIEW, ignore=shutil.ignore_patterns("run", "test-run", "verify-logs"))
        shutil.copytree(paired.WORKTREE / "mods" / "doomerfall" / "src", REVIEW / "doomerfall")
    elif command == "uzdoom":
        paired.UZ_TREE = paired.Path(sys.argv[2])
        paired.copy_uzdoom()
    elif command == "run":
        run(sys.argv[2])
    else:
        sys.exit(__doc__)
