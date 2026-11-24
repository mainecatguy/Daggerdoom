"""Launches the real play.bat minimized for about 25 seconds and reports what both games and the sound system did.

Also summarizes the profiled worst frame before and after, from the benchmark's saved profiles.
"""
import glob, os, re, statistics, subprocess, sys

REVIEW = r"D:\dev\DoomDaggerfall-loop\review\transition-speed"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
RUN = os.path.join(REVIEW, "run")
for name in ("log-console.txt", "console.log", "uz.log", "df.log", "launcher.log"):
    path = os.path.join(RUN, name)
    if os.path.exists(path):
        os.remove(path)
env = dict(os.environ, DD_PLAY_ARGS="--minimized --nodraw")
code = subprocess.call([sys.executable, QUIET, "--timeout", "25", "--", "cmd", "/c", os.path.join(REVIEW, "play.bat")], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("play.bat run, exit", code, "(124 is the planned time limit)")
logs = glob.glob(os.path.join(RUN, "*console*"))
text = open(logs[0], errors="replace").read() if logs else ""
print("console log:", os.path.basename(logs[0]) if logs else "missing", "| fatal lines:", sum("FATAL" in l for l in text.splitlines()), "| city active:", "DDTOWN active DDT09183" in text)
print("sound lines:", [l.strip()[:90] for l in text.splitlines() if re.search(r"openal|sndfile|sound init|I_InitSound", l, re.I)][:4])
df = os.path.join(RUN, "df.log")
body = open(df, errors="replace").read() if os.path.exists(df) else ""
print("Daggerfall log bytes:", len(body), "| reached play:", "PLAY" in body.upper())

print("\nworst frame during a return to town, from the profiler (ms):")
for route in ("city", "gothway", "dungeon"):
    row = []
    for label in ("before", "final"):
        worst = []
        for csv in glob.glob(os.path.join(REVIEW, "bench", "profiles", f"{label}-{route}-*.csv")):
            marks, frames = [], []
            for line in open(csv, errors="replace"):
                p = line.strip().split(",")
                if p[0] == "M" and len(p) == 8:
                    marks.append((float(p[1]), p[2]))
                elif p[0] == "F" and len(p) == 3:
                    frames.append((float(p[1]), float(p[2])))
            for i, (t, phase) in enumerate(marks):
                if phase.startswith("leave>DDT"):
                    arrive = next((m[0] for m in marks[i + 1:] if m[1] == "arrive"), None)
                    if arrive is not None:
                        worst.append(max((ms for at, ms in frames if t <= at <= arrive + 1000), default=0))
        row.append(f"{label}: n={len(worst)} median={statistics.median(worst):.0f} worst={max(worst):.0f}" if worst else f"{label}: none")
    print(f"  {route:8}", " | ".join(row))
