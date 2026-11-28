"""Rest refuses only while living hostile Doom monsters or guard bots are near (Daggerfall's 12 m, 360 Doom units).

usage: rest_enemies.py assemble <source review folder> | run fresh | run load | run loadguard | run dungeon | check
assemble builds review\\rest-enemies from a paired review folder (data, dfitems.pk3, portable Daggerfall Unity) with this
checkout's UZDoom (D:\\dev\\DoomDaggerfall-build\\uzdoom-quiet), launcher, bridge, Daggerfall Unity build and
doomerfall.pk3, and writes the demo play.bat.
run fresh: town start at noon with DRLA. A ZombieMan 160 units away and one 600 units away (20 m): rest is refused;
the near one killed: rest opens (the far one is past 12 m). Into the Gothway tavern with Daggerfall's -dfguardtest
(guards called as for a theft) and -dfresttestroom (a rented room): rest refused next to a living guard bot; all
guards killed: rest opens. Then an autosave.
run load: loads that autosave in a fresh launch: rest opens beside the dead guards; a ZombieMan 120 units away: refused;
killed: opens.
run loadguard: loads the same autosave with -dfguardtest. Guard bots do not carry over a load (dd_guards.cpp
DD_GuardsLeaveLevel), so newly called guards stand in: refused next to a living guard bot; guards killed: opens.
run dungeon: into Privateer's Hold; after 8 s with its packs alive, Daggerfall's answer must match Doom's count; every
monster killed: rest opens (Daggerfall's hidden enemies and spawners there no longer refuse it).
Each case runs the rest key's command (netevent df_rest, through -ddqa), reads Doom's count and Daggerfall's top
window, and presses the rest key in Doom's window to close what opened, as a player does.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA, and -norun.
"""
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "town_corpses"))
import town_corpses as tc  # noqa: E402  (its command line runs only as __main__)

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\rest-enemies")
tc.REVIEW = REVIEW
BUILD = tc.BUILD
QUIET, GAME, MODS, DRLA, FATAL = tc.QUIET, tc.GAME, tc.MODS, tc.DRLA, tc.FATAL
REST_KEY = 0x5A  # Z, bound to netevent df_rest
# True: refused; False: the rest window opens; None: Daggerfall's answer must match Doom's count.
EXPECT = {"fresh": {"near": True, "neardead": False, "guard": True, "guarddead": False},
          "load": {"loaded": False, "loadednear": True, "loadeddead": False},
          "loadguard": {"loadguard": True, "loadguarddead": False},
          "dungeon": {"dungeonalive": None, "dungeondead": False}}
read = tc.read


def dungeon_door():
    """Privateer's Hold's door row in town (x y z nx ny in fields 3-7), as tools/monster_deaths picks it."""
    rows = tc.lumps(REVIEW / "data" / "cache" / f"T{tc.GROUP:05d}.ddt")["DDDOORS"].decode().splitlines()
    return next(l.split() for l in rows if l.startswith("1 187853213"))


