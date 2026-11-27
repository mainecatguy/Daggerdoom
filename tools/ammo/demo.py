"""Builds the one-click demo folder review\\ammosizefix-demo from the tested review\\ammosizefix folder (run assemble
first). The play.bat is the ammoreload demo's, with this change's notes on top."""
import shutil
from pathlib import Path

SRC = Path(r"D:\dev\DoomDaggerfall-loop\review\ammosizefix")
DST = Path(r"D:\dev\DoomDaggerfall-loop\review\ammosizefix-demo")
TEMPLATE = Path(r"D:\dev\DoomDaggerfall-loop\review\ammoreload\play.bat")

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
    "rem THIS DEMO (ammo amounts are Doom's): Regular ammo pickups give stock Doom's amounts: clip 10, box of bullets 50,",
    "rem  shells 4, box of shells 20, rocket 1, box of rockets 5, cell 20, cell pack 100. A clip a former human drops gives 5",
    "rem  (any dropped pickup gives half, at least 1). Every tier gives the same: a Silver or Ebony clip is 10 bullets too.",
    "rem  Higher tiers are rarer, not smaller. Shop packs of every tier hold a Regular pack: 80 bullets, 20 shells,",
    "rem  8 rockets, 100 cells (the item info popup says \"One pack holds ...\").",
    "rem  Try: New Game, walk over ammo in Privateer's Hold, read the pickup message and the inventory count (I).",
]
body = lines[5:]  # Past the template's own "THIS DEMO" block (its lines 2-5).
assert body[0].startswith("rem Doomerfall:"), body[0]
(DST / "play.bat").write_text("\r\n".join(head + body) + "\r\n")
print("demo at", DST)
