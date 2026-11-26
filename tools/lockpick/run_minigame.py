"""Doom-only test of the lockpicking minigame (mods/doomerfall DoomerfallLockpick.zs).

Runs E1M1 with the Doomerfall mod and tools/lockpick/harness through quiet_run, with or without the DRLA set, and
prints the harness's LPTEST lines. Exit 0 only when every case passed.

    python tools/lockpick/run_minigame.py --out <dir> [--drla] [--exe uzdoom.exe]
"""
import argparse, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--drla", action="store_true")
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe")
    ap.add_argument("--timeout", type=int, default=35)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    name = "drla" if a.drla else "stock"
    log = os.path.join(a.out, "lp-%s.log" % name)
    files = [os.path.join(MODS, f) for f in DRLA] if a.drla else []
    files += [os.path.join(ROOT, "mods", "doomerfall", "src"), os.path.join(ROOT, "tools", "lockpick", "harness")]
    cmd = [sys.executable, QUIET, "--timeout", str(a.timeout), "--", a.exe, "-iwad", IWAD, "-file"] + files + [
        "-config", os.path.join(a.out, "lp-%s.ini" % name), "-skill", "3", "+map", "E1M1", "+vid_fullscreen", "0",
        "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    cmd.append("-stdout")
    with open(log, "w", encoding="utf-8") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    text = open(log, encoding="utf-8", errors="replace").read()
    for line in text.splitlines():
        if re.search(r"LPTEST|DFLOCKPICK|Script error|ZScript|error", line):
            print(line)
    m = re.search(r"LPTEST done (\d+)/(\d+)", text)
    ok = bool(m) and m.group(1) == m.group(2) == "6"
    if not ok:
        print(chr(10).join(text.splitlines()[-15:]))
    print("RESULT", name, "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
