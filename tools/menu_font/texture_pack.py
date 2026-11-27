"""Installs or removes a sample Daggerfall Unity "texture pack for text" in a demo's Daggerfall Unity copy.

usage: texture_pack.py install <demo folder> <font.ttf|otf>   |   texture_pack.py remove <demo folder>
install puts the font in StreamingAssets/Fonts as FONT0003-SDF (Daggerfall Unity's own font replacement for its
default font) and a 4x, blue-tinted GNRC01I0.IMG.png in StreamingAssets/Textures/Img (an image texture pack's larger
copy of the merchant Talk / Sell popup), so both replacements are easy to see in a render. Nothing here is committed.
"""
import shutil
import struct
import sys
from pathlib import Path

from PIL import Image

ARENA2 = Path(r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2")


def streaming(demo):
    return Path(demo) / "dfu" / "DaggerfallUnity_Data" / "StreamingAssets"


def hd_popup(out):
    data = (ARENA2 / "GNRC01I0.IMG").read_bytes()
    w, h = struct.unpack("<hh", data[4:8])
    pal = (ARENA2 / "ART_PAL.COL").read_bytes()[8:]
    image = Image.new("RGB", (w, h))
    image.putdata([(pal[p * 3] // 2, pal[p * 3 + 1] // 2, min(255, pal[p * 3 + 2] + 80)) for p in data[12:12 + w * h]])
    image.resize((w * 4, h * 4), Image.NEAREST).save(out)


def main():
    action, demo = sys.argv[1], sys.argv[2]
    fonts, img = streaming(demo) / "Fonts", streaming(demo) / "Textures" / "Img"
    for old in list(fonts.glob("FONT0003-SDF.*")) + [img / "GNRC01I0.IMG.png"]:
        if old.suffix in (".ttf", ".otf", ".png") and old.exists():
            old.unlink()
    if action == "install":
        font = Path(sys.argv[3])
        fonts.mkdir(parents=True, exist_ok=True)
        img.mkdir(parents=True, exist_ok=True)
        shutil.copy2(font, fonts / ("FONT0003-SDF" + font.suffix.lower()))
        hd_popup(img / "GNRC01I0.IMG.png")
    print(action, "done:", fonts, img)


if __name__ == "__main__":
    main()
