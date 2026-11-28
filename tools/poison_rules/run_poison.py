"""Paired run: Doom poison goes through Daggerfall's HP and death rules.

Runs the real UZDoom and Daggerfall Unity through the launcher (minimized, private desktop via quiet_run.py, private
config) on DOOM.WAD E1M1 with -dfhptest poison|poisonhit (UZDoom/src/dd_bridge_test.cpp):
  1. ZDoom-style poison (P_PoisonMobj -> P_DamageMobj): its hits must reach Daggerfall.
  2. Daggerfall's HP is set to 4, then Hexen-style poison (P_PoisonPlayer ticking, or one P_PoisonDamage of 50):
     every poison hit must be sent to Daggerfall, Doom's player must stay alive until Daggerfall reports death,
     and die then.

usage: run_poison.py <review dir> <poison|poisonhit> <stock|drla>
Exit code 0 when every check passes.
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
TIMEOUT = 40


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def run(review, mode, mods):
    run_dir = review / "run"
    run_dir.mkdir(exist_ok=True)
    name = f"{mode}-{mods}"
    uz_log, df_log, console = run_dir / f"{name}-uz.log", run_dir / f"{name}-df.log", run_dir / f"log-{name}.txt"
    for path in (uz_log, df_log, console, run_dir / f"{name}-launcher.log"):
        path.unlink(missing_ok=True)
    uz_args = ["-config", str(run_dir / f"{name}.ini"), "-dfbridgelog", str(uz_log), "-dfhptest", mode, "-noautoload",
               "-skill", "3", "+logfile", name,  # written as log-<name>.txt "+map", "E1M1", "+vid_fullscreen", "0", "+wipetype", "0",
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfhptest", "-screen-fullscreen", "0",
                "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(review / "doomerfall-launcher.exe"),
               "--minimized", "--nodraw", "--uzdoom", str(review / "uzdoom" / "uzdoom.exe"),
               "--dfu", str(review / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run_dir), "--log", str(run_dir / f"{name}-launcher.log")]
    if mods == "drla":
        for mod in DRLA:
            command += ["--mod", str(mod)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT + 4
    while time.time() < deadline and proc.poll() is None:
        if any(k in read(console) for k in FATAL):
            print("FATAL in console log")
            break
        if "hp test: poison: finished" in read(uz_log):
            break
        time.sleep(0.2)
    time.sleep(1.0)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    return check(name, uz_log, df_log, console)


def check(name, uz_log, df_log, console):
    uz, df = read(uz_log), read(df_log)
    lines = uz.splitlines()
    print(f"==== {name}")
    for line in lines:
        if "hp test:" in line or "hp: sent" in line or "Daggerfall reports death" in line:
            print("UZ", line)
    for line in df.splitlines():
        if "hp: applied" in line:
            print("DF", line)

    def index(text):
        return next((i for i, line in enumerate(lines) if text in line), -1)

    results = []

    def expect(label, ok):
        results.append(ok)
        print(("PASS " if ok else "FAIL ") + label)

    expect("no fatal error in the console log", console.exists() and not any(k in read(console) for k in FATAL))
    expect("finished", index("hp test: poison: finished") >= 0)
    zdoom_start, zdoom_end = index("ZDoom-style poison 2 every"), index("poison: after ZDoom-style poison")
    zdoom_hits = [l for l in lines[zdoom_start:zdoom_end] if "hp: sent event" in l and "hit" in l] if zdoom_start >= 0 else []
    expect(f"ZDoom-style poison hits reach Daggerfall ({len(zdoom_hits)})", len(zdoom_hits) >= 2)
    low = index("poison: at low hp")
    m = re.search(r"confirmed=(\d+)/", lines[low]) if low >= 0 else None
    expect("Daggerfall hp is 4 before Hexen poison", bool(m) and m.group(1) == "4")
    poisoned = index("poison: Hexen poison 100") if "poisonhit" not in name else index("poison: one Hexen poison hit")
    expect("player alive in the tic it is poisoned", poisoned >= 0 and "player alive=1" in lines[poisoned])
    poison_hits = [l for l in lines if "hp: sent event" in l and "(poison)" in l]
    expect(f"Hexen poison hits are sent to Daggerfall ({len(poison_hits)})", len(poison_hits) >= 1)
    kill, died = index("Daggerfall reports death"), index("poison: player died")
    expect("Daggerfall reports death", kill >= 0)
    expect("Doom's player dies, and only after Daggerfall reports death", died > kill >= 0)
    dm = re.search(r"confirmed=(-?\d+)/", lines[died]) if died >= 0 else None
    expect("Daggerfall hp is 0 when the player dies", bool(dm) and int(dm.group(1)) <= 0)
    alive_lines = [l for l in lines[poisoned:kill] if "hp test:" in l and "state=" in l] if poisoned >= 0 and kill > 0 else []
    expect("player stays alive between poisoning and Daggerfall's death report",
           all("state=0" in l for l in alive_lines))
    df_zero = [l for l in df.splitlines() if re.search(r"hp: applied event \d+: hit \d+, hp \d+ -> 0 ", l)]
    expect("Daggerfall applied the lethal hit itself (hp -> 0)", len(df_zero) == 1)
    sent = [int(x) for x in re.findall(r"hp: sent event (\d+):", uz)]
    applied = [int(x) for x in re.findall(r"hp: applied event (\d+):", df)]
    expect(f"every event applied in order (sent {len(sent)}, applied {len(applied)})",
           bool(sent) and applied == list(range(1, len(applied) + 1)) and df.count("arrived after") == 0)
    return all(results)


def main():
    review, mode, mods = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    ok = run(review, mode, mods)
    print("RESULT", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
