"""Load check for the dungeon lighting (lightparity 01): loading a dungeon save from another map must apply the
current dungeon ambient and torch, even when the save's map time is later than the map it is loaded from.

    python tools/lightparity/loadcheck.py --play <play folder> --out <folder outside the repo>

Run 1: paired game, through Privateer's Hold's town door, about 20 s inside, save. Run 2: a new paired game with
+dd_dungeon_ambient 60, which loads that save from the town at once (the town's map time is lower than the save's).
PASS when run 2's console log shows "DDLIGHTS dungeon ambient 60" after the load. Screenshots after each step.
"""
import argparse
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "visual_parity"))


def session(c, out, name, uz_extra):
    os.environ["DDQA_SESSION"] = str(out / name)
    if "qa" in sys.modules:
        del sys.modules["qa"]
    sys.path.insert(0, str(c.REPO / "tools" / "qa"))
    import qa
    run = out / name / "run"
    c.fresh_run_folder(run)
    if qa.QA.exists():
        shutil.rmtree(qa.QA)
    qa.QA.mkdir(parents=True)
    qa.INBOX.write_text("")
    proc = subprocess.Popen(c.paired_command(out / "work", run, 240, uz_extra=uz_extra, qa=qa.QA),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not qa.await_line(lambda o: o.get("event") == "level", 90):
        c.kill(proc)
        raise RuntimeError(f"{name}: no level event (fatal: {c.fatal(run)})")
    t0 = time.time()
    while time.time() - t0 < 90 and qa.command(["pos"]).get("df_phase") != 3:
        time.sleep(0.5)
    return qa, proc, run


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--play", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    os.environ["VP_PLAY"] = args.play
    import common as c
    out = args.out.resolve()
    c.ensure_outside_repo(out)
    (out / "work").mkdir(parents=True, exist_ok=True)
    c.prepare(out / "work")
    save = "lightcheck"  # a bare name in the run's -savedir: the save command refuses absolute paths

    qa, proc, run = session(c, out, "run1", [])
    try:
        rows = [r.split() for r in qa.lumps(c.PLAY / "data" / "cache" / "T07154.ddt")["DDDOORS"].decode().splitlines() if r.strip()]
        x, y, z, nx, ny = map(float, next(r for r in rows if r[0] == "1")[3:8])
        qa.command(["teleport", f"{x + nx * 48:.1f}", f"{y + ny * 48:.1f}", "nan", f"{math.degrees(math.atan2(-ny, -nx)):.1f}"])
        qa.command(["con", "dd_tm_use", "1"])
        for _ in range(80):
            time.sleep(0.5)
            p = qa.command(["pos"])
            if p.get("map") and not str(p["map"]).upper().startswith("DDT"):
                break
        else:
            raise RuntimeError("run1: did not get into the dungeon")
        qa.command(["god", "on"])
        time.sleep(20)
        qa.command(["con", f'screenshot "{(out / "run1.png").as_posix()}"'])
        qa.command(["con", f"save {save}"])
        c.wait_until(lambda: (run / "saves" / "lightcheck.zds").exists(), 15)
        time.sleep(2)
    finally:
        c.kill(proc)
    log1 = c.read(run / "log-vpcon.txt")
    saved = run / "saves" / "lightcheck.zds"
    print("run1 save", saved.exists(), "| dungeon lines:", [l for l in log1.splitlines() if "DDLIGHTS dungeon" in l])
    if not saved.exists():
        return 1
    (out / "run2" / "run" / "saves").mkdir(parents=True, exist_ok=True)
    shutil.copy(saved, out / "run2" / "run" / "saves" / "lightcheck.zds")

    qa, proc, run = session(c, out, "run2", ["+dd_dungeon_ambient", "60"])
    try:
        print("run2 in town at", qa.command(["pos"]).get("map"))
        before = c.read(run / "log-vpcon.txt").count("DDLIGHTS dungeon ambient 60")
        qa.command(["con", f"load {save}"])
        time.sleep(8)
        print("run2 after load at", qa.command(["pos"]).get("map"))
        qa.command(["con", f'screenshot "{(out / "run2.png").as_posix()}"'])
        time.sleep(2)
    finally:
        c.kill(proc)
    log2 = c.read(run / "log-vpcon.txt")
    after = log2.count("DDLIGHTS dungeon ambient 60")
    print("run2 dungeon lines:", [l for l in log2.splitlines() if "DDLIGHTS dungeon" in l], "fatal:", c.fatal(run))
    ok = after > before
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
