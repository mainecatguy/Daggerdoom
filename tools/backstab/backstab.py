"""Paired test of Backstabbing (UZDoom dd_backstab.cpp + dd_bridge.cpp DD_BridgeDamageBonus <- backstab_bonus_bp from
DoomerfallDamageBonus.cs; sneak hits -> DFB_KIND_SNEAK_HITS -> DoomerfallBackstab.cs). Daggerfall Unity's
-dfbackstabtest sets the Backstabbing skill and logs every Backstabbing tally. Both games run on quiet_run's private
desktop.

usage: backstab.py assemble <source review folder> | run [SKILL ...] [--stock-mods] | check
assemble builds review\\backstab from a paired review folder (data, launcher, dfitems.pk3, uzdoom folder, Daggerfall
Unity portable settings) with this checkout's UZDoom, bridge DLL, Daggerfall Unity build and doomerfall pk3s, and writes
the demo play.bat.
run: one paired run per skill (default 0 50 100), --bonus 2 also forces the rest of the damage bonus to x2; the harness (harness.zs) hits a monster unaware, alerted, and so on.
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
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\backstab")
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
USES_PER_SNEAK_HIT = 10   # 10 x Daggerfall's per-hit weapon tally (1, WeaponManager)


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
                          ["-dfbackstabtest", str(play / "backstab.log"), "100", "-screen-width", "1280", "-screen-height", "800"], minimized=False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    bind_args = " ".join(f'--uzdoom-arg "{a}"' for a in binds)
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Backstabbing. Starts outside a town with DRLA, with the Backstabbing skill set to 100 (x5 damage on sneak hits).\r\n"
        "rem Find monsters that have not noticed you (fast travel with K to a dungeon, or wait for an encounter) and shoot\r\n"
        "rem one before it sees you: the first hit does five times the damage. Once it is after you, hits are normal again.\r\n"
        "rem Each sneak hit practises Backstabbing (10 uses); they are written to play\\backstab.log (not shown in game),\r\n"
        "rem and Doom's damage per hit to play\\uz.log ('damage bonus:' lines, 'backstab x5' on sneak hits).\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\\saves\" mkdir \"%HERE%play\\saves\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={bind_args}\r\n"
        f"start \"\" {line} %BINDS%\r\n", newline="")


def tallies(body):
    out = []
    for m in re.finditer(r"^([\d.]+) tally Backstabbing: uses (-?\d+) -> (-?\d+)", body, re.M):
        out.append(int(m[3]) - int(m[2]))
    return out


def run_one(skill, stock_mods, bonus=None):
    name = f"skill{skill}" + ("-stock" if stock_mods else "") + (f"-bonus{bonus:g}" if bonus else "")
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text())
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "BSHarness" }\n')
    console = runs / "log-console.txt"
    log = runs / "backstab.log"
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    df = ["-dfmute", "-dfbackstabtest", str(log), str(skill), "-screen-width", "640", "-screen-height", "360"]
    df += ["-dfdamagetest", f"{bonus:g}"] if bonus else []  # forces the rest of the damage bonus
    timeout = 150
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch_args(runs, harness, uz, df, stock_mods)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, fired, released, n = "timeout", time.time() + timeout + 3, False, None, 0
    mini_fired, mini_sent_before = False, None

    def send(cmds):
        nonlocal n
        with open(inbox, "a") as f:
            for c in cmds:
                n += 1
                f.write(f"r{n} con {c}\n")

    while time.time() < end and proc.poll() is None:
        time.sleep(0.1)
        body = read(console)
        if "BSPHASE fire" in body and not fired:
            fired = True
            send(["+attack"])
            released = time.time() + 0.4
        if "BSPHASE minigun" in body and not mini_fired:
            mini_fired = True
            time.sleep(0.3)  # sneak hits of the steps before have gone out
            mini_sent_before = sum(int(x) for x in re.findall(r"backstab: sent (\d+) sneak hits", read(runs / "uz.log")))
            send(["+attack"])
            released = time.time() + 1.6  # about 22 tics of wind-up, then firing
        if released and time.time() >= released:
            send(["-attack"])
            released = None
        if "BSDONE" in body:
            reason = "route finished"
            time.sleep(2.0)  # the last sneak hits reach Daggerfall
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print(f"== skill {skill}: stopped: {reason}")
    body = read(console)
    hits = {}
    for line in body.splitlines():
        if re.match(r"BS[A-Z]+", line) or any(k in line for k in FATAL):
            print("  ", line[:190])
        m = re.match(r"BSHIT (\w+) (\d+) (-?\d+) before (\S+) after (\S+)", line)
        if m:
            hits[m[1]] = (int(m[2]), int(m[3]), m[4], m[5])
    text = read(log)
    print("  ", "\n   ".join(l for l in text.splitlines() if "tally" not in l))
    uz = read(runs / "uz.log")
    sent = sum(int(x) for x in re.findall(r"backstab: sent (\d+) sneak hits", uz))
    published = re.findall(r"damage bonus: publishing backstab (-?\d+) bp", read(runs / "df.log"))
    total = sum(tallies(text))
    for l in [l for l in uz.splitlines() if "damage bonus:" in l][:14]:
        print("   uz:", l.split("damage bonus: ", 1)[1][:150])
    expect = 1 + 4 * min(max(skill, 0), 100) / 100
    ok = reason == "route finished" and all(k in hits for k in ("unaware", "alerted", "volley", "infight", "hitscan", "silentafter", "heardtwice", "ownnoise", "ownflight", "windup", "noattack", "spread"))
    mini_sent = sent - mini_sent_before if mini_sent_before is not None else None
    with_minigun = "minigun" in hits
    spread_b = re.search(r"BSSPREAD B (-?\d+)", body)
    spread_sent = re.findall(r"backstab: sent (\d+) sneak hits", uz)
    ok = ok and spread_b is not None
    if ok:
        base = hits["alerted"][1]                       # base damage x the rest of the damage bonus
        ratio = hits["unaware"][1] / base if base else 0
        hs_ratio = hits["hitscan"][1] / (base * 20 / 100) if base else 0
        print(f"   expected multiplier x{expect:g}; unaware {hits['unaware'][1]} / alerted {base} = x{ratio:.3f}; "
              f"volley {hits['volley'][1]} (3 x unaware = {3 * hits['unaware'][1]}); infight {hits['infight'][1]}; "
              f"hitscan x{hs_ratio:.3f}; earlier noise then silent attack {hits['silentafter'][1]}, earlier noise + own noise {hits['heardtwice'][1]}, "
              f"own noise only {hits['ownnoise'][1]}, own noise 6 tics before {hits['ownflight'][1]}, wind-up (two noises 20 tics apart) {hits['windup'][1]}, "
              f"hit outside any attack {hits['noattack'][1]}; real gun: {hits.get('fire', ('', 'none'))[1]} health lost; "
              f"spread A,B,A: A lost {hits['spread'][1]} (2 x unaware = {2 * hits['unaware'][1]}), B lost {spread_b[1]}, "
              f"events with 2 sneak hits: {spread_sent.count('2')}")
        print(f"   DRLA minigun (wind-up): {hits['minigun'][1] if with_minigun else 'not run'} health lost, sneak hits during it: {mini_sent}")
        print(f"   Doom sent {sent} sneak hits; Daggerfall tallied {total} Backstabbing uses (expected {sent * USES_PER_SNEAK_HIT}); "
              f"published backstab bp {published}")
        ok = (not bonus or base == round(100 * bonus)) and abs(ratio - expect) <= 0.02 and hits["infight"][1] == base and hits["volley"][1] == 3 * hits["unaware"][1] \
            and abs(hs_ratio - expect) <= 0.06 \
            and hits["silentafter"][1] == base and hits["heardtwice"][1] == base and hits["noattack"][1] == base \
            and hits["windup"][1] == hits["unaware"][1] \
            and hits["ownnoise"][1] == hits["unaware"][1] and hits["ownflight"][1] == hits["unaware"][1] \
            and all(hits[k][2] == "no-target+heard" for k in ("silentafter", "heardtwice", "ownnoise", "ownflight", "windup", "noattack")) \
            and hits["unaware"][2] == "no-target" and hits["unaware"][3] == "target-player" and hits["alerted"][2] == "target-player" and sent == (10 if with_minigun else 9) and total == sent * USES_PER_SNEAK_HIT \
            and hits["spread"][1] == 2 * hits["unaware"][1] and int(spread_b[1]) == hits["unaware"][1] \
            and (stock_mods or (with_minigun and hits["minigun"][1] > 0 and mini_sent == 1))
        # sent exactly 10: 8 harness sneak hits (unaware, volley, hitscan, ownnoise, ownflight, windup, spread A and B once
        # each), the real gun's first bullet and the minigun's first bullet; counting A twice in the spread adds one. (Events batch per frame, so the per-event counts are not checked.)
    kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
    print("   Player.log exception kinds:", len(kinds), *kinds[:3])
    print("   RESULT", "PASS" if ok else "FAIL")
    return ok


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
ap.add_argument("args", nargs="*")
ap.add_argument("--stock-mods", action="store_true")
ap.add_argument("--bonus", type=float, help="force the rest of the damage bonus (-dfdamagetest), e.g. 2 for x2")
args = ap.parse_args()
if args.command == "assemble":
    assemble(Path(args.args[0]))
elif args.command == "run":
    results = [run_one(int(s), args.stock_mods, args.bonus) for s in (args.args or ["0", "50", "100"])]
    print("ALL", "PASS" if all(results) else "FAIL")
else:
    check()
