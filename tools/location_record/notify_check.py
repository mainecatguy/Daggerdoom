"""Checks that no DDLOC line reaches the on-screen messages during paired.py's dungeon route, with screenshots.

usage: notify_check.py setup STAGE | uzdoom BUILD_RELEASE | run NAME [--console]
setup:  makes review\\locrecord\\paired from a play folder (scripts/play/install.py layout) and this mod source.
uzdoom: copies a UZDoom build over the folder's.
run:    paired.py's "run NAME", keeping every on-screen message up (cleared by UZDoom only at a map change) and taking a
        screenshot every 3 s into run\\shots\\NAME. Read the screenshots; the log's DDLOC lines are counted here.
        --console also opens the console after the sixth shot and takes console.png. Closing it clears the on-screen
        messages, so judge those from a run without --console.
"""
import shutil
import sys

import paired

ledger2, REVIEW = paired.ledger2, paired.REVIEW


def run(name, console=False):
    shots = REVIEW / "run" / "shots" / name
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir(parents=True)
    steps = [f"wait 105;screenshot {shots.as_posix()}/{i:02d}.png;" for i in range(24)]
    if console:
        steps.insert(6, f"toggleconsole;wait 20;screenshot {shots.as_posix()}/console.png;wait 5;toggleconsole;")
    script = "".join(steps)
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
        run(sys.argv[2], "--console" in sys.argv)
    else:
        sys.exit(__doc__)
