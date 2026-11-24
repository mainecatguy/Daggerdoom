"""Warns about scripts that start a game, the launcher, or Unity without quiet_run.py.

Usage: python loud_launch_lint.py [--base REV] [PATH ...]
With --base, checks the .py, .ps1, .bat and .cmd files changed since REV (git diff REV HEAD). Otherwise checks the
given files or folders. Prints one warning per file and exits 1 when there is any, so a caller can show it.

A file is loud when it names one of the programs below and starts processes, but never mentions quiet_run.py, or
when it passes --user-desktop to quiet_run.py. It is a reading check, not proof: quiet_probe.py measures a real run.
"""
import re
import subprocess
import sys
from pathlib import Path

PROGRAMS = re.compile(r"uzdoom(\.exe)?\b|DaggerfallUnity\.exe|\bUnity\.exe|doomerfall-launcher|launcher\.exe", re.I)
STARTS = re.compile(r"\bPopen\(|subprocess\.(run|call|check_call|check_output)\(|Start-Process|os\.startfile|"
                    r"^\s*(&|start\s)", re.I | re.M)
QUIET = re.compile(r"quiet_run|QuietRun|\bQUIET\b", re.I)
# Builds, copies and kills start nothing; %HERE% marks a play.bat the script writes for the owner's own play.
BUILDS = re.compile(r"cmake|--target|dotnet|msbuild|copy2?\(|copytree|taskkill|%HERE%|%~dp0", re.I)
SUFFIXES = {".py", ".ps1", ".bat", ".cmd"}
# Normal play keeps its own windows, mouse and sound on purpose.
PLAY = re.compile(r"(^|[\\/])(play[^\\/]*\.bat|scripts[\\/]play[\\/])", re.I)


def changed(base):
    names = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", base, "HEAD"], capture_output=True,
                           text=True).stdout.split()
    return [Path(n) for n in names]


def files(paths):
    for path in paths:
        if path.is_dir():
            yield from (p for p in path.rglob("*") if p.suffix.lower() in SUFFIXES)
        elif path.suffix.lower() in SUFFIXES and path.exists():
            yield path


EXE_NAMES = re.compile(r"\b(UZDOOM|UZ_EXE|DFU|DFU_EXE|LAUNCHER)\b")  # the constants tools keep exe paths in


class Targets:
    @staticmethod
    def search(text):
        return PROGRAMS.search(text) or EXE_NAMES.search(text)


TARGETS = Targets


def check(path):
    if PLAY.search(str(path)) or path.name == Path(__file__).name:
        return None
    text = path.read_text(errors="replace")
    if "--user-desktop" in text:
        return f"{path}: runs on the user's desktop (--user-desktop); say why in the notes, or remove it"
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if not STARTS.search(line):
            continue
        # The start call and two lines either side: the program it starts, and whether quiet_run.py wraps it.
        window = "\n".join(lines[max(0, number - 2):number + 3])
        found = TARGETS.search(window)
        if found and not QUIET.search(window) and not BUILDS.search(window):
            return f"{path}:{number + 1}: starts {found.group(0)} without quiet_run.py"
    return None


def main():
    args = sys.argv[1:]
    if args[:1] == ["--base"]:
        targets = changed(args[1]) + [Path(a) for a in args[2:]]
    else:
        targets = [Path(a) for a in args] or [Path("tools"), Path("scripts")]
    warnings = [w for w in (check(p) for p in files(targets)) if w]
    for warning in warnings:
        print("loud launch:", warning)
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
