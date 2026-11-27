"""The owner's "YouGotAPickup" save (test only): load it in both games and record the look label while the player stands
where the save left them. In that save a clip lies on the 3D floor of the storey above the player, 17 units away, and
the old engine labelled it although nothing is in view.

usage: storey.py <play folder> <save .zds> [--out <results folder>]
  Copies the save into the results folder as an autosave and runs tools/fixed_drops/paired.py's load route with
  tools/looklabel/storey.zs. Prints every look label and STOREY PASS when none showed. Wrap in quiet_run.py.
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "fixed_drops"))
import paired  # noqa: E402


def make_harness(out, name, play=None):
    harness = out / "storey-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "storey.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PDHarness" }\n')
    return harness


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    play, save = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else play.parent / "storey-results"
    (out / "saves").mkdir(parents=True, exist_ok=True)
    for old in (out / "saves").glob("*.zds"):
        old.unlink()
    shutil.copy2(save, out / "saves" / "storey-auto00.zds")  # paired.run's load route takes the newest *auto*.zds.
    paired.make_harness = make_harness
    paired.DATA = paired.DATA + ["../doomerfall-drla.pk3"]  # The owner's play.bat loads it too.
    paired.TIMEOUT = 180
    paired.run(play, out, "load", 10)
    log = (out / "log-load.txt").read_text(errors="replace") if (out / "log-load.txt").exists() else ""
    windows, current = {}, None
    for line in log.splitlines():
        m = re.match(r"PDAT (\S+)", line)
        if m:
            current = m.group(1)
            windows[current] = []
        elif line.startswith("PDEND"):
            current = None
        elif current and (m := re.match(r'look: "(.*)"$', line)):
            windows[current].append(m.group(1))
    spot = re.search(r"^PDSTOREY .*$", log, re.M)
    print("spot:", spot.group(0) if spot else None)
    for name, looks in windows.items():
        print(f"look labels at {name}: {looks}")
    empty = "spot" in windows and spot and not any(windows["spot"])
    stim = windows.get("stim", [])[-1:] == ["Stimpack"]
    gun = windows.get("gun", [])
    named = bool(gun) and gun[-1].endswith(" Battle Rifle")  # Daggerfall's material name wins once it arrives.
    print(f"no label at the saved spot {bool(empty)}, stimpack named {stim}, gun: Doom's name then Daggerfall's {named}")
    print("STOREY", "PASS" if empty and stim and named else "FAIL")
