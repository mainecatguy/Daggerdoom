"""Damage numbers test: the "Show damage numbers" option (mods/doomerfall/src/zscript/DoomerfallDamageNumbers.zs).

usage: damage_numbers.py run NAME [--stock] [--dev] [--set 0|1] [--reset] [--keep-config] [--expect 0|1]
                         [--expect-stored -1|0|1] [--uzdoom EXE] [--iwad WAD] | check
--reset makes a choice mid-game, opposite to the launch's default, then runs reset2defaults (Options > Reset to
defaults); the option must go back to the launch's default. Each run checks the stored value, whether numbers show,
what HUD Options displays, and what the config holds after quitting (the default is never saved).
Runs UZDoom alone (no Daggerfall) on E1M1 with DRLA (unless --stock), a fresh doomerfall.pk3 and
tools/damage_numbers/harness.zs, which freezes a monster in front of the player and hits it with the player as the
source. Screenshots shot-a.png and shot-c.png and the console log go to the run folder. --dev passes +dd_dev 1; --set passes
+dd_damagenumbers N; --keep-config reuses the run folder's config from an earlier run, to check the choice is kept.
Prints the setting's value at the start of the map (DNCVAR) and RESULT; the screenshots are for a person (or Claude)
to look at: a must show gold numbers over the monster when the option is on, c none.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = Path(r"D:\dev\DoomDaggerfall-build\damage-numbers")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SIZE = ["-width", "1280", "-height", "800", "+win_w", "1280", "+win_h", "800", "+vid_fullscreen", "0", "+vid_scalemode", "0", "+vid_scalefactor", "1"]
FATAL = ("DIED WITH FATAL", "errors while parsing", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def run(a):
    runs = RUNS / a.name
    config = runs / "uzdoom.ini"
    kept = config.read_bytes() if a.keep_config and config.exists() else None
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "qa").mkdir(parents=True)
    if kept:
        config.write_bytes(kept)
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    pk3 = runs / "doomerfall.pk3"
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(pk3)], stdout=subprocess.DEVNULL)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DNHarness" }\n')
    mods = ([] if a.stock else [MODS / n for n in DRLA]) + [pk3, harness]
    extra = (["+dd_dev", "1"] if a.dev else []) + (["+dd_damagenumbers", a.set] if a.set is not None else [])
    extra += ["+set", "dn_wait", "1"] if a.reset else []
    timeout = 60
    uz = [a.uzdoom, "-iwad", a.iwad, "-file", *mods, "-config", config, "-ddqa", inbox.parent, "-noautoload", "-skill", "3",
          "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
          "+vid_lowerinbackground", "0", *SIZE, *extra, "+map", "E1M1"]
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--cwd", str(runs), "--", *map(str, uz)]
    out = open(runs / "stdout.txt", "wb")
    proc = subprocess.Popen(command + ["-stdout"], stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
    reason, end, shots, waiting, resetDone = "timeout", time.time() + timeout + 3, 0, None, False

    def body_now():
        return read(runs / "stdout.txt")  # -stdout output arrives line by line, unlike the buffered -logfile log.

    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = body_now()
        if a.reset and not resetDone:
            # Make a choice opposite to the launch's default; once the harness logs it, run Options > Reset to
            # defaults' own command.
            choice = 0 if a.dev else 1
            if resetDone is False and "DNCVAR" in body:
                resetDone = None
                with open(inbox, "a") as f:
                    f.write(f"c1 con dd_damagenumbers {choice}\n")
            elif resetDone is None and f"DNCVAR {choice} " in body:
                resetDone = True
                with open(inbox, "a") as f:
                    f.write("c2 con reset2defaults\n")
                    f.write("c3 con set dn_reset 1\n")
        if waiting and waiting.exists():  # The screenshot waits for a rendered frame; only then may the harness move on.
            time.sleep(0.3)
            with open(inbox, "a") as f:
                f.write(f"a{shots} con set dn_ack {shots}\n")
            waiting = None
        for shot in re.findall(r"(?m)^DNSHOT (\S+)", body)[shots:shots + 1] if not waiting else []:
            shots += 1
            waiting = runs / ("shot-" + shot + ".png")
            with open(inbox, "a") as f:
                f.write(f"s{shots} con screenshot \"{waiting.as_posix()}\"\n")
        if "DNDONE" in body:
            reason = "done"
            time.sleep(1.5)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        with open(inbox, "a") as f:
            f.write("q con quit\n")
        time.sleep(2)
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    body = body_now()
    print("stopped:", reason)
    for line in body.splitlines():
        if line.startswith("DN") or any(k in line for k in FATAL):
            print(line[:200])
    # The last values logged: after a reset, if one was asked for.
    values = re.findall(r"DNCVAR (-?\d+) dev (-?\d+) shown (\d)", body)
    stored, shown = (values[-1][0], values[-1][2]) if values else ("?", "?")
    want_stored = a.expect_stored or (a.set if a.set is not None and not a.reset else "-1")
    want_shown = a.expect or (a.set if a.set is not None and not a.reset else ("1" if a.dev else "0"))
    ok = reason == "done" and stored == want_stored and shown == want_shown
    if a.reset and (len(values) < 3 or values[-2][0] != ("0" if a.dev else "1")):
        print("FAIL: the choice and then the reset were not both logged")
        ok = False
    menus = re.findall(r"DNMENU Show damage numbers = (\S+)", body)
    want_menu = "On" if want_shown == "1" else "Off"
    if not menus or menus[-1] != want_menu:
        print(f"FAIL: HUD Options shows {menus[-1] if menus else 'no entry'}, wanted {want_menu}")
        ok = False
    saved = re.search(r"(?m)^dd_damagenumbers=(\S+)", read(config))
    if not saved or saved[1] != want_stored:  # Only a real choice is saved; the launch's default never is.
        print(f"FAIL: config holds dd_damagenumbers={saved[1] if saved else '(none)'}, wanted {want_stored}")
        ok = False
    if re.search(r"(?m)^dd_dev=", read(config)):
        print("FAIL: dd_dev was saved")
        ok = False
    summed = re.findall(r"DNNUMS handler:(.*)", body)
    if not summed or not summed[0].split()[-1:] == ["21"]:  # Three hits in one tic make one number.
        print("FAIL: the three hits in one tic did not make one number 21:", summed)
        ok = False
    shots = sorted(p.name for p in runs.glob("shot-*.png"))
    print("screenshots:", shots, "in", runs)
    print("RESULT", "PASS" if ok and len(shots) == 2 else "FAIL",
          f"(stored {stored}, wanted {want_stored}; shown {shown}, wanted {want_shown}; menu {menus[-1] if menus else '?'})")


def check(a):
    """Startup check (exit code 1337) on DOOM.WAD: stock, with DRLA, and with DRLA plus doomerfall.pk3."""
    RUNS.mkdir(parents=True, exist_ok=True)
    pk3 = RUNS / "check-doomerfall.pk3"
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(pk3)], stdout=subprocess.DEVNULL)
    for label, files in (("stock", []), ("drla", [MODS / n for n in DRLA]), ("drla+doomerfall", [MODS / n for n in DRLA] + [pk3])):
        uz = [a.uzdoom, "-iwad", a.iwad, *(["-file", *files] if files else []), "-config", RUNS / "check.ini", "-norun"]
        code = subprocess.call([sys.executable, QUIET, "--timeout", "60", "--cwd", str(RUNS), "--", *map(str, uz)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(label, "exit", code, "PASS" if code == 1337 else "FAIL")


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("run", "check"))
ap.add_argument("name", nargs="?", default="t")
ap.add_argument("--stock", action="store_true")
ap.add_argument("--dev", action="store_true")
ap.add_argument("--set", choices=("0", "1"))
ap.add_argument("--expect", choices=("0", "1"), help="whether numbers must show (default: --set's value, else 1 with --dev, else 0)")
ap.add_argument("--expect-stored", choices=("-1", "0", "1"), help="the stored value (default: --set's value, else -1)")
ap.add_argument("--reset", action="store_true", help="mid-game, choose the opposite of the default, then reset2defaults")
ap.add_argument("--keep-config", action="store_true")
ap.add_argument("--uzdoom", default=r"D:\dev\DoomDaggerfall-loop\play\uzdoom\uzdoom.exe")
ap.add_argument("--iwad", default=str(GAME / "wads" / "DOOM.WAD"))
args = ap.parse_args()
check(args) if args.command == "check" else run(args)
