"""Measures player height against the drawn terrain on varied ground.

Usage: height_test.py [--exe PATH] [--modes walk,scan] [--only steep,flat,coast]
Picks steep, flat, and coastal map pixels from WOODS.WLD, then runs height_harness.zs on each.
Output stays in the build folder because it is derived from game data.
"""
import argparse, csv, os, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
WOODS = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2\WOODS.WLD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WORK = r"D:\dev\DoomDaggerfall-build\terrain-tests"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error", "Execution could not continue")
W, H, OCEAN = 1000, 500, 3


def pick_sites():
    data = open(WOODS, "rb").read()
    off = struct.unpack_from("<I", data, 28)[0]
    m = data[off:off + W * H]
    steep, flat, coast = (0, None), (999, None), (0, None)
    for y in range(40, H - 40, 2):
        for x in range(40, W - 40, 2):
            around = [m[(y + b) * W + x + a] for a in range(-2, 3) for b in range(-2, 3)]
            span = max(around) - min(around)
            if min(around) > OCEAN and span > steep[0]: steep = (span, (x, y))
            if min(around) > OCEAN + 3 and span < flat[0]: flat = (span, (x, y))
            if min(around) <= OCEAN and max(around) > OCEAN and span > coast[0]: coast = (span, (x, y))
    return {"steep": steep[1], "flat": flat[1], "coast": coast[1], "route": (862, 442)}


def run(exe, site, start, mode):
    name = f"ht-{site}-{mode}"
    pk3 = os.path.join(WORK, name + ".pk3")
    log = os.path.join(WORK, "log-" + name + ".txt")
    frames = os.path.join(WORK, name + ".csv")
    for path in (log, frames, frames + ".shifts.csv"):
        if os.path.exists(path):
            os.remove(path)
    subprocess.check_call([sys.executable, os.path.join(HERE, "gen_overworld.py"), "--out", pk3, "--start", f"{start[0]},{start[1]}",
                           "--packchance", "0", "--harness", os.path.join(HERE, "height_harness.zs"), "--mode", mode], stdout=subprocess.DEVNULL)
    game = [exe, "-iwad", IWAD, "-file", pk3, "-config", os.path.join(WORK, "test.ini"), "-nosound", "-noautoload", "-skill", "3",
            "-width", "640", "-height", "360", "-noactivate", "-ddtmverify", "-ddtmlog", frames, "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0",
            "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", "DDOVER01"]
    proc = subprocess.Popen([sys.executable, QUIET, "--timeout", "30", "--cwd", WORK, "--"] + game,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + 33
    text = ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        text = open(log, errors="replace").read() if os.path.exists(log) else ""
        if "OWDONE" in text:
            reason = "done"
            break
        if any(k in text for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    text = open(log, errors="replace").read() if os.path.exists(log) else ""
    lines = [l for l in text.splitlines() if "HTRESULT" in l or any(k in l for k in FATAL)]
    print(f"{site} {start} {mode}: {reason}")
    for l in lines[:4]:
        print("  " + l[:300])
    if os.path.exists(frames + ".shifts.csv"):
        rows = list(csv.DictReader(open(frames + ".shifts.csv")))
        if rows:
            print(f"  shifts={len(rows)} worstPlaneError={max(float(r['plane_err']) for r in rows):.6f}")
    return reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\dev\DoomDaggerfall-build\uzdoom-terrain\Release\uzdoom.exe")
    ap.add_argument("--modes", default="walk,scan")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    sites = pick_sites()
    for site, start in sites.items():
        if args.only and site not in args.only.split(","):
            continue
        for mode in args.modes.split(","):
            if run(args.exe, site, start, mode) == "fatal":
                sys.exit(1)


if __name__ == "__main__":
    main()
