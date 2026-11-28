"""Attribute rework (owner, 2026-11-27) in a real paired game: Daggerfall Unity sends the attributes, Doom applies them.

usage:
  python tools/attributes/attributes_rework_paired.py <play folder> <uzdoom build Release dir> <dfu build folder>
      <bridge build Release dir> <launcher build Release dir> <work folder>

As tools/attributes/attributes_paired.py paired: <play folder> is copied once to <work folder>/play and gets this
checkout's UZDoom, Daggerfall Unity, bridge DLL and launcher. One launch through the launcher and quiet_run.py: UZDoom on
DOOM.WAD E1M1 with the DRLA set, doomerfall.pk3, doomerfall-drla.pk3 and the harness (attributes_rework.zs, with
attrrw_nohits so the player is never really hit); Daggerfall Unity with -dfsynctest and "-dfattrtest 9 rework", which
sets Strength, Agility and Luck to each triple of PAIRED in turn through Daggerfall's own stats (1 is the lowest living
value). The checks are attributes_rework_test.py's: each weapon's curve against the all-50 triple, no dodge, no crits
at Luck 50, about 5% at Luck 100, blasts all-or-none, burn ticks never crit.
"""
import shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import attributes_paired as ap  # noqa: E402
import attributes_rework_test as rt  # noqa: E402

# Must match DoomerfallAttributesTest.Rework (Strength, Agility, Luck).
PAIRED = {"n": (50, 50, 50), "s1": (1, 50, 50), "s100": (100, 50, 50), "a1": (50, 1, 50), "a100": (50, 100, 50),
          "x1": (1, 1, 50), "x100": (100, 100, 50), "l100": (50, 50, 100)}
ORDER = ["n", "s1", "s100", "a1", "a100", "x1", "x100", "l100"]


def main():
    source, build, dfu, bridge, launcher, work = (Path(a) for a in sys.argv[1:7])
    work.mkdir(parents=True, exist_ok=True)
    play = work / "play"
    if not play.exists():
        shutil.copytree(source, play, ignore=shutil.ignore_patterns("run", "PortableAppdata"))
    for f in build.iterdir():
        if f.suffix.lower() in (".exe", ".pk3", ".dll"):
            shutil.copy2(f, play / "uzdoom" / f.name)
    ap.copy_over(dfu, play / "dfu")
    plugins = play / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bridge / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (play / "dfu" / "Portable.txt").write_text("")
    sys.path.insert(0, str(ap.REPO / "scripts" / "play"))
    import install
    install.isolate_registry(play / "dfu")
    shutil.copy2(launcher / "doomerfall-launcher.exe", play / "doomerfall-launcher.exe")
    ap.build_mod(play / "doomerfall.pk3")
    subprocess.run([sys.executable, str(ap.REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(play / "doomerfall-drla.pk3")], check=True)
    harn = rt.harness_pk3(work / "attrrw.pk3")
    run = play / "run"
    run.mkdir(exist_ok=True)
    uz_log, df_log, con_log = run / "attrrw-uz.log", run / "attrrw-df.log", run / "log-attrrw.txt"
    for p in (uz_log, df_log, con_log):
        p.unlink(missing_ok=True)
    uz = ["-noactivate", "-config", str(run / "attrrw.ini"), "-dfbridgelog", str(uz_log), "+logfile", "attrrw", "-nosound",
          "-skill", "3", "-nomonsters", "+map", "E1M1", "+set", "attrrw_nohits", "1"] + ap.BG
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", ap.DAGGER, "-dfattrtest", "9", "rework", "-screen-fullscreen", "0",
          "-screen-width", "640", "-screen-height", "360"]
    command = [sys.executable, ap.QUIET, "--timeout", "200", "--", str(play / "doomerfall-launcher.exe"), "--minimized",
               "--uzdoom", str(play / "uzdoom" / "uzdoom.exe"), "--dfu", str(play / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", ap.IWAD, "--uzdoom-cwd", str(run), "--log", str(run / "attrrw-launcher.log")]
    for mod in ap.DRLA + [play / "doomerfall.pk3", play / "doomerfall-drla.pk3", harn]:
        command += ["--mod", str(mod)]
    for a in uz:
        command += ["--uzdoom-arg", a]
    for a in df:
        command += ["--dfu-arg", a]
    print("launcher exit", subprocess.run(command, capture_output=True, text=True).returncode)
    con, dfl = ap.read(con_log), ap.read(df_log)
    print("Daggerfall:", "; ".join(l.split("attr test: ", 1)[1] for l in dfl if "attr test: " in l))
    failures = []

    def check(name, label, ok, detail=None):
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {label}" + (f"  {detail}" if detail and not ok else ""), flush=True)
        if not ok:
            failures.append(label)

    check("paired", "Daggerfall's test ran to the end", any("attr test: done" in l for l in dfl))
    rt.analyse("paired", con, check, True, PAIRED, ORDER, paired=True)
    print("RESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
