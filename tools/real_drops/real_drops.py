"""Builds, audits, and assembles the real enemy drops demo in a private review folder.

usage: real_drops.py build | audit | unity | assemble | usegame audit-dfu|final | run NAME [--load] [--drla] [--presave] [--area N] [--audit]
       | playcheck | registry save|compare
The audit source is copied into the Unity project only for the audit build, then removed.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "monster_deaths"))
import monster_deaths as deaths  # noqa: E402

base, pickup = deaths.base, deaths.pickup
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\real-enemy-drops")
NATIVE = REVIEW / "build"
deaths.REVIEW = pickup.REVIEW = base.REVIEW = REVIEW
base.BUILD, base.RUN = NATIVE, REVIEW / "run"
base.PREVIOUS = Path(r"D:\dev\DoomDaggerfall-loop\review\monster-deaths")
AUDIT_SOURCE = HERE / "DoomerfallDropAudit.cs.txt"
AUDIT_TARGET = base.WORKTREE / "daggerfall-unity-master" / "Assets" / "Scripts" / "Doomerfall" / "DoomerfallDropAudit.cs"
BUILT = base.WORKTREE / "daggerfall-unity-master" / "Builds" / "Windows64"


def audit_build():
    shutil.copy2(AUDIT_SOURCE, AUDIT_TARGET)
    try:
        base.unity()
    finally:
        AUDIT_TARGET.unlink(missing_ok=True)
        Path(str(AUDIT_TARGET) + ".meta").unlink(missing_ok=True)
    target = REVIEW / "audit-dfu"
    if target.exists():
        shutil.rmtree(target)
    REVIEW.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BUILT, target)
    print("audit game at", target)


def use_game(folder):
    """Swaps which Daggerfall build the shared run path launches, keeping the isolated settings folder."""
    dfu = REVIEW / "dfu"
    base.copy_tree(folder, dfu)
    (dfu / "Portable.txt").touch()
    manager = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if b"Daggerfall Unity" in data:
        manager.write_bytes(data.replace(b"Daggerfall Unity", b"Doomerfall Local"))
    elif b"Doomerfall Local" not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")


def assemble():
    deaths.make_wad()
    deaths.assemble()
    play = REVIEW / "play.bat"
    text = play.read_text()
    mods = " ".join(f'--mod "{base.MODS / name}"' for name in base.DRLA)
    marker = '--mod "%HERE%data\\ddruntime.pk3"'
    if marker not in text:
        sys.exit("play.bat layout changed")
    play.write_text(text.replace(marker, mods + " " + marker), newline="")
    print("play.bat loads DRLA, DRLA Monsters, and DRLAX")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        base.build()
    elif command == "audit":
        audit_build()
    elif command == "unity":
        base.unity()
    elif command == "assemble":
        assemble()
    elif command == "usegame":
        use_game(REVIEW / sys.argv[2] if sys.argv[2] == "audit-dfu" else BUILT)
    elif command == "run":
        extra = []
        if "--area" in sys.argv:
            extra += ["-dfarealevel", sys.argv[sys.argv.index("--area") + 1]]
        if "--audit" in sys.argv:
            extra += ["-dfdropaudit", str(REVIEW / "run" / "audit.txt")]
        deaths.EXTRA_DF = extra
        deaths.run(sys.argv[2], "--load" in sys.argv, "--drla" in sys.argv, "--presave" in sys.argv)
    elif command == "playcheck":
        launch = pickup.launch_args
        pickup.launch_args = lambda here, uz=(), df=(), minimized=False: launch(here, uz, list(df) + ["-dfmonsterquest", deaths.QUEST], minimized)
        pickup.play_check()
    elif command == "registry":
        base.registry(sys.argv[2])
    else:
        sys.exit(__doc__)
