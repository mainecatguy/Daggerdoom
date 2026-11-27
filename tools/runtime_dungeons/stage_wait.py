"""Stages a play folder with no prebuilt dungeon, so Privateer's Hold is converted at runtime like every other dungeon.

Usage: stage_wait.py --from INSTALL --to DIR
Copies an installed play folder (launcher, uzdoom, dfu, data) and replaces privateershold.wad, _mesh.pk3 and _doors.pk3
with empty packages, with an empty town cache. tools/new_game/run_new_game.py and tools/plain_load/run_plain_load.py
then show that New Game and a plain load into an unconverted dungeon wait for its conversion (--review / --root DIR).
"""
import argparse
import shutil
import struct
import zipfile
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path, required=True)
    ap.add_argument("--to", type=Path, required=True)
    a = ap.parse_args()
    skip = shutil.ignore_patterns("run", "test-run", "evidence", "cache", "privateershold*", "PortableAppdata")
    shutil.copytree(a.src, a.to, ignore=skip, dirs_exist_ok=True)
    data = a.to / "data"
    shutil.rmtree(data / "cache", ignore_errors=True)
    (data / "cache").mkdir()
    (data / "privateershold.wad").write_bytes(b"PWAD" + struct.pack("<ii", 0, 12))  # a valid WAD with no lumps
    for name in ("privateershold_mesh.pk3", "privateershold_doors.pk3"):
        with zipfile.ZipFile(data / name, "w") as z:
            z.writestr("dd_empty.txt", "No prebuilt dungeon: every dungeon converts at runtime.\n")
    print("staged", a.to)


if __name__ == "__main__":
    main()
