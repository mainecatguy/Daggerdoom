"""Marks where a Daggerfall Unity pixel dump's flats should stand on that pixel's DFU screenshot, to check the shot
against the layout. Red: as dumped. Blue: mirrored north/south about the player. Camera from the dump test: middle of
tile (16, 64), facing east, eye 1.9 m above the ground, vertical FOV 65 degrees.

    python tools/nature/project_flats.py <pixel_X_Y.txt> <shot_X_Y.png> <out.png> [--px 16.5 --py 64.5 --fov 65]
"""
import argparse
import math

from PIL import Image, ImageDraw

TILE = 6.4  # Daggerfall Unity metres per tile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("shot")
    ap.add_argument("out")
    ap.add_argument("--px", type=float, default=16.5)
    ap.add_argument("--py", type=float, default=64.5)
    ap.add_argument("--fov", type=float, default=65)
    ap.add_argument("--eye", type=float, default=1.9)
    a = ap.parse_args()
    lines = open(a.dump).read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("flats ")) + 1
    flats = [tuple(int(v) for v in l.split()) for l in lines[start:] if l.strip()]
    img = Image.open(a.shot).convert("RGB")
    w, h = img.size
    focal = (h / 2) / math.tan(math.radians(a.fov / 2))
    d = ImageDraw.Draw(img)
    for colour, mirror in (("red", False), ("blue", True)):
        for x, y, rec in flats:
            fy = 2 * a.py - y if mirror else y
            depth, left = (x - a.px) * TILE, (fy - a.py) * TILE  # east forward, north to the left
            if depth < 1 or depth > 60:
                continue
            sx, sy = w / 2 - focal * left / depth, h / 2 + focal * a.eye / depth
            if 0 <= sx < w and 0 <= sy < h:
                r = max(3, int(200 / depth))
                d.ellipse((sx - r, sy - r, sx + r, sy + r), outline=colour, width=3)
                if depth < 15:
                    d.text((sx + r, sy), f"{x},{y}:{rec}", fill=colour)
    img.resize((w // 2, h // 2)).save(a.out)


if __name__ == "__main__":
    main()
