"""Real autosaves through ZScript's Level.MakeAutoSave, with both real games.

Usage: run_indoor.py building|dungeon|early
building and dungeon take the real door first, then autosave inside. early autosaves on the second tic of the
map, before Daggerfall can save, which must hold the autosave until it can.
"""
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\synchronized-saving")
DATA = REVIEW.parent / "combined-bridge" / "data"
mode = sys.argv[1]
run = REVIEW / "test" / f"indoor-{mode}"
run.mkdir(parents=True, exist_ok=True)
harness = run / "harness.pk3"
group = 7154 if mode == "dungeon" else 9183  # Privateer's Hold is the converted dungeon.


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


if mode == "early":
    text = 'version "4.14"\nclass EarlySave : EventHandler\n{\n\toverride void WorldTick() { if (level.maptime == 2) { Console.Printf("EARLYSAVE"); level.MakeAutoSave(); } }\n}\n'
    handler = "EarlySave"
else:
    doors = [l.split() for l in lumps(DATA / "cache" / f"T{group:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
    if mode == "dungeon":
        door = next(d for d in doors if d[0] == "1")
    else:
        door = next(d for d in doors if d[0] == "0" and (DATA / "cache" / f"T{d[1]}.ddt").exists())
    text = (HERE.parent / "overworld" / "door_harness.zs").read_text()
    text = text.replace("@DOORS@", ", ".join(door[3:8])).replace("@EXITS@", "0, 0, 0, 0, 0").replace("@MODE@", "save")
    text = text.replace("EXITS.Size() >= FIELDS", "false")
    text = text.replace("if (inside || level.maptime < 4) break;", 'if (inside || level.maptime < 4 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;')
    handler = "DTHarness"
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", f'gameinfo {{ addeventhandlers = "{handler}" }}\n')

sys.exit(subprocess.call([sys.executable, str(HERE / "run_save.py"), f"indoor-{mode}", "--no-savetest", "--bundle", "auto00.zds", "--map", f"DDT{group:05d}",
                          "--mod", str(harness), "--extra-uz=+autosavecount", "--extra-uz=1", "--until", "autosave committed", "--timeout", "35"]))
