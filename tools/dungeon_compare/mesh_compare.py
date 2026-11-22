"""Compare Daggerfall, the UZDoom mesh layer, and the Doom collider at the saved viewpoints, then test popping and timing.

Usage: python tools/dungeon_compare/mesh_compare.py --views tools/dungeon_compare/views/privateers_hold.txt
           --map <map.wad> --mesh <map_mesh.pk3> --df <dir with <id>.df.png> --out <dir outside the repo>
           [--mode views|sweep|bench|all] [--width 960 --height 720]

views: writes <id>.mesh.png, <id>.collider.png, <id>.triple.png, index.html, and image difference scores.
sweep: walks a dense camera path in mesh view, screenshots each step, and flags sudden frame-to-frame changes.
bench: runs the same camera path in both views and prints frame time median, 95th percentile, and worst case.
"""
import argparse
import html
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import read_png, read_views, write_png, HERE, IWAD, OFFSCREEN, REPO, SW_SHOWNOACTIVATE

UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
EYE = 48
SWEEP_STEPS = 16  # interpolated camera positions between consecutive viewpoints
SPIKE_RATIO = 6.0  # a frame change this many times the local median is reported
SPIKE_FLOOR = 12.0  # mean absolute difference per channel below which a change is never reported
BLOCK_FLICKER = 15.0  # brightness (0-255) by which a grid block may differ from both neighboring frames
BLOCK_JUMP = 60.0  # brightness change of a grid block between two frames that is reported for review
FINE_VIEWS = ("v02", "v04", "v06", "v07", "v14", "v16")


def sweep_path(views):
    """Interpolates between viewpoints that share a floor and are close, and turns in place at each viewpoint."""
    path = []
    for a, b in zip(views, views[1:]):
        for yaw in range(0, 360, 15):
            path.append((a["x"], a["y"], a["floor"] + EYE, a["yaw"] + yaw, 0))
        if abs(a["floor"] - b["floor"]) <= 512 and abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) <= 1200:
            for s in range(1, SWEEP_STEPS):
                t = s / SWEEP_STEPS
                path.append((a["x"] + (b["x"] - a["x"]) * t, a["y"] + (b["y"] - a["y"]) * t,
                             a["floor"] + (b["floor"] - a["floor"]) * t + EYE, a["yaw"], 0))
    return path


def fine_path(views):
    """Slow turns and walks in rooms, doorways, stacked areas, the ramp, and the cave, so a popped model stands out."""
    path = []
    for v in views:
        if not v["id"].startswith(FINE_VIEWS):
            continue
        for turn in range(0, 91):
            path.append((v["x"], v["y"], v["floor"] + EYE, v["yaw"] - 45 + turn, v["pitch"]))
        c, s = math.cos(math.radians(v["yaw"])), math.sin(math.radians(v["yaw"]))
        for step in range(1, 41):
            path.append((v["x"] + c * step * 4, v["y"] + s * step * 4, v["floor"] + EYE, v["yaw"] + 45, v["pitch"]))
    return path


