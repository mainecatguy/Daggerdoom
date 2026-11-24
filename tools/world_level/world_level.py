"""World level test: the same place gives the same loot, gold, and enemies at any player level.

usage: world_level.py assemble [LANE] | run LEVEL | compare LEVEL_A LEVEL_B
assemble: builds review\\world-level from review\\questfaces(UZDoom, launcher, bridge DLL, data; same bridge header)
          and this worktree's Daggerfall Unity build. With LANE, UZDoom, launcher and bridge DLL come instead from
          D:\\dev\\DoomDaggerfall-build\\{uzdoom,launcher,bridge}-LANE\\Release (needed after a bridge header merge).
run:      paired games, minimized, with Daggerfall's -dfworldleveltest LEVEL (the player's level is set to LEVEL, then
          fixed-seed rolls run through Daggerfall's own code at the current place and at Daggerfall city's dungeon).
compare:  compares two runs' "area" rolls (must match) and "control" rolls (no area level provider: must differ).
odds:     world_level.py odds LEVEL: material shares of piles, shelves, containers, magic items and enemy equipment
          rolled at area levels 1, 10, 20, 30 in that run, against the owner's approved table; plus the classic
          formula at level 20 with the Doomerfall hook off, which must differ. Also quest reward magic items rolled with
          the player at level 1, which must follow the approved odds at the fixed quest reward level (20).
"""
import math
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
# UZDoom, launcher and bridge DLL from the questfaces lane, the last change to bridge/doomerfall_bridge.h (db43379).
BASE = Path(r"D:\dev\DoomDaggerfall-loop\review\questfaces")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
TIMEOUT = 90


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble(builds=None):
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
    if builds:
        # Use this worktree's own native builds (uzdoom-<lane>, bridge-<lane>, launcher-<lane> trees), so the bridge
        # layout matches the Daggerfall Unity build after header changes merge.
        root = Path(r"D:\dev\DoomDaggerfall-build")
        release = root / f"uzdoom-{builds}" / "Release"
        for item in release.iterdir():
            if item.suffix.lower() in (".exe", ".dll", ".pk3"):
                shutil.copy2(item, REVIEW / "uzdoom" / item.name)
        if (release / "doomerfall.pk3").exists():
            shutil.copy2(release / "doomerfall.pk3", REVIEW / "doomerfall.pk3")
        shutil.copy2(root / f"launcher-{builds}" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
        shutil.copy2(root / f"bridge-{builds}" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
        print("native builds from", root, builds)
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
        if ("worldleveltest" in line and " area " not in line) or "questreward: reward" in line or "questreward: control" in line or "area level" in line or "Exception" in line or "error" in line.lower():
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


TIERS = ["Iron", "Steel", "Silver", "Elven", "Dwarven", "Mithril", "Adamantium", "Ebony", "Orcish", "Daedric"]


def approved(level):
    """The owner's approved odds (work/notes/20261123-material-tier-proposal.md), computed independently of the game."""
    level = min(max(level, 1), 30)
    daedric = 0.025 * ((level - 1) / 19) ** 3 if level <= 20 else 0.025 + 0.025 * (level - 20) / 10
    falloff = 0.50 + 0.30 * (level - 1) / 19 if level <= 20 else 0.80 + 0.10 * (level - 20) / 10
    weights = [falloff ** i for i in range(9)]
    total = sum(weights)
    return [(1 - daedric) * w / total for w in weights] + [daedric]


def zscores(counts, expected):
    n = sum(counts)
    if n == 0:
        return [0.0] * len(counts)
    return [(c - n * p) / math.sqrt(n * p * (1 - p)) if 0 < p < 1 else (0.0 if c == 0 else float("inf")) for c, p in zip(counts, expected)]


def odds(level):
    """Material shares from -dfworldleveltest's materialodds lines against the approved table (|z| < 4 per tier)."""
    body = read(REVIEW / "run" / f"level{level}-df.log")
    rows = {}
    for mode, lvl, source, rest in re.findall(r"materialodds: (\w+) level (\d+) (\w+) (rolls .*)", body):
        m = re.match(r"rolls (\d+) weapon ([\d,]+) plate ([\d,]+) leather (\d+) chain (\d+)", rest)
        weapon = [int(x) for x in m.group(2).split(",")]
        plate = [int(x) for x in m.group(3).split(",")]
        rows[(mode, int(lvl), source)] = (int(m.group(1)), weapon, plate, int(m.group(4)), int(m.group(5)))
    for line in re.findall(r"materialodds: \w+ done .*", body):
        print(line)
    if not rows:
        print("no materialodds lines in", REVIEW / "run" / f"level{level}-df.log")
        return False
    ok = True
    if not any(k[0] == "quest" for k in rows):
        print("no quest reward materialodds line (DoomerfallQuestRewardTest)")
        ok = False
    for mode in ("approved", "quest", "classic"):
        for lvl in sorted({k[1] for k in rows if k[0] == mode}):
            sources = sorted(k[2] for k in rows if k[0] == mode and k[1] == lvl)
            total = [0] * 10
            leather = chain = 0
            print(f"\n{mode} odds, area level {lvl}")
            for source in sources:
                _, weapon, plate, le, ch = rows[(mode, lvl, source)]
                items = [a + b for a, b in zip(weapon, plate)]
                total = [a + b for a, b in zip(total, items)]
                leather += le
                chain += ch
                z = zscores(items, approved(lvl))
                print(f"  {source:8s} n={sum(items):6d}  max|z| {max(abs(x) for x in z):5.2f}")
            exp = approved(lvl)
            z = zscores(total, exp)
            n = sum(total)
            print(f"  {'tier':10s} {'measured':>9s} {'approved':>9s} {'z':>6s}")
            for name, c, p, zz in zip(TIERS, total, exp, z):
                print(f"  {name:10s} {100 * c / n:8.2f}% {100 * p:8.2f}% {zz:6.2f}")
            armor = leather + chain + sum(sum(rows[(mode, lvl, s)][2]) for s in sources)
            print(f"  all n={n}  max|z| {max(abs(x) for x in z):.2f}  armor: leather {100 * leather / armor:.1f}% chain {100 * chain / armor:.1f}% plate {100 * (armor - leather - chain) / armor:.1f}% (n={armor})")
            fits = max(abs(x) for x in z) < 4
            if mode in ("approved", "quest"):
                ok = ok and fits
                print("  ->", "MATCHES approved table" if fits else "DOES NOT MATCH approved table")
            else:
                print("  ->", "differs from approved table (expected, classic formula)" if not fits else "SAME as approved (test not sensitive)")
    print("\nmaterial odds:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "odds":
        odds(int(sys.argv[2]))
        sys.exit(0)
    if len(sys.argv) >= 2 and sys.argv[1] == "assemble":
        assemble(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif len(sys.argv) == 3 and sys.argv[1] == "run":
        run(int(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        compare(int(sys.argv[2]), int(sys.argv[3]))
    else:
        sys.exit(__doc__)
