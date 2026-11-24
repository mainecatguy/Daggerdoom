"""Side-by-side images: Daggerfall Unity capture (<id>.df.png from compare.py --lit) left, light_shots.py image right.

Usage: python pair_shots.py <compare dir> <light_shots dir> [<second light_shots dir>] <out dir>
With two light_shots dirs the output has three panels: Daggerfall Unity, the first (for example lights off), the second.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dungeon_compare"))
from compare import read_png, write_png  # noqa: E402

df_dir, shot_dirs, out = sys.argv[1], sys.argv[2:-1], sys.argv[-1]
os.makedirs(out, exist_ok=True)
divider = b"\xff\xff\x00" * 6
for name in sorted(os.listdir(df_dir)):
    if not name.endswith(".df.png"):
        continue
    view = name[:-7]
    panels = [os.path.join(df_dir, name)] + [os.path.join(d, view + ".png") for d in shot_dirs]
    if not all(os.path.exists(p) for p in panels):
        continue
    images = [read_png(p) for p in panels]
    rows = [divider.join(img[2][y] for img in images) for y in range(min(img[1] for img in images))]
    write_png(os.path.join(out, view + ".side.png"), sum(img[0] for img in images) + 6 * (len(images) - 1), rows)
    print("wrote", view)