def launch(args, out, name, lines, cfg, timeout):
    lumps = os.path.join(out, name + "_lumps")
    os.makedirs(lumps, exist_ok=True)
    with open(os.path.join(lumps, "DFVIEWS"), "w", newline="\n") as f:
        f.write("".join(f"{i} {x:.2f} {y:.2f} {z:.2f} {yaw:.2f} {pitch:.2f}\n" for i, x, y, z, yaw, pitch in lines))
    with open(os.path.join(out, name + ".cfg"), "w", newline="\n") as f:
        f.write(cfg)
    ini = os.path.join(out, name + ".ini")
    with open(ini, "w", newline="\n") as f:
        f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth={args.width}\n"
                f"vid_defheight={args.height}\nwin_w={args.width}\nwin_h={args.height}\nvid_scalefactor=1\nwin_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWNOACTIVATE
    log = os.path.join(out, f"log-{name}.txt")
    if os.path.exists(log):
        os.remove(log)
    with open(os.path.join(out, name + ".console.txt"), "w") as console:
        process = subprocess.Popen([UZDOOM, "-iwad", IWAD, "-file", os.path.abspath(args.map), os.path.abspath(args.mesh),
                                    os.path.join(HERE, "doom"), lumps, "-config", ini, "-stdout", "-noactivate", "-nosound", "-nomonsters",
                                    "-skill", "3", "-width", str(args.width), "-height", str(args.height), "+vid_fullscreen", "0",
                                    "+vid_scalefactor", "1", "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png", "+show_messages", "0",
                                    "+r_drawplayersprites", "0", "+vid_vsync", "0", "+vid_maxfps", "0", "+cl_capfps", "0",
                                    "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                    "+logfile", name, "+map", "MAP01", "+exec", name + ".cfg"],
                                   cwd=out, startupinfo=startup, stdout=console, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = "timed out"
    print(f"{name}: UZDoom exit {code}")
    return open(log, errors="replace").read() if os.path.exists(log) else ""


def shot(path):
    return path.replace("\\", "/")


def difference(a, b, match_brightness=False):
    """Mean absolute channel difference. match_brightness scales b to a's mean, because the engines are lit differently."""
    gain = 1.0
    if match_brightness:
        sum_a = sum(sum(r[::4]) for r in a[::4])
        sum_b = sum(sum(r[::4]) for r in b[::4])
        gain = sum_a / max(sum_b, 1)
    total = count = 0
    for ra, rb in zip(a[::4], b[::4]):
        for i in range(0, len(ra), 12):
            total += abs(ra[i] - rb[i] * gain) + abs(ra[i + 1] - rb[i + 1] * gain) + abs(ra[i + 2] - rb[i + 2] * gain)
            count += 3
    return total / max(count, 1)


def magenta_share(rows):
    hits = count = 0
    for row in rows[::4]:
        for i in range(0, len(row), 12):
            hits += row[i] > 200 and row[i + 1] < 60 and row[i + 2] > 200
            count += 1
    return hits / max(count, 1)


def black_share(rows):
    hits = count = 0
    for row in rows[::4]:
        for i in range(0, len(row), 12):
            hits += row[i] < 4 and row[i + 1] < 4 and row[i + 2] < 4
            count += 1
    return hits / max(count, 1)


def block_means(rows, columns=12, lines=9):
    """Mean brightness of a coarse grid. Averaging removes the texture shimmer that hides a popped model."""
    h, w = len(rows), len(rows[0]) // 3
    totals, counts = [0] * (columns * lines), [0] * (columns * lines)
    for y in range(0, h, 2):
        row, line = rows[y], y * lines // h
        for x in range(0, w, 2):
            at = line * columns + x * columns // w
            totals[at] += row[x * 3] + row[x * 3 + 1] + row[x * 3 + 2]
            counts[at] += 3
    return [t / max(c, 1) for t, c in zip(totals, counts)]


def flicker_score(before, now, after):
    """Largest block that differs from both neighbors by more than the neighbors differ from each other."""
    return max(min(abs(n - b), abs(n - a)) - abs(b - a) for b, n, a in zip(before, now, after))


def run_views(args, views, out):
    cfg = ""
    for i, v in enumerate(views):
        mesh, collider = (shot(os.path.join(out, f"{v['id']}.{k}.png")) for k in ("mesh", "collider"))
        cfg += (f'alias dfstep{i} "netevent dfview {i}; dfmesh_view 1; wait 6; screenshot \\"{mesh}\\"; wait 6; '
                f'dfmesh_view 0; wait 6; screenshot \\"{collider}\\"; wait 6; dfstep{i + 1}"\n')
    cfg += f'alias dfstep{len(views)} "quit"\nalias dfgo "vid_setsize {args.width} {args.height}; wait 35; dfstep0"\nwait 105; dfgo\n'
    lines = [(v["id"], v["x"], v["y"], v["floor"] + EYE, v["yaw"], v["pitch"]) for v in views]
    text = launch(args, out, "views", lines, cfg, args.timeout)
    for line in text.splitlines():
        if line.startswith("DFMesh"):
            print(line)
    cards, rows = [], []
    for v in views:
        paths = [os.path.join(args.df, v["id"] + ".df.png")] + [os.path.join(out, f"{v['id']}.{k}.png") for k in ("mesh", "collider")]
        try:
            images = [read_png(p) for p in paths]
        except (OSError, ValueError) as error:
            print(v["id"], "missing image:", error)
            rows.append((v["id"], None, None, None))
            continue
        w, h = images[0][0], images[0][1]
        if any((i[0], i[1]) != (w, h) for i in images):
            print(v["id"], "size mismatch", [(i[0], i[1]) for i in images])
            rows.append((v["id"], None, None, None))
            continue
        divider = b"\xff\xff\x00" * 4
        triple = os.path.join(out, v["id"] + ".triple.png")
        write_png(triple, w * 3 + 8, [a + divider + b + divider + c for a, b, c in zip(images[0][2], images[1][2], images[2][2])])
        mesh_score, collider_score = (difference(images[0][2], images[k][2], True) for k in (1, 2))
        rows.append((v["id"], mesh_score, collider_score, black_share(images[1][2])))
        cards.append(f"<h2>{html.escape(v['id'])}: {html.escape(v['note'])}</h2><p>Mean difference from Daggerfall: mesh {mesh_score:.1f}, "
                     f"collider {collider_score:.1f}. Empty (black) mesh pixels: {rows[-1][3] * 100:.1f}%</p>"
                     f'<img src="{html.escape(v["id"])}.triple.png" loading="lazy">')
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset=utf-8><title>Daggerfall mesh comparison</title>"
                "<style>body{background:#222;color:#eee;font:15px sans-serif}img{max-width:100%}</style>"
                "<h1>Left: Daggerfall Unity. Middle: UZDoom mesh view. Right: UZDoom collider view.</h1>" + "".join(cards))
    print("id, mesh difference, collider difference, black share")
    for r in rows:
        print(r[0], *("n/a" if x is None else f"{x:.3f}" for x in r[1:]))


def run_sweep(args, views, out):
    folder = os.path.join(out, "sweep")
    os.makedirs(folder, exist_ok=True)
    for old in os.listdir(folder):
        if old.endswith(".png"):
            os.remove(os.path.join(folder, old))
    path = fine_path(views)
    cfg = ""
    for i in range(len(path)):
        cfg += f'alias dfstep{i} "netevent dfview {i}; wait 2; screenshot \\"{shot(os.path.join(folder, f"{i:04d}.png"))}\\"; wait 2; dfstep{i + 1}"\n'
    cfg += f'alias dfstep{len(path)} "quit"\nalias dfgo "dfmesh_view 1; vid_setsize {args.width} {args.height}; wait 35; dfstep0"\nwait 105; dfgo\n'
    launch(args, out, "sweep", [(f"s{i}", *p) for i, p in enumerate(path)], cfg, args.timeout * 4)
    def continuous(i):
        # Deliberate jumps between viewpoints are not evidence of popping.
        a, b = path[i - 1], path[i]
        turn = abs((a[3] - b[3] + 180) % 360 - 180)
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) <= 160 and turn <= 15
    images, holes, missing = {}, [], 0
    for i in range(len(path)):
        name = os.path.join(folder, f"{i:04d}.png")
        if not os.path.exists(name):
            missing += 1
            continue
        images[i] = read_png(name)[2]
        holes.append((black_share(images[i]), i))
    blocks = {i: block_means(rows) for i, rows in images.items()}
    flickers, jumps = [], []
    for i in range(1, len(path) - 1):
        if all(k in blocks for k in (i - 1, i, i + 1)) and continuous(i) and continuous(i + 1):
            flickers.append((flicker_score(blocks[i - 1], blocks[i], blocks[i + 1]), i))
            jumps.append((max(abs(p - q) for p, q in zip(blocks[i - 1], blocks[i])), i))
    flagged = [(s, i) for s, i in flickers if s > BLOCK_FLICKER]
    lasting = [(s, i) for s, i in jumps if s > BLOCK_JUMP]
    print(f"sweep: {len(path)} steps, {missing} missing, {len(flickers)} tested frames, one-frame flickers {len(flagged)} "
          f"(largest {max(flickers)[0]:.1f}, limit {BLOCK_FLICKER}), sudden block changes {len(lasting)} "
          f"(largest {max(jumps)[0]:.1f}, limit {BLOCK_JUMP}), worst black share {max(holes)[0] * 100:.1f}% at step {max(holes)[1]}")
    # Positive control: black out a model-sized block (5% of the frame) in one frame.
    caught = tried = 0
    for _, i in flickers[::10]:
        w, h = len(images[i][0]) // 3, len(images[i])
        fake = [bytes(r[:(w * 2 // 5) * 3]) + b"\0" * ((w // 4) * 3) + bytes(r[((w * 2 // 5) + w // 4) * 3:])
                if h * 2 // 5 <= y < h * 3 // 5 else r for y, r in enumerate(images[i])]
        tried += 1
        caught += flicker_score(blocks[i - 1], block_means(fake), blocks[i + 1]) > BLOCK_FLICKER
    print(f"detector control: caught {caught} of {tried} injected one-frame disappearances")
    for s, i in sorted(flagged, reverse=True)[:10]:
        print(f"  flicker step {i}: score {s:.1f} pose {path[i]}")
    for s, i in sorted(lasting, reverse=True)[:10]:
        print(f"  sudden change step {i}: score {s:.1f} pose {path[i]}")


def run_bench(args, views, out):
    path = sweep_path(views)
    cfg = ""
    for mode, label in ((1, "m"), (0, "c")):
        for i in range(len(path)):
            following = f"{label}step{i + 1}"
            cfg += f'alias {label}step{i} "netevent dfview {i}; wait 2; {following}"\n'
    cfg += (f'alias mstep{len(path)} "dfmesh_bench 0; dfmesh_view 0; wait 35; dfmesh_bench 1; cstep0"\n'
            f'alias cstep{len(path)} "dfmesh_bench 0; quit"\n'
            f'alias dfgo "dfmesh_view 1; vid_setsize {args.width} {args.height}; wait 70; dfmesh_bench 1; mstep0"\nwait 105; dfgo\n')
    text = launch(args, out, "bench", [(f"s{i}", *p) for i, p in enumerate(path)], cfg, args.timeout * 2)
    for line in text.splitlines():
        if re.match(r"DFBENCH|DFMesh", line):
            print(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--views", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--df", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", default="all", choices=("views", "sweep", "bench", "all"))
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    if (os.path.normcase(out) + os.sep).startswith(os.path.normcase(REPO) + os.sep):
        sys.exit("--out must be outside the repository: captures are derived from game data")
    os.makedirs(out, exist_ok=True)
    views = read_views(args.views)
    if args.mode in ("views", "all"):
        run_views(args, views, out)
    if args.mode in ("sweep", "all"):
        run_sweep(args, views, out)
    if args.mode in ("bench", "all"):
        run_bench(args, views, out)


if __name__ == "__main__":
    main()
