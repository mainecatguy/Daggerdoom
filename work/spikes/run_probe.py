"""Throwaway: launch the built UZDoom on a probe PK3 for each start map, print probe lines.
usage: run_probe.py <outdir> <pk3> <map,map,...> <timeout_s> [extra args...]"""
import os, re, shutil, subprocess, sys, time
out, pk3, starts, limit = sys.argv[1], sys.argv[2], sys.argv[3].split(","), float(sys.argv[4])
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
for start in starts:
    log = os.path.join(out, f"run_{start}.log")
    args = [EXE, "-iwad", IWAD, "-file", pk3, "-config", os.path.join(out, "t.ini"), "-nosound", "-stdout",
            "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+vid_vsync", "0", "+wipetype", "0",
            "+gl_cachenodes", "0", "+disableautosave", "1", "+alwaysrun", "1", "+map", start] + sys.argv[5:]
    with open(log, "wb") as f:
        p = subprocess.Popen(args, stdout=f, stderr=subprocess.STDOUT, cwd=out)
        t = time.time()
        while time.time() - t < limit and p.poll() is None:
            time.sleep(0.5)
            text = open(log, "rb").read()
            if pk3 + ".src.wad" and os.path.exists(pk3 + ".src.wad") and b"DDMAP" in text and not os.path.exists(os.path.join(out, "ext.wad")):
                shutil.copy(pk3 + ".src.wad", os.path.join(out, "ext.wad"))  # written only after the engine is running
                print("wrote ext.wad after engine start")
            if b"DDDONE" in text:
                break
        code = p.poll()
        if code is None:
            p.kill()
    print("==", start, "exit", code, "elapsed", round(time.time() - t, 1))
    for line in open(log, errors="replace"):
        if re.match(r"\s*DD(HOP|MAP|LOAD|FPS|SPEED|PLANES)", line) or re.search(r"out of range|Script error|FATAL|Bad ", line, re.I):
            print(line.rstrip()[:150])
