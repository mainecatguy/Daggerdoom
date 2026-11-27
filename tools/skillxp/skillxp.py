"""Tests Skill XP and the skill purchase menu in a paired run with both real games on quiet_run's private desktop.

usage: skillxp.py unity | assemble | run | check
unity: builds Daggerfall Unity (windowed, through quiet_run).
assemble: copies this worktree's builds (tools/skillxp/build_native.py, unity) and data into the review folder.
run: in the town by Privateer's Hold with DRLA. harness.zs hurts a Baron of Hell, two zombies and a townsperson as the
player for far more than their health; the bridge's -dfuitest then opens the skills menu through the command its key
is bound to (netevent df_skills, menu 15). Daggerfall's -dfskillxptest (DoomerfallSkillXpTest.cs) logs that menu with
its perk lines and the Skill XP earned, opens the character sheet and clicks its SKILLS button, buys points with BUY
POINT (with logged test XP once the earned XP is spent) until a level-up, lets the sheet level up, then saves with
Daggerfall's save, spoils the pool and the skill, loads and logs what came back.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, the new key event doing nothing there, and -norun.
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
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\skill-menu")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\looklabel")  # Data, converter, cache, item and sprite packages.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-items" / "Release"
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-ammopile" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-ammopile" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
BINDS = ["+bind", "u", "netevent df_skills"]


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def unity():
    project = REPO / "daggerfall-unity-master"
    log = project / "Logs" / "cli-build.log"
    log.unlink(missing_ok=True)
    exe = shutil.which("Unity.exe") or r"C:\Program Files\Unity\Hub\Editor\2019.4.41f2\Editor\Unity.exe"
    code = subprocess.call([sys.executable, QUIET, "--timeout", "2400", "--", exe, "-projectPath", str(project), "-buildTarget", "Win64",
                            "-executeMethod", "CliBuild.BuildWindows64", "-logFile", str(log)], stdin=subprocess.DEVNULL)
    text = read(log)
    print(f"unity exit {code}, succeeded {'CliBuild result: Succeeded' in text}")
    for line in text.splitlines():
        if "error CS" in line:
            print(line[:220])


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name, source in (("uzdoom", UZ_BUILD), ("dfu", REPO / "daggerfall-unity-master" / "Builds" / "Windows64")):
        if (REVIEW / name).exists():
            shutil.rmtree(REVIEW / name)
        shutil.copytree(source, REVIEW / name, ignore=shutil.ignore_patterns("*.pdb", "*.ini", "*.ilk", "*.exp", "*.lib", "*.log"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(SOUND / dll, REVIEW / "uzdoom" / dll)
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRIDGE_DLL, plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    if not (REVIEW / "data").exists():
        shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    shutil.copy2(LAUNCHER, REVIEW / "doomerfall-launcher.exe")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    keys = (("u", "df_skills"), ("q", "df_info"), ("i", "df_inventory"), ("k", "df_fast_travel"), ("j", "df_journal"), ("z", "df_rest"),
            ("p", "df_character"), ("y", "df_status"))
    binds = " ".join(f'--uzdoom-arg +bind --uzdoom-arg {k} --uzdoom-arg "netevent {e}"' for k, e in keys)
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Skill XP and the Skills menu. Starts in the town outside Privateer's Hold with DRLA and Daggerfall's test character.\r\n"
        "rem Hurt monsters or townspeople to earn Skill XP: 1 per 100 damage. Press U for the Skills menu, or P for the character\r\n"
        "rem sheet and click SKILLS. Pick a skill to see its price and its perks at 25/50/75/100; BUY POINT spends the XP.\r\n"
        "rem Privateer's Hold (the big door in town) has monsters. Rebind U in Options, Customize Controls, Doomerfall Controls.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={binds}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


def run():
    d = REVIEW / "run"
    d.mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher, test = d / "uz.log", d / "df.log", d / "log-skillxp.txt", d / "launcher.log", d / "skillxp-test.log"
    for path in (uz_log, df_log, console, launcher, test):
        path.unlink(missing_ok=True)
    shutil.rmtree(d / "shots", ignore_errors=True)
    shutil.rmtree(REVIEW / "dfu" / "PortableAppdata" / "Saves", ignore_errors=True)
    harness = d / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SXHarness" }\n')
    uz = ["-noactivate", "-config", str(d / "uz.ini"), "-savedir", str(d / "saves"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
          "-dfuitest", "1", "+dd_ui_test_hold", "1", "+dd_ui_test_menu", "15", *BINDS, "+logfile", "skillxp", "+screenshot_dir", str(d / "shots"), "+vid_fullscreen", "0",
          "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
    df = ["-dfbridgelog", str(df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfskillxptest", str(test),
          "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
    command = [sys.executable, QUIET, "--timeout", "260", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
               "--uzdoom-cwd", str(d), "--log", str(launcher)]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", harness]:
        command += ["--mod", str(mod)]
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + 250
    while time.time() < end and proc.poll() is None:
        if "SXDONE" in read(test) or any(k in read(console) for k in FATAL):
            time.sleep(3)
            break
        time.sleep(1)
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    for line in read(console).splitlines():
        if line.startswith("SX") or "Script error" in line or any(k in line for k in FATAL):
            print("uz", line[:240])
    for line in read(uz_log).splitlines():
        if "skillxp:" in line or "opened menu 15" in line:
            print("uzlog", line[:200])
    for line in read(df_log).splitlines():
        if "skillxp:" in line or "level up" in line:
            print("dflog", line[:200])
    print(read(test))
    shots = sorted((d / "shots").glob("*")) if (d / "shots").exists() else []
    print("screenshots:", [s.name for s in shots])
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("Player.log exception kinds:", len(kinds), kinds[:6])


def check():
    runs = REVIEW / "run-check"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        files = [*mods, str(REVIEW / "doomerfall.pk3")] + ([str(REVIEW / "doomerfall-drla.pk3")] if mods else [])
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *files, "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;netevent df_skills;give all;wait 35;netevent df_skills;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        lines = body.splitlines()
        print(label, "exit", code, "| lines", len(lines), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in lines),
              "| skillxp lines", sum("skillxp" in l.lower() or "dfs_xp" in l for l in lines),
              "| unknown action lines", sum("unknown action" in l for l in lines), "| script errors", sum("Script error" in l for l in lines),
              "| fatal", sum(any(k in l for k in FATAL) for l in lines))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


{"unity": unity, "assemble": assemble, "run": run, "check": check}[sys.argv[1]]()
