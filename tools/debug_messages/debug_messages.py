"""Checks that Doomerfall's diagnostics stay off the screen and out of the console unless dd_debugmessages is on.

usage: debug_messages.py assemble | solo | e1m1
assemble: builds review\\no-debug-messages from review\\cleanlaunch (Daggerfall Unity, bridge DLL, launcher, data) with
          this worktree's UZDoom build, doomerfall.pk3, and ddruntime.pk3's generated script patched the way the
          converter now writes it (CityExport.cs).
solo:     UZDoom alone with play.bat's mod set on Privateer's Hold. It sends the events behind the reported messages (the
          weapon switch's 'loaded ammo', the inventory and fast travel actions), then screenshots the screen and the
          open console. Runs twice: dd_debugmessages off, then on. The log must hold the diagnostics both times; the
          screenshots in run-checks\\ show whether they reached the screen and the console (judge them by eye:
          nothing with the option off, the lines with it on).
e1m1:     DOOM.WAD E1M1 with no bridge, stock and with the DRLA set; must start and run with no script errors.
"""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\no-debug-messages")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\cleanlaunch")
UZ_BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-encounters\Release")  # Configured from this worktree.
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = [MODS / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
BG = ["+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0"]
# DRLA's set logs three non-fatal "Script error" lines with every UZDoom build (translation line 1, and two DRLA Monsters
# menudef lines; the cleanlaunch build does the same), so only these count as failures.
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
FATAL_SCRIPT = re.compile(r"Script error, \"(?!translation\"|DoomRL_Monsters_Beta_7\.3\.pk3:menudef\.)")
DIAG = re.compile(r"^(DD[A-Z]+|DF[A-Z]+|DFMesh:|\[bridge\]|Doomerfall:)")
NEED = ("Doomerfall: loaded ammo", "Doomerfall: action fired: Open Inventory")
# The same text replacement CityExport.cs now makes when it writes the runtime script.
GATED = re.compile(r'Console\.Printf\("(DF(?:GATES|CITY|RULE|ACTIONS|FLATOUT|DFLATS|DLIGHTS|DOORS)[^"]*)"((?:, [^;]*?)?)\);')


def fatal_lines(logtext):
    return [l for l in logtext.splitlines() if any(k in l for k in FATAL) or FATAL_SCRIPT.search(l)]


def gate(text):
    return GATED.sub(lambda m: '{ let dbg = CVar.FindCVar("dd_debugmessages"); Console.PrintfEx((dbg && dbg.GetBool()) ? PRINT_HIGH : '
                     'PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE, "' + m.group(1) + '"' + m.group(2) + '); } // diagnostics: on screen only with dd_debugmessages', text)


def assemble():
    if REVIEW.exists():
        shutil.rmtree(REVIEW)
    shutil.copytree(SOURCE, REVIEW, ignore=shutil.ignore_patterns("run", "run-tests", "uzdoom", "*.pdb"))
    shutil.copytree(UZ_BUILD, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        if (SOURCE / "uzdoom" / dll).exists():
            shutil.copy2(SOURCE / "uzdoom" / dll, REVIEW / "uzdoom" / dll)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    # The converter copies CityExport.cs's runtime script, door_objects.zs and action_objects.zs into these packages
    # verbatim, so gating the same lines here gives what the fixed converter writes.
    for name in ("ddruntime.pk3", "privateershold_doors.pk3", "privateershold_mesh.pk3", "overworld.pk3"):
        src, dst = SOURCE / "data" / name, REVIEW / "data" / name
        patched = 0
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info)
                if info.filename.lower().endswith(".zs") or info.filename.lower().startswith("zscript"):
                    text = data.decode("utf-8")
                    new = gate(text)
                    patched += text.count('Console.Printf("DF') - new.count('Console.Printf("DF')
                    data = new.encode("utf-8")
                zout.writestr(info, data)
        print(name, "gated", patched, "runtime prints")
    write_play()
    print("assembled", REVIEW)


NOTES = r"""rem Doomerfall without debug messages on screen (run 20261124-202353). Choose New Game in Doom's menu.
rem Use picks up what you look at, E is a second Interact key, Q is Info, I opens the inventory, K opens fast travel.
rem What to try: New Game, switch weapons (no more "Doomerfall: loaded ammo ..." at the top), pick things up, open
rem doors, walk into town, use a shop, save and load. Only messages meant for you should appear at the top of the
rem screen, and the console (~) should hold no DD.../DF.../[bridge] lines.
rem The diagnostics still go to run\log-uzdoom.txt (and Doom's bridge log run\uz.log as before).
rem play-debug.bat is the same game with +dd_debugmessages 1: the diagnostics show on screen and in the console again."""


def write_play():
    """play.bat from cleanlaunch's, with +logfile uzdoom (run\\log-uzdoom.txt); play-debug.bat adds +dd_debugmessages 1."""
    lines = (SOURCE / "play.bat").read_text(encoding="utf-8").splitlines()
    rest = [l for l in lines if not l.startswith(("@echo off", "rem"))]
    start = next(i for i, l in enumerate(rest) if l.startswith('start "" '))
    log = "--uzdoom-arg -dfflow --uzdoom-arg +logfile --uzdoom-arg uzdoom"
    for name, extra in (("play.bat", ""), ("play-debug.bat", " --uzdoom-arg +dd_debugmessages --uzdoom-arg 1")):
        cmd = rest[start].replace("--uzdoom-arg -dfflow", log + extra, 1)
        body = ["@echo off", *NOTES.splitlines(), *rest[:start], cmd, *rest[start + 1:]]
        (REVIEW / name).write_text("\r\n".join(body) + "\r\n", encoding="utf-8", newline="")


def run_uz(name, args, timeout=40):
    run = REVIEW / "run-checks"
    run.mkdir(parents=True, exist_ok=True)
    log = run / f"log-{name}.txt"  # UZDoom writes +logfile NAME to log-NAME.txt in its working folder.
    log.unlink(missing_ok=True)
    cmd = [sys.executable, QUIET, "--timeout", str(timeout), "--cwd", str(run), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"),
           "-config", str(run / f"{name}.ini"), "+logfile", name, *BG, *args]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return out, (log.read_text(errors="replace") if log.exists() else "")


def solo():
    ok = True
    files = [*DRLA, *(REVIEW / "data" / n for n in DATA), REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3"]
    for debug in (0, 1):
        name = f"solo-debug{debug}"
        shot, conshot = (REVIEW / "run-checks" / f"{name}{s}.png" for s in ("", "-console"))
        script = ("wait 70; netevent dfa_loaded:1:0:; netevent df_inventory; netevent df_fast_travel; wait 35; "
                  f"screenshot \"{shot.as_posix()}\"; wait 5; toggleconsole; wait 30; screenshot \"{conshot.as_posix()}\"; wait 5; quit")
        out, logtext = run_uz(name, ["-iwad", str(GAME / "wads" / "DOOM2.WAD"), "-file", *map(str, files), "-skill", "3",
                                     "+map", "MAP01", "+dd_debugmessages", str(debug), "+" + script])
        diag = [l for l in logtext.splitlines() if DIAG.match(l)]
        fatal = fatal_lines(logtext)
        missing = [n for n in NEED if not any(l.startswith(n) for l in diag)]
        kinds = sorted({DIAG.match(l).group(1) for l in diag})
        print(f"{name}: exit {out.returncode}; log diagnostics {len(diag)} ({' '.join(kinds)}); fatal {len(fatal)}; screenshots {shot.exists()} {conshot.exists()}")
        for l in fatal[:5]:
            print("   fatal:", l)
        if missing:
            print("   missing from the log:", missing)
        good = shot.exists() and conshot.exists() and not fatal and not missing
        print("   ", "PASS (log); judge the screenshots" if good else "FAIL")
        ok = ok and good
    return ok


def e1m1():
    ok = True
    for name, extra in (("e1m1-stock", []), ("e1m1-drla", ["-file", *map(str, DRLA), str(REVIEW / "dfitems.pk3"), str(REVIEW / "doomerfall.pk3")])):
        shot = REVIEW / "run-checks" / f"{name}.png"
        out, logtext = run_uz(name, ["-iwad", str(GAME / "wads" / "DOOM.WAD"), *extra, "+map", "E1M1",
                                     f"+wait 140; screenshot \"{shot.as_posix()}\"; wait 5; quit"])
        fatal = fatal_lines(logtext)
        good = out.returncode == 0 and not fatal and "E1M1" in logtext and shot.exists()
        print(f"{name}: exit {out.returncode}; fatal {len(fatal)}; screenshot {shot.exists()}; {'PASS' if good else 'FAIL'}")
        for l in fatal[:5]:
            print("   fatal:", l)
        ok = ok and good
    return ok


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "assemble":
        assemble()
    elif mode == "solo":
        sys.exit(0 if solo() else 1)
    elif mode == "e1m1":
        sys.exit(0 if e1m1() else 1)
    else:
        sys.exit(__doc__)
