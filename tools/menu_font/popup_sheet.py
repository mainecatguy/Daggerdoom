"""Crops the NPC popups out of Daggerfall Unity's saved renders (dfu-<name>.png from -dfmenutexttest) into one sheet.

usage: popup_sheet.py <test folder> [<test folder> ...] <out.png>
Each folder becomes a column, each popup a row: merchant, guild, repair, coven.
"""
import sys
from pathlib import Path

from PIL import Image

NAMES = ("merchant", "guild", "guildmember", "repair", "coven")


def crop(path):
    image = Image.open(path) if path.exists() else Image.new("RGB", (1252, 721))  # black cell: that popup did not open
    w, h = image.size
    scale = min(w / 320, h / 200)
    left, top = (w - 320 * scale) / 2, (h - 200 * scale) / 2
    # The popups are 130 wide and up to 51 tall, around native x 95-225, y 74-130.
    box = (int(left + 90 * scale), int(top + 72 * scale), int(left + 230 * scale), int(top + 132 * scale))
    return image.crop(box)


def main():
    folders, out = [Path(p) for p in sys.argv[1:-1]], sys.argv[-1]
    cells = [[crop(f / ("dfu-" + n + ".png")) for n in NAMES] for f in folders]
    cw, ch = cells[0][0].size
    sheet = Image.new("RGB", (cw * len(folders), ch * len(NAMES)))
    for x, column in enumerate(cells):
        for y, cell in enumerate(column):
            sheet.paste(cell, (x * cw, y * ch))
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
