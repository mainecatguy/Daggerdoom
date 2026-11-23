"""Checks that nothing changes without a bridge session, and that a killed game is handled.

Usage: python no_session_check.py doom | dfu | kill-uz | kill-df
"""
import re
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(__file__).resolve().parents[2] / "daggerfall-unity-master" / "Builds" / "bridge-core"
RUN = REVIEW / "run"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
MODS = [r"D:\dev\DoomDaggerfall\GameMods\DoomRL_Arsenal_1.1.5.pk3",
        r"D:\dev\DoomDaggerfall\GameMods\DoomRL_Monsters_Beta_7.3.pk3",
        r"D:\dev\DoomDaggerfall\GameMods\drlax_1.2b.pk3"]
BASELINE = r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release\uzdoom.exe"
BRIDGE = str(REVIEW / "uzdoom" / "uzdoom.exe")
QUIET_ARGS = ["-noactivate", "-nosound", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
NOISE = re.compile(r"\d+\.\d+|\d{2}:\d{2}|[A-Za-z]:[\\/]|Log started|Log stopped|commit|version|UZDoom g", re.I)


def run_doom(exe, label, mods, seconds):
    log = RUN / f"log-nosession-{label}.txt"  # +logfile writes log-<name>.txt in the working directory
    log.unlink(missing_ok=True)
    args = [exe, "-iwad", IWAD]
    if mods:
        args += ["-file"] + mods
    args += ["-config", str(RUN / f"nosession-{label}.ini"), "-skill", "3", "+logfile", f"nosession-{label}", "+map", "E1M1"] + QUIET_ARGS
    code = subprocess.run([sys.executable, QUIET, "--timeout", str(seconds), "--cwd", str(RUN), "--"] + args,
                          capture_output=True, text=True).returncode
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    return code, text


def compare_doom():
    for name, mods, seconds in (("stock", [], 12), ("drla", MODS, 25)):
        _, base = run_doom(BASELINE, name + "-base", mods, seconds)
        _, new = run_doom(BRIDGE, name + "-bridge", mods, seconds)
        keep = lambda text: [l for l in text.splitlines() if l.strip() and not NOISE.search(l)]
        a, b = keep(base), keep(new)
        only_a = [l for l in a if l not in set(b)]
        only_b = [l for l in b if l not in set(a)]
        print(f"{name}: baseline {len(a)} lines, bridge build {len(b)} lines, only-baseline {len(only_a)}, only-bridge {len(only_b)}")
        print(f"  entered E1M1: baseline {'E1M1' in base}, bridge build {'E1M1' in new}; bridge text in log: {'[bridge]' in new}")
        for line in (only_a[:3] + only_b[:3]):
            print("  differs:", line[:120])
    print("-norun exit:", subprocess.run([sys.executable, QUIET, "--timeout", "20", "--cwd", str(RUN), "--", BRIDGE, "-iwad", IWAD,
                                           "-norun", "-nosound", "-stdout", "-config", str(RUN / "nosession-norun.ini")],
                                          capture_output=True, text=True).returncode)


def check_dfu():
    dll = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
    hidden = dll.with_suffix(".hidden")
    dll.rename(hidden)  # any native bridge call in a normal launch would now raise DllNotFoundException
    try:
        code = subprocess.run([sys.executable, QUIET, "--timeout", "15", "--", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
                               "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"],
                              capture_output=True, text=True).returncode
    finally:
        hidden.rename(dll)
    player = REVIEW / "dfu" / "PortableAppdata" / "Player.log"  # portable installs log beside their settings
    text = player.read_text(encoding="utf-8", errors="replace") if player.exists() else ""
    age = time.time() - player.stat().st_mtime if player.exists() else -1
    print(f"run exit {code}; private Player.log age {age:.0f}s, {len(text)} bytes")
    print("bridge mentions:", len(re.findall(r"doomerfall_bridge|\[bridge\]|DllNotFound", text)))


def kill_game(which):
    log = RUN / f"t-{which}-launcher.log"
    uz_log, df_log = RUN / f"t-{which}-uz.log", RUN / f"t-{which}-df.log"
    for path in (log, uz_log, df_log):
        path.unlink(missing_ok=True)
    command = [str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--uzdoom", BRIDGE, "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", IWAD, "--uzdoom-cwd", str(RUN), "--log", str(log)]
    for arg in ["-config", str(RUN / f"t-{which}.ini"), "-dfbridgelog", str(uz_log), "+map", "E1M1"] + QUIET_ARGS:
        command += ["--uzdoom-arg", arg]
    for arg in ["-dfbridgelog", str(df_log), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]:
        command += ["--dfu-arg", arg]
    launcher = subprocess.Popen(command)
    time.sleep(15)
    name = "UZDoom" if which == "kill-uz" else "Daggerfall Unity"
    pid = re.search(rf"started {name} pid (\d+)", log.read_text(encoding="utf-8")).group(1)
    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    try:
        code = launcher.wait(timeout=12)
    except subprocess.TimeoutExpired:
        launcher.kill()
        code = "timeout"
    print("launcher exit", code)
    print("\n".join(l for l in log.read_text(encoding="utf-8").splitlines() if "started" not in l))
    for path in (uz_log, df_log):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
        status = [l for l in lines if "heartbeat=" in l]
        print(path.name, "status lines", len(status), "gaps", set(re.findall(r"gaps=(\d+)", "\n".join(status))))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "doom":
        compare_doom()
    elif mode == "dfu":
        check_dfu()
    else:
        kill_game(mode)
