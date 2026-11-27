"""Tests Daggerfall's spellbook opened from Doom, from its own key and from the character sheet, in a paired run with both
real games on quiet_run's private desktop.

usage: spellbook.py assemble | run hotkey | run sheet | run nobook | check
All runs start outside Privateer's Hold with DRLA. Daggerfall's -dfspellbooktest gives the player a spellbook with two
standard spells (the cheapest caster-only one first, the cheapest ranged one second) and full magicka, and logs the top
window, the spellbook's selected row, magicka, the ready spell and whether a cast is playing. Doom's -dfuitest opens the
menu through the same command the key is bound to (netevent df_spellbook / df_character); after that every press and
click is a real window message through Doom's window (key presses posted to Doom's window do not reach its game bindings,
as tools/journal found).
run hotkey: the spellbook opens on the first spell; Down and a click change the selection; Backspace (bound to the
  spellbook, as play.bat binds it) closes it back to Doom; Doom runs again before the next open; the Exit button closes
  it; choosing the caster-only spell (double click) is Daggerfall's own: the spell is readied and cast in Daggerfall, the
  menu closes, and the spellbook opens again afterwards.
run sheet: P's command opens the character sheet; its Spellbook button opens the spellbook inside the same Doom menu;
  Backspace closes the spellbook back to the sheet (Daggerfall's own key); the sheet's Exit closes the menu.
run nobook: without a spellbook, the key shows Daggerfall's "no spellbook" line on Doom's HUD and opens nothing.
check: DOOM.WAD E1M1 with no bridge, stock and with the DRLA set, plus the new events doing nothing there, and -norun.
"""
import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\spellbook")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\runtime-dungeons")  # Data, converter, item and sprite packages.
BUILD = Path(r"D:\dev\DoomDaggerfall-build")
UZ_BUILD = BUILD / "uzdoom-quiet" / "Release"  # Configured from this worktree (tools/spellbook/build_native.py).
SOUND = BUILD / "uzdoom-launcher" / "Release"
BRIDGE_DLL = BUILD / "bridge-quiet" / "Release" / "doomerfall_bridge.dll"
LAUNCHER = BUILD / "launcher-quiet" / "Release" / "doomerfall-launcher.exe"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")
# Daggerfall's 320x200 layout. The spellbook's 259x164 panel is centered (offset 30.5, 18): the spell list starts at
# (5,13) with 16 rows in 130 pixels, and Exit is (216,149 43x15). The character sheet's Spellbook button is (69,151 65x12)
# and its Exit (50,179 39x19).
FIRST_ROW = (75, 35)
BOOK_EXIT = (268, 174)
SHEET_SPELLBOOK = (101, 157)
SHEET_EXIT = (69, 188)
VK_BACK, VK_DOWN = 0x08, 0x28
BINDS = ["+bind", "backspace", "netevent df_spellbook", "+bind", "p", "netevent df_character"]


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


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
    if (REVIEW / "data").exists():
        shutil.rmtree(REVIEW / "data")
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
    binds = ("--uzdoom-arg +bind --uzdoom-arg backspace --uzdoom-arg \"netevent df_spellbook\" --uzdoom-arg +bind --uzdoom-arg p --uzdoom-arg \"netevent df_character\" "
             "--uzdoom-arg +bind --uzdoom-arg i --uzdoom-arg \"netevent df_inventory\" --uzdoom-arg +bind --uzdoom-arg k --uzdoom-arg \"netevent df_fast_travel\" "
             "--uzdoom-arg +bind --uzdoom-arg j --uzdoom-arg \"netevent df_journal\" --uzdoom-arg +bind --uzdoom-arg z --uzdoom-arg \"netevent df_rest\"")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Spellbook. Starts outside Privateer's Hold with DRLA. A second after the game starts, a test hook gives you a spellbook\r\n"
        "rem with two spells and fills your magicka. Press Backspace to open Daggerfall's spellbook (Backspace, Escape or Exit closes\r\n"
        "rem it). Press P for the character sheet, then click its Spellbook button; closing the spellbook returns to the sheet.\r\n"
        "rem Choosing a spell is Daggerfall's own: a caster-only spell is cast in Daggerfall at once (no Doom animation yet).\r\n"
        "rem Rebind the keys in Options, Customize Controls, Doomerfall Controls.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={binds}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dfspellbooktest --dfu-arg \"%HERE%play\\spellbook.log\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800 %BINDS%\r\n",
        newline="")


