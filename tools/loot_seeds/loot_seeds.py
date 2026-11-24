"""Builds and runs the fixed loot seed audit, then compares two fresh runs.

usage: loot_seeds.py build | run NAME | compare A B | all
The audit source is copied into the Unity project only for the audit build, then removed.
Runs go to D:\\dev\\DoomDaggerfall-loop\\review\\loot-seeds, in a portable copy with its own product name.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
PROJECT = WORKTREE / "daggerfall-unity-master"
BUILT = PROJECT / "Builds" / "Windows64"
AUDIT_SOURCE = HERE / "LootSeedAudit.cs.txt"
AUDIT_TARGET = PROJECT / "Assets" / "Scripts" / "Doomerfall" / "LootSeedAudit.cs"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
ARENA = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\loot-seeds")
GAME = REVIEW / "audit-dfu"
COMPARED = ("PILE", "DOOM", "CHECK")


def build():
    log = PROJECT / "Logs" / "cli-build.log"
    log.unlink(missing_ok=True)
    shutil.copy2(AUDIT_SOURCE, AUDIT_TARGET)
    try:
        code = subprocess.call([sys.executable, QUIET, "--desktop", "--timeout", "1800", "--", "Unity.exe", "-projectPath", str(PROJECT),
                                "-buildTarget", "Win64", "-executeMethod", "CliBuild.BuildWindows64", "-logFile", str(log)],
                               stdin=subprocess.DEVNULL)
    finally:
        AUDIT_TARGET.unlink(missing_ok=True)
        Path(str(AUDIT_TARGET) + ".meta").unlink(missing_ok=True)
    text = log.read_text(errors="replace") if log.exists() else ""
    for line in text.splitlines():
        if "error CS" in line:
            print(line)
    if "CliBuild result: Succeeded" not in text:
        sys.exit(f"unity build failed (exit {code})")
    if GAME.exists():
        shutil.rmtree(GAME)
    shutil.copytree(BUILT, GAME)
    (GAME / "Portable.txt").touch()
    manager = GAME / "DaggerfallUnity_Data" / "globalgamemanagers"
    data = manager.read_bytes()
    if b"Daggerfall Unity" not in data:
        sys.exit("product name not found; refusing to run an unisolated Daggerfall copy")
    manager.write_bytes(data.replace(b"Daggerfall Unity", b"Doomerfall Local"))
    print("audit game at", GAME)


def run(name):
    out = REVIEW / f"{name}.txt"
    out.unlink(missing_ok=True)
    # A fresh settings folder each run, so nothing carries over between the two games.
    shutil.rmtree(GAME / "PortableAppdata", ignore_errors=True)
    code = subprocess.call([sys.executable, QUIET, "--desktop", "--timeout", "90", "--cwd", str(GAME), "--",
                            str(GAME / "DaggerfallUnity.exe"), "-dfmute", "-screen-fullscreen", "0", "-logFile", str(REVIEW / f"{name}.log"),
                            "-dflootseedaudit", str(out), ARENA], stdin=subprocess.DEVNULL)
    print(f"run {name}: exit {code}")
    if not out.exists():
        sys.exit("no audit output")
    text = out.read_text()
    print("\n".join(l for l in text.splitlines() if l.startswith(("INFO", "CHECK", "FAIL", "AUDIT"))))


def compare(a, b):
    left = (REVIEW / f"{a}.txt").read_text().splitlines()
    right = (REVIEW / f"{b}.txt").read_text().splitlines()
    pick = lambda lines: [l for l in lines if l.startswith(COMPARED)]
    la, lb = pick(left), pick(right)
    same = la == lb
    print(f"{len(la)} compared lines in {a}, {len(lb)} in {b}: {'IDENTICAL' if same else 'DIFFERENT'}")
    for x, y in zip(la, lb):
        if x != y:
            print("-", x[:200])
            print("+", y[:200])
    # Placed enemies: Daggerfall's random marker type comes from the clock, so compare only matching types.
    enemies = lambda lines: {l.split(" -> ")[0]: l for l in lines if l.startswith("ENEMY")}
    ea, eb = enemies(left), enemies(right)
    shared = sorted(set(ea) & set(eb))
    differing = [k for k in shared if ea[k] != eb[k]]
    print(f"enemies: {len(ea)} and {len(eb)}, {len(shared)} same placement and type, {len(differing)} with different loot")
    for k in differing:
        print("-", ea[k][:200])
        print("+", eb[k][:200])
    controls = [l for l in left if l.startswith("CONTROL")], [l for l in right if l.startswith("CONTROL")]
    print("unseeded control", "same" if controls[0] == controls[1] else "differs", "between runs")
    ok = same and not differing and any(l == "AUDIT PASS" for l in left) and any(l == "AUDIT PASS" for l in right)
    print("RESULT", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    REVIEW.mkdir(parents=True, exist_ok=True)
    if command == "build":
        build()
    elif command == "run":
        run(sys.argv[2])
    elif command == "compare":
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)
    elif command == "all":
        build()
        run("first")
        run("second")
        sys.exit(0 if compare("first", "second") else 1)
    else:
        sys.exit(__doc__)
