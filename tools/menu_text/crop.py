"""Crops one native 320x200 region from a screenshot of a letterboxed Daggerfall menu and enlarges it with nearest
filtering, so text sharpness can be compared side by side.

usage: crop.py <out.png> <x0,y0,x1,y1 native> <zoom> <screenshot> [<screenshot> ...]   (several inputs: placed side by side)
"""
import sys
from PIL import Image


def crop(path, box, zoom):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = min(w / 320, h / 200)
    ox, oy = (w - 320 * s) / 2, (h - 200 * s) / 2
    x0, y0, x1, y1 = box
    c = im.crop((int(ox + x0 * s), int(oy + y0 * s), int(ox + x1 * s), int(oy + y1 * s)))
    return c.resize((c.width * zoom, c.height * zoom), Image.NEAREST)


def main():
    out, box, zoom = sys.argv[1], [float(v) for v in sys.argv[2].split(",")], int(sys.argv[3])
    parts = [crop(p, box, zoom) for p in sys.argv[4:]]
    sheet = Image.new("RGB", (sum(p.width for p in parts) + 8 * (len(parts) - 1), max(p.height for p in parts)), (255, 0, 255))
    x = 0
    for p in parts:
        sheet.paste(p, (x, 0))
        x += p.width + 8
    sheet.save(out)


if __name__ == "__main__":
    main()