class Run:
    def __init__(self, mode):
        self.mode = mode
        self.dir = REVIEW / f"run-{mode}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.df_log, self.console = self.dir / "uz.log", self.dir / "df.log", self.dir / "log-spellbook.txt"
        self.launcher, self.views = self.dir / "launcher.log", self.dir / "spellbook.log"
        self.results = []
        self.proc = None

    def case(self, ok, what):
        self.results.append((bool(ok), what))
        print("CASE", "pass" if ok else "FAIL", what)

    def wait(self, path, pattern, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if re.search(pattern, read(path)):
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def count(self, path, pattern):
        return len(re.findall(pattern, read(path)))

    def wait_count(self, path, pattern, n, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if self.count(path, pattern) >= n:
                return True
            time.sleep(0.2)
        return False

    def state(self):
        """The last logged state: (top, selected, spells, magicka, ready, casting)."""
        rows = re.findall(r"top (\S+) \| selected (\S+) spells (\d+) \| magicka (\d+)/\d+ hp \S+ \| ready (.*?) casting (\w+)", read(self.views))
        if not rows:
            return None
        top, selected, spells, magicka, ready, casting = rows[-1]
        return top, selected, int(spells), int(magicka), ready, casting == "True"

    def top_is(self, name, seconds=5):
        return self.wait(self.views, r"top %s \|[^\n]*\n?$" % name, seconds) or (self.state() or ("",))[0] == name

    def go(self):
        for path in (self.uz_log, self.df_log, self.console, self.launcher, self.views):
            path.unlink(missing_ok=True)
        menu, opens = {"hotkey": (12, 4), "sheet": (11, 1), "nobook": (12, 1)}[self.mode]
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "-dfuitest", str(opens), "+dd_ui_test_menu", str(menu), *BINDS, "+logfile", "spellbook", "+screenshot_dir", str(self.dir / "shots"), "+vid_fullscreen", "0", "+wipetype", "0",
              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.df_log), "-dfsynctest", str(GAME / "DAGGER"), "-dfspellbooktest", str(self.views), *(["nobook"] if self.mode == "nobook" else []),
              "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "240", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if not self.wait(self.views, r"prepared:", 120):
                self.case(False, "the test never prepared the player (game not ready)")
            else:
                print("  ", [l for l in read(self.views).splitlines() if "prepared" in l])
                getattr(self, self.mode)()
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            self.case(False, f"driver error: {e!r}")
        finally:
            if self.proc.poll() is None:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.proc.wait()
        self.summary()

    def doom(self):
        # tools/levelup's window driver; that script runs its command line on import, so only its definitions are loaded.
        path = REPO / "tools" / "levelup" / "levelup.py"
        ns = {"__file__": str(path), "__name__": "levelup_driver"}
        exec(compile(read(path).split("\nap = argparse.ArgumentParser()")[0], str(path), "exec"), ns)
        doom = ns["Doom"](self.launcher)
        size = re.findall(r"opened menu \d+ at (\d+)x(\d+)", read(self.uz_log))
        doom.surface = (int(size[-1][0]), int(size[-1][1]))
        return doom

    def opened(self, n, menu=12):
        return self.wait_count(self.uz_log, r"Daggerfall opened menu %d at" % menu, n, 60)

    def closed(self, n, why=None):
        ok = self.wait_count(self.uz_log, r"ui: closed \(", n, 8)
        reasons = re.findall(r"ui: closed \(([^)]*)\)", read(self.uz_log))
        return ok and (why is None or (len(reasons) >= n and reasons[n - 1] == why)), reasons

    def hotkey(self):
        shown = self.opened(1) and self.top_is("DaggerfallSpellBookWindow")
        time.sleep(0.5)
        s = self.state()
        self.case(shown and s and s[1] == "0/2" and s[2] == 2, f"the spellbook key opens Daggerfall's spellbook in Doom on the first of two spells (state {s})")
        if not shown:
            return
        doom = self.doom()
        doom.press(VK_DOWN)
        time.sleep(0.3)
        down = self.state()
        doom.click((FIRST_ROW[0], FIRST_ROW[1]))
        time.sleep(0.3)
        clicked = self.state()
        self.case(down and down[1] == "1/2" and clicked and clicked[1] == "0/2", f"Down selects the second spell ({down and down[1]}), a click on the first row selects it again ({clicked and clicked[1]})")
        doom.press(VK_BACK)
        ok, reasons = self.closed(1, "Doom asked")
        self.case(ok and self.top_is("DaggerfallHUD"), f"Backspace closes it back to Doom ({reasons})")

        # Doom runs between menus: its map time at the next open is later than at this close.
        reopened = self.opened(2) and self.top_is("DaggerfallSpellBookWindow")
        times = [int(t) for t in re.findall(r"maptime \d+ then (\d+)", read(self.uz_log))]
        asked = [int(t) for t in re.findall(r"asked Daggerfall to open menu 12, maptime (\d+)", read(self.uz_log))]
        self.case(reopened and times and len(asked) >= 2 and asked[1] > times[0], f"Doom resumed after the close (map time at close {times[:1]}, at the next open {asked[1:2]})")
        if not reopened:
            return
        doom.click(BOOK_EXIT)
        ok, reasons = self.closed(2, "player closed it")
        self.case(ok, f"the spellbook's Exit button closes it ({reasons})")

        # Choosing a spell is Daggerfall's own (DaggerfallSpellBookWindow.SpellsListBox_OnUseSelectedItem): it readies the
        # spell and returns to the HUD; a caster-only spell is cast at once by Daggerfall's effect manager.
        if not (self.opened(3) and self.top_is("DaggerfallSpellBookWindow")):
            self.case(False, "the spellbook opened a third time")
            return
        time.sleep(0.5)
        before = self.state()
        doom = self.doom()
        doom.double_click(FIRST_ROW)
        ok, reasons = self.closed(3)
        time.sleep(3.0)
        after = self.state()
        cast = re.findall(r"casting True", read(self.views))
        self.case(ok and before and after and after[3] < before[3] and after[4] == "none" and not after[5],
                  f"choosing the caster-only spell closes the menu and Daggerfall casts it (magicka {before and before[3]} -> {after and after[3]}, "
                  f"ready {after and after[4]}, cast animation seen {bool(cast)}, now playing {after and after[5]}; {reasons[-1:]})")
        again = self.opened(4) and self.top_is("DaggerfallSpellBookWindow")
        self.case(again, "after the cast, the spellbook opens again")
        if again:
            doom.press(VK_BACK)
            ok, reasons = self.closed(4, "Doom asked")
            self.case(ok, f"and closes again ({reasons})")

    def sheet(self):
        shown = self.opened(1, 11) and self.top_is("DaggerfallCharacterSheetWindow")
        self.case(shown, "the character sheet key opens Daggerfall's character sheet in Doom")
        if not shown:
            return
        time.sleep(0.5)
        doom = self.doom()
        doom.click(SHEET_SPELLBOOK)
        book = self.top_is("DaggerfallSpellBookWindow")
        s = self.state()
        self.case(book and s and s[2] == 2 and "ui: closed" not in read(self.uz_log), f"the sheet's Spellbook button opens the spellbook in the same Doom menu (state {s})")
        if not book:
            return
        doom.press(VK_DOWN)
        time.sleep(0.3)
        s = self.state()
        self.case(s and s[1] == "1/2", f"the spellbook takes input there (Down selects {s and s[1]})")
        doom.press(VK_BACK)
        back = self.top_is("DaggerfallCharacterSheetWindow")
        self.case(back and "ui: closed" not in read(self.uz_log), "Backspace closes the spellbook back to the character sheet (Daggerfall's own key), the menu stays open")
        doom.click(SHEET_EXIT)
        ok, reasons = self.closed(1, "player closed it")
        self.case(ok and self.top_is("DaggerfallHUD"), f"the sheet's Exit closes the menu back to Doom ({reasons})")

    def nobook(self):
        asked = self.wait(self.uz_log, r"asked Daggerfall to open menu 12", 60)
        ok, reasons = self.closed(1)
        line = self.wait(self.console, r"(?i)spellbook", 5)
        lines = [l for l in read(self.console).splitlines() if "spellbook" in l.lower() or "cannot open" in l]
        self.case(asked and ok and line and "Daggerfall cannot open that menu here" not in read(self.console) and "Daggerfall opened menu 12" not in read(self.uz_log),
                  f"without a spellbook the key opens nothing and Doom's HUD shows Daggerfall's line ({lines[-2:]}, {reasons})")
        self.case("spellbook refused, the player carries no spellbook" in read(self.df_log) and "DaggerfallSpellBookWindow" not in read(self.views),
                  "Daggerfall logged the refusal and never pushed its spellbook window")

    def summary(self):
        for line in read(self.views).splitlines():
            if "error" in line or "prepared" in line:
                print("df", line)
        for line in read(self.console).splitlines():
            if "Script error" in line or any(k in line for k in FATAL):
                print("uz", line[:200])
        kinds = sorted({l[:150] for l in read(REVIEW / "dfu" / "PortableAppdata" / "Player.log").splitlines() if "Exception" in l})
        print("Player.log exception kinds:", len(kinds), kinds[:6])
        bad = sum(not ok for ok, _ in self.results)
        print(f"RESULT spellbook {self.mode}: {len(self.results) - bad} passed, {bad} failed")


def check():
    runs = REVIEW / "run-check"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "60" if mods else "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-config", str(runs / f"check-{label}.ini"),
                   "-nosound", "-noautoload", "-skill", "3", *(["-file", *mods] if mods else []), "+logfile", f"check-{label}", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0",
                   "+map", "E1M1", "+wait 35;netevent df_spellbook;netevent df_character;wait 70;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| lines", len(body.splitlines()), "| E1M1", "E1M1" in body, "| bridge lines", sum("bridge" in l.lower() for l in body.splitlines()),
              "| script errors", sum("Script error" in l for l in body.splitlines()), "| fatal", sum(any(k in l for k in FATAL) for l in body.splitlines()),
              "| menu lines", sum("menu" in l.lower() and "daggerfall" in l.lower() for l in body.splitlines()))
    code = subprocess.call([sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"), "-norun", "-nosound", "-stdout"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("-norun exit", code)


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("assemble", "run", "check"))
ap.add_argument("mode", nargs="?", choices=("hotkey", "sheet", "nobook"), default="hotkey")
args = ap.parse_args()
if args.command == "assemble":
    assemble()
elif args.command == "check":
    check()
else:
    Run(args.mode).go()
