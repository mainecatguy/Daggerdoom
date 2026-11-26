"""Paired run for the HP formula (gamedesign/hp.md): real UZDoom and Daggerfall Unity through the launcher, minimized,
on a private desktop, with a private config. Daggerfall runs -dfhpformulatest (DoomerfallHpFormulaTest.cs) and logs
each step's max HP; this script checks that Doom's max health followed every one of them.

usage: run_hpformula.py <play folder> <stock|drla> [run name, default the mod choice]
Stops at once on a fatal error.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [MODS / "DoomRL_Arsenal_1.1.5.pk3", MODS / "DoomRL_Monsters_Beta_7.3.pk3", MODS / "drlax_1.2b.pk3"]
FATAL = ("Fatal error", "FATAL", "VM execution aborted", "Unhandled exception")
TIMEOUT = 110  # A new game, spell effects, three loads, and a screenshot: longer than the usual 30 seconds.


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def main():
    play, mods = Path(sys.argv[1]), sys.argv[2]
    run = play.parent / "results" / (sys.argv[3] if len(sys.argv) > 3 else mods)
    run.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console = run / "uz.log", run / "df.log", run / "log-console.txt"
    for path in (uz_log, df_log, console, run / "launcher.log"):
        path.unlink(missing_ok=True)

    uz_args = ["-config", str(run / "uzdoom.ini"), "-dfbridgelog", str(uz_log), "-noautoload", "-skill", "3", "+logfile", str(console),
               "+map", "E1M1", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfhpformulatest", str(run),
                "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(play / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(run / "launcher.log")]
    if mods == "drla":
        for mod in DRLA:
            command += ["--mod", str(mod)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT + 5
    while time.time() < deadline and proc.poll() is None:
        if any(k in read(console) for k in FATAL):
            print("FATAL in console log")
            break
        if "hp formula test: finished" in read(df_log):
            time.sleep(2.0)  # Doom follows the last step
            break
        time.sleep(0.3)
    # quiet_run ends the whole run (both games and the launcher) at its own timeout. Killing quiet_run instead would
    # leave the games running on the private desktop, so wait for it.
    proc.wait()
    report(uz_log, df_log)


def report(uz_log, df_log):
    uz, df = read(uz_log), read(df_log)
    print("---- Daggerfall")
    for line in df.splitlines():
        if "hp formula test" in line or "endurance:" in line or "error" in line:
            print(line)
    print("---- Doom")
    doom_max = []
    for line in uz.splitlines():
        m = re.search(r"hp: Doom max health (?:now follows Daggerfall's (\d+)|-?\d+ -> (\d+) from Daggerfall)", line)
        if m:
            print(line)
            doom_max.append(int(m.group(1) or m.group(2)))
    print("---- checks")
    steps = re.findall(r"hp formula test: state ([^:]+): .*hp -?\d+/(\d+)", df)
    # In order: each step's max must reach Doom after the previous step's (a value seen earlier does not count).
    at, followed = 0, []
    for step, value in steps:
        hit = next((i for i in range(at, len(doom_max)) if doom_max[i] == int(value)), None)
        followed.append(hit is not None)
        at = hit + 1 if hit is not None else at
        print(f"{step}: Daggerfall max {value}, Doom took it in order: {hit is not None}")
    fails = df.count("hp formula test: FAIL")
    print(f"Daggerfall checks: {df.count('hp formula test: PASS')} passed, {fails} failed, finished: {'hp formula test: finished' in df}")
    print("ALL OK" if steps and fails == 0 and all(followed) else "NOT OK")


if __name__ == "__main__":
    main()
