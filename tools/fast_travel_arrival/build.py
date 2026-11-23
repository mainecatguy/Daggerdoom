"""Builds the native parts of the fast travel demo in a private folder. Logs go beside the build."""
import subprocess
import sys
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\fast-travel-arrival")
BUILD = REVIEW / "build"
PROJECTS = {"bridge": WORKTREE / "bridge", "launcher": WORKTREE / "launcher", "uzdoom": WORKTREE / "UZDoom"}


def run(args, log):
    with log.open("a", encoding="utf-8", errors="replace") as out:
        code = subprocess.call(args, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, cwd=WORKTREE)
    if code:
        sys.exit(f"failed ({code}): see {log}")


def converter():
    """Current converter and its shared package. Intermediates stay out of the source folder."""
    out, log = BUILD / "converter", BUILD / "converter-build.log"
    log.unlink(missing_ok=True)
    run(["dotnet", "build", str(WORKTREE / "tools" / "dungeon_converter" / "DungeonConverter.csproj"), "-c", "Release", "-o", str(out),
         f"-p:BaseIntermediateOutputPath={BUILD / 'converter-obj'}\\"], log)
    run([str(out / "DungeonConverter.exe"), "--runtime-assets", "--out", str(BUILD / "ddruntime.pk3"),
         "--arena2", r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"], log)
    print("built converter")


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or [*PROJECTS, "converter"]:
        if name == "converter":
            converter()
            continue
        target = BUILD / name
        log = BUILD / f"{name}-build.log"
        log.unlink(missing_ok=True)
        if not (target / "CMakeCache.txt").exists():
            run(["cmake", "-S", str(PROJECTS[name]), "-B", str(target), "-G", "Visual Studio 18 2026", "-A", "x64"], log)
        run(["cmake", "--build", str(target), "--config", "Release", "--parallel", "6"], log)
        print("built", name)


if __name__ == "__main__":
    main()
