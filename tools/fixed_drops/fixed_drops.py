"""Fixed Doom drops: every monster in Privateer's Hold is killed in fresh UZDoom processes, and what they drop is compared.

usage: fixed_drops.py [LEVEL] [--stock]

Runs UZDoom alone (no Daggerfall) with -ddenctest LEVEL -ddloottest on the encounter placer's Privateer's Hold map,
with the DRLA set (DRLA Arsenal, DRLA Monsters, DRLAX) unless --stock. Each run places the encounters, claims DRLA's
spawned monsters as a bridge session would, adds 8 unplaced control monsters next to the player (no id, so their
drops stay unseeded), kills everything at map time 120, and lists every monster and every loose item at 300.

Four runs: a, b (two fresh games), save (saves at map time 100, before the kill) and load (loads that save, then kills).
Each process has its own random seed. PASS needs: the same mooks, and the same drops (class, lasting id and spot) from
them in all four runs. The control monsters' drops are printed for comparison; they are expected to differ.
Game data and generated maps stay outside the repo (review folder).
"""
import re
import subprocess
import sys
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\fixed-drops")
PLACER = Path(r"D:\dev\DoomDaggerfall-loop\review\encounter-placer")
DATA = Path(r"D:\dev\DoomDaggerfall-loop\review\encounter-facts\data")
WORKTREE = Path(__file__).resolve().parents[2]
UZ = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-items\Release\uzdoom.exe")
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
FATAL = ("VM execution aborted", "Unhandled exception", "Execution could not continue", "FATAL")


def launch(name, level, stock, extra):
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    log = runs / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    files = ([] if stock else [str(MODS / n) for n in DRLA]) + [str(DATA / n) for n in ("ddruntime.pk3", "overworld.pk3")] + \
        [str(PLACER / "wad" / "placer_privateershold.wad")] + [str(DATA / n) for n in ("privateershold_mesh.pk3", "privateershold_doors.pk3")] + \
        [str(WORKTREE / "mods" / "doomerfall" / "src")]
    args = [str(UZ), "-iwad", IWAD, "-file", *files, "-noactivate", "-nosound", "-noautoload", "-config", str(runs / "fixed.ini"), "-skill", "3",
            "-ddenctest", str(level), "-ddloottest", "+logfile", name, "+vid_fullscreen", "0", "+i_pauseinbackground", "0",
            "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+set", "save_dir", REVIEW.as_posix()] + extra
    code = subprocess.call([sys.executable, QUIET, "--timeout", "45", "--cwd", str(runs), "--", *args],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    body = log.read_text(errors="replace") if log.exists() else ""
    fatal = [k for k in FATAL if k in body]
    print(f"{name}: exit {code}, log {len(body)} bytes, fatal {fatal or 'none'}, done {'DDLOOTTEST done' in body or 'quit' in extra}")
    return body


def rows(body):
    mooks, drops, control, cdrops = [], [], [], []
    for line in body.splitlines():
        m = re.match(r"DDLOOT (mook|control|item) (.*)", line)
        if not m:
            continue
        kind, rest = m.groups()
        # Spots are left out: a living monster wanders and gets pushed by stock AI, so where it dies (and where its drops
        # land) is combat, not loot.
        rest = re.sub(r" at \S+$", "", rest)
        if kind == "mook":
            mooks.append(rest)
        elif kind == "control":
            control.append(rest)
        elif " id 0000000000000000" in rest:
            cdrops.append(re.sub(r" id 0+$", "", rest))   # unseeded: class only
        else:
            drops.append(rest)
    return sorted(mooks), sorted(drops), control, cdrops


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    level = int(args[0]) if args else 10
    stock = "--stock" in sys.argv
    tag = "stock" if stock else "drla"
    out = {}
    out["a"] = rows(launch(f"{tag}-a", level, stock, ["+map", "MAP01"]))
    out["b"] = rows(launch(f"{tag}-b", level, stock, ["+map", "MAP01"]))
    launch(f"{tag}-save", level, stock, ["-ddtestsave", "100", f"fixed-{tag}", "-ddtestquit", "105", "+map", "MAP01"])
    out["load"] = rows(launch(f"{tag}-load", level, stock, ["-loadgame", f"fixed-{tag}.zds"]))
    a = out["a"]
    ok = bool(a[0]) and bool(a[1])
    print(f"run a: {len(a[0])} mooks ({sum(r.endswith(' dead 1') for r in a[0])} dead), {len(a[1])} drops with a lasting id, "
          f"{len(a[2])} controls, {len(a[3])} items without an id")
    for name in ("b", "load"):
        o = out[name]
        same_mooks, same_drops = o[0] == a[0], o[1] == a[1]
        ok &= same_mooks and same_drops
        print(f"a vs {name}: mooks {'identical' if same_mooks else 'DIFFER'} ({len(o[0])}), drops {'identical' if same_drops else 'DIFFER'} ({len(o[1])})")
        if not same_drops:
            only_a, only_o = sorted(set(a[1]) - set(o[1])), sorted(set(o[1]) - set(a[1]))
            print(f"  only in a: {only_a[:8]}\n  only in {name}: {only_o[:8]}")
        print(f"  control drops a: {sorted(a[3])}\n  control drops {name}: {sorted(o[3])}")
    classes = {}
    for r in a[1]:
        c = r.split()[0]
        classes[c] = classes.get(c, 0) + 1
    print("drop classes in run a:", ", ".join(f"{c} x{n}" for c, n in sorted(classes.items())))
    print("FIXED DROPS", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
