"""Paired run for the Enhances Skill powers (DoomerfallSkillPowers.cs): real UZDoom and Daggerfall Unity through the
launcher, minimized, on a private desktop, with a private config. Daggerfall runs -dfenchantskillstest
(DoomerfallEnchantSkillsTest.cs). Runs twice (stock, then the DRLA set) and checks every Daggerfall check passed in
both and that the mapping ("MAP" lines) is identical across the runs.

usage: run_enchant_skills.py <play folder> [results folder, default <play folder>/../results/enchant-skills]
Stops at once on a fatal error.
"""
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
TIMEOUT = 90  # A new game, then 19 ring equips a frame or two apart.


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def run_once(play, run, mods):
    run.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, test_log = run / "uz.log", run / "df.log", run / "log-console.txt", run / "enchant.log"
    for path in (uz_log, df_log, console, test_log, run / "launcher.log"):
        path.unlink(missing_ok=True)
    uz_args = ["-config", str(run / "uzdoom.ini"), "-dfbridgelog", str(uz_log), "-noautoload", "-skill", "3", "+logfile", str(console),
               "+map", "E1M1", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfenchantskillstest", str(test_log),
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
            print(f"{mods}: FATAL in console log")
            break
        if "DONE" in read(test_log):
            break
        time.sleep(0.3)
    # quiet_run ends the whole run (both games and the launcher) at its own timeout; wait for it rather than kill it.
    proc.wait()
    return read(test_log), any(k in read(console) for k in FATAL)


def main():
    play = Path(sys.argv[1])
    results = Path(sys.argv[2]) if len(sys.argv) > 2 else play.parent / "results" / "enchant-skills"
    ok, maps = True, []
    for mods in ("stock", "drla"):
        log, fatal = run_once(play, results / mods, mods)
        lines = log.splitlines()
        fails = [l for l in lines if l.startswith("FAIL")]
        done = next((l for l in lines if l.startswith("DONE")), "not finished")
        print(f"---- {mods}: {done}, fatal: {fatal}")
        for l in lines:
            if l.startswith("MAP") or l.startswith("FAIL"):
                print(l)
        maps.append([l for l in lines if l.startswith("MAP")])
        ok = ok and not fatal and not fails and done.startswith("DONE")
    same = bool(maps[0]) and maps[0] == maps[1]
    print(f"mapping identical across runs: {same}")
    print("ALL OK" if ok and same else "NOT OK")


if __name__ == "__main__":
    main()
