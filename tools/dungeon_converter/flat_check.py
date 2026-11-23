"""Measures the frame cost of ordinary dungeon billboards and proves that animated textures change on screen.

Usage:
  python flat_check.py bench <dir> <slug> <work dir>             with and without DFDFLATS, twice each, at the densest reachable view
  python flat_check.py anim <dir> <slug> <work dir> <texture>    four shots of one mesh texture, such as dfmesh/a087r00.png
  python flat_check.py flat <dir> <slug> <work dir> <archive>    four shots of the first billboard from one archive

Each launch has a private config, a 30 second limit, and an off-screen window that never takes focus.
"""
import hashlib
import math
import os
import re
import struct
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-dungeon-flats\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
WIDTH, HEIGHT, OFFSCREEN = 1280, 720, -32000
BAD = ("Script error", "VM execution aborted", "FatalError", "Unknown class", "Execution could not continue")

mode, folder, slug, work = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3], os.path.abspath(sys.argv[4])
os.makedirs(work, exist_ok=True)
base = os.path.join(folder, slug)


def launch(name, doors, commands, extra=()):
    log, cfg, ini = (os.path.join(work, name + e) for e in (".stdout", ".cfg", ".ini"))
    if os.path.exists(log):
        os.remove(log)
    with open(cfg, "w", newline="\n") as f:
        f.write(commands + "\nquit\n" if not commands.endswith("quit") else commands + "\n")
    with open(ini, "w", newline="\n") as f:
        f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth={WIDTH}\nvid_defheight={HEIGHT}\n"
                f"win_w={WIDTH}\nwin_h={HEIGHT}\nvid_scalefactor=1\nwin_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 4
    files = [base + ".wad", base + "_mesh.pk3", doors, os.path.join(HERE, "texture_shot")]
    process = subprocess.Popen([EXE, "-iwad", IWAD, "-file", *files, "-config", ini, "-noactivate", "-nosound", "-nomonsters", "-skill", "3", "-stdout",
                                "-width", str(WIDTH), "-height", str(HEIGHT), "+vid_fullscreen", "0", "+vid_scalefactor", "1", "+vid_vsync", "0",
                                "+vid_maxfps", "0", "+cl_capfps", "0", "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png",
                                "+show_messages", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                *extra, "+map", "MAP01", "+exec", name + ".cfg"], cwd=work, startupinfo=startup,
                               stdout=open(log, "w"), stderr=subprocess.STDOUT)
    started = time.time()
    text = ""
    while time.time() - started < 30 and process.poll() is None:
        time.sleep(0.5)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        if any(b in text for b in BAD):
            break
    if process.poll() is None:
        process.kill()
    process.wait()
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    for b in BAD:
        if b in text:
            sys.exit(f"{name}: fatal log line: {b}\n" + "\n".join(l for l in text.splitlines() if b in l)[:600])
    return text


def points():
    nodes = []
    for line in open(base + ".points.txt"):
        q = line.split()
        if q and q[0] == "N":
            nodes.append((int(q[2]), int(q[3]), int(q[4])))
    return nodes


def flats(doors):
    rows = [l.split() for l in zipfile.ZipFile(doors).read("DFDFLATS").decode().splitlines()]
    return [(r[0], float(r[1]), float(r[2]), float(r[3])) for r in rows]


def view_of(target, nodes):
    """The nearest reachable node, looking at the target."""
    x, y, z = target
    n = min(nodes, key=lambda p: max(0, 40 - math.hypot(p[0] - x, p[1] - y)) * 100 + math.hypot(p[0] - x, p[1] - y) + abs(p[2] - z))
    return n[0], n[1], n[2], round(math.degrees(math.atan2(y - n[1], x - n[0]))) % 360


def shots(name, doors, view):
    x, y, z, angle = view
    names = [os.path.join(work, f"{name}_{i}.png").replace("\\", "/") for i in range(4)]
    for p in names:
        if os.path.exists(p):
            os.remove(p)
    steps = "".join(f'wait 5; screenshot "{p}"; ' for p in names)
    text = launch(name, doors, f"wait 40; netevent dftyaw {angle}; netevent dftshot {x} {y} {z}; wait 40; {steps}wait 8; quit")
    digests = [hashlib.sha1(open(p, "rb").read()).hexdigest()[:8] if os.path.exists(p) else "missing" for p in names]
    print(f"{name}: view {x},{y},{z} angle {angle}; {len(set(digests))} different images of 4: {' '.join(digests)}")
    return text


doors_file = base + "_doors.pk3"
if mode == "anim":
    data = zipfile.ZipFile(base + "_mesh.pk3").read("DFMESH")
    textures, batches, _ = struct.unpack_from("<iii", data, 12)
    names = [data[24 + i * 32:56 + i * 32].split(b"\0")[0].decode() for i in range(textures)]
    table = 24 + textures * 32
    vertices = table + batches * 12
    index = names.index(sys.argv[5])
    _, first, count = struct.unpack_from("<iii", data, table + index * 12)
    v = [struct.unpack_from("<8f", data, vertices + (first + i) * 32) for i in range(3)]
    middle = (sum(p[0] for p in v) / 3, sum(p[2] for p in v) / 3, sum(p[1] for p in v) / 3)
    shots("anim_" + re.sub(r"\W", "_", sys.argv[5]), doors_file, view_of(middle, points()))
elif mode == "flat":
    wanted = f"dfflat/a{int(sys.argv[5]):03d}"
    # The nearest node can be behind a wall, so try a few billboards until one visibly animates.
    for n, target in enumerate([f for f in flats(doors_file) if f[0].startswith(wanted)][:8]):
        name = f"flat_{sys.argv[5]}_{n}"
        shots(name, doors_file, view_of(target[1:], points()))
        if len({open(os.path.join(work, f"{name}_{i}.png"), "rb").read() for i in range(4)}) > 1:
            print("animating:", target[0], "in", name)
            break
    else:
        print("no tried view showed a change")
else:
    plain = os.path.join(work, slug + "_noflats_doors.pk3")
    with zipfile.ZipFile(doors_file) as source, zipfile.ZipFile(plain, "w", zipfile.ZIP_STORED) as out:
        for item in source.infolist():
            if item.filename != "DFDFLATS":
                out.writestr(item, source.read(item.filename))
    all_flats = flats(doors_file)
    nodes = points()[::4]
    best = max(nodes, key=lambda n: sum(1 for f in all_flats if abs(f[1] - n[0]) < 512 and abs(f[2] - n[1]) < 512))
    near = [f for f in all_flats if abs(f[1] - best[0]) < 512 and abs(f[2] - best[1]) < 512]
    angle = round(math.degrees(math.atan2(sum(f[2] for f in near) / len(near) - best[1], sum(f[1] for f in near) / len(near) - best[0]))) % 360
    print(f"view {best} angle {angle}, {len(near)} of {len(all_flats)} billboards within 512 units")
    script = f"wait 70; netevent dftyaw {angle}; netevent dftshot {best[0]} {best[1]} {best[2]}; wait 70; dfmesh_bench 1; wait 350; dfmesh_bench 0; wait 2; quit"
    for run in ("flats_a", "none_a", "flats_b", "none_b"):
        text = launch("bench_" + run, doors_file if run.startswith("flats") else plain, script)
        spawn = [l for l in text.splitlines() if l.startswith("DFDFLATS")]
        bench = [l for l in text.splitlines() if l.startswith("DFBENCH")]
        print(run, spawn[0] if spawn else "no billboards", "|", bench[0] if bench else "NO BENCH LINE")