def assemble(source):
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "data", "dfu"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(source / "data", REVIEW / "data")
    shutil.copytree(BUILD / "uzdoom-quiet" / "Release", REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ilk", "*.lib", "*.exp"))
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("Player*.log", "*.pdb"))
    shutil.copy2(source / "dfitems.pk3", REVIEW / "dfitems.pk3")
    for name in ("launcher", "bridge"):
        out = BUILD / f"{name}-quiet"
        subprocess.check_call(["cmake", "-S", str(REPO / name), "-B", str(out), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=subprocess.DEVNULL)
        subprocess.check_call(["cmake", "--build", str(out), "--config", "Release", "--parallel", "6"], stdout=subprocess.DEVNULL)
    shutil.copy2(BUILD / "launcher-quiet" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(BUILD / "bridge-quiet" / "Release" / "doomerfall_bridge.dll", REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64")
    shutil.copy2(source / "dfu" / "Portable.txt", REVIEW / "dfu")
    shutil.copytree(source / "dfu" / "PortableAppdata", REVIEW / "dfu" / "PortableAppdata", dirs_exist_ok=True)
    build = REPO / "scripts" / "doomerfall" / "build_pk3.py"
    subprocess.check_call([sys.executable, str(build), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(build), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    play = REVIEW / "play"
    command = tc.launch_args(play, tc.size_args(1280, 800) + ["+i_pauseinbackground", "0", "+bind", "z", "netevent df_rest"],
                             ["-dfmute", "-dftownhour", "12", "-dfguardtest", "-dfresttestroom"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Rest and nearby enemies. Town start at noon with DRLA in a 1280x800 window. Z opens Daggerfall's rest window.\r\n"
        "rem Rest is refused while a living hostile monster is within 12 m (or one that targets you can see you), and allowed\r\n"
        "rem once they are dead; monsters farther than 12 m that have not noticed you do not stop it.\r\n"
        "rem Walk into any shop, tavern or house: test hooks call the guards in (as for a theft) and rent you a room in the\r\n"
        "rem first tavern. Rest is refused while a living guard is near, and allowed once the guards are dead.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


def window_driver(runs):
    # tools/levelup's window driver; that script runs its command line on import, so only its definitions are loaded.
    path = REPO / "tools" / "levelup" / "levelup.py"
    ns = {"__file__": str(path), "__name__": "levelup_driver"}
    exec(compile(read(path).split("\nap = argparse.ArgumentParser()")[0], str(path), "exec"), ns)
    return ns["Doom"](runs / "launcher.log")


def run(mode):
    runs = REVIEW / "run" / mode
    shutil.rmtree(runs, ignore_errors=True)
    runs.mkdir(parents=True)
    saves = REVIEW / "run" / ("saves-dungeon" if mode == "dungeon" else "saves")  # the dungeon's autosaves stay apart
    saves.mkdir(exist_ok=True)
    tavern = saves / "tavern.zds"  # the fresh run's save after the guards died, for both load runs
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@MODE@", mode).replace("@DOOR@", ", ".join(tc.tavern_door()[3:8]))
                    .replace("@DDOOR@", ", ".join(dungeon_door()[3:8])))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "REHarness" }\n')
    console, uz_log, df_log, views = runs / "log-console.txt", runs / "uz.log", runs / "df.log", runs / "views.log"
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "-file", str(harness), "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+dd_debugmessages", "0",
          "+bind", "z", "netevent df_rest"] + tc.size_args(1280, 800)
    if mode in ("load", "loadguard"):
        if not tavern.exists():
            sys.exit("no save to load: run fresh first")
        resume = saves / "resume.zds"
        shutil.copy2(tavern, resume)
        uz += ["-dfloadtest", "resume:" + str(resume), "+dd_ui_test_hold", "1"]
    elif mode == "fresh":
        for old in saves.glob("*.zds"):
            old.unlink()
    df = ["-dfmute", "-dfresttest", str(views)] + (["-dfguardtest", "-dftownhour", "12", "-dfresttestroom"] if mode == "fresh" else
                                                   ["-dfguardtest"] if mode == "loadguard" else [])
    timeout = 220 if mode == "fresh" else 150
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + tc.launch_args(runs, uz, df, True)
    command = [str(saves) if a == str(runs / "saves") else a for a in command]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results, handled, sent, doom = [], set(), 0, None
    reason, end = "timeout", time.time() + timeout + 3

    def wait(path, pattern, seconds, start=0):
        stop = time.time() + seconds
        while time.time() < stop and proc.poll() is None:
            m = re.search(pattern, read(path)[start:])
            if m:
                return m
            time.sleep(0.1)
        return None

    try:
        while time.time() < end and proc.poll() is None:
            time.sleep(0.1)
            body = read(console)
            if any(k in body for k in FATAL):
                reason = "fatal"
                break
            if "REDONE" in body:
                reason = "done"
                time.sleep(1.5)
                break
            labels = [l.split()[1] for l in body.splitlines() if l.startswith("RENOW ")]
            pending = [l for l in labels if l not in handled]
            if not pending:
                continue
            label = pending[0]
            handled.add(label)
            if doom is None:
                doom = window_driver(runs)
            uz_at, df_at, views_at = len(read(uz_log)), len(read(df_log)), len(read(views))
            # Opened by the rest key's own command; a posted key reaches Doom only once its menu has the input.
            with open(inbox, "a") as f:
                f.write(f"r{sent} con netevent df_rest\n")
            count = wait(uz_log, r"rest: (\d+) hostile monsters near \((\d+) see the player\)([^\n]*)", 8, uz_at)
            asked = wait(df_log, r"rest: Doom asks to rest, monsters near (\w+)", 8, df_at)
            top = wait(views, r"top (DaggerfallRestWindow|DaggerfallMessageBox)", 8, views_at)
            refused = asked and asked.group(1) == "True"
            shown = top.group(1) if top else None
            want = EXPECT[mode][label]
            if want is None:
                want = bool(count) and count.group(1) != "0"
            ok = bool(count and asked and top) and refused == want and shown == ("DaggerfallMessageBox" if want else "DaggerfallRestWindow")
            results.append((ok, label))
            print("CASE", "pass" if ok else "FAIL", f"{label}: Doom counted {count.group(0) if count else None}; Daggerfall monsters near {asked.group(1) if asked else None}, "
                  f"showed {shown} (want {'refused' if want else 'rest window'})")
            time.sleep(0.5)
            doom.press(REST_KEY)
            if not wait(uz_log, r"ui: closed", 6, uz_at):
                doom.press(0x1B)
                print("  ", label, "the rest key did not close the window; Escape closed it:", bool(wait(uz_log, r"ui: closed", 4, uz_at)))
            time.sleep(0.5)
            with open(inbox, "a") as f:
                f.write(f"n{sent} con netevent re_next\n")
            sent += 1
    finally:
        if proc.poll() is None:
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
    print("stopped:", reason)
    if mode == "fresh" and reason == "done":
        newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)  # written at RESAVE, the last save
        if newest:
            shutil.copy2(newest, tavern)
            print("kept", newest.name, "as", tavern.name)
    for line in read(console).splitlines():
        if line.startswith("RE") or any(k in line for k in FATAL):
            print(line[:220])
    for line in read(df_log).splitlines():
        if "rest:" in line or "guards:" in line or "exception" in line.lower():
            print("DF", line[:220])
    if mode == "fresh":
        far = re.search(r"REFAR alive 1, ([\d.]+) units away", read(console))
        ok = bool(far) and 360 < float(far.group(1)) < 900
        results.append((ok, "far"))
        print("CASE", "pass" if ok else "FAIL", f"far: a living, unaware monster between 12 m and the old 30 m stood by during 'neardead' ({far.group(0) if far else None})")
    missing = [l for l in EXPECT[mode] if l not in handled]
    bad = sum(not ok for ok, _ in results) + len(missing)
    print(f"RESULT rest_enemies {mode}: {len(results) - sum(not ok for ok, _ in results)} passed, {bad} failed" + (f" (never reached: {missing})" if missing else ""))


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "60" if mods else "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate",
                   "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3",
                   *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                   "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 105;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                            "-norun", "-nosound", "-stdout"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


if __name__ == "__main__":
    argv = sys.argv
    command = argv[1] if len(argv) > 1 else ""
    if command == "assemble" and len(argv) > 2:
        assemble(Path(argv[2]))
    elif command == "run" and len(argv) > 2 and argv[2] in EXPECT:
        run(argv[2])
    elif command == "check":
        check()
    else:
        sys.exit(__doc__)
