"""Run the real games through the launcher and report what crossed the bridge.

Usage: python real_games_test.py <scenario>   (play | pauseext | menupause)
Each launch is limited to about 30 seconds and stays minimized and unfocused.
"""
import re
import subprocess
import sys
from pathlib import Path

REVIEW = Path(__file__).resolve().parents[2] / "daggerfall-unity-master" / "Builds" / "bridge-core"  # git-ignored
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
SECONDS = 30

SCENARIOS = {
    "play": ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
    "drla": ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
    "ext": ["-dfbridgetestpause", "ext", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
    "game": ["-dfbridgetestpause", "game", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
    "menu": ["-dfbridgetestpause", "menu", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"],
}


def pause_report(lines):
    """Compares the playsim clock and bridge counters across the held pause."""
    begin = next((i for i, l in enumerate(lines) if "test pause" in l and "begin" in l), None)
    end = next((i for i, l in enumerate(lines) if "test pause" in l and ": end" in l), None)
    if begin is None or end is None:
        print("PAUSE: did not complete")
        return
    held = [l for l in lines[begin:end] if "heartbeat=" in l]
    if len(held) < 2:
        print("PAUSE: too few status lines")
        return
    field = lambda line, key: int(re.search(key + r"=(-?\d+)", line).group(1))
    first, last = held[0], held[-1]
    print("PAUSE held:", first.split()[0], "to", last.split()[0],
          *(f"{k}+{field(last, k) - field(first, k)}" for k in ("tic", "maptime", "heartbeat", "df_value", "answered", "pongs")),
          *(f"{k}={field(last, k)}" for k in ("paused", "pauseext", "menu")))


def main():
    name = sys.argv[1]
    run = REVIEW / "run"
    uz_log, df_log = run / f"t-{name}-uz.log", run / f"t-{name}-df.log"
    for path in (uz_log, df_log):
        path.unlink(missing_ok=True)

    uz_args = ["-noactivate", "-config", str(run / f"t-{name}.ini"), "-dfbridgelog", str(uz_log), "-nosound", "-skill", "3",
               "+map", "E1M1", "+vid_fullscreen", "0"] + SCENARIOS[name]
    dfu_args = ["-dfbridgelog", str(df_log), "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(SECONDS), "--", str(REVIEW / "doomerfall-launcher.exe"),
               "--minimized", "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", IWAD, "--uzdoom-cwd", str(run), "--log", str(run / f"t-{name}-launcher.log")]
    if name == "drla":
        command += ["--mod-list", str(REVIEW / "mods.txt")]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]
    result = subprocess.run(command, capture_output=True, text=True)
    print("launcher run exit", result.returncode)

    for label, path in (("UZDoom", uz_log), ("Daggerfall", df_log)):
        print(f"--- {label} log")
        if not path.exists():
            print("(missing)")
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        key = [l for l in lines if re.search(r"attached|hello|message|live|stale|error", l)]
        status = [l for l in lines if "heartbeat=" in l]
        latency = [l for l in lines if " latency " in l]
        print("\n".join(key[:8]))
        print("\n".join(status[:1] + status[-2:]))
        print("\n".join(latency[-1:]))
        if label == "UZDoom" and name in ("ext", "game", "menu"):
            pause_report(lines)
        steady = latency[3:]  # skip the startup windows, which include Daggerfall's scene load
        for channel in ("rtt", "uz->df", "df->uz"):
            found = [re.search(re.escape(channel) + r" n=\d+ p50=([\d.]+)ms p99=([\d.]+)ms max=([\d.]+)ms", l) for l in steady]
            found = [m for m in found if m]
            if found:
                p50 = sorted(float(m.group(1)) for m in found)[len(found) // 2]
                print(f"steady {channel}: {len(found)} windows, median p50 {p50:.2f}ms, worst p99 "
                      f"{max(float(m.group(2)) for m in found):.2f}ms, worst max {max(float(m.group(3)) for m in found):.2f}ms")


if __name__ == "__main__":
    main()
