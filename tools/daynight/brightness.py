"""Compares the brightness of Daggerfall's own camera with Doom's screenshot of the same moment.

usage: brightness.py DF_SHOTS DOOM_SHOTS DF_LOG HOLD
paired.py run --draw calls this. DF_SHOTS holds step<N>.png from -dfworldlookshots; Doom's screenshot for a step is
the latest one taken within the last HOLD seconds before Daggerfall's. Both games stand at the same place facing the
same way, but their scenes differ (field of view, trees, people), so only the average is compared: mean luma of the
ground band (below the horizon) and of the sky band. Ratio = Doom / Daggerfall; 1.0 means equally bright.
"""
import re
import sys
from pathlib import Path

from PIL import Image

GROUND = (0.52, 0.90)  # rows, as a fraction of the height; the horizon is the middle with pitch 0
SKY = (0.10, 0.42)


def luma(path, band):
    image = Image.open(path).convert("RGB").resize((320, 180))
    w, h = image.size
    pixels = list(image.crop((0, int(band[0] * h), w, int(band[1] * h))).getdata())
    return sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels) / len(pixels)


def compare(df_shots, doom_shots, df_log, hold):
    df_shots, doom_shots = Path(df_shots), Path(doom_shots)
    text = Path(df_log).read_text(errors="replace") if Path(df_log).exists() else ""
    labels = {int(n): f"{h}:00 {w} {s[:3]}".strip() for n, h, w, s in re.findall(r"worldlooktest: step (\d+) hour (\d+) weather (\w+)(?: season (\w+))?", text)}
    doom = sorted(doom_shots.glob("*.png"), key=lambda p: p.stat().st_mtime)
    rows = []
    for shot in sorted(df_shots.glob("step*.png"), key=lambda p: int(p.stem[4:])):
        n, t = int(shot.stem[4:]), shot.stat().st_mtime
        near = [p for p in doom if t - hold + 1.5 < p.stat().st_mtime <= t + 0.5]
        if not near:
            print(f"step {n}: no Doom screenshot near Daggerfall's")
            continue
        d = near[-1]
        rows.append((n, labels.get(n, "?"), luma(shot, GROUND), luma(d, GROUND), luma(shot, SKY), luma(d, SKY), d.name))
    print(f"{'step':>4} {'Daggerfall step':<16} {'ground DF':>9} {'Doom':>6} {'ratio':>6}   {'sky DF':>6} {'Doom':>6} {'ratio':>6}  Doom shot")
    for n, label, gf, gd, sf, sd, name in rows:
        print(f"{n:>4} {label:<16} {gf:9.1f} {gd:6.1f} {gd / max(gf, 0.1):6.2f}   {sf:6.1f} {sd:6.1f} {sd / max(sf, 0.1):6.2f}  {name}")
    return rows


if __name__ == "__main__":
    compare(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]))
