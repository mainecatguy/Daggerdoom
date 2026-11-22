"""Capture matching Daggerfall Unity and UZDoom views of a converted dungeon.

Usage: python tools/dungeon_compare/compare.py --views tools/dungeon_compare/views/privateers_hold.txt
           --map <converted.wad> --out <dir outside the repo> [--skip-df] [--skip-doom] [--eye 48]

Writes <id>.df.png, <id>.doom.png, <id>.side.png, probes.csv, and index.html. See README.md.
"""
import argparse
import csv
import html
import os
import re
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGERFALL = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
CAPTURE_EXE = os.path.join(REPO, "daggerfall-unity-master", "Builds", "Capture", "DFCapture.exe")
WIDTH, HEIGHT = 960, 720
VERTICAL_FOV = 73.74  # matches Doom's 90 degree horizontal view at 4:3
PROBES = ("down", "up", "east", "north", "west", "south")
MISMATCH = 24  # Doom units; larger than the 16-unit grid plus height rounding
SW_SHOWNOACTIVATE = 4
OFFSCREEN = -8000


def read_views(path):
    views = []
    for raw in open(path, encoding="utf-8"):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = [f.strip() for f in line.split("|")]
        x, y, floor, yaw, pitch = (float(v) for v in fields[2].split())
        views.append(dict(id=fields[0], kind=fields[1], x=x, y=y, floor=floor, yaw=yaw, pitch=pitch,
                          note=fields[3] if len(fields) > 3 else ""))
    return views


def capture_daggerfall(views, out, eye, exe, timeout, dungeon="Privateer's Hold", flood=True):
    job = os.path.join(out, "df_job.txt")
    with open(job, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"dungeon\t{dungeon}\nout\t{out}\ndaggerfall\t{DAGGERFALL}\nsize\t{WIDTH}\t{HEIGHT}\nvfov\t{VERTICAL_FOV}\n")
        # The first viewpoint must be the entrance: the collision flood fill starts there.
        # The flood's position key rounds to even, so a start on a cell center (8 mod 16) merges neighboring cells.
        if flood:
            f.write(f"flood\t{views[0]['x'] + 4}\t{views[0]['y'] + 4}\t{views[0]['floor']}\n")
        for v in views:
            f.write(f"view\t{v['id']}\t{v['x']}\t{v['y']}\t{v['floor'] + eye}\t{v['yaw']}\t{v['pitch']}\n")
    result = os.path.join(out, "df_probes.txt")
    if os.path.exists(result):
        os.remove(result)
    code = subprocess.run([sys.executable, QUIET, "--timeout", str(timeout), "--", exe, "-dfcapture", job,
                           "-screen-fullscreen", "0", "-screen-width", str(WIDTH), "-screen-height", str(HEIGHT),
                           "-logFile", os.path.join(out, "df_player.log")]).returncode
    print("Daggerfall capture exit code:", code)
    return parse_probes(result, "PROBE")


