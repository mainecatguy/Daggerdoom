"""Records the section-output hash of real maps, to compare two engine builds.

Usage: sechash.py EXE OUTFILE
Covers stock DOOM.WAD E1M1 to E1M3, DOOM2 MAP01, plus every generated map the benchmark profiles visited.
"""
import glob, os, re, subprocess, sys

exe, out = sys.argv[1:3]
BENCH = r"D:\dev\DoomDaggerfall-loop\review\transition-speed\bench"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
work = os.path.join(BENCH, "sechash")
os.makedirs(work, exist_ok=True)
found = {}
for iwad, maps in (("DOOM.WAD", ["E1M1", "E1M2", "E1M3"]), ("DOOM2.WAD", ["MAP01"])):
    for name in maps:
        log = os.path.join(work, f"{iwad}-{name}.csv")
        if os.path.exists(log):
            os.remove(log)
        subprocess.run([sys.executable, QUIET, "--timeout", "6", "--", exe, "-iwad", os.path.join(WADS, iwad), "-config", os.path.join(work, "test.ini"), "-nosound", "-noautoload",
                        "-noactivate", "-ddtranslog", log, "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", name], cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        hashes = re.findall(r"sechash_(\w+?)_([0-9a-f]{16})", text)
        if not hashes:
            sys.exit(f"no section hash for {iwad} {name}")
        found[f"{iwad}:{hashes[-1][0]}"] = hashes[-1][1]
for csv in glob.glob(os.path.join(BENCH, "profiles", "*.csv")):
    label = os.path.basename(csv).split("-")[0]
    if label == os.path.basename(out).split(".")[0]:
        for name, value in re.findall(r"sechash_(\w+?)_([0-9a-f]{16})", open(csv, errors="replace").read()):
            found[f"generated:{name}"] = value
with open(out, "w") as f:
    for key in sorted(found):
        f.write(f"{key} {found[key]}\n")
print(len(found), "maps hashed")
print(open(out).read())
