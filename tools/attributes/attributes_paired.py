"""Attributes in Doom (card 01): Strength raises melee damage, Speed changes movement speed.

usage:
  python tools/attributes/attributes_paired.py stock  <uzdoom build Release dir> <work folder>
  python tools/attributes/attributes_paired.py paired <play folder> <uzdoom build Release dir> <dfu build folder>
      <bridge build Release dir> <launcher build Release dir> <work folder>

stock: startup checks (-norun, exit 1337) for DOOM.WAD alone and with play_drlax.bat's DRLA set, then E1M1 stock and with
DRLA plus doomerfall.pk3 and the harness (attributes_paired.zs), with no Daggerfall. Checks: no script errors, the
effects item is never given, and fists, chainsaw and pistol deal the same damage and movement is unscaled.

paired: <play folder> is a paired play folder (doomerfall-launcher.exe, uzdoom/, dfu/ with a portable Daggerfall Unity).
It is copied once to <work folder>/play; its uzdoom/ gets the given build, its dfu/ the given Daggerfall Unity build and
bridge DLL, and the launcher is replaced, so every part matches this checkout's bridge layout.
One launch through the launcher and quiet_run.py: UZDoom on DOOM.WAD E1M1 with the DRLA set, doomerfall.pk3 and the
harness, the harness walking forward; Daggerfall Unity with -dfsynctest and -dfattrtest, which sets Strength and Speed to 0, 100,
50 and 10 in turn. Checks, for every report with a Daggerfall character: fists and chainsaw deal pistol damage times
1 + Strength/100 (Doom's integer rounding), the speed factor is 0.75 + Speed/200, and low and high values were both
seen, with the distance walked in 12 tics in the ratio of the speed factors. Source checks (Strength above 0, really
holding fists): a rocket fired from a pistol and a barrel credited to the player do pistol damage, while a rocket fired
while holding fists and a direct fist hit are boosted.
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
LINE = re.compile(r"ATTR str=(-?\d+) spd=(-?\d+) fist=(\d+) saw=(\d+) pistol=(\d+) move=([\d.]+) tweak=([\d.]+) item=(\d) climb=(-?[\d.]+)")
SRC = re.compile(r"ATTRSRC str=(\d+) gunrocket=(\d+) meleerocket=(\d+) barrel=(\d+) player=(\d+) pistol=(\d+) held=(\w+) punch=(\d+)"
                 r" null=(\d+) bfg=(\d+) gunboom=(-?\d+) gunlate=(-?\d+) meleeboom=(-?\d+) meleelate=(-?\d+)")
REF = re.compile(r"ATTRREF boom=(-?\d+) late=(-?\d+)")
BAD = re.compile(r'Script error, "(doomerfall|attr-harness)\.pk3|(doomerfall|attr-harness)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
BG = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0"]


def harness(work):
    path = work / "attr-harness.pk3"
    with zipfile.ZipFile(path, "w") as z:
        z.write(Path(__file__).with_name("attributes_paired.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "AttrPaired" }\n')
    return path


def build_mod(target):
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(target)], check=True)


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []


def reports(lines):
    return [(int(a), int(b), int(c), int(d), int(e), float(f), float(g), int(h), float(i)) for a, b, c, d, e, f, g, h, i in
            (m.groups() for m in map(LINE.search, lines) if m)]


def climb_unchanged(rs):
    # Climbing speed (DoomerfallClimb.GroundSpeed) must not follow Speed until the owner decides it should.
    return bool(rs) and all(r[8] > 0 and abs(r[8] - rs[0][8]) < 1e-6 for r in rs)


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
        checks.append((f"{label}: no character, no effects item, damage and speed unchanged",
                       bool(rs) and all(r[0] == -1 and r[7] == 0 and r[2] == r[3] == r[4] and abs(r[6] - 1) < 1e-6 for r in rs)))
        checks.append((f"{label}: climbing speed reported", climb_unchanged(rs)))
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
    # As scripts/play/install.py does: this checkout's Daggerfall Unity, bridge DLL and launcher, so the layouts match.
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
    uz_log, df_log, con_log = run / "attr-uz.log", run / "attr-df.log", run / "log-attr.txt"
    for p in (uz_log, df_log, con_log):
        p.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "attr.ini"), "-dfbridgelog", str(uz_log), "+logfile", "attr", "-nosound",
          "-skill", "3", "-nomonsters", "+map", "E1M1"] + BG
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfattrtest", "-screen-fullscreen", "0", "-screen-width",
          "640", "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", "110", "--", str(play / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", IWAD, "--uzdoom-cwd", str(run), "--log", str(run / "attr-launcher.log")]
    for mod in DRLA + [play / "doomerfall.pk3", harn]:
        command += ["--mod", str(mod)]
    for a in uz:
        command += ["--uzdoom-arg", a]
    for a in df:
        command += ["--dfu-arg", a]
    print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)
    con, dfl = read(con_log), read(df_log)
    print("Daggerfall:", "; ".join(l.split("attr test: ", 1)[1] for l in dfl if "attr test: " in l))
    rs = reports(con)
    for r in rs:
        print("  ", r)
    live = [r for r in rs if r[0] >= 0]
    checks = [("no script errors", bool(con) and not any(BAD.search(l) for l in con)),
              ("reports with a Daggerfall character", bool(live)),
              ("effects item held whenever there is a character", bool(live) and all(r[7] == 1 for r in live))]
    melee = lambda r, x: x == max(1, int(r[4] * (1 + min(r[0], 100) / 100.0)))
    checks.append(("fists deal pistol damage x (1 + Strength/100)", bool(live) and all(melee(r, r[2]) for r in live)))
    checks.append(("chainsaw deals pistol damage x (1 + Strength/100)", bool(live) and all(melee(r, r[3]) for r in live)))
    checks.append(("speed factor is 0.75 + Speed/200", bool(live) and all(abs(r[6] - (0.75 + min(r[1], 100) / 200.0)) < 1e-3 for r in live)))
    low = [r for r in live if r[0] <= 10 and r[1] <= 10]
    high = [r for r in live if r[0] >= 100 and r[1] >= 100]
    checks.append(("low (<= 10) and high (100) Strength and Speed both seen", bool(low) and bool(high)))
    if low and high:
        lo, hi = min(low, key=lambda r: r[1]), high[0]
        print(f"low  str {lo[0]} spd {lo[1]}: fist {lo[2]} saw {lo[3]} pistol {lo[4]} walked {lo[5]:.1f} in 12 tics")
        print(f"high str {hi[0]} spd {hi[1]}: fist {hi[2]} saw {hi[3]} pistol {hi[4]} walked {hi[5]:.1f} in 12 tics")
        want = hi[6] / lo[6]
        got = hi[5] / lo[5] if lo[5] > 0 else 0
        print(f"walk ratio high/low {got:.3f}, speed factor ratio {want:.3f}")
        checks.append(("high Strength hits harder with melee than low", hi[2] > lo[2] and hi[3] > lo[3]))
        checks.append(("walked distance follows the speed factor (within 5%)", lo[5] > 0 and abs(got / want - 1) < 0.05))
    # The bonus follows the attack that dealt the damage, not the weapon held when it lands.
    src = [m for m in map(SRC.search, con) if m]
    for m in src:
        print("  ", m.group(0))
    checks.append(("source test ran with Strength above 0, holding fists", bool(src)))
    if src:
        gr = src[0].groups()
        s, g, mr, b, pl, pc = (int(x) for x in gr[:6])
        punch, null, bfg, ge, gl, me, ml = (int(x) for x in gr[7:14])
        f = 1 + min(s, 100) / 100.0
        boost = lambda d: max(1, int(d * f))
        print(f"source test str {s}, holding {gr[6]}: pistol {pc} (boosted would be {boost(pc)}); gun rocket {g}, fist rocket {mr},"
              f" barrel {b}, player as inflictor {pl}, no inflictor {null}, BFG tracer {bfg}, punch {punch};"
              f" explosions gun {ge}/{gl} late, fist {me}/{ml} late")
        checks.append(("held fists for the source test", gr[6] in ("Fist", "RLFist")))
        checks.append(("gun-fired rocket landing while fists are held is not boosted", g == pc and boost(pc) > pc))
        checks.append(("barrel credited to the player is not boosted", b == pc))
        checks.append(("player as inflictor is not boosted", pl == pc))
        checks.append(("no inflictor is not boosted", null == pc))
        checks.append(("BFG tracer (A_BFGSpray) while fists are held is not boosted", bfg == pc))
        checks.append(("rocket fired while holding fists is boosted (traced to the melee attack)", mr == boost(pc)))
        checks.append(("real hitscan punch (puff as inflictor) is boosted", punch == boost(pc)))
        ref = [m for m in map(REF.search, con) if m]
        re_, rl = (int(x) for x in ref[0].groups()) if ref else (-1, -1)
        print(f"reference explosion without the effects item: {re_} / {rl} late")
        checks.append(("gun rocket's real explosion is not boosted, fist rocket's is", re_ > 0 and ge == re_ and me == boost(re_)))
        checks.append(("late death-frame splash (MISSILE cleared): gun not boosted, fist boosted", rl > 0 and gl == rl and ml == boost(rl)))
    checks.append(("climbing speed does not follow Speed", climb_unchanged(live)))
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
