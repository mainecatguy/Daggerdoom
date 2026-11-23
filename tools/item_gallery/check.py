"""Launches the item gallery and the stock E1M1 regressions, each with a private config and a short timeout.

Usage: python check.py <review dir> <run dir> [expected item count]
"""
import pathlib
import subprocess
import sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = pathlib.Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [str(MODS / n) for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
BACKGROUND = ["-noactivate", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
FATAL = ("Script error", "FATAL", "Execution could not continue", "Unknown class", "VM abort")
# Grid points in front of the player start, near the first rows, the middle, and the artifacts at the end.
VIEWS = [(96, 96), (1600, 700), (3000, 1500), (700, 1700)]


def launch(name, review, run, files, level, script):
    cfg = run / f"{name}.cfg"
    cfg.write_text(script, encoding="ascii")
    log = run / f"log-{name}-log.txt"   # UZDoom's name for "+logfile <name>.log".
    log.unlink(missing_ok=True)
    base = [str(review / "uzdoom.exe"), "-iwad", IWAD, "-config", str(run / f"{name}.ini"), "-nosound", "-noautoload"]
    if files:
        base += ["-file", *files]

    # Script errors open a blocking dialog in a normal launch, so check them first.
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 7
    done = subprocess.run([*base, "-norun", "-noactivate", "-stdout", "+vid_fullscreen", "0"], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=startup, timeout=30)
    if done.returncode != 1337:
        lines = done.stdout.decode("utf-8", "replace").splitlines()
        return done.returncode, "", [l[:220] for l in lines if "error" in l.lower() or ", line " in l][:8] or lines[-5:]

    args = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(run), "--", *base, "-skill", "3", "-width", "1280", "-height", "720",
            *BACKGROUND, "+vid_fullscreen", "0", "+screenshot_type", "png", "+logfile", f"{name}.log", "+map", level, "+exec", cfg.name]
    code = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    if code != 0:
        print(f"--- {name} log tail ---\n" + "\n".join(text.splitlines()[-12:]))
    bad = [line for line in text.splitlines() if any(f in line for f in FATAL)]
    return code, text, bad


def main():
    review, run = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    expected = int(sys.argv[3]) if len(sys.argv) > 3 else None
    run.mkdir(parents=True, exist_ok=True)
    package = str(review / "daggerfall_items.pk3")
    failed = False

    steps = "".join(f'warp {x} {y}; wait 12; screenshot "{run / f"gallery{i}.png"}"; wait 6; '.replace("\\", "/") for i, (x, y) in enumerate(VIEWS))
    code, text, bad = launch("gallery", review, run, [package], "DFGALLRY", f"wait 70; {steps}quit\n")
    line = next((l for l in text.splitlines() if l.startswith("DFITEMS:")), "no DFITEMS line")
    ok = code == 0 and not bad and " broken=0" in line and (expected is None or f"shown={expected} total={expected}" in line)
    print(f"gallery exit={code} {line} errors={bad[:3]} {'PASS' if ok else 'FAIL'}")
    failed |= not ok

    # DRLA logs its own errors without our package, so that run is the baseline: adding the package must add none.
    drla_baseline = None
    for name, files in (("e1m1_stock", []), ("e1m1_drla", DRLA), ("e1m1_drla_items", [*DRLA, package])):
        code, text, bad = launch(name, review, run, files, "E1M1", "wait 70; quit\n")
        entered = "E1M1" in text
        spawned = "DFITEMS:" in text
        if name == "e1m1_drla":
            drla_baseline = set(bad)
            new = []
        elif name == "e1m1_drla_items":
            new = sorted(set(bad) - drla_baseline)
        else:
            new = bad
        ok = code == 0 and not new and entered and not spawned
        print(f"{name} exit={code} entered={entered} itemsSpawned={spawned} errorLines={len(bad)} newErrors={new[:3]} {'PASS' if ok else 'FAIL'}")
        failed |= not ok
        if not ok:
            break
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
