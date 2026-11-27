"""Stairs on foot from Privateer's Hold's starting cave (cave_stairs.zs).

usage: run_cave_stairs.py <uzdoom.exe> <play data folder with privateershold.wad> <output folder>
Runs the converted map alone (no Daggerfall) on a private desktop (quiet_run), groups the CSTEP edges into stair
flights (steps joined within 24 units), and prints each flight in order of walking distance from the cave, with the
placement nearest to it. Then prints the floor changes on the walk to the nearest placements."""
import math
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
P = [(563, 1419, 960), (247, 2311, 384), (992, 1357, 392), (1328, 2508, 384), (1824, 531, 384), (290, -1011, 384),
     (1134, 459, 1152), (576, 170, 384), (852, 2764, 384), (1441, -1300, 960), (1206, 572, 768), (980, 113, 384),
     (2246, 675, 384), (105, 578, 192), (1767, 1208, 960), (96, 570, 960), (684, 2265, 384), (-893, 321, 960),
     (336, -246, 960), (1076, 305, 384), (2600, 60, 384), (1041, 1154, 0), (237, -672, 576), (332, 206, 960),
     (1015, 95, 1152), (458, 1292, 576), (1245, 504, 384), (612, 152, 768), (1452, 381, 192), (-841, 1438, 840),
     (950, 764, 1152), (780, 383, 0), (2054, 1437, 480), (1113, 1010, 192), (1432, 337, 1248), (-54, 879, 384),
     (405, 525, 1344), (851, 1049, 381), (1236, 648, 192), (1251, 385, 1152), (951, 1002, 1344), (1319, -485, 384)]

uz, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
pk3 = out / "first_room_cave_stairs.pk3"
with zipfile.ZipFile(pk3, "w") as z:
    z.write(Path(__file__).with_name("cave_stairs.zs"), "zscript.txt")
    z.writestr("mapinfo.txt", 'GameInfo { AddEventHandlers = "FirstRoomCaveStairs" }\n')
log = out / "log-cave-stairs-log.txt"  # UZDoom names +logfile cave-stairs.log this way
log.unlink(missing_ok=True)
files = [str(data / n) for n in ("ddruntime.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
cmd = [sys.executable, QUIET, "--timeout", "400", "--cwd", str(out), "--", str(uz), "-iwad", IWAD, "-file", *files, str(pk3),
       "-config", str(out / "cave-stairs.ini"), "+logfile", "cave-stairs.log", "+map", "MAP01",
       "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.time() + 400
while time.time() < deadline and proc.poll() is None:
    text = log.read_text(errors="replace") if log.exists() else ""
    if "CAVESTAIRS done" in text or "Fatal error" in text or "VM execution aborted" in text:
        break
    time.sleep(0.5)
subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
text = log.read_text(errors="replace") if log.exists() else ""
lines = text.splitlines()
done = [l for l in lines if l.startswith("CAVESTAIRS done")]
if not done:
    print("no result\n" + "\n".join(l for l in lines if "error" in l.lower())[-2000:])
    sys.exit(1)
print(done[0])

steps = []
for l in lines:
    m = re.match(r"CSTEP (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\d+)", l)
    if m:
        steps.append(tuple(int(v) for v in m.groups()))
# group steps into flights: union steps within 24 units in x/y and 32 in z
parent = list(range(len(steps)))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a
cell = {}
for i, (x, y, z0, z1, w) in enumerate(steps):
    cell.setdefault((x // 24, y // 24), []).append(i)
for i, (x, y, z0, z1, w) in enumerate(steps):
    for cx in range(x // 24 - 1, x // 24 + 2):
        for cy in range(y // 24 - 1, y // 24 + 2):
            for j in cell.get((cx, cy), []):
                X, Y, Z0, Z1, W = steps[j]
                if abs(X - x) <= 24 and abs(Y - y) <= 24 and abs(min(Z0, Z1) - min(z0, z1)) <= 32:
                    parent[find(i)] = find(j)
groups = {}
for i in range(len(steps)):
    groups.setdefault(find(i), []).append(steps[i])
flights = []
for g in groups.values():
    zs = [s[2] for s in g] + [s[3] for s in g]
    rise = max(zs) - min(zs)
    levels = len(set(zs))
    if rise < 24 or levels < 3:  # a single lip or sill, not a flight of stairs
        continue
    xs, ys = [s[0] for s in g], [s[1] for s in g]
    cx, cy, cz = sum(xs) / len(xs), sum(ys) / len(ys), (max(zs) + min(zs)) / 2
    near = min(range(len(P)), key=lambda i: math.dist((cx, cy, cz), P[i]))
    flights.append((min(s[4] for s in g), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), levels, len(g), near,
                    int(math.dist((cx, cy, cz), P[near]))))
flights.sort()
print(f"stair flights (rise >= 24, >= 3 floor heights), nearest on foot first: {len(flights)}")
for f in flights[:25]:
    print("FLIGHT walk %5d  x %d..%d  y %d..%d  z %d..%d  heights %d edges %d  nearest placement p%d (%d away)" % f)
print("floor changes on the walk from the cave:")
for l in lines:
    if l.startswith("CPATH"):
        print(l)
