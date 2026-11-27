"""Paired check: a weapon in two skills uses whichever of them is higher in Daggerfall's live character sheet.

usage: python tools/weapon_category/twoskill_paired.py <play folder> <uzdoom build Release dir> <work folder>

<play folder> is a paired play folder (doomerfall-launcher.exe, uzdoom/, dfu/ with a portable Daggerfall Unity, as
scripts/play/install.py or a merge folder makes). It is copied once to <work folder>/play and its uzdoom/ is replaced
by the given build. One launch through the launcher and quiet_run.py, about a minute: UZDoom on DOOM.WAD E1M1 with
play_drlax.bat's DRLA set, doomerfall.pk3 and the test harness (twoskill_paired.zs); Daggerfall Unity with -dfsynctest
and -dfsheettest, which changes the character's skills, levels up, saves, loads and makes a new character, so Doom
sees several different sheets. The harness holds an energy shotgun (Energy + Shotgun) and an energy pistol (Pistol +
Energy) in turn and logs what each reads.

Checks: both guns report two categories; with a character, every report uses the higher of its two live skills (the
first on a tie); and the second skill won at least once and the first won at least once with a clear lead, so
the choice really follows the sheet.
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
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
SECONDS = 75
LINE = re.compile(r"TWOSKILL (\w+) first=(\w+):(-?\d+):(-?\d+) second=(\w+):(-?\d+):(-?\d+) uses=(-?\d+)")
# Errors in our own pk3s, or any fatal one. DRLA prints its own harmless menu and translation script errors.
BAD = re.compile(r'Script error, "(doomerfall|twoskill-harness)\.pk3|(doomerfall|twoskill-harness)\.pk3:zscript\S*, line \d+|\bFatal error|VM execution aborted', re.I)
EXPECT = {"RLPlasmaShotgun": ("energy", "shotgun"), "RLPlasmaPistol": ("pistol", "energy")}


def assemble(source, build, work):
    play = work / "play"
    if not play.exists():
        shutil.copytree(source, play, ignore=shutil.ignore_patterns("run"))
    for f in Path(build).iterdir():
        if f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, play / "uzdoom" / f.name)
    subprocess.run([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(play / "doomerfall.pk3")], check=True)
    harness = work / "twoskill-harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.write(Path(__file__).with_name("twoskill_paired.zs"), "zscript.txt")
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "TwoSkillPaired" }\n')
    return play, harness


def launch(play, harness):
    run = play / "run"
    run.mkdir(exist_ok=True)
    # +logfile takes a plain name and writes log-<name>.txt in UZDoom's working folder (run).
    uz_log, df_log, con_log = run / "twoskill-uz.log", run / "twoskill-df.log", run / "log-twoskill.txt"
    for path in (uz_log, df_log, con_log):
        path.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "twoskill.ini"), "-dfbridgelog", str(uz_log), "+logfile", "twoskill", "-nosound",
          "-skill", "3", "-nomonsters", "+map", "E1M1", "+vid_fullscreen", "0", "+i_pauseinbackground", "0",
          "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-dfsheettest", "-screen-fullscreen", "0", "-screen-width", "640",
          "-screen-height", "360"]
    command = [sys.executable, QUIET, "--timeout", str(SECONDS), "--", str(play / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(run / "twoskill-launcher.log")]
    for mod in [MODS / f for f in DRLA] + [play / "doomerfall.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)
    read = lambda p: p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []
    return read(con_log), read(df_log)


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    work = Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    play, harness = assemble(Path(sys.argv[1]), sys.argv[2], work)
    con, df = launch(play, harness)
    steps = [l.split("sheet test: ", 1)[1] for l in df if "sheet test: " in l]
    print("Daggerfall sheet test steps:", ", ".join(steps))
    reports = [m.groups() for m in map(LINE.search, con) if m]
    for r in reports:
        print("  ", " ".join(r))
    checks = [("no script errors", not any(BAD.search(l) for l in con)), ("harness reported", bool(reports))]
    for gun, (first, second) in EXPECT.items():
        mine = [r for r in reports if r[0] == gun]
        checks.append((f"{gun} is {first} + {second}", bool(mine) and all(r[1] == first and r[4] == second for r in mine)))
    live = [r for r in reports if int(r[3]) >= 0 and int(r[6]) >= 0]
    checks.append(("reports with a Daggerfall character", bool(live)))
    higher = lambda r: r[5] if int(r[6]) > int(r[3]) else r[2]
    wrong = [r for r in live if r[7] != higher(r)]
    checks.append(("every report uses the higher live skill (first on a tie)", bool(live) and not wrong))
    checks.append(("the second skill won when it was higher", any(int(r[6]) > int(r[3]) and r[7] == r[5] for r in live)))
    checks.append(("the first skill won when it was higher", any(int(r[3]) > int(r[6]) and r[7] == r[2] for r in live)))
    for label, ok in checks:
        print(("PASS " if ok else "FAIL ") + label)
    for r in wrong:
        print("  wrong:", r)
    failed = sum(1 for _, ok in checks if not ok)
    print("RESULT", "PASS" if not failed else f"FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
