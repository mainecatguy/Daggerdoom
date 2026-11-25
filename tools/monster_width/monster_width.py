"""Monster width check: monsters are narrowed by 10.5/16 on Daggerfall maps and keep stock widths elsewhere.

Launches (each private, minimized, time limited; wrap the whole script in quiet_run.py):
  e1m1_stock / e1m1_drla   DOOM.WAD E1M1 with the Doomerfall mod (and DRLA): every monster must keep its stock radius.
  ph_stock / ph_drla       a converted Privateer's Hold (MAP01) with the mod (and DRLA): every monster must be narrowed.

Usage: python tools/monster_width/monster_width.py --exe <uzdoom.exe> --ph <dir with privateershold.wad, _mesh.pk3, _doors.pk3> --out <dir>
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = [os.path.join(MODS, n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
MOD = os.path.join(REPO, "mods", "doomerfall", "src")
HARNESS = os.path.join(HERE, "harness")
FATAL = ("VM execution aborted", "FatalError", "Execution could not continue")

ap = argparse.ArgumentParser()
ap.add_argument("--exe", required=True)
ap.add_argument("--ph", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)


def launch(name, iwad, files, mapname, limit=30):
    out = os.path.join(args.out, name + ".log")
    config = os.path.join(args.out, name + ".ini")
    with open(config, "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\n")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7
    with open(out, "w") as sink:
        p = subprocess.Popen([args.exe, "-iwad", os.path.join(WADS, iwad), "-file", *files, "-config", config, "-noactivate", "-nosound",
                              "-stdout", "-skill", "3", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0",
                              "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", mapname],
                             cwd=args.out, startupinfo=startup, stdout=sink, stderr=subprocess.STDOUT)
        started = time.time()
        while time.time() - started < limit and p.poll() is None:
            time.sleep(0.5)
            text = open(out, errors="replace").read()
            if "MWDONE" in text or any(b in text for b in FATAL):
                break
        if p.poll() is None:
            p.kill()
        p.wait()
    return open(out, errors="replace").read()


ph = [os.path.join(args.ph, "privateershold" + s) for s in (".wad", "_mesh.pk3", "_doors.pk3")]
cases = (("e1m1_stock", "DOOM.WAD", [MOD, HARNESS], "E1M1", False),
         ("e1m1_drla", "DOOM.WAD", [*DRLA, MOD, HARNESS], "E1M1", False),
         ("ph_stock", "DOOM2.WAD", [*ph, MOD, HARNESS], "MAP01", True),
         ("ph_drla", "DOOM2.WAD", [*DRLA, *ph, MOD, HARNESS], "MAP01", True))
failures = 0
for name, iwad, files, mapname, daggerfall in cases:
    text = launch(name, iwad, files, mapname)
    summary = next((l for l in text.splitlines() if l.startswith("MWSUMMARY")), "")
    f = dict(kv.split("=") for kv in summary.split()[1:]) if summary else {}
    narrow, stock, other = (int(f.get(k, -1)) for k in ("narrow", "stock", "other"))
    if daggerfall:
        ok = narrow > 0 and stock == 0 and other == 0
    else:
        ok = stock > 0 and narrow == 0 and other == 0
    ok = ok and not any(b in text for b in FATAL)
    failures += 0 if ok else 1
    classes = sorted({l.split()[1] for l in text.splitlines() if l.startswith("MW ")})
    print(f"{name}: {'PASS' if ok else 'FAIL'} {summary or 'no summary'} classes={','.join(classes[:12])}{'...' if len(classes) > 12 else ''}")
sys.exit(1 if failures else 0)
