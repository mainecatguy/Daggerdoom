"""Quick stock check before the Unity build lands: builds the mod pk3 into a folder and runs DOOM.WAD E1M1 with this
worktree's UZDoom build, opening the skills key and killing a summoned Baron (no bridge: nothing must happen).
usage: quick_e1m1.py <folder>
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
pk3, log = out / "doomerfall.pk3", out / "e1.txt"
log.unlink(missing_ok=True)
subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(pk3)], stdout=subprocess.DEVNULL)
code = subprocess.call([sys.executable, r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py", "--timeout", "40", "--cwd", str(out), "--",
                        r"D:\dev\DoomDaggerfall-build\uzdoom-items\Release\uzdoom.exe", "-noactivate", "-iwad", r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD",
                        "-config", str(out / "e1.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", str(pk3), "+logfile", str(log),
                        "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1",
                        "+wait 35;netevent df_skills;summon baronofhell;wait 10;kill monsters;wait 70;quit"], stdin=subprocess.DEVNULL)
text = log.read_text(errors="replace") if log.exists() else ""
print("exit", code, "lines", len(text.splitlines()))
for line in text.splitlines():
    if any(k in line.lower() for k in ("error", "skillxp", "dfs_", "unknown action", "e1m1", "fatal")):
        print(line[:200])
