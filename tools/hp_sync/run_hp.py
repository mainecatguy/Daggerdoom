"""Runs the real UZDoom and Daggerfall Unity through the launcher, minimized, with a private config, and checks HP sync.

usage: run_hp.py <name> <basic|monsters> <stock|drla|none>
  none = no bridge session for Doom's side is not possible here; use no_session_check.py for that.
Stops at once on a fatal error. About 30 seconds per launch.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\hp-sync")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3"]
FATAL = ("Fatal error", "FATAL", "VM execution aborted", "Unhandled exception")  # DRLA's load warnings contain "Script error"
TIMEOUT = 32


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def main():
    name, mode, mods = sys.argv[1], sys.argv[2], sys.argv[3]
    run = REVIEW / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log, console = run / f"{name}-uz.log", run / f"{name}-df.log", run / f"log-{name}.txt"
    for path in (uz_log, df_log, console, run / f"{name}-launcher.log"):
        path.unlink(missing_ok=True)

    uz_args = ["-noactivate", "-config", str(run / f"{name}.ini"), "-dfbridgelog", str(uz_log), "-dfhptest", mode, "-nosound", "-noautoload",
               "-skill", "3", "+logfile", name, "+map", "E1M1", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfhptest", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(run / f"{name}-launcher.log")]
    if mods == "drla":
        for mod in DRLA:
            command += ["--mod", str(mod)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT + 4
    done_text = "hp test: finished" if mode == "basic" else "hp test: monsters"
    seen_done = 0
    while time.time() < deadline and proc.poll() is None:
        text = read(uz_log)
        if any(k in read(console) for k in FATAL):
            print("FATAL in console log")
            break
        if mode == "monsters":
            seen_done = text.count(done_text)
            if seen_done >= 3:
                break
        elif done_text in text:
            break
        time.sleep(0.2)
    # Give the games a moment to flush, then end them.
    time.sleep(1.0)
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
    report(name, uz_log, df_log)


def report(name, uz_log, df_log):
    uz, df = read(uz_log), read(df_log)
    print("---- Doom log: hp lines")
    for line in uz.splitlines():
        if " hp" in line and "hp: shown" not in line:
            print(line)
    print("---- Daggerfall log: hp lines")
    for line in df.splitlines():
        if " hp" in line or "error" in line:
            print(line)
    sent = [int(m) for m in re.findall(r"hp: sent event (\d+):", uz)]
    applied = [int(m) for m in re.findall(r"hp: applied event (\d+):", df)]
    print("---- checks")
    print("events sent:", len(sent), "applied:", len(applied))
    print("sent in order 1..N:", sent == list(range(1, len(sent) + 1)))
    print("applied in order 1..N:", applied == list(range(1, len(applied) + 1)))
    print("out-of-order or missing warnings:", df.count("arrived after"))
    print("Doom refused sends:", uz.count("was refused"))
    print("death kill lines:", uz.count("killing the player"))


if __name__ == "__main__":
    main()
