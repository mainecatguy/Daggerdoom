"""Runs each way agents launch programs under quiet_probe and prints one table row per launch path.

Usage: python measure.py [--quiet-run QUIET_RUN_PY] OUT_DIR [CASE ...]
With no CASE, runs every case except the slow ones (unity_build). Prints a Markdown table, and writes each case's
probe report to OUT_DIR/<case>.json and its output to OUT_DIR/<case>.txt.
Paths below point at the main checkout's game data and at existing review builds; change them to measure others.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parent.parent
QUIET = str(WORKTREE / "scripts" / "overnight" / "quiet_run.py")
PROBE = str(HERE / "quiet_probe.py")
PY = sys.executable
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-quiet\Release\uzdoom.exe"
DFU = r"D:\dev\DoomDaggerfall-loop\review\questfaces\dfu\DaggerfallUnity.exe"
AGENT_CVARS = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]


def cases(out):
    uz = [UZDOOM, "-iwad", IWAD, "-config", str(out / "measure.ini"), "-nosound", "-skill", "3"]
    paired = [PY, str(WORKTREE / "tools" / "stationary_npcs" / "stationary_npcs.py"), "run", "quietprobe", "dungeon"]
    return {
        # UZDoom as AGENTS.md says: quiet_run, -noactivate, background cvars, 20 s of E1M1.
        "uzdoom_agents": [PY, QUIET, "--timeout", "20", "--cwd", str(out), "--"] + uz + ["-noactivate"] + AGENT_CVARS +
                         ["+map", "E1M1"],
        # The same without -noactivate, as an agent that forgets it would run it.
        "uzdoom_no_noactivate": [PY, QUIET, "--timeout", "20", "--cwd", str(out), "--"] + uz + AGENT_CVARS +
                                ["+map", "E1M1"],
        # check.ps1's startup check.
        "uzdoom_norun": [PY, QUIET, "--timeout", "60", "--cwd", str(out), "--"] + uz + ["-norun", "-stdout"],
        # Daggerfall Unity started directly through quiet_run, without and with --desktop. 25 s of the title screen.
        "dfu_direct": [PY, QUIET, "--timeout", "25", "--", DFU, "-dfmute", "-screen-fullscreen", "0"],
        "dfu_desktop": [PY, QUIET, "--timeout", "25", "--desktop", "--", DFU, "-dfmute", "-screen-fullscreen", "0"],
        # A real paired test through the launcher (--minimized).
        "paired_stationary_npcs": paired,
        # The same harness run inside quiet_run: everything it starts inherits the private desktop.
        "paired_in_quiet_run": [PY, QUIET, "--timeout", "120", "--"] + paired,
        # A smoke load of a converted dungeon.
        "smoke_load": [PY, str(WORKTREE / "tools" / "dungeon_converter" / "smoke_load.py"),
                       r"D:\dev\DoomDaggerfall-loop\review\building-entry\dungeon-standalone", "privateershold"],
        # check.ps1's Unity build line. Slow (minutes); run it by name.
        "unity_build": ["powershell", "-NoProfile", "-Command",
                        f"Set-Location '{WORKTREE}'; & python '{QUIET}' --timeout 1800 --desktop -- Unity.exe "
                        "-projectPath daggerfall-unity-master -buildTarget Win64 -executeMethod CliBuild.BuildWindows64 "
                        "-logFile daggerfall-unity-master/Logs/cli-build.log; exit $LASTEXITCODE"],
    }


COLUMNS = ("shown", "onscreen", "focus", "flash", "audible", "clip", "move", "hidden", "capture", "injected")


def main():
    global QUIET
    args = sys.argv[1:]
    if args[:1] == ["--quiet-run"]:  # measure another copy of quiet_run.py
        QUIET, args = str(Path(args[1]).resolve()), args[2:]
    if not args:
        sys.exit(__doc__)
    out = Path(args[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    table = cases(out)
    names = args[1:] or [n for n in table if n != "unity_build"]
    rows = []
    for name in names:
        report = out / f"{name}.json"
        with open(out / f"{name}.txt", "w", encoding="utf-8", errors="replace") as log:
            code = subprocess.call([PY, PROBE, "--json", str(report), "--timeout", "2400", "--"] + table[name],
                                   stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        data = json.loads(report.read_text())
        counts = data["counts"]
        cells = [str(counts[c]) + (f" (+{counts[c + '_other']} other)" if counts.get(c + "_other") else "")
                 for c in COLUMNS]
        rows.append(f"| {name} | {code} | " + " | ".join(cells) + " |")
        print(rows[-1], flush=True)
    print("\n| Launch path | Exit | " + " | ".join(COLUMNS) + " |")
    print("|---|---|" + "---|" * len(COLUMNS))
    print("\n".join(rows))


if __name__ == "__main__":
    main()
