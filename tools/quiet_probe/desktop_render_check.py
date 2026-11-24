"""Compares UZDoom's rendering on the user's desktop (minimized) with a private desktop.

Usage: python desktop_render_check.py UZDOOM_EXE WORK_DIR [PROPOSED_QUIET_RUN_PY]
Runs DOOM.WAD E1M1 twice through quiet_run.py, once as before (minimized, -noactivate) and once with --desktop,
takes a screenshot after a fixed number of tics, and compares the two images pixel by pixel. Also reports the
frame rate UZDoom logs (vid_fps) and the console log's map line.
"""
import struct
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUIET = str(HERE.parent.parent / "scripts" / "overnight" / "quiet_run.py")
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"


def png_pixels(path):
    """Decodes an 8-bit RGB or RGBA PNG (what UZDoom writes) into (width, height, rows of bytes)."""
    data = path.read_bytes()
    pos, chunks = 8, {}
    idat = b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            chunks["IHDR"] = body
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    width, height, depth, color = struct.unpack(">IIBB", chunks["IHDR"][:10])
    channels = {2: 3, 6: 4}[color]
    raw = zlib.decompress(idat)
    stride = width * channels
    rows, previous = [], bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            left = line[x - channels] if x >= channels else 0
            up = previous[x]
            corner = previous[x - channels] if x >= channels else 0
            if kind == 1:
                line[x] = (line[x] + left) & 255
            elif kind == 2:
                line[x] = (line[x] + up) & 255
            elif kind == 3:
                line[x] = (line[x] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[x] = (line[x] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
        rows.append(bytes(line))
        previous = line
    return width, height, channels, rows


def run(exe, work, name, desktop, quiet=QUIET):
    folder = work / name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    # Command-line "+wait" does not delay later "+" commands, so the timed steps run from a script.
    # Same pattern as tools/dungeon_converter/texture_shot.py: waits chained on one line through an alias.
    shot = str(folder / "shot.png").replace("\\", "/")
    (folder / "steps.cfg").write_text(f'alias ddshot "screenshot \\"{shot}\\"; wait 35; quit"\nwait 105; ddshot\n')
    command = [sys.executable, quiet, "--timeout", "40", "--cwd", str(folder)] + (["--desktop"] if desktop else []) + [
        "--", exe, "-iwad", IWAD, "-config", str(folder / "render.ini"), "-noactivate", "-nosound", "-skill", "3",
        "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
        "-width", "640", "-height", "400", "+vid_fullscreen", "0", "+vid_scalefactor", "1", "+screenshot_type",
        "png", "+show_messages", "0", "+logfile", "render", "+wipetype", "0", "+map", "E1M1",
        "+exec", str(folder / "steps.cfg")]
    code = subprocess.call(command)
    shots = sorted(folder.glob("*.png"))
    log = (folder / "log-render.txt").read_text(errors="replace") if (folder / "log-render.txt").exists() else ""
    return code, shots, log


def main():
    exe, work = sys.argv[1], Path(sys.argv[2]).resolve()
    # Optional third argument: a quiet_run.py whose default (private desktop) run is compared with --user-desktop
    # style runs of the current quiet_run.py.
    private_quiet = sys.argv[3] if len(sys.argv) > 3 else QUIET
    results = {"user": run(exe, work, "user", False),
               "private": run(exe, work, "private", private_quiet == QUIET, private_quiet)}
    for name, (code, shots, log) in results.items():
        print(f"{name}: exit {code}, screenshots {[s.name for s in shots]}, E1M1 in log {'E1M1' in log}")
    if not all(r[1] for r in results.values()):
        print("FAIL: a run made no screenshot")
        return 1
    a, b = (png_pixels(results[n][1][0]) for n in ("user", "private"))
    if a[:3] != b[:3]:
        print(f"FAIL: sizes differ {a[:3]} vs {b[:3]}")
        return 1
    differing = sum(1 for ra, rb in zip(a[3], b[3]) for i in range(0, len(ra), a[2]) if ra[i:i + 3] != rb[i:i + 3])
    blank = all(len(set(row)) <= 1 for row in b[3])
    print(f"size {a[0]}x{a[1]}, differing pixels {differing} of {a[0] * a[1]}, private image blank {blank}")
    return 0 if differing == 0 and not blank else 1


if __name__ == "__main__":
    sys.exit(main())
