"""Side-by-side of Doom's screenshot and Daggerfall Unity's own render of the same menu (from -dfmenutexttest <out>),
with the mean pixel difference, to show Doom draws Daggerfall's text 1:1.

usage: compare.py <run folder> <out folder> name=DoomShot.png[:x0,y0,x1,y1] ...
Boxes are native 320x200 units (default: the whole menu). Each sheet is: Doom (left) | Daggerfall Unity (right), 3x nearest.
The top 80 screen rows are left out of the difference: Doom's own "captured screenshot" messages draw there.
"""
import sys
from pathlib import Path
from PIL import Image, ImageChops, ImageStat


def box_px(size, box):
    w, h = size
    s = min(w / 320, h / 200)
    ox, oy = (w - 320 * s) / 2, (h - 200 * s) / 2
    x0, y0, x1, y1 = box
    return int(ox + x0 * s), int(oy + y0 * s), int(ox + x1 * s), int(oy + y1 * s)


def main():
    run, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for spec in sys.argv[3:]:
        name, rest = spec.split("=", 1)
        shot, _, box = rest.partition(":")
        doom = Image.open(run / "shots" / shot).convert("RGB")
        dfu = Image.open(run / ("dfu-" + name + ".png")).convert("RGB")
        if doom.size != dfu.size:
            print(name, "size differs", doom.size, dfu.size)
            continue
        whole = (0, 80, doom.width, doom.height)
        diff = ImageStat.Stat(ImageChops.difference(doom.crop(whole), dfu.crop(whole))).mean
        px = box_px(doom.size, [float(v) for v in box.split(",")]) if box else (0, 0, doom.width, doom.height)
        a, b = doom.crop(px), dfu.crop(px)
        zoom = 3 if box else 1
        a, b = (c.resize((c.width * zoom, c.height * zoom), Image.NEAREST) for c in (a, b))
        sheet = Image.new("RGB", (a.width * 2 + 8, a.height), (255, 0, 255))
        sheet.paste(a, (0, 0))
        sheet.paste(b, (a.width + 8, 0))
        sheet.save(out / (name + "-doom-vs-dfu.png"))
        print(f"{name}: {doom.width}x{doom.height}, mean abs difference per channel {sum(diff) / 3:.2f} of 255")


if __name__ == "__main__":
    main()
