"""Builds review/dungeon-reentry: the fixed UZDoom, the demo data, and a play.bat that starts at Privateer's Hold."""
import shutil
import struct
import zipfile
import zlib
from pathlib import Path

SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\position-sync-10hz")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\dungeon-reentry")
BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-reentry\Release")
DLLS = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release")
GROUP = 7154

HANDLER = """version "4.14"
class DRStartAtDoor : StaticEventHandler
{
	bool placed;
	override void WorldTick()
	{
		if (placed || !players[0].mo) return;
		placed = true;
		if (!(level.MapName ~== "DDT07154") || level.maptime > 2) return;
		let p = players[0].mo;
		p.SetOrigin((%(x)s + (%(nx)s) * 64, %(y)s + (%(ny)s) * 64, %(z)s), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-(%(ny)s), -(%(nx)s));
	}
}
"""


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


REVIEW.mkdir(parents=True, exist_ok=True)
for name in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3", "doomerfall-launcher.exe"):
    if not (REVIEW / name).exists():
        shutil.copy2(SOURCE / name, REVIEW / name)
for name in ("town-cache", "converter", "dfu", "doomerfall"):
    if not (REVIEW / name).exists():
        shutil.copytree(SOURCE / name, REVIEW / name)

target = REVIEW / "uzdoom"
target.mkdir(exist_ok=True)
for item in BUILD.iterdir():
    if item.suffix.lower() in (".exe", ".pk3"):
        shutil.copy2(item, target / item.name)
    elif item.is_dir() and item.name in ("soundfonts", "fm_banks"):
        shutil.copytree(item, target / item.name, dirs_exist_ok=True)
for name in ("sndfile.dll", "soft_oal.dll"):
    shutil.copy2(DLLS / name, target / name)

doors = [l.split() for l in lumps(REVIEW / "town-cache" / f"T{GROUP:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
door = next(d for d in doors if d[0] == "1")
with zipfile.ZipFile(REVIEW / "start-at-door.pk3", "w") as z:
    z.writestr("zscript.txt", HANDLER % dict(x=door[3], y=door[4], z=door[5], nx=door[6], ny=door[7]))
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DRStartAtDoor" }\n')

bat = (SOURCE / "play.bat").read_text()
bat = bat.replace("rem Starts in Gothway Garden. Walk around, enter a building or Privateer's Hold with Use.",
                  "rem Starts facing the Privateer's Hold entrance in Gothway Garden. Press Use to enter, and repeat the trip as often as you like.")
bat = bat.replace('--mod "%HERE%doomerfall"', '--mod "%HERE%doomerfall" --mod "%HERE%start-at-door.pk3"')
(REVIEW / "play.bat").write_text(bat)
print("demo ready:", REVIEW / "play.bat", "door", door[3:8])
