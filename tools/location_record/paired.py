"""Paired runs for the location record, reusing the location ledger harness (tools/location_ledger).

usage: paired.py setup | uzdoom | unity | dfu | run NAME [--load] [--notable] | report NAME [FIRST] | plans NAME

setup:  copies card 2's review folder (locledger2, game data stays outside the repo) to review\\locrecord\\paired,
        without its runs, then copies this worktree's UZDoom build in.
uzdoom: copies this worktree's UZDoom build and the doomerfall mod's source in again (after a rebuild).
unity:  builds this worktree's Daggerfall Unity (windowed, on a private desktop through quiet_run).
dfu:    copies that build into the review folder, keeping its PortableAppdata and bridge DLL.
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


WORKTREE = HERE.parents[1]
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UNITY = shutil.which("Unity.exe") or r"C:\Program Files\Unity\Hub\Editor\2019.4.41f2\Editor\Unity.exe"


def copy_uzdoom():
    for item in UZ_TREE.iterdir():
        if item.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(item, REVIEW / "uzdoom" / item.name)
    shutil.copytree(WORKTREE / "mods" / "doomerfall" / "src", REVIEW / "doomerfall", dirs_exist_ok=True)
    print("uzdoom from", UZ_TREE)


def unity():
    import subprocess
    project = WORKTREE / "daggerfall-unity-master"
    log = project / "Logs" / "cli-build.log"
    log.unlink(missing_ok=True)
    code = subprocess.call([sys.executable, QUIET, "--timeout", "1800", "--", UNITY, "-projectPath", str(project), "-buildTarget", "Win64",
                            "-executeMethod", "CliBuild.BuildWindows64", "-logFile", str(log)], stdin=subprocess.DEVNULL)
    text = log.read_text(errors="replace") if log.exists() else ""
    print(f"unity exit {code}, succeeded {'CliBuild result: Succeeded' in text}")
    for line in text.splitlines():
        if "error CS" in line:
            print(line[:220])


def copy_dfu():
    dfu = REVIEW / "dfu"
    plugin = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
    kept = plugin.read_bytes()
    shutil.copytree(WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64", dfu, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.pdb", "PortableAppdata"))
    plugin.write_bytes(kept)
    manager = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if b"Daggerfall Unity" in data:
        manager.write_bytes(data.replace(b"Daggerfall Unity", b"Doomerfall Local"))
    elif b"Doomerfall Local" not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")
    print("dfu from", WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64")


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
    elif command == "unity":
        unity()
    elif command == "dfu":
        copy_dfu()
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
