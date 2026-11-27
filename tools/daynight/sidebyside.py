"""Side-by-side sheet of Daggerfall's camera and Doom's screenshot for each paired step.

usage: sidebyside.py OUT.png DFSHOT DOOMSHOT [DFSHOT DOOMSHOT ...]
Each pair becomes one row, Daggerfall left, Doom right, both scaled to 480 px high... width 640.
"""
import sys
from PIL import Image

W, H = 640, 360


def fit(path):
    im = Image.open(path).convert("RGB")
    return im.resize((W, int(im.height * W / im.width))).crop((0, 0, W, H)) if im.width / im.height > W / H - 0.01 else \
        im.resize((int(im.width * H / im.height), H)).crop((0, 0, W, H))


def main():
    out, paths = sys.argv[1], sys.argv[2:]
    rows = len(paths) // 2
    sheet = Image.new("RGB", (2 * W, rows * H))
    for i in range(rows):
        sheet.paste(fit(paths[2 * i]), (0, i * H))
        sheet.paste(fit(paths[2 * i + 1]), (W, i * H))
    sheet.save(out)


if __name__ == "__main__":
    main()
