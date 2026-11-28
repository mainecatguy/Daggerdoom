"""Paired test of Running skill uses from running in Doom (UZDoom dd_running.cpp -> DFB_KIND_RUN_TIME ->
DoomerfallRunning.cs). Daggerfall Unity's -dfrunningtest logs every Running tally; with "prime" it starts Running a few
seconds of running short of advancing and runs Daggerfall's skill check after each tally. Both games run on quiet_run's
private desktop.

usage: running.py assemble <source review folder> | run [NAME] [--no-prime] [--stock-mods] | check
assemble builds review\\running from a paired review folder (data, launcher, dfitems.pk3, uzdoom folder, Daggerfall
Unity portable settings) with this checkout's UZDoom, bridge DLL, Daggerfall Unity build and doomerfall pk3s, and writes
the demo play.bat.
run: the harness (harness.zs) phases stand, walk, run, runstand; this script holds Doom's buttons through the QA console.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\running")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-shoplvl" / "Release"   # this worktree's UZDoom build
BRIDGE_DLL = BUILD / "bridge-shoplvl" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-shoplvl" / "Release" / "doomerfall-launcher.exe"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
GROUP = 7154
DUNGEON = ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")
FATAL = ("DIED WITH FATAL", "errors while parsing", "error while compiling harness", "errors, 0 warnings while compiling",
         "VM execution aborted", "Execution could not continue", "Unable to open map")
PLUGIN = Path("DaggerfallUnity_Data") / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
TICS_PER_USE = 112 / 15   # Daggerfall: one use per 4 classic updates of 0.08 s = 0.32 s; x1.5 -> 0.2133 s = 7.467 tics
# What the runner holds at the start of each phase (QA console commands).
PRESS = {"walk": ["+forward", "+left"], "run": ["+speed"], "runstand": ["-forward", "-left"], "wall": ["+forward"],
         "pause": ["+left"], "done": ["-forward", "-left", "-speed"]}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data", "dfu"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(source / "data", REVIEW / "data")
    shutil.copytree(source / "uzdoom", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.ini", "*.log"))
    shutil.copy2(UZ_BUILD / "uzdoom.exe", REVIEW / "uzdoom" / "uzdoom.exe")
    for name in ("uzdoom.pk3", "game_support.pk3", "game_widescreen_gfx.pk3", "brightmaps.pk3", "lights.pk3"):
        if (UZ_BUILD.parent / name).exists() and (REVIEW / "uzdoom" / name).exists():
            shutil.copy2(UZ_BUILD.parent / name, REVIEW / "uzdoom" / name)
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    (REVIEW / "dfu" / PLUGIN).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, REVIEW / "dfu" / PLUGIN)
    shutil.copy2(source / "dfu" / "Portable.txt", REVIEW / "dfu")  # -dfsynctest needs a portable install
    if (source / "dfu" / "PortableAppdata").exists():
        shutil.copytree(source / "dfu" / "PortableAppdata", REVIEW / "dfu" / "PortableAppdata", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("Player*.log", "Saves"))
    shutil.copy2(source / "dfitems.pk3", REVIEW / "dfitems.pk3")
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")  # it creates the bridge session, so it needs this bridge
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def launch_args(runs, harness, uz_extra, df_extra, stock_mods=False, minimized=True):
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    mods = ([] if stock_mods else [MODS / n for n in DRLA]) + [REVIEW / "data" / n for n in DUNGEON] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]
    mods += [] if stock_mods else [REVIEW / "doomerfall-drla.pk3"]
    mods += [harness] if harness else []
    for mod in mods:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(GAME / "DAGGER" / "ARENA2"), "+vid_fullscreen", "0", "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0"] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def write_demo():
    play = REVIEW / "play"
    binds = ["+bind", "q", "netevent df_info", "+bind", "i", "netevent df_inventory", "+bind", "k", "netevent df_fast_travel",
             "+bind", "z", "netevent df_rest"]
    command = launch_args(play, None, ["+i_pauseinbackground", "0"],
                          ["-dfrunningtest", str(play / "running.log"), "prime", "-screen-width", "1280", "-screen-height", "800"], minimized=False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    bind_args = " ".join(f'--uzdoom-arg "{a}"' for a in binds)
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Running skill from running. Starts outside a town with DRLA. Hold Run (Shift, or turn on Always Run) and move:\r\n"
        "rem every second of running practises Running (Athletics). Walking, standing, or holding Run without moving does not.\r\n"
        "rem This demo starts Running a few seconds of running short of rising, and checks for a rise after each use,\r\n"
        "rem so after about 9 seconds of running the character sheet (Q) shows Running one point higher.\r\n"
        "rem Each use is written to play\\running.log (the test log, not shown in game).\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\\saves\" mkdir \"%HERE%play\\saves\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={bind_args}\r\n"
        f"start \"\" {line} %BINDS%\r\n", newline="")


def tallies(body):
    """(seconds, uses gained) for each Running tally the test log recorded."""
    out = []
    for m in re.finditer(r"^([\d.]+) tally Running: uses (-?\d+) -> (-?\d+)", body, re.M):
        if int(m[3]) > int(m[2]):
            out.append((float(m[1]), int(m[3]) - int(m[2])))
    return out


def run(name, prime, stock_mods):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "RNHarness" }\n')
    console = runs / "log-console.txt"
    log = runs / "running.log"
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0", "+cl_run", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfmute", "-dfrunningtest", str(log)] + (["prime"] if prime else []) + ["-screen-width", "640", "-screen-height", "360"]
    timeout = 200
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, harness, uz, df, stock_mods)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, seen, marks = "timeout", time.time() + timeout + 3, set(), {}
    timed = []  # (wall time, mark name or None, console commands): the runner's own clock, for what WorldTick cannot do
    n = 0

    def send(cmds):
        nonlocal n
        with open(inbox, "a") as f:
            for c in cmds:
                n += 1
                f.write(f"r{n} con {c}\n")

    def count():
        return sum(u for _, u in tallies(read(log)))

    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = read(console)
        for phase in re.findall(r"RNPHASE (\w+)", body):
            if phase in seen:
                continue
            seen.add(phase)
            marks[phase] = count()  # before this phase's buttons change
            send(PRESS.get(phase, []))
            now = time.time()
            if phase == "runstand":
                timed.append((now + 2.5, "runstand+settle", []))  # the last running report (at most a second old) lands
            elif phase == "wall":
                timed.append((now + 2.5, "wall+settle", []))
            elif phase == "pause":
                # Run a circle for 1.5 s, press Pause with the keys still held, let the last report land, then watch 6 s.
                timed += [(now + 1.5, "pausing", ["pause"]), (now + 4.0, "paused", []), (now + 10.0, "paused end", ["pause"])]
        for item in [t for t in timed if time.time() >= t[0]]:
            timed.remove(item)
            if item[1]:
                marks[item[1]] = count()
            send(item[2])
        if "RNPHASE done" in body and not timed:
            reason = "route finished"
            time.sleep(1.5)
            marks["end"] = count()
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    body = read(console)
    sums = {}
    for line in body.splitlines():
        if re.match(r"RN[A-Z]+ ", line) or any(k in line for k in FATAL):
            print(line[:190])
        m = re.match(r"RNSUM (\w+) tics (\d+) moved (\d+) runinput (\d+)", line)
        if m:
            sums[m[1]] = (int(m[2]), int(m[3]), int(m[4]))
    text = read(log)
    print("\n".join(l for l in text.splitlines() if not l.split(" ", 1)[-1].startswith("tally"))[:3000])
    sent = [int(x) for x in re.findall(r"running: sent (\d+) running tics", read(runs / "uz.log"))]
    df_tallied = [int(x) for x in re.findall(r"running: \d+ running tics, tallied (\d+)", read(runs / "df.log"))]
    total = sum(u for _, u in tallies(text))
    print("marks (Running uses tallied so far, at each phase start):", marks)
    print(f"Doom reported {sum(sent)} running tics in {len(sent)} events; Daggerfall tallied {sum(df_tallied)} uses (df.log), test log {total}")
    ok = reason == "route finished" and len(sums) == 7 and "RNWALL none" not in body
    if ok:
        stand = marks["walk"] - marks["stand"]
        walk = marks["run"] - marks["walk"]
        runstand = marks["wall"] - marks["runstand+settle"]
        wall = marks["slide"] - marks["wall+settle"]
        slide = marks["pause"] - marks["slide"]
        paused = marks["paused end"] - marks["paused"]
        run_input = sums["run"][2]
        expect = run_input / TICS_PER_USE
        run_secs = sums["run"][0] / 35
        run_uses = marks["runstand+settle"] - marks["run"]
        print(f"stand: {stand} uses (moved {sums['stand'][1]}); walk: {walk} uses (moved {sums['walk'][1]}); "
              f"runstand: {runstand} uses after settling (moved {sums['runstand'][1]})")
        print(f"wall (run held, pushing straight in): {wall} uses after settling (moved {sums['wall'][1]}, run input {sums['wall'][2]} tics); "
              f"slide (45 degrees along it): {slide} uses (moved {sums['slide'][1]}, run input {sums['slide'][2]} tics)")
        print(f"paused with run and forward held: {paused} uses over 6 s (before the pause {marks['pausing'] - marks['pause']} uses in 1.5 s)")
        print(f"run: {run_uses} uses over the {run_secs:.1f} s run phase (moved {sums['run'][1]}) = {run_uses / run_secs:.2f}/s; "
              f"harness counted {run_input} tics of run input, expected {expect:.1f} uses ({35 / TICS_PER_USE:.3f}/s); "
              f"Doom sent {sum(sent)} tics -> {sum(sent) / TICS_PER_USE:.1f} uses, test log total {total}")
        # Sliding along a wall is moving with run held, so it counts by the rule; only a straight push counts nothing.
        ok = stand == 0 and walk == 0 and runstand == 0 and wall == 0 and paused == 0 and run_uses > 0 \
            and abs(run_uses - expect) <= max(3, 0.05 * expect) and abs(sum(sent) / TICS_PER_USE - total) <= 1.01 \
            and (slide > 0 or sums["slide"][1] < 64)
        if prime:
            rises = re.findall(r"advance Running: skill (\d+) -> (\d+)", text)
            print("rises:", rises)
            ok = ok and len(rises) >= 1
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds))
    for line in kinds[:5]:
        print("  ", line)
    print("RESULT", "PASS" if ok else "FAIL")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, str(REVIEW / "doomerfall.pk3")] + \
                  ([str(REVIEW / "doomerfall-drla.pk3")] if mods else []) + ["+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("arg", nargs="?")
ap.add_argument("--no-prime", action="store_true")
ap.add_argument("--stock-mods", action="store_true")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.arg))
elif args.command == "run":
    run(args.arg or "run", not args.no_prime, args.stock_mods)
else:
    check()
