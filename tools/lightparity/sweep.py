"""Dungeon light sweep: runs tools/visual_parity/scenes.py once per Doom setting against the same Daggerfall Unity
shots, and prints each spot's mean brightness side by side.

    python tools/lightparity/sweep.py --play <play folder> --df-shots <folder with s1_*.df.png> --out <folder> \
        --set "dd_dungeon_light=64" --set "dd_dungeon_light=48 dd_light_range=0.5"

Each --set is one run; its cvars go to UZDoom as +name value. Output stays outside the repository.
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENES = HERE.parent / "visual_parity" / "scenes.py"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--play", required=True, type=Path)
    ap.add_argument("--df-shots", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--set", action="append", required=True, help='space-separated name=value cvars for one run')
    args = ap.parse_args()
    env = dict(os.environ, VP_PLAY=str(args.play))
    table = {}
    for setting in args.set:
        pairs = [kv.split("=", 1) for kv in setting.split()]
        tag = "_".join(f"{k.replace('dd_', '')}{v}" for k, v in pairs)
        out = args.out / tag
        out.mkdir(parents=True, exist_ok=True)
        for f in args.df_shots.glob("*.df.png"):
            shutil.copy(f, out / f.name)
        cmd = [sys.executable, str(SCENES), "--out", str(out), "--skip-df"]
        for k, v in pairs:
            cmd += [f"--uz-arg=+{k}", f"--uz-arg={v}"]
        print("run", tag, flush=True)
        code = subprocess.call(cmd, env=env)
        print("exit", code, flush=True)
        if (out / "scenes.csv").exists():
            for row in csv.DictReader(open(out / "scenes.csv")):
                table.setdefault(row["id"], {"dfu": row["brightness_dfu"]})[tag] = row["brightness_doomerfall"]
    tags = [t for t in dict.fromkeys(k for r in table.values() for k in r) if t != "dfu"]
    print("id\tdfu\t" + "\t".join(tags))
    for sid, r in sorted(table.items()):
        print(sid + "\t" + r["dfu"] + "\t" + "\t".join(r.get(t, "") for t in tags))
    with open(args.out / "sweep.tsv", "a") as f:
        f.write("id\tdfu\t" + "\t".join(tags) + "\n")
        for sid, r in sorted(table.items()):
            f.write(sid + "\t" + r["dfu"] + "\t" + "\t".join(r.get(t, "") for t in tags) + "\n")


if __name__ == "__main__":
    sys.exit(main())
