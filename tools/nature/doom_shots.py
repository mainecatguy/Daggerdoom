"""Doom side of the nature comparison: for each map pixel, warps to tile (16, 64) of it facing east (as
DoomerfallNatureDumpTest stands in Daggerfall Unity), dumps the pixel's layout with dd_nature_dump, and takes a
screenshot. Then leaves and comes back to the first pixel and dumps it again, to show the layout does not change.

    python tools/nature/doom_shots.py --exe <uzdoom.exe> --data <make_data.py output> --out <dir> 122 257 227 477 ...
"""
import argparse
import os
import subprocess
from pathlib import Path

IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
ARENA2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-nature\Release\uzdoom.exe")
    ap.add_argument("--data", default=r"D:\dev\DoomDaggerfall-build\nature-data")
    ap.add_argument("--out", default=r"D:\dev\DoomDaggerfall-build\nature-tests\doom")
    ap.add_argument("pixels", nargs="+", type=int)
    a = ap.parse_args()
    out, data = Path(a.out), Path(a.data)
    out.mkdir(parents=True, exist_ok=True)
    pairs = list(zip(a.pixels[0::2], a.pixels[1::2]))
    lines = ["wait 175", "turn180", "wait 35"]
    for mx, my in pairs + [pairs[0]]:
        gx, gy = mx * 128 + 16, (499 - my) * 128 + 64
        lines += [f'dd_tm_warp "{gx} {gy}"', "wait 350"]
        name = f"{mx}_{my}" + ("_again" if any(f"doom_{mx}_{my}.txt" in l for l in lines) else "")
        lines += [f'dd_nature_dump {mx} {my} "{out / ("doom_" + name + ".txt")}"', "screenshot", "wait 35"]
    lines.append("quit")
    script = out / "shots.cfg"
    script.write_text("; ".join(lines).replace("\\", "/") + "\n")	# one line: waits only hold within one command line
    for old in out.glob("doom_*.txt"):
        old.unlink()
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    game = [a.exe, "-iwad", IWAD, "-file", str(data / "ddruntime.pk3"), str(data / "overworld.pk3"), "-config", str(out / "test.ini"),
            "-nosound", "-noautoload", "-skill", "3", "-width", "1280", "-height", "720", "-ddtowncache", str(cache),
            "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ARENA2, "+logfile", "log.txt", "+dd_debugmessages", "1",
            "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
            "+screenshot_dir", str(out), "+map", "DDOVER01", "+exec", str(script)]
    subprocess.run(["python", QUIET, "--cwd", str(out), "--timeout", str(60 + 15 * len(pairs)), "--", *game])


if __name__ == "__main__":
    main()
