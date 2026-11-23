"""Screenshot every distinct action object, door model, and flat of a converted dungeon from four sides.

Usage: python texture_shot.py <dir with slug.wad, slug_mesh.pk3, slug_doors.pk3[, slug_player.pk3]> <slug> <output dir> [first] [count]
The window runs off-screen and never takes focus, because a minimized UZDoom renders only 320x200.
Writes targets.txt next to the shots, one line per shot: name x y z angle.
"""
import math
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
WIDTH, HEIGHT, OFFSCREEN = 960, 540, -32000
DISTANCE = 72

folder, slug, out = os.path.abspath(sys.argv[1]), sys.argv[2], os.path.abspath(sys.argv[3])
first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
count = int(sys.argv[5]) if len(sys.argv) > 5 else 1000
os.makedirs(out, exist_ok=True)
doors = zipfile.ZipFile(os.path.join(folder, slug + "_doors.pk3"))
records = [l.split() for l in doors.read("DFACTIONS").decode().split("\n") if l.startswith("A ")]
targets, seen = [], set()
for p in records:
    kind, visual = int(p[2]), int(p[7])
    if kind == 0 or visual < 0 or (kind, visual) in seen:
        continue
    seen.add((kind, visual))
    x, y, z = float(p[8]), float(p[9]), float(p[10])
    z0, z1 = float(p[27]), float(p[28])
    targets.append((f"action{kind}_{visual}", x, y, z + (z0 + z1) / 2))
doorseen = set()
for line in doors.read("DFDOORS").decode().split("\n"):
    p = line.split()
    if not p or p[0] in doorseen:
        continue
    doorseen.add(p[0])
    targets.append((f"door_{p[0]}", float(p[1]), float(p[2]), float(p[3]) + (float(p[9]) + float(p[10])) / 2))
shots = []
if len(sys.argv) > 6:  # walk mode: <points file> <step>: four views at every step-th node reachable from the entrance
    import collections
    nodes, adjacency, start = {}, collections.defaultdict(list), 0
    for line in open(sys.argv[6]):
        q = line.split()
        if q[0] == "S": start = int(q[1])
        elif q[0] == "N": nodes[int(q[1])] = (int(q[2]), int(q[3]), int(q[4]))
        elif q[0] == "E": adjacency[int(q[1])].append(int(q[2]))
    order, queue, seen = [], collections.deque([start]), {start}
    while queue:
        n = queue.popleft(); order.append(n)
        for m in adjacency[n]:
            if m not in seen: seen.add(m); queue.append(m)
    step = int(sys.argv[7])
    targets = [(f"walk{n}", nodes[n][0], nodes[n][1], nodes[n][2] + 41) for n in order[::step]]
for name, x, y, z in targets:
    for angle in (0, 90, 180, 270):
        rad = math.radians(angle)
        # The camera stands DISTANCE away and looks back at the target, so its angle is opposite.
        shots.append((f"{name}_{angle}", x + (0 if len(sys.argv) > 6 else DISTANCE) * math.cos(rad), y + (0 if len(sys.argv) > 6 else DISTANCE) * math.sin(rad), z - 41, angle if len(sys.argv) > 6 else (angle + 180) % 360))
shots = shots[first:first + count]
with open(os.path.join(out, "targets.txt"), "w") as f:
    for s in shots:
        f.write("%s %.1f %.1f %.1f %d\n" % s)
with open(os.path.join(out, "shot.cfg"), "w", newline="\n") as f:
    for i, (name, x, y, z, angle) in enumerate(shots):
        shot = os.path.join(out, name + ".png").replace("\\", "/")
        f.write(f'alias dfstep{i} "netevent dftyaw {angle}; netevent dftshot {x:.0f} {y:.0f} {z:.0f}; wait 10; screenshot \\"{shot}\\"; wait 4; dfstep{i + 1}"\n')
    f.write(f'alias dfstep{len(shots)} "quit"\nalias dfgo "vid_setsize {WIDTH} {HEIGHT}; wait 35; dfstep0"\nwait 105; dfgo\n')
with open(os.path.join(out, "shot.ini"), "w", newline="\n") as f:
    f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth={WIDTH}\n"
            f"vid_defheight={HEIGHT}\nwin_w={WIDTH}\nwin_h={HEIGHT}\nvid_scalefactor=1\nwin_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 4
files = [os.path.join(folder, slug + s) for s in (".wad", "_mesh.pk3", "_doors.pk3", "_player.pk3")]
files = [p for p in files if os.path.exists(p)]
process = subprocess.Popen([UZDOOM, "-iwad", IWAD, "-file", *files, os.path.join(HERE, "texture_shot"),
                            "-config", os.path.join(out, "shot.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3", "-stdout",
                            "-width", str(WIDTH), "-height", str(HEIGHT), "+vid_fullscreen", "0", "+vid_scalefactor", "1",
                            "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png", "+show_messages", "0",
                            "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                            "+logfile", "tshot.log", "+map", "MAP01", "+exec", "shot.cfg"], cwd=out, startupinfo=startup,
                           stdout=open(os.path.join(out, "tshot.stdout"), "w"), stderr=subprocess.STDOUT)
try:
    code = process.wait(30 + len(shots))
except subprocess.TimeoutExpired:
    process.kill()
    process.wait()
    code = "timed out"
print("UZDoom exit:", code, "| shots:", sum(os.path.exists(os.path.join(out, s[0] + ".png")) for s in shots), "of", len(shots))
