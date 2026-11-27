"""Stock check: DOOM.WAD E1M1 plain, and with DRLA, DRLA Monsters and DRLAX as in play_drlax.bat.

usage: stock_check.py UZDOOM OUT
Each run: private config, about 30 s, screenshot after 10 s of play, then quit. Passes when both exit on their own, no
fatal error is logged, and no Doomerfall line (DDTM, DDWEATHER, DDTCACHE, DFMESH) appears.
"""
import os
import subprocess
import sys
import time

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
DRLA = [os.path.join(MODS, n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
FATAL = ("FATAL", "VM execution aborted", "Script error", "Execution could not continue")
OURS = ("DDTM", "DDWEATHER", "DDTCACHE", "DFMESH")


def run(exe, out, name, files):
    work = os.path.join(out, name)
    os.makedirs(work, exist_ok=True)
    shot = os.path.join(work, "e1m1.png").replace("\\", "/")
    with open(os.path.join(work, "stock.cfg"), "w", newline="\n") as f:
        f.write(f'wait 350; screenshot "{shot}"; wait 20; quit\n')
    with open(os.path.join(work, "stock.ini"), "w", newline="\n") as f:
        f.write("[GlobalSettings]\nqueryiwad=false\n")
    log = os.path.join(work, "log-stock.txt")
    if os.path.exists(log):
        os.remove(log)
    cmd = [sys.executable, QUIET, "--timeout", "30", "--cwd", work, "--", exe, "-iwad", IWAD, "-config", os.path.join(work, "stock.ini"),
           "-noautoload", "-skill", "3", "-stdout"] + (["-file"] + files if files else []) + \
          ["+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_type", "png", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
           "+vid_lowerinbackground", "0", "+logfile", "log-stock.txt", "+map", "E1M1", "+exec", "stock.cfg"]
    code = subprocess.call(cmd, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    fatal = [l for l in text.splitlines() if any(k in l for k in FATAL)]
    ours = [l for l in text.splitlines() if l.startswith(OURS)]
    ok = code == 0 and not fatal and not ours and os.path.exists(shot)
    print(f"{name}: exit {code}, screenshot {'yes' if os.path.exists(shot) else 'no'}, fatal {len(fatal)}, Doomerfall lines {len(ours)} -> {'PASS' if ok else 'FAIL'}")
    for line in (fatal + ours)[:5]:
        print("  " + line[:200])
    return ok


def main():
    exe, out = sys.argv[1], sys.argv[2]
    ok = run(exe, out, "plain", [])
    ok = run(exe, out, "drla", DRLA) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
