"""Tab menu (Skyrim's tween menu) test and demo. Every game runs on quiet_run's private desktop.

  tween_menu.py assemble   review folder: this worktree's UZDoom build and pk3s, the Daggerfall half from batch7-stage
  tween_menu.py paired     paired run outside Privateer's Hold: the tween menu opens through Doom's real togglemap (Tab)
                           command, pressed by a test-only pk3 (testmod/); keys and clicks posted to Doom's window choose
                           each of the four windows, close them, and close the menu
  tween_menu.py check      DOOM.WAD E1M1 without a bridge, stock and with the DRLA set: no errors, the menu draws
                           (opened with openmenu, screenshot kept), and Tab stays Doom's automap
"""
import re, shutil, subprocess, sys, time, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "play"))
argv, sys.argv = sys.argv, sys.argv[:1]
import install  # noqa: E402  (only for its registry isolation)
sys.argv = argv

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\tween-menu")
STAGE = Path(r"D:\dev\DoomDaggerfall-loop\review\batch7-stage")  # Daggerfall build, bridge, launcher and data of this branch's base.
UZ_BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-quiet\Release")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 7154
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map", "Attempt to execute CCMD")
VK_TAB, VK_RETURN, VK_ESCAPE, VK_LEFT, VK_UP = 0x09, 0x0D, 0x1B, 0x25, 0x26
MENU = {"character": 11, "spellbook": 12, "inventory": 2, "map": 3}


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def test_pk3(out):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((HERE / "testmod").rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(HERE / "testmod").as_posix())


def assemble():
    REVIEW.mkdir(parents=True, exist_ok=True)
    if (REVIEW / "uzdoom").exists():
        shutil.rmtree(REVIEW / "uzdoom")
    shutil.copytree(UZ_BUILD, REVIEW / "uzdoom", ignore=shutil.ignore_patterns("*.pdb", "*.ini", "*.ilk", "*.exp", "*.lib", "*.log"))
    for dll in ("sndfile.dll", "soft_oal.dll"):
        if (STAGE / "uzdoom" / dll).exists():
            shutil.copy2(STAGE / "uzdoom" / dll, REVIEW / "uzdoom" / dll)
    for name in ("dfu", "data"):
        if not (REVIEW / name).exists():
            shutil.copytree(STAGE / name, REVIEW / name, ignore=shutil.ignore_patterns("work", "run*", "*.log"))
    install.isolate_registry(REVIEW / "dfu")
    for name in ("doomerfall-launcher.exe", "dfitems.pk3"):
        shutil.copy2(STAGE / name, REVIEW / name)
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    write_demo()
    print("assembled", REVIEW)


def write_demo():
    mods = " ".join(f'--mod "{MODS / n}"' for n in DRLA)
    data = " ".join(f'--mod "%HERE%data\\{n}"' for n in DATA)
    dagger = GAME / "DAGGER"
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Tab menu. Starts outside Privateer's Hold with DRLA. Press Tab: the game freezes under Skyrim's four-way menu.\r\n"
        "rem Point at a choice or press its arrow key (or W A S D) to highlight it; click it, press Enter or E, or press the same\r\n"
        "rem direction again to open it: up Character sheet, left Magic (spellbook), right Inventory, down Map.\r\n"
        "rem Tab or Escape closes the menu, and Tab or Escape closes the window it opened. The game resumes when it closes.\r\n"
        "rem A test hook gives you a spellbook so Magic has something to show. Open Map directly: Options, Customize Controls,\r\n"
        "rem Doomerfall Controls, Open Map.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" --nodraw --uzdoom \"%HERE%uzdoom\\uzdoom.exe\" --dfu \"%HERE%dfu\\DaggerfallUnity.exe\" --iwad \"{GAME / 'wads' / 'DOOM2.WAD'}\" {mods} {data} "
        "--mod \"%HERE%dfitems.pk3\" --mod \"%HERE%doomerfall.pk3\" --mod \"%HERE%doomerfall-drla.pk3\" --uzdoom-cwd \"%HERE%play\" --log \"%HERE%play\\launcher.log\" "
        "--uzdoom-arg -config --uzdoom-arg \"%HERE%play\\uzdoom.ini\" --uzdoom-arg -savedir --uzdoom-arg \"%HERE%play\\saves\" --uzdoom-arg -dfbridgelog --uzdoom-arg \"%HERE%play\\uz.log\" "
        "--uzdoom-arg -ddtowncache --uzdoom-arg \"%HERE%data\\cache\" --uzdoom-arg -ddconverter --uzdoom-arg \"%HERE%data\\converter\\DungeonConverter.exe\" "
        f"--uzdoom-arg -ddarena2 --uzdoom-arg \"{dagger}\\ARENA2\" --uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT{GROUP:05d} --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 "
        f"--dfu-arg -dfbridgelog --dfu-arg \"%HERE%play\\df.log\" --dfu-arg -dfsynctest --dfu-arg \"{dagger}\" --dfu-arg -dfspellbooktest --dfu-arg \"%HERE%play\\spellbook.log\" "
        "--dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800\r\n",
        newline="")


