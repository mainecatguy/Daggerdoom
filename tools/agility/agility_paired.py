"""Attributes in Doom (card 02): Agility speeds reloads and weapon switches and gives a chance to evade damage.

usage:
  python tools/agility/agility_paired.py stock  <uzdoom build Release dir> <work folder>
  python tools/agility/agility_paired.py paired <play folder> <uzdoom build Release dir> <dfu build folder>
      <bridge build Release dir> <launcher build Release dir> <work folder>

stock: startup checks (-norun, exit 1337) for DOOM.WAD alone and with play_drlax.bat's DRLA set, then E1M1 stock and with
DRLA plus doomerfall.pk3 and the harness (agility_paired.zs), with no Daggerfall. Checks: no script errors, the Agility
item is never given, nothing is evaded, and switch and reload times are measured (the unchanged baseline).

paired: as tools/attributes/attributes_paired.py (card 01): <play folder> is copied once to <work folder>/play and gets
this checkout's UZDoom, Daggerfall Unity, bridge DLL and launcher. One launch through the launcher and quiet_run.py:
UZDoom on DOOM.WAD E1M1 with the DRLA set, doomerfall.pk3 and the harness; Daggerfall Unity with -dfsynctest and
-dfagilitytest, which sets Agility to 0, 100, 50 and 10 in turn, twice. Checks: the item is held, low and high Agility
were both measured, reload and switch at 100 take about 1/1.4 of the time at 0, every measurement's times follow
1 / (1 + 0.4 x Agility/100) against the Agility 0 baseline, evasion is about 15% x Agility/100 of the hits, and
self-damage, attacker-less damage and telefrags are never evaded.
"""
import math
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
LINE = re.compile(r"AGI agi=(-?\d+) item=(\d) weapon=(\w+) switch=(-?\d+) reload=(-?\d+) evade=(\d+) of=(\d+) self=(\d+) null=(\d+) tele=(\d+)")
BAD = re.compile(r'Script error, "(doomerfall|agi-harness)\.pk3|(doomerfall|agi-harness)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
BG = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0"]


def harness(work):
    path = work / "agi-harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.write(Path(__file__).with_name("agility_paired.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AgiPaired" }\n')
    return path


def build_mod(target):
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(target)], check=True)


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []


def reports(lines):
    out = []
    for m in map(LINE.search, lines):
        if m:
            g = m.groups()
            out.append(dict(agi=int(g[0]), item=int(g[1]), weapon=g[2], switch=int(g[3]), reload=int(g[4]),
                            evade=int(g[5]), of=int(g[6]), self=int(g[7]), null=int(g[8]), tele=int(g[9])))
    return out


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
        rs = reports(lines)
        for r in rs:
            print(f"  {label}:", r)
        checks.append((f"{label}: no script errors", bool(lines) and not any(BAD.search(l) for l in lines)))
        checks.append((f"{label}: harness reported", bool(rs)))
        checks.append((f"{label}: no character, no Agility item, nothing evaded",
                       bool(rs) and all(r["agi"] == -1 and r["item"] == 0 and r["evade"] == r["self"] == r["null"] == r["tele"] == 0 for r in rs)))
        checks.append((f"{label}: switch measured", bool(rs) and all(r["switch"] > 0 for r in rs)))
        if label == "drla-e1m1":
            checks.append((f"{label}: DRLA reload measured", bool(rs) and all(r["reload"] > 0 for r in rs)))
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
    uz_log, df_log, con_log = run / "agi-uz.log", run / "agi-df.log", run / "log-agi.txt"
    for p in (uz_log, df_log, con_log):
        p.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "agi.ini"), "-dfbridgelog", str(uz_log), "+logfile", "agi", "-nosound",
          "-skill", "3", "-nomonsters", "+map", "E1M1"] + BG
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfagilitytest", "-screen-fullscreen", "0", "-screen-width",
          "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", "110", "--", str(play / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", IWAD, "--uzdoom-cwd", str(run), "--log", str(run / "agi-launcher.log")]
    for mod in DRLA + [play / "doomerfall.pk3", harn]:
        command += ["--mod", str(mod)]
    for a in uz:
        command += ["--uzdoom-arg", a]
    for a in df:
        command += ["--dfu-arg", a]
    print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)
    con, dfl = read(con_log), read(df_log)
    print("Daggerfall:", "; ".join(l.split("agility test: ", 1)[1] for l in dfl if "agility test: " in l))
    rs = reports(con)
    for r in rs:
        print("  ", r)
    live = [r for r in rs if r["agi"] >= 0]
    checks = [("no script errors", bool(con) and not any(BAD.search(l) for l in con)),
              ("reports with a Daggerfall character", bool(live)),
              ("Agility item held whenever there is a character", bool(live) and all(r["item"] == 1 for r in live)),
              ("switch and reload measured every time", bool(live) and all(r["switch"] > 0 and r["reload"] > 0 for r in live))]
    zero = [r for r in live if r["agi"] == 0]
    high = [r for r in live if r["agi"] >= 100]
    checks.append(("Agility 0 and 100 both measured", bool(zero) and bool(high)))
    if zero and high:
        bs = sum(r["switch"] for r in zero) / len(zero)
        br = sum(r["reload"] for r in zero) / len(zero)
        hs = sum(r["switch"] for r in high) / len(high)
        hr = sum(r["reload"] for r in high) / len(high)
        print(f"Agility 0: switch {bs:.1f} tics, reload {br:.1f} tics; Agility 100: switch {hs:.1f}, reload {hr:.1f}")
        print(f"speed-up at 100: switch x{bs / hs:.3f}, reload x{br / hr:.3f} (want x1.4)")
        checks.append(("reload at 100 is x1.4 faster (within 8%)", abs((br / hr) / 1.4 - 1) < 0.08))
        checks.append(("switch at 100 is x1.4 faster (within 12%, A_Raise and A_Lower move in steps)", abs((bs / hs) / 1.4 - 1) < 0.12))
        for r in live:
            want = 1 + 0.4 * min(r["agi"], 100) / 100.0
            print(f"  agility {r['agi']}: reload x{br / r['reload']:.3f}, switch x{bs / r['switch']:.3f}, want x{want:.3f};"
                  f" evaded {r['evade']} of {r['of']} ({100.0 * r['evade'] / r['of']:.1f}%, want {15 * min(r['agi'], 100) / 100.0:.1f}%)")
        checks.append(("every reload time follows 1 / (1 + 0.4 x Agility/100) (within 8%)",
                       all(abs((br / r["reload"]) / (1 + 0.4 * min(r["agi"], 100) / 100.0) - 1) < 0.08 for r in live)))
    # Evasion: binomial, 4 standard deviations, against 15% x Agility/100.
    def evade_ok(r):
        p = 0.15 * min(r["agi"], 100) / 100.0
        sd = math.sqrt(max(p * (1 - p), 1e-9) / r["of"])
        return abs(r["evade"] / r["of"] - p) <= 4 * sd + 1e-9
    checks.append(("evaded share is 15% x Agility/100 (within 4 standard deviations)", bool(live) and all(evade_ok(r) for r in live)))
    checks.append(("high Agility evades some hits, Agility 0 none", bool(high) and bool(zero) and all(r["evade"] > 0 for r in high)
                   and all(r["evade"] == 0 for r in zero)))
    checks.append(("self-damage, attacker-less damage and telefrags never evaded",
                   bool(live) and all(r["self"] == r["null"] == r["tele"] == 0 for r in live)))
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
