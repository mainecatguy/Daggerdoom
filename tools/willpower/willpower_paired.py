"""Attributes in Doom (card 03): Willpower is a final modifier to all damage the player takes.

usage:
  python tools/willpower/willpower_paired.py stock  <uzdoom build Release dir> <work folder>
  python tools/willpower/willpower_paired.py paired <play folder> <uzdoom build Release dir> <dfu build folder>
      <bridge build Release dir> <launcher build Release dir> <work folder>

stock: startup checks (-norun, exit 1337) for DOOM.WAD alone and with play_drlax.bat's DRLA set, then E1M1 stock and with
DRLA plus doomerfall.pk3 and the harness (willpower_paired.zs), with no Daggerfall. Checks: no script errors, the harness
sees no character (-1) and runs no damage windows.

paired: as tools/agility/agility_paired.py: <play folder> is copied once to <work folder>/play and gets this checkout's
UZDoom, Daggerfall Unity, bridge DLL and launcher. One launch through the launcher and quiet_run.py: UZDoom on DOOM.WAD
E1M1 with the DRLA set, doomerfall.pk3 and the harness; Daggerfall Unity with -dfsynctest and -dfwillpowertest, which
sets Willpower to 1, 100, 50 and 75 in turn. For each value the harness hurts the real player from hitscan,
projectile, melee, environment (sector damage), layered (a test armor absorbing a flat 2 of 5) and direct (health
lowered by assignment) sources. Checks: every logged hit is exactly (damage x (300 - Willpower) + carry) / 250; per
window: every hit reaching the Willpower step logged its damage in and out; the damage in on the layered window is 3
(after the armor, so Willpower comes last); the damage out totals damage in x (1.2 - 0.4 x Willpower/100) within one
point; Daggerfall's HP dropped by exactly the damage out; and against Willpower 50 each source's damage at 1 and 100
changes by the expected factor.
"""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [MODS / f for f in ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]]
WINDOW = re.compile(r"WILL src=(\w+) will=(-?\d+) nominal=(\d+) before=(-?\d+) after=(-?\d+) from=(\d+) to=(\d+)")
SEEN = re.compile(r"WILLSEEN will=(-?\d+)")
HIT = re.compile(r"willpower: tic (\d+) player takes (\d+) -> (\d+) \(willpower (-?\d+)\)")
BAD = re.compile(r'Script error, "(doomerfall|will-harness)\.pk3|(doomerfall|will-harness)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
BG = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0"]
SOURCES = ["hitscan", "projectile", "melee", "environment", "layered", "direct"]


def factor(will):
    return 1.2 - 0.4 * min(max(will, 0), 100) / 100.0


def harness(work):
    path = work / "will-harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.write(Path(__file__).with_name("willpower_paired.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "WillPaired" }\n')
    return path


def build_mod(target):
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(target)], check=True)


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []


def stock(build, work):
    exe = str(Path(build) / "uzdoom.exe")
    mod = work / "doomerfall.pk3"
    build_mod(mod)
    harn = harness(work)
    checks = []
    for label, files in (("stock", []), ("drla", DRLA)):
        cmd = [sys.executable, QUIET, "--timeout", "40", "--cwd", str(work), "--", exe, "-iwad", IWAD, "-norun", "-stdout",
               "-config", str(work / f"{label}.ini")]
        if files:
            cmd[cmd.index("-norun"):cmd.index("-norun")] = ["-file"] + [str(f) for f in files]
        code = subprocess.run(cmd, capture_output=True, text=True).returncode
        checks.append((f"{label} startup exit 1337 (quiet_run shows its low byte 57)", code in (1337, 57)))
    for label, files in (("stock-e1m1", [mod, harn]), ("drla-e1m1", DRLA + [mod, harn])):
        log = work / f"log-{label}.txt"
        log.unlink(missing_ok=True)
        cmd = [sys.executable, QUIET, "--timeout", "25", "--cwd", str(work), "--", exe, "-iwad", IWAD, "-file"] + \
              [str(f) for f in files] + ["-config", str(work / f"{label}.ini"), "-skill", "3", "-nomonsters", "+map", "E1M1",
                                         "+logfile", label] + BG
        subprocess.run(cmd, capture_output=True, text=True)
        lines = read(log)
        seen = [int(m.group(1)) for m in map(SEEN.search, lines) if m]
        print(f"  {label}: harness saw willpower {seen}")
        checks.append((f"{label}: no script errors", bool(lines) and not any(BAD.search(l) for l in lines)))
        checks.append((f"{label}: harness ran and saw no character (-1)", seen == [-1]))
        checks.append((f"{label}: no damage windows, no Willpower step", not any(WINDOW.search(l) or HIT.search(l) for l in lines)))
    return checks


def copy_over(src, dst):
    for f in Path(src).iterdir():
        if f.is_dir():
            shutil.rmtree(dst / f.name, ignore_errors=True)
            shutil.copytree(f, dst / f.name)
        else:
            shutil.copy2(f, dst / f.name)