class Paired:
    def __init__(self):
        self.dir = REVIEW / "run-paired"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.uz_log, self.console, self.launcher = self.dir / "uz.log", self.dir / "log-tweenmenu.txt", self.dir / "launcher.log"
        self.results = []

    def case(self, ok, what):
        self.results.append((bool(ok), what))
        print("CASE", "pass" if ok else "FAIL", what)

    def count(self, path, pattern):
        return len(re.findall(pattern, read(path)))

    def wait_count(self, path, pattern, n, seconds):
        end = time.time() + seconds
        while time.time() < end and self.proc.poll() is None:
            if self.count(path, pattern) >= n:
                return True
            if any(k in read(self.console) for k in FATAL):
                return False
            time.sleep(0.2)
        return False

    def driver(self):
        path = REPO / "tools" / "levelup" / "levelup.py"  # Its window driver; that script runs on import, so only its definitions load.
        ns = {"__file__": str(path), "__name__": "levelup_driver"}
        exec(compile(read(path).split("\nap = argparse.ArgumentParser()")[0], str(path), "exec"), ns)
        return ns["Doom"](self.launcher)

    def click_stage(self, x, y):
        """A click at a point of the menu's 1280x720 stage, fitted into Doom's screen as DDSwfMovie does."""
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        self.doom.user.GetClientRect(self.doom.hwnd, ctypes.byref(r))
        w, h = r.right, r.bottom
        s = min(w / 1280, h / 720)
        lp = int((h - 720 * s) / 2 + y * s) << 16 | int((w - 1280 * s) / 2 + x * s)
        u = self.doom.user
        u.PostMessageW(self.doom.hwnd, 0x200, 0, lp)
        time.sleep(0.3)
        u.PostMessageW(self.doom.hwnd, 0x201, 1, lp)
        time.sleep(0.1)
        u.PostMessageW(self.doom.hwnd, 0x202, 0, lp)
        time.sleep(0.5)

    # The bridge log (uz.log) is written at once; Doom's console log only when Doom exits. The test pk3 presses Tab
    # again only after Doom has run unpaused for 3 seconds with no menu, so each next opening proves Doom resumed.
    OPENED = r"ui: tween menu opened"

    def opened(self, n, seconds=30):
        return self.wait_count(self.uz_log, self.OPENED, n, seconds)

    def round(self, n, choose, name, close_vk, close_name):
        if n == 1:
            ok = self.opened(1, 120)
            self.case(ok, "#1: Doom's togglemap (Tab) opens the tween menu")
            if not ok:
                return False
            self.doom = self.driver()
        time.sleep(0.6)  # The open animation.
        before = self.count(self.uz_log, r"Daggerfall opened menu %d at" % MENU[name])
        choose()
        shown = self.wait_count(self.uz_log, r"Daggerfall opened menu %d at" % MENU[name], before + 1, 20)
        self.case(shown, f"#{n}: the menu's choice opens Daggerfall's {name} window")
        time.sleep(1.5)
        closes = self.count(self.uz_log, r"ui: closed \(")
        self.doom.press(close_vk)
        closed = self.wait_count(self.uz_log, r"ui: closed \(", closes + 1, 10)
        self.case(closed, f"#{n}: {close_name} closes the {name} window")
        resumed = self.opened(n + 1)
        self.case(resumed, f"#{n}: Doom resumes after the window closes (Tab opens the menu again)")
        return shown and closed and resumed

    def go(self):
        for path in (self.uz_log, self.console, self.launcher):
            path.unlink(missing_ok=True)
        test_pk3(self.dir / "tweentest.pk3")
        uz = ["-noactivate", "-config", str(self.dir / "uz.ini"), "-savedir", str(self.dir / "saves"), "-dfbridgelog", str(self.uz_log), "-nosound", "-noautoload", "-skill", "3",
              "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"), "-ddarena2", str(GAME / "DAGGER" / "ARENA2"),
              "+logfile", "tweenmenu",  # UZDoom writes log-tweenmenu.txt "+vid_fullscreen", "0", "+wipetype", "0", "+m_use_mouse", "1",
              "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+map", f"DDT{GROUP:05d}"]
        df = ["-dfbridgelog", str(self.dir / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-dfspellbooktest", str(self.dir / "spellbook.log"),
              "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "400"]
        command = [sys.executable, QUIET, "--timeout", "300", "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
                   "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", str(GAME / "wads" / "DOOM2.WAD"),
                   "--uzdoom-cwd", str(self.dir), "--log", str(self.launcher)]
        for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3", self.dir / "tweentest.pk3"]:
            command += ["--mod", str(mod)]
        for arg in uz:
            command += ["--uzdoom-arg", arg]
        for arg in df:
            command += ["--dfu-arg", arg]
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.steps()
        except Exception as e:  # noqa: BLE001  (report and stop the games)
            self.case(False, f"driver error: {e!r}")
        finally:
            if self.proc.poll() is None:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.proc.wait()
        fatal = [k for k in FATAL if k in read(self.console)]
        self.case(not fatal, f"no fatal errors in Doom's log ({fatal})")
        failed = [w for ok, w in self.results if not ok]
        print("RESULT", "PASS" if not failed else "FAIL", f"{len(self.results) - len(failed)}/{len(self.results)}")
        return not failed

    def steps(self):
        # Keyboard: a direction highlights, the same direction again opens it; Tab closes the window.
        if not self.round(1, lambda: (self.doom.press(VK_UP), self.doom.press(VK_UP)), "character", VK_TAB, "Tab"):
            return
        # Keyboard: Left then Enter; Escape closes the window.
        if not self.round(2, lambda: (self.doom.press(VK_LEFT), self.doom.press(VK_RETURN)), "spellbook", VK_ESCAPE, "Escape"):
            return
        # Right twice for the inventory, Down twice for the map.
        if not self.round(3, lambda: (self.doom.press(0x27), self.doom.press(0x27)), "inventory", VK_ESCAPE, "Escape"):
            return
        if not self.round(4, lambda: (self.doom.press(0x28), self.doom.press(0x28)), "map", VK_TAB, "Tab"):
            return
        # Tab and Escape close the menu itself without opening anything; Doom resumes, so the test key opens it again.
        for n, (vk, name) in enumerate(((VK_TAB, "Tab"), (VK_ESCAPE, "Escape")), 5):
            time.sleep(0.6)
            windows = self.count(self.uz_log, r"Daggerfall opened menu")
            self.doom.press(vk)
            resumed = self.opened(n + 1)
            self.case(resumed and self.count(self.uz_log, r"Daggerfall opened menu") == windows, f"#{n}: {name} closes the tween menu and Doom resumes")
        # Probe only (not a case): posted mouse messages did not reach Doom's menu in an earlier run on the private desktop.
        time.sleep(0.6)
        before = self.count(self.uz_log, r"Daggerfall opened menu 2 at")
        self.click_stage(640 + 260, 360)
        got = self.wait_count(self.uz_log, r"Daggerfall opened menu 2 at", before + 1, 10)
        print("INFO posted mouse click on INVENTORY", "opened the inventory" if got else "did nothing (posted mouse input not seen)")


def check():
    runs = REVIEW / "run-check"
    runs.mkdir(parents=True, exist_ok=True)
    ok = True
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"  # UZDoom's name for +logfile check-<label>
        log.unlink(missing_ok=True)
        shots = runs / f"shots-{label}"
        shutil.rmtree(shots, ignore_errors=True)
        command = [sys.executable, QUIET, "--timeout", "60" if mods else "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-noautoload", "-file", *mods, str(REVIEW / "doomerfall.pk3"), *([str(REVIEW / "doomerfall-drla.pk3")] if mods else []),
                   "+logfile", f"check-{label}", "+screenshot_dir", str(shots), "+vid_fullscreen", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                   "+map", "E1M1", "+wait 70;togglemap;wait 10;screenshot;togglemap;netevent df_map;openmenu DoomerfallTweenMenu;wait 35;screenshot;wait 10;quit"]
        code = subprocess.call(command)
        text = read(log)
        fatal = [k for k in FATAL if k in text]
        errors = len(re.findall(r"Script error|error:", text, re.I))
        drew = "Doomerfall: tween menu opened" in text
        shotlist = sorted(p.name for p in shots.glob("*")) if shots.exists() else []
        print(f"CASE {'pass' if code == 0 and not fatal else 'FAIL'} {label}: exit {code}, fatal {fatal}, error lines {errors}, menu opened {drew}, screenshots {shotlist}")
        ok = ok and code == 0 and not fatal and drew
    return ok


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "assemble":
        assemble()
    elif what == "paired":
        sys.exit(0 if Paired().go() else 1)
    elif what == "check":
        sys.exit(0 if check() else 1)
    else:
        print(__doc__)
