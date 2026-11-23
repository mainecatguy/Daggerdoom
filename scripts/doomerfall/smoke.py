"""Smoke test for the Doomerfall mod. Usage: smoke.py [--exe X] [--iwad X] [--timeout 30]
Runs DOOM.WAD E1M1 in three setups (mod only, DRLA set only, DRLA set + mod), each with a private
config and -stdout, fires both actions by netevent, and checks the log. Needs doomerfall.pk3 and doomerfall-smoke.pk3 (build_pk3.py [--smoke])."""
import threading, argparse, subprocess, sys, tempfile, pathlib, time, os
root = pathlib.Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-stitch\Release\uzdoom.exe")
ap.add_argument("--iwad", default=r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD")
ap.add_argument("--mods", default=r"D:\dev\DoomDaggerfall\GameMods")
ap.add_argument("--pk3", default=r"D:\dev\DoomDaggerfall-loop\review\doomerfall-mod\doomerfall.pk3")
ap.add_argument("--smoke", default=r"D:\dev\DoomDaggerfall-loop\review\doomerfall-mod\doomerfall-smoke.pk3")
ap.add_argument("--timeout", type=int, default=30)
a = ap.parse_args()
drla = [os.path.join(a.mods, f) for f in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
setups = {"mod-only": [a.pk3], "drla-only": drla, "drla+mod": drla + [a.pk3]}
fail = 0
results = {}
for name, files in setups.items():
    d = tempfile.mkdtemp(prefix="dfsmoke_")
    cmd = [a.exe, "-iwad", a.iwad, "-file", *files, a.smoke, "-config", os.path.join(d, "t.ini"), "-skill", "3",
           "+map", "E1M1", "-nosound", "-stdout", "-noactivate",
           "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    out = ""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=d)
    threading.Timer(a.timeout, proc.kill).start()
    for line in proc.stdout:
        out += line
        if "DoomerfallSmoke: done" in line: break
    else:
        out += "[TIMEOUT]"
    proc.kill()
    want = [] if name == "drla-only" else ["Doomerfall: mod loaded", "action fired: Open Fast Travel", "action fired: Open Inventory"]
    # DRLA prints some errors of its own on every launch; record them as a baseline and
    # require that adding our mod adds none.
    errs = [l for l in out.splitlines() if "Script error" in l or "Fatal" in l or "Unknown class" in l]
    results[name] = len(errs)
    bad = [l for l in out.splitlines() if "[TIMEOUT]" in l or "Doomerfall" in l and "rror" in l]
    if name == "mod-only": bad += errs
    ok = all(w in out for w in want) and not bad
    if name != "mod-only" and "DRLAX" not in out and "DoomRL" not in out: ok = False; bad.append("DRLA not loaded?")
    if name == "drla-only" and "Doomerfall: mod loaded" in out: ok = False
    if name == "drla+mod" and results[name] > results.get("drla-only", 0): ok = False; bad.append("extra errors vs drla-only")
    print(f"  [{name}] errors in log: {len(errs)}")
    print(f"{name}: {'PASS' if ok else 'FAIL'}  (log: {d})", *bad[:5], sep="\n  " if bad else "")
    pathlib.Path(d, "log.txt").write_text(out, encoding="utf-8")
    fail += not ok
sys.exit(fail)
