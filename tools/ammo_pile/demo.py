"""Builds the one-click demo folder review\\ammo-pile-demo from the tested review\\ammo-pile folder (run assemble
first). The play.bat is the ammosizefix demo's, with this change's notes on top."""
import shutil
from pathlib import Path

SRC = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-pile")
DST = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-pile-demo")
TEMPLATE = Path(r"D:\dev\DoomDaggerfall-loop\review\ammosizefix-demo\play.bat")

DST.mkdir(parents=True, exist_ok=True)
for name in ("uzdoom", "dfu", "data"):
    if (DST / name).exists():
        shutil.rmtree(DST / name)
    shutil.copytree(SRC / name, DST / name, ignore=shutil.ignore_patterns("*.ini", "PortableAppdata"))
for name in ("doomerfall-launcher.exe", "dfitems.pk3", "doomerfall.pk3"):
    shutil.copy2(SRC / name, DST / name)
(DST / "run" / "saves").mkdir(parents=True, exist_ok=True)

lines = TEMPLATE.read_text().splitlines()
head = [
    "@echo off",
    "rem THIS DEMO (dropped ammo looks like ammo): drop ammo from the inventory (I) and close it. A pile of only bullets",
    "rem  shows Doom's clip, shells a shell, rockets a rocket, cells a cell; a box's worth (50 bullets, 20 shells, 5 rockets,",
    "rem  100 cells) shows the box. A pile with anything else in it shows the loot sack. Put a ring into a bullet pile and",
    "rem  it turns into a sack; take it out and it is bullets again. Leave and come back, or save and load: same piles.",
    "rem  Try: New Game, pick up some ammo in Privateer's Hold, press I and drop part of a stack.",
]
body = lines[next(i for i, l in enumerate(lines) if l.startswith("rem Doomerfall:")):]  # Past the template's own "THIS DEMO" block.
assert body[0].startswith("rem Doomerfall:"), body[0]
(DST / "play.bat").write_text("\r\n".join(head + body) + "\r\n")
print("demo at", DST)
