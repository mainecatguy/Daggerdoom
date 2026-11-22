"""Convert a dungeon by name and test it in UZDoom.

Usage: python tools/dungeon_converter/run.py "Privateer's Hold" --out <dir outside the repo> [--timeout 420]
Writes <slug>.wad, <slug>.points.txt, <slug>.stats.txt, and <slug>.report.txt.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("dungeon")
parser.add_argument("--out", required=True)
parser.add_argument("--timeout", type=int, default=420)
args = parser.parse_args()
out = os.path.abspath(args.out)
repo = os.path.normcase(os.path.dirname(os.path.dirname(HERE)))
if (os.path.normcase(out) + os.sep).startswith(repo + os.sep):
    sys.exit("--out must be outside the repository: generated maps are derived from game data")
slug = "".join(c for c in args.dungeon if c.isalnum()).lower()
convert = subprocess.run(["dotnet", "run", "-c", "Release", "-v", "q", "--project", os.path.join(HERE, "DungeonConverter.csproj"),
                          "--", args.dungeon, "--out", out])
if convert.returncode:
    sys.exit(convert.returncode)
base = os.path.join(out, slug)
sys.exit(subprocess.run([sys.executable, os.path.join(HERE, "check_map.py"), base + ".wad", base + ".points.txt",
                         base + ".report.txt", "--timeout", str(args.timeout)]).returncode)
