"""Location record card 1: the overworld snapshot without the treadmill's terrain planes.

usage: card1.py UZDOOM_EXE save|load|size

save: UZDoom alone on DDOVER01 (no Daggerfall) makes an autosave after 3 s (card1.zs).
load: loads that save in a new launch. Both print the terrain under and around the player, which must match.
size: the save's size and each file in it, raw and packed.
Data (overworld.pk3, ddruntime.pk3) comes from card 2's review folder and stays outside the repo.
"""
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\locrecord\card1")
DATA = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger2\data")
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"


def harness():
    path = REVIEW / "card1.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("zscript.txt", (HERE / "card1.zs").read_text())
        z.writestr("cvarinfo.txt", "user bool lrc1_load = false;\n")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LRCard1" }\n')
    return path


def run(exe, mode, tag=""):
    REVIEW.mkdir(parents=True, exist_ok=True)
    saves = REVIEW / "saves"
    saves.mkdir(exist_ok=True)
    log = REVIEW / f"log-{mode}{tag}.txt"
    log.unlink(missing_ok=True)
    args = [exe, "-iwad", IWAD, "-file", str(DATA / "ddruntime.pk3"), str(DATA / "overworld.pk3"), str(harness()),
            "-savedir", str(saves), "-config", str(REVIEW / "uz.ini"), "-noautoload", "-skill", "3", "+logfile", f"{mode}{tag}",
            "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    if mode == "save":
        for old in saves.glob("*.zds"):
            old.unlink()
        args += ["+set", "lrc1_load", "0", "+map", "DDOVER01"]
    else:
        args += ["+set", "lrc1_load", "1", "-loadgame", max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime).name]
    proc = subprocess.Popen([sys.executable, QUIET, "--timeout", "40", "--"] + args, cwd=REVIEW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + 42
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
        if log.exists() and "LRC1DONE" in log.read_text(errors="replace"):
            time.sleep(0.5)
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()
    text = log.read_text(errors="replace") if log.exists() else ""
    for line in text.splitlines():
        if line.startswith(("LRC1", "DDTM saved", "DDTM resumed", "DDTM failed")) or "error" in line.lower():
            print(" ", line[:200])


def size(tag=""):
    save = max((REVIEW / "saves").glob("auto*.zds"), key=lambda p: p.stat().st_mtime)
    print(save, save.stat().st_size, "bytes")
    with zipfile.ZipFile(save) as z:
        for info in z.infolist():
            print(f"  {info.filename} {info.file_size} raw, {info.compress_size} packed")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if sys.argv[2] == "size":
        size()
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
