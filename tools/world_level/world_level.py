"""World level test: the same place gives the same loot, gold, and enemies at any player level.

usage: world_level.py assemble | run LEVEL | compare LEVEL_A LEVEL_B
assemble: builds review\\world-level from review\\ammo-change (UZDoom, launcher, bridge DLL, data; same bridge header)
          and this worktree's Daggerfall Unity build.
run:      paired games, minimized, with Daggerfall's -dfworldleveltest LEVEL (the player's level is set to LEVEL, then
          fixed-seed rolls run through Daggerfall's own code at the current place and at Daggerfall city's dungeon).
compare:  compares two runs' "area" rolls (must match) and "control" rolls (no area level provider: must differ).
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\world-level")
BASE = Path(r"D:\dev\DoomDaggerfall-loop\review\ammo-change")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
TIMEOUT = 90


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data", "dfu"):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
    shutil.copytree(BASE / "uzdoom", REVIEW / "uzdoom")
    shutil.copytree(BASE / "data", REVIEW / "data")
    for name in ("doomerfall-launcher.exe", "dfitems.pk3", "doomerfall.pk3"):
        shutil.copy2(BASE / name, REVIEW / name)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASE / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    print("assembled", REVIEW)


def run(level):
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    name = f"level{level}"
    uz_log, df_log, launcher = runs / f"{name}-uz.log", runs / f"{name}-df.log", runs / f"{name}-launcher.log"
    for path in (uz_log, df_log, launcher, runs / f"{name}.txt"):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(runs / f"{name}.ini"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfworldleveltest", str(level),
          "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(runs), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + TIMEOUT + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
        body = read(df_log)
        if "worldleveltest: control hash" in body:
            reason = "test finished"
            break
        if "Exception" in body or "DIED WITH FATAL" in read(runs / f"{name}.txt"):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    for line in read(df_log).splitlines():
        if ("worldleveltest" in line and " area " not in line) or "area level" in line or "Exception" in line or "error" in line.lower():
            print("df", line[:300])


def rolls(level):
    body = read(REVIEW / "run" / f"level{level}-df.log")
    area = [re.sub(r"^.*?worldleveltest: area ", "", l) for l in body.splitlines() if "worldleveltest: area " in l and "area hash" not in l]
    hashes = dict(re.findall(r"worldleveltest: (area|control) hash (\w+)", body))
    head = re.findall(r"worldleveltest: player level .*", body)
    return area, hashes, head[-1] if head else "(no result)"


def compare(a, b):
    ra, ha, xa = rolls(a)
    rb, hb, xb = rolls(b)
    print("A:", xa)
    print("B:", xb)
    print("area lines", len(ra), len(rb), "hashes", ha.get("area"), hb.get("area"))
    print("control hashes", ha.get("control"), hb.get("control"))
    diffs = [(x, y) for x, y in zip(ra, rb) if x != y]
    for x, y in diffs[:10]:
        print("DIFF A:", x[:200])
        print("     B:", y[:200])
    same = bool(ra) and len(ra) == len(rb) and not diffs and ha.get("area") == hb.get("area")
    control_differs = ha.get("control") is not None and ha.get("control") != hb.get("control")
    print("area rolls:", "MATCH" if same else "MISMATCH")
    print("control rolls (player level, as normal Daggerfall Unity):", "DIFFER (expected)" if control_differs else "SAME (test not sensitive)")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "assemble":
        assemble()
    elif len(sys.argv) == 3 and sys.argv[1] == "run":
        run(int(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        compare(int(sys.argv[2]), int(sys.argv[3]))
    else:
        sys.exit(__doc__)
