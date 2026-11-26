"""Doom-only test of locked dungeon doors (door_objects.zs, action_objects.zs and the lockpicking minigame), no Daggerfall.

Loads Privateer's Hold as converted by scripts/play/install.py (its data folder), the Doomerfall mod and this harness,
and runs on the locked door 29539363 (starting lock 2). The harness plays Daggerfall's answers as network events.
Prints the DGTEST lines. Exit 0 only when every case passed.

    python tools/lockpick/doorgate/run_doorgate.py [--root <install folder>] [--drla] [--out DIR] [--saveload]

--saveload: a save made before Daggerfall armed the locks asks for the arm when loaded; an armed save does not and
keeps its locks (three short runs: make both autosaves, then load each).
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
LOADID = 29539363


def launch(a, out, name, extra, until):
    """One UZDoom run on Privateer's Hold with the harness; returns its log text."""
    log = out / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    data = a.root / "data"
    files = ([str(MODS / f) for f in DRLA] if a.drla else []) + [str(data / "ddruntime.pk3"), str(data / "privateershold.wad"), str(data / "privateershold_mesh.pk3"),
                                                                  str(data / "privateershold_doors.pk3"), str(REPO / "mods" / "doomerfall" / "src"), str(HERE)]
    cmd = [sys.executable, QUIET, "--timeout", "40", "--cwd", str(out), "--", str(a.root / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM2.WAD"),
           "-file", *files, "-config", str(out / f"{name}.ini"), "-savedir", str(out / "saves-doorgate"), "-noautoload", "-skill", "3", "+logfile", name,
           "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", *extra]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end, body = time.time() + 43, ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = log.read_text(errors="replace") if log.exists() else ""
        if until in body or re.search(r"[1-9]\d* errors? .*while (compiling|parsing)|VM execution aborted|DIED WITH FATAL", body):
            time.sleep(1)
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return log.read_text(errors="replace") if log.exists() else ""


def saveload(a, out):
    saves = out / "saves-doorgate"
    for old in saves.glob("*.zds"):
        old.unlink()
    tag = "-drla" if a.drla else ""
    body = launch(a, out, "doorgate-save" + tag, ["+dd_lockload", "1", "+map", "MAP01"], "DGSAVE done")
    for line in body.splitlines():
        if line.startswith("DGSAVE") or "error" in line.lower():
            print(line[:200])
    made = sorted(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime)
    if "DGSAVE unarmed 0" not in body or not re.search(r"DGSAVE armed [1-9]", body) or len(made) < 2:
        print(f"FAIL the save run made {len(made)} autosaves")
        return False
    ok = True
    for save, want_facts, label in ((made[-2], 1, "unarmed"), (made[-1], 0, "armed")):
        body = launch(a, out, f"doorgate-load-{label}{tag}", ["+dd_lockload", "2", "-loadgame", save.name], "DGLOAD")
        m = re.search(r"DGLOAD facts=(\d+) armed=(\d+)", body)
        armed = int(m.group(2)) if m else -1
        good = bool(m) and int(m.group(1)) == want_facts and (armed == 0 if label == "unarmed" else armed > 0)
        ok &= good
        print(("PASS" if good else "FAIL") + f" loading the {label} save {save.name}: " + (m.group(0) if m else "no DGLOAD line") + f" (want facts={want_facts})")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(r"D:\dev\DoomDaggerfall-loop\review\locked-doors"))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--drla", action="store_true")
    ap.add_argument("--saveload", action="store_true")
    a = ap.parse_args()
    out = a.out or a.root / "test"
    out.mkdir(parents=True, exist_ok=True)
    if a.saveload:
        sys.exit(0 if saveload(a, out) else 1)
    name = "doorgate-drla" if a.drla else "doorgate"
    log = out / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    data = a.root / "data"
    files = ([str(MODS / f) for f in DRLA] if a.drla else []) + [str(data / "ddruntime.pk3"), str(data / "privateershold.wad"), str(data / "privateershold_mesh.pk3"),
                                                                  str(data / "privateershold_doors.pk3"), str(REPO / "mods" / "doomerfall" / "src"), str(HERE)]
    cmd = [sys.executable, QUIET, "--timeout", "45", "--cwd", str(out), "--", str(a.root / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM2.WAD"),
           "-file", *files, "-config", str(out / f"{name}.ini"), "-noautoload", "-skill", "3", "+logfile", name, "+dd_lockdoor", str(LOADID),
           "+map", "MAP01", "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time
    end, body = time.time() + 48, ""
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = log.read_text(errors="replace") if log.exists() else ""
        if "DGTEST done" in body or re.search(r"[1-9]\d* errors? .*while (compiling|parsing)|VM execution aborted|DIED WITH FATAL", body):
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    for line in body.splitlines():
        if line.startswith("DGTEST") or "error" in line.lower() or "aborted" in line:
            print(line[:220])
    m = re.search(r"DGTEST done (\d+)/(\d+)", body)
    sys.exit(0 if m and m.group(1) == m.group(2) else 1)


if __name__ == "__main__":
    main()
