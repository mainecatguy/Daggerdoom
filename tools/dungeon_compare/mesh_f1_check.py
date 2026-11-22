"""Checks F1 on the Daggerfall-layer map and on stock DOOM.WAD E1M1, using a real key event and no window focus.

Usage: python tools/dungeon_compare/mesh_f1_check.py --map <map.wad> --mesh <map_mesh.pk3> --out <dir outside the repo>
Pass: on MAP01 F1 flips the view and opens no menu. On E1M1 there is no layer, F1 opens the help menu, and the game keeps running.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import OFFSCREEN, SW_SHOWNOACTIVATE
from mesh_compare import UZDOOM

WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"


def run(out, name, iwad, files, level, timeout=90):
    cfg = ('alias s5 "dfmesh_status; quit"\n'
           'alias s4 "closemenu; wait 10; s5"\n'
           'alias s3 "dfmesh_status; wait 5; s4"\n'
           'alias s2 "dfmesh_pressf1; wait 10; s3"\n'
           'alias s1 "dfmesh_status; wait 5; s2"\n'
           'wait 140; s1\n')
    with open(os.path.join(out, name + ".cfg"), "w", newline="\n") as f:
        f.write(cfg)
    ini = os.path.join(out, name + ".ini")
    with open(ini, "w", newline="\n") as f:
        f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nwin_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
    log = os.path.join(out, f"log-{name}.txt")
    if os.path.exists(log):
        os.remove(log)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWNOACTIVATE
    command = [UZDOOM, "-iwad", os.path.join(WADS, iwad)] + (["-file"] + files if files else []) + [
        "-config", ini, "-stdout", "-noactivate", "-nosound", "-skill", "3", "-width", "640", "-height", "480",
        "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
        "+logfile", name, "+map", level, "+exec", name + ".cfg"]
    with open(os.path.join(out, name + ".console.txt"), "w") as console:
        process = subprocess.Popen(command, cwd=out, startupinfo=startup, stdout=console, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = "timed out"
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    states = [dict(map=m, layer=int(l), view=int(v), menu=int(u), time=int(t)) for m, l, v, u, t in
              re.findall(r"DFSTATUS map=(\S+) layer=(\d) view=(\d) menu=(\d) time=(\d+)", text)]
    print(name, "exit", code, states)
    return code, states


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", required=True)
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    code, s = run(out, "f1_layer", "DOOM2.WAD", [os.path.abspath(args.map), os.path.abspath(args.mesh)], "MAP01")
    layer_ok = code == 0 and len(s) == 3 and s[0]["layer"] == 1 and s[1]["view"] != s[0]["view"] and s[1]["menu"] == 0
    code, s = run(out, "f1_e1m1", "DOOM.WAD", [], "E1M1")
    doom_ok = code == 0 and len(s) == 3 and all(x["layer"] == 0 and x["map"] == "E1M1" for x in s) \
        and s[0]["menu"] == 0 and s[1]["menu"] == 1 and s[2]["menu"] == 0 and s[0]["time"] > 0 and s[2]["time"] > s[0]["time"]
    print("Daggerfall-layer F1:", "PASS" if layer_ok else "FAIL")
    print("E1M1 no layer, normal F1 help menu, keeps running:", "PASS" if doom_ok else "FAIL")
    return 0 if layer_ok and doom_ok else 1


if __name__ == "__main__":
    sys.exit(main())
