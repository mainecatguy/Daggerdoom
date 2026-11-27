"""Builds this checkout's converter and the data the nature flats need: ddruntime.pk3 (nature textures and the
DFNatureFlat class) and overworld.pk3 (with the DDNATURE lump). Output stays outside the repository.

    python tools/nature/make_data.py [--out D:/dev/DoomDaggerfall-build/nature-data]
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"


def run(cmd):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-build\nature-data")
    ap.add_argument("--start-tile", default="26592,36608")
    a = ap.parse_args()
    out = Path(a.out)
    converter = out / "converter"
    run(["dotnet", "build", REPO / "tools" / "dungeon_converter" / "DungeonConverter.csproj", "-c", "Release", "-v", "q", "-o", converter,
         f"-p:DungeonConverterBuildRoot={out / 'converter-build'}\\"])
    exe = converter / "DungeonConverter.exe"
    run([exe, "--runtime-assets", "--out", out / "ddruntime.pk3", "--arena2", ARENA2])
    run([exe, "--world", "--out", out / "world", "--arena2", ARENA2])
    run([sys.executable, REPO / "tools" / "overworld" / "gen_overworld.py", "--out", out / "overworld.pk3", "--world-dir", out / "world",
         "--ground-from", out / "ddruntime.pk3", "--start-tile", a.start_tile, "--start-angle", "180"])


if __name__ == "__main__":
    main()
