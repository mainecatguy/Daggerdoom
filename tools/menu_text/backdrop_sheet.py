"""Contact sheet for a menu_text.py --backdrop run: for each window in <run>/dfu-steps.txt, Doom's screenshot taken
1-2 s after Daggerfall's capture, beside Daggerfall's own render (alpha shown over a checkerboard).

usage: backdrop_sheet.py <run folder> <out png> [--scale 0.3]
"""
import argparse
import datetime
import re
from pathlib import Path

from PIL import Image, ImageDraw


def checker(size, cell=24):
    im = Image.new("RGB", size, (90, 90, 90))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], cell):
        for x in range((y // cell % 2) * cell, size[0], cell * 2):
            d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(160, 160, 160))
    return im


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("out")
    p.add_argument("--scale", type=float, default=0.3)
    a = p.parse_args()
    run = Path(a.run)
    shots = {}
    for f in (run / "shots").glob("Screenshot_Doom_*.png"):
        m = re.search(r"_(\d{8})_(\d{6})", f.name)
        shots[datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").time()] = f
    rows = []
    for line in (run / "dfu-steps.txt").read_text().splitlines():
        m = re.match(r"(\S+) (\d\d):(\d\d):(\d\d)\.\d+ ", line)
        if not m:
            continue
        name, h, mi, s = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        want = datetime.time(h, mi, min(59, s + 2))
        doom = shots.get(want) or shots.get(datetime.time(h, mi, min(59, s + 1)))
        dfu = run / ("dfu-" + name + ".png")
        if doom and dfu.exists():
            rows.append((name, Image.open(doom).convert("RGB"), Image.open(dfu).convert("RGBA")))
    if not rows:
        raise SystemExit("no matching screenshots")
    w, h = (int(v * a.scale) for v in rows[0][1].size)
    sheet = Image.new("RGB", (w * 2 + 30, (h + 24) * len(rows)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, (name, doom, dfu) in enumerate(rows):
        y = i * (h + 24)
        d.text((4, y + 4), name + ": Doom (left), Daggerfall's render with alpha over a checkerboard (right)", fill=(255, 255, 255))
        sheet.paste(doom.resize((w, h), Image.LANCZOS), (0, y + 20))
        back = checker(dfu.size)
        back.paste(dfu, (0, 0), dfu)
        sheet.paste(back.resize((w, h), Image.LANCZOS), (w + 30, y + 20))
    sheet.save(a.out)
    print("wrote", a.out, len(rows), "rows")


if __name__ == "__main__":
    main()