def paired(source, build, dfu, bridge, launcher, work):
    play = work / "play"
    if not play.exists():
        shutil.copytree(source, play, ignore=shutil.ignore_patterns("run", "PortableAppdata"))
    for f in Path(build).iterdir():
        if f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, play / "uzdoom" / f.name)
    copy_over(dfu, play / "dfu")
    plugins = play / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(bridge) / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (play / "dfu" / "Portable.txt").write_text("")
    sys.path.insert(0, str(REPO / "scripts" / "play"))
    import install
    install.isolate_registry(play / "dfu")
    shutil.copy2(Path(launcher) / "doomerfall-launcher.exe", play / "doomerfall-launcher.exe")
    build_mod(play / "doomerfall.pk3")
    harn = harness(work)
    run = play / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log, con_log = run / "will-uz.log", run / "will-df.log", run / "log-will.txt"
    for p in (uz_log, df_log, con_log):
        p.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "will.ini"), "-dfbridgelog", str(uz_log), "+logfile", "will", "-nosound",
          "-skill", "3", "-nomonsters", "+map", "E1M1"] + BG
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfwillpowertest", "40", "-screen-fullscreen", "0", "-screen-width",
          "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", "230", "--", str(play / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", IWAD, "--uzdoom-cwd", str(run), "--log", str(run / "will-launcher.log")]
    for mod in DRLA + [play / "doomerfall.pk3", harn]:
        command += ["--mod", str(mod)]
    for a in uz:
        command += ["--uzdoom-arg", a]
    for a in df:
        command += ["--dfu-arg", a]
    print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)
    con, dfl, uzl = read(con_log), read(df_log), read(uz_log)
    print("Daggerfall:", "; ".join(l.split("willpower test: ", 1)[1] for l in dfl if "willpower test: " in l))
    hits = [tuple(int(x) for x in m.groups()) for m in map(HIT.search, uzl) if m]
    windows = []
    for m in map(WINDOW.search, con):
        if m:
            g = m.groups()
            windows.append(dict(src=g[0], will=int(g[1]), nominal=int(g[2]), before=int(g[3]), after=int(g[4]),
                                start=int(g[5]), end=int(g[6])))
    checks = [("no script errors", bool(con) and not any(BAD.search(l) for l in con)),
              ("Willpower step logged hits", bool(hits)),
              ("Willpower step log not capped", len(hits) < 1000)]
    by = {}
    for w in windows:
        hs = [h for h in hits if w["start"] <= h[0] <= w["end"]]
        w["n"], w["din"], w["dout"] = len(hs), sum(h[1] for h in hs), sum(h[2] for h in hs)
        w["logwill"] = sorted({h[3] for h in hs})
        w["drop"] = w["before"] - w["after"]
        print(f"  willpower {w['will']:3d} {w['src']:11s} nominal {w['nominal']:2d}  in {w['din']:2d} ({w['n']} hits)  out "
              f"{w['dout']:2d} (want {w['din'] * factor(w['will']):.1f})  Daggerfall HP {w['before']} -> {w['after']} (-{w['drop']})")
        by[(w["will"], w["src"])] = w
    wills = sorted({w["will"] for w in windows})
    # Exact per hit: replay the integer rule (300 - Willpower) / 250 with its carry over every logged hit, in order.
    carry, exact = 0, bool(hits)
    for _, din, dout, w in hits:
        units = din * (300 - min(w, 100)) + carry
        exact = exact and dout == units // 250
        carry = units % 250
    checks.append(("every logged hit is exactly (damage x (300 - Willpower) + carry) / 250", exact))
    checks.append(("all six sources measured at Willpower 1, 50 and 100",
                   all((v, s) in by for v in (1, 50, 100) for s in SOURCES)))
    checks.append(("every window took hits and logged the Daggerfall value", bool(windows) and
                   all(w["n"] > 0 and w["logwill"] == [w["will"]] for w in windows)))
    checks.append(("layered: damage reaching the Willpower step is after the armor (3 per hit)",
                   bool(windows) and all(w["din"] == 3 * w["n"] for w in windows if w["src"] == "layered")))
    checks.append(("damage out = damage in x (1.2 - 0.4 x Willpower/100), within one point",
                   bool(windows) and all(abs(w["dout"] - w["din"] * factor(w["will"])) < 1.0 for w in windows)))
    checks.append(("Daggerfall's HP dropped by exactly the damage out", bool(windows) and all(w["drop"] == w["dout"] for w in windows)))
    # Against Willpower 50 (x1), per source: Daggerfall's HP drop per hit that reached the step.
    for v in (1, 100):
        ok = True
        for s in SOURCES:
            a, b = by.get((v, s)), by.get((50, s))
            if not a or not b or not a["n"] or not b["n"]:
                ok = False
                continue
            ratio = (a["drop"] / a["n"]) / (b["drop"] / b["n"])
            print(f"  {s:11s} willpower {v} vs 50: x{ratio:.3f} (want x{factor(v):.3f})")
            ok = ok and abs(ratio - factor(v)) <= 1.5 / max(1, b["drop"]) * factor(v) + 0.03
        checks.append((f"each source at Willpower {v} vs 50 changes by x{factor(v):.3f}", ok))
    print("Willpower values measured:", wills)
    return checks


def main():
    a = sys.argv[1:]
    if a[:1] == ["stock"] and len(a) == 3:
        work = Path(a[2]); work.mkdir(parents=True, exist_ok=True)
        checks = stock(a[1], work)
    elif a[:1] == ["paired"] and len(a) == 7:
        work = Path(a[6]); work.mkdir(parents=True, exist_ok=True)
        checks = paired(Path(a[1]), a[2], a[3], a[4], a[5], work)
    else:
        sys.exit(__doc__)
    for label, ok in checks:
        print(("PASS " if ok else "FAIL ") + label)
    failed = sum(1 for _, ok in checks if not ok)
    print("RESULT", "PASS" if not failed else f"FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
