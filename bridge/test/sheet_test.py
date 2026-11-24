"""Runs both real games with the character sheet test and checks that Doom read what Daggerfall published.

usage: sheet_test.py [demo folder]   (default D:\\dev\\DoomDaggerfall-loop\\review\\skill-publishing)
Daggerfall uses the demo's portable, registry-isolated copy. One launch, about 40 seconds, minimized.
"""
import re, subprocess, sys
from pathlib import Path

DEMO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\dev\DoomDaggerfall-loop\review\skill-publishing")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
SECONDS = 40
LINE = re.compile(r"sheet: (published|read) v(\d+) epoch (\d+) valid (\d+) level (-?\d+) str (-?\d+)/(-?\d+) archery (-?\d+)/(-?\d+) armor0 (-?\d+)/(-?\d+) fire (\d+)/(-?\d+) sum ([0-9a-f]{8})")


def main():
    run = DEMO / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log = run / "sheet-uz.log", run / "sheet-df.log"
    for path in (uz_log, df_log):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "sheet.ini"), "-dfbridgelog", str(uz_log), "-nosound", "-skill", "3", "+map", "E1M1",
          "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfsheettest", "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(SECONDS), "--", str(DEMO / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(DEMO / "uzdoom" / "uzdoom.exe"), "--dfu", str(DEMO / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(run / "sheet-launcher.log")]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)

    df_lines = df_log.read_text(encoding="utf-8", errors="replace").splitlines() if df_log.exists() else []
    uz_lines = uz_log.read_text(encoding="utf-8", errors="replace").splitlines() if uz_log.exists() else []
    print("--- Daggerfall")
    for l in df_lines:
        if "sheet" in l or "error" in l:
            print(l[:220])
    print("--- UZDoom")
    for l in uz_lines:
        if "sheet" in l or "error" in l:
            print(l[:220])
    published = [m.groups() for m in map(LINE.search, df_lines) if m and m.group(1) == "published"]
    read = {(m.group(2), m.group(14)) for m in map(LINE.search, uz_lines) if m and m.group(1) == "read"}
    missing = [p for p in published if (p[1], p[13]) not in read]
    print(f"published {len(published)}, read by Doom {len(read)}, published versions Doom never read {len(missing)}")
    for p in missing:
        print("  missing", p)
    steps = [l.split("sheet test: ", 1)[1] for l in df_lines if "sheet test: " in l]
    print("steps:", ", ".join(steps))
    ok = published and not missing and "done" in steps and "loaded" in steps
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