def capture_doom(views, out, eye, wad, timeout, scale):
    lumps = os.path.join(out, "doom_views")
    os.makedirs(lumps, exist_ok=True)
    with open(os.path.join(lumps, "DFVIEWS"), "w", newline="\n") as f:
        for v in views:  # viewpoints are in Daggerfall units; the map is at world scale
            f.write(f"{v['id']} {v['x'] * scale} {v['y'] * scale} {(v['floor'] + eye) * scale} {v['yaw']} {v['pitch']}\n")
    # Console waits only delay the rest of one command string, so each step is an alias that calls the next.
    with open(os.path.join(out, "doom_capture.cfg"), "w", newline="\n") as f:
        for i, v in enumerate(views):
            shot = os.path.join(out, v["id"] + ".doom.png").replace("\\", "/")
            f.write(f'alias dfstep{i} "netevent dfview {i}; wait 6; screenshot \\"{shot}\\"; wait 6; dfstep{i + 1}"\n')
        f.write(f'alias dfstep{len(views)} "quit"\nalias dfgo "vid_setsize {WIDTH} {HEIGHT}; wait 35; dfstep0"\n'
                # Aliases are queued during startup, so the first call must also wait until the game is running.
                'wait 105; dfgo\n')
    # A private config fixes the window size and leaves the owner's UZDoom settings alone.
    with open(os.path.join(out, "doom.ini"), "w", newline="\n") as f:
        f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n"
                f"vid_defwidth={WIDTH}\nvid_defheight={HEIGHT}\nwin_w={WIDTH}\nwin_h={HEIGHT}\nvid_scalefactor=1\n"
                f"win_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
    console = os.path.join(out, "doom_console.txt")
    with open(console, "w") as log:
        # A minimized UZDoom renders only 320x200, so it runs unminimized, off-screen, and without taking focus.
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = SW_SHOWNOACTIVATE
        process = subprocess.Popen([UZDOOM,
                                    "-iwad", IWAD, "-file", wad, os.path.join(HERE, "doom"), lumps,
                                    "-config", os.path.join(out, "doom.ini"), "-stdout", "-noactivate", "-nosound", "-nomonsters",
                                    "-skill", "3", "-width", str(WIDTH), "-height", str(HEIGHT),
                                    "+vid_fullscreen", "0", "+vid_scalefactor", "1", "+screenblocks", "12", "+crosshair", "0",
                                    "+screenshot_type", "png", "+show_messages", "0",
                                    "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                                    "+logfile", "doomcap", "+map", "MAP01", "+exec", "doom_capture.cfg"],
                                   cwd=out, startupinfo=startup, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = "timed out"
    print("UZDoom capture exit code:", code)
    return parse_probes(os.path.join(out, "log-doomcap.txt"), "DFPROBE")


def parse_probes(path, tag):
    found = {}
    if os.path.exists(path):
        for line in open(path, errors="replace"):
            match = re.match(rf"{tag} (\S+)((?: -?\d+\.\d+){{6}})", line.strip())
            if match:
                found[match.group(1)] = [float(v) for v in match.group(2).split()]
    return found


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: " + path)
    pos, idat, palette = 8, [], None
    while pos < len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + size]
        if kind == b"IHDR":
            w, h, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"IDAT":
            idat.append(body)
        pos += size + 12
    channels = {0: 1, 2: 3, 3: 1, 6: 4}.get(color)
    if depth != 8 or interlace or channels is None:
        raise ValueError(f"unsupported PNG format in {path}")
    raw, rows, previous, at = zlib.decompress(b"".join(idat)), [], bytearray(w * channels), 0
    for _ in range(h):
        kind, row = raw[at], bytearray(raw[at + 1:at + 1 + w * channels])
        at += 1 + w * channels
        for i in range(len(row)):
            a = row[i - channels] if i >= channels else 0
            b = previous[i]
            c = previous[i - channels] if i >= channels else 0
            if kind == 1: row[i] = (row[i] + a) & 255
            elif kind == 2: row[i] = (row[i] + b) & 255
            elif kind == 3: row[i] = (row[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        previous = row
        if color == 2: rows.append(bytes(row))
        elif color == 6: rows.append(b"".join(bytes(row[i:i + 3]) for i in range(0, len(row), 4)))
        elif color == 0: rows.append(b"".join(bytes((v, v, v)) for v in row))
        else: rows.append(b"".join(palette[v * 3:v * 3 + 3] for v in row))
    return w, h, rows


def write_png(path, w, rows):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    raw = b"".join(b"\0" + row for row in rows)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, len(rows), 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def side_by_side(left, right, out):
    lw, lh, lrows = read_png(left)
    rw, rh, rrows = read_png(right)
    if (lw, lh) != (rw, rh):
        raise ValueError(f"size mismatch: {lw}x{lh} and {rw}x{rh}")
    divider = b"\xff\xff\x00" * 6
    write_png(out, lw + rw + 6, [a + divider + b for a, b in zip(lrows, rrows)])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--views", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--eye", type=float, default=48, help="eye height above the floor, in map units")
    parser.add_argument("--exe", default=CAPTURE_EXE)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-df", action="store_true", help="reuse existing Daggerfall captures")
    parser.add_argument("--skip-doom", action="store_true", help="reuse existing UZDoom captures")
    parser.add_argument("--dungeon", default="Privateer's Hold")
    parser.add_argument("--no-flood", action="store_true", help="capture views only")
    parser.add_argument("--uzdoom", help="UZDoom executable to use")
    parser.add_argument("--world-scale", type=float, default=0.75, help="scale the map was converted at")
    args = parser.parse_args()
    if args.uzdoom:
        global UZDOOM
        UZDOOM = args.uzdoom

    out = os.path.abspath(args.out)
    if (os.path.normcase(out) + os.sep).startswith(os.path.normcase(REPO) + os.sep):
        sys.exit("--out must be outside the repository: captures are derived from game data")
    os.makedirs(out, exist_ok=True)
    views = read_views(args.views)

    df = parse_probes(os.path.join(out, "df_probes.txt"), "PROBE") if args.skip_df else \
        capture_daggerfall(views, out, args.eye, os.path.abspath(args.exe), args.timeout, args.dungeon, not args.no_flood)
    doom = parse_probes(os.path.join(out, "log-doomcap.txt"), "DFPROBE") if args.skip_doom else \
        capture_doom(views, out, args.eye, os.path.abspath(args.map), args.timeout, args.world_scale)
    # Probes are compared in Daggerfall units. A negative distance means the ray hit nothing.
    doom = {k: [d / args.world_scale if d >= 0 else d for d in p] for k, p in doom.items()}

    cards, failures = [], 0
    with open(os.path.join(out, "probes.csv"), "w", newline="") as f:
        table = csv.writer(f)
        table.writerow(["id", "kind"] + [f"{n}_{e}" for n in PROBES for e in ("df", "doom")] + ["mismatches"])
        for v in views:
            a, b = df.get(v["id"]), doom.get(v["id"])
            bad = [n for n, p, q in zip(PROBES, a or [], b or []) if (p < 0) != (q < 0) or abs(p - q) > MISMATCH]
            table.writerow([v["id"], v["kind"]] + [x for i in range(6) for x in (a[i] if a else "", b[i] if b else "")]
                           + [" ".join(bad) if a and b else "missing probe"])
            left, right, side = (os.path.join(out, v["id"] + s) for s in (".df.png", ".doom.png", ".side.png"))
            status = ""
            try:
                side_by_side(left, right, side)
            except (OSError, ValueError) as error:
                status, failures = f"No side-by-side: {error}", failures + 1
            print(f"{v['id']}: df={a} doom={b} mismatch={bad} {status}")
            caption = f"{v['id']} ({v['kind']}) at {v['x']:g}, {v['y']:g}, floor {v['floor']:g}, yaw {v['yaw']:g}. {v['note']}"
            body = f"<p>{html.escape(status)}</p>" if status else f'<img src="{html.escape(v["id"])}.side.png" loading="lazy">'
            cards.append(f"<h2>{html.escape(caption)}</h2><p>Mismatched probes: {html.escape(', '.join(bad) or 'none')}</p>{body}")
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset=utf-8><title>Dungeon comparison</title>"
                "<style>body{background:#222;color:#eee;font:15px sans-serif}img{max-width:100%}</style>"
                "<h1>Daggerfall Unity (left) and UZDoom (right)</h1>" + "".join(cards))
    print(f"Wrote {len(views) - failures} of {len(views)} comparisons to {out}")
    return 1 if failures or len(df) < len(views) or len(doom) < len(views) else 0


if __name__ == "__main__":
    sys.exit(main())
