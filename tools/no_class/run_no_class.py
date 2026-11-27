"""No DRLA class in bridged games: drives Doom's real main menu (opened by +menu_main, then Enter on New Game) and reads the probe's log.

Run the whole script under quiet_run.py, so the keys reach Doom's window on the same private desktop:
  python D:\\dev\\DoomDaggerfall\\scripts\\overnight\\quiet_run.py --timeout 120 -- python tools\\no_class\\run_no_class.py <mode> <stage>

  standalone  UZDoom + DRLA + DRLA X, no Daggerfall: New Game must open DRLA X's class menu; Enter through it starts E1M1
              as the Marine with its perk.
  e1m1        DOOM.WAD E1M1 by +map, stock and with the DRLA set (as play_drlax.bat): both must start, no fatal error.
  bridged     The launcher with DRLA, doomerfall.pk3 and doomerfall-drla.pk3: New Game must go straight to Daggerfall's
              character creation (no class menu) and the arrived player must be DoomerfallPlayer with no perk item.
<stage> is a staged folder (uzdoom\\uzdoom.exe, dfu, data, launcher, doomerfall.pk3, doomerfall-drla.pk3).
Logs go to <stage>\\test-noclass. Exit code 0 means PASS.
"""
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "new_game"))
import run_new_game as ng  # noqa: E402  (window, key and character-creation helpers)

MODS = Path(r"D:\dev\DoomDaggerfall\GameMods")
DRLA = [str(MODS / f) for f in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
WADS = Path(r"D:\dev\DoomDaggerfall\GameResources\wads")
BG = ["+menu_main", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+wipetype", "0"]
VK_ESC, VK_ENTER = 0x1B, 0x0D


def probe_pk3(run):
    out = run / "noclass-probe.pk3"
    with zipfile.ZipFile(out, "w") as z:
        for p in (Path(__file__).parent / "probe").iterdir():
            z.write(p, p.name)
    return str(out)


def window_of(pid):
    found = []

    def visit(hwnd, _):
        owner = ng.wt.DWORD()
        ng.user32.GetWindowThreadProcessId(hwnd, ng.ctypes.byref(owner))
        if owner.value == pid and ng.user32.IsWindowVisible(hwnd) and not ng.user32.GetWindow(hwnd, 4):
            found.append(hwnd)
        return True

    ng.user32.EnumWindows(ng.EnumProc(visit), 0)
    return found[0] if found else None


def menus(console):
    return re.findall(r"noclass probe: menu (\S+)", ng.read(console))


def reports(console):
    return re.findall(r"noclass probe: map (\S+) tick \d+ class (\S+) perks \[(.*?) \] weapons \[(.*?) \] ready (\S+) stamina (-?\d+) armorspecial (-?\d+)",
                      ng.read(console))


def fatal(console):
    """A fatal error, by whole line. DRLA's own load logs non-fatal 'Script error' lines and 'Midas_Statue_Fatality' warnings."""
    return bool(re.search(r'^(Fatal|FATAL)|VM execution aborted|Execution could not continue', ng.read(console), re.M))


def open_new_game(hwnd, console, until, deadline):
    """+menu_main opened the main menu at the title (posted keys reach Doom only as menu input, so Escape cannot open it).
    Enter takes its first item, New Game. Repeats until `until()`."""
    while time.time() < deadline and not until() and not fatal(console):
        seen = menus(console)
        if seen and seen[-1] == "MainMenu": ng.key(hwnd, VK_ENTER)
        time.sleep(1.0)


def standalone(stage, run):
    console = run / "log-standalone.txt"
    console.unlink(missing_ok=True)
    cmd = [str(stage / "uzdoom" / "uzdoom.exe"), "-iwad", str(WADS / "DOOM.WAD"), "-file", *DRLA, probe_pk3(run), "-config", str(run / "standalone.ini"),
           "-noactivate", "-nosound", "+logfile", console.stem[4:], *BG]
    proc = subprocess.Popen(cmd, cwd=run)
    deadline, ok = time.time() + 60, False
    try:
        hwnd = None
        while time.time() < deadline and not hwnd and not fatal(console):
            time.sleep(0.5)
            hwnd = window_of(proc.pid) if "noclass probe: menu" in ng.read(console) else None  # The probe's UI tick runs at the title.
        time.sleep(2.0)
        if hwnd:
            open_new_game(hwnd, console, lambda: "DRLAX_PlayerClassProxyMenu" in menus(console), deadline)
            for _ in range(6):  # Marine (first row), then the episode and skill menus, until the game starts.
                if reports(console) or fatal(console): break
                ng.key(hwnd, VK_ENTER)
                time.sleep(1.5)
            while time.time() < deadline and not reports(console) and not fatal(console): time.sleep(0.5)
        r = reports(console)
        ok = not fatal(console) and "DRLAX_PlayerClassProxyMenu" in menus(console) and bool(r) and r[-1][1] == "DoomRLMarine" and "RLAmmochainPerk" in r[-1][2]
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    print("standalone:", "PASS" if ok else "FAIL", "| menus:", menus(console), "| reports:", reports(console)[-1:] or "none", "| fatal:", fatal(console))
    return ok


def e1m1(stage, run):
    ok = True
    for name, files in (("stock", []), ("drla", DRLA)):
        console = run / f"log-e1m1-{name}.txt"
        console.unlink(missing_ok=True)
        cmd = [str(stage / "uzdoom" / "uzdoom.exe"), "-iwad", str(WADS / "DOOM.WAD"), *(["-file", *files] if files else []), "-file", probe_pk3(run),
               "-config", str(run / f"e1m1-{name}.ini"), "-noactivate", "-nosound", "-skill", "3", "+map", "E1M1", "+logfile", console.stem[4:], *BG[1:]]
        proc = subprocess.Popen(cmd, cwd=run)
        deadline = time.time() + 45  # DRLA takes about 20 s to load.
        while time.time() < deadline and len(reports(console)) < 2 and not fatal(console): time.sleep(0.5)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        r = reports(console)
        # +map starts the class the player's playerclass setting names: stock DoomPlayer, or one of DRLA's classes.
        good = not fatal(console) and bool(r) and r[-1][0] == "E1M1" and (r[-1][1] == "DoomPlayer" if name == "stock" else r[-1][1].startswith("DoomRL"))
        ok &= good
        print(f"e1m1 {name}:", "PASS" if good else "FAIL", "| reports:", r[-1:] or "none", "| fatal:", fatal(console))
    return ok


def bridged(stage, run):
    uz_log, df_log, console, launcher = run / "bridged-uz.log", run / "bridged-df.log", run / "log-bridged.txt", run / "bridged-launcher.log"
    for p in (uz_log, df_log, console, launcher):
        p.unlink(missing_ok=True)
    (run / "saves").mkdir(parents=True, exist_ok=True)
    data = stage / "data"
    uz_args = ["-noactivate", "-nosound", "-config", str(run / "bridged.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-dfflow", "-dfuitest", "0",  # 0: no menus opened, but only marked test clicks count.
               "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", ng.DAGGER + r"\ARENA2",
               "+logfile", console.stem[4:], *BG]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfflow", ng.DAGGER, "-dfmute", "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    cmd = [str(stage / "doomerfall-launcher.exe"), "--minimized", "--nodraw", "--uzdoom", str(stage / "uzdoom" / "uzdoom.exe"),
           "--dfu", str(stage / "dfu" / "DaggerfallUnity.exe"), "--iwad", ng.IWAD, "--uzdoom-cwd", str(run), "--log", str(launcher)]
    for mod in DRLA + [str(data / m) for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")] + \
            [str(stage / m) for m in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-drla.pk3")] + [probe_pk3(run)]:
        cmd += ["--mod", mod]
    for a in uz_args: cmd += ["--uzdoom-arg", a]
    for a in dfu_args: cmd += ["--dfu-arg", a]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline, result, last, tries, hwnd, arrived = time.time() + 90, "timeout", "", 0, None, 0.0
    try:
        while time.time() < deadline and not hwnd:
            time.sleep(0.5)
            hwnd = ng.doom_window(launcher) if "noclass probe: menu" in ng.read(console) else None
        time.sleep(3.0)  # Daggerfall finishes booting behind Doom's title.
        if hwnd:
            open_new_game(hwnd, console, lambda: "new game: chosen in Doom's menu" in ng.read(uz_log) or "DRLAX_PlayerClassProxyMenu" in menus(console), deadline)
        while time.time() < deadline and proc.poll() is None:
            uz = ng.read(uz_log)
            if fatal(console): result = "fatal"; break
            if "DRLAX_PlayerClassProxyMenu" in menus(console) or "PlayerclassMenu" in menus(console): result = "class menu shown"; break
            if "both games running" in uz:
                arrived = arrived or time.time()
                if time.time() - arrived > 12: result = "arrived"; break  # The probe reports 10 s into the map.
                time.sleep(0.5)
                continue
            if "difficulty chosen" not in uz and "asking for a difficulty" in uz:
                ng.key(hwnd, VK_ENTER)  # The difficulty prompt: Enter takes the highlighted skill.
                time.sleep(0.8)
                continue
            size = re.search(r"opened menu 4 at (\d+)x(\d+)", uz)
            if not size or "ui: closed" in uz[uz.rfind("opened menu 4"):]:
                time.sleep(0.1)
                continue
            ng.SURFACE[:] = [int(size.group(1)), int(size.group(2))]
            top = ng.top_window(df_log)
            tries = tries + 1 if top == last else 0
            last = top
            ng.act(hwnd, top, tries)
            time.sleep(0.15)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    r = reports(console)
    final = r[-1] if r else None
    ok = result == "arrived" and final is not None and final[1] == "DoomerfallPlayer" and final[2].strip() == "" and int(final[5]) > 0
    print("bridged:", "PASS" if ok else "FAIL", "| result:", result, "| last DF window:", last, "| menus:", menus(console))
    print("  class list:", re.findall(r"noclass probe: \d+ player classes:.*", ng.read(console))[:1])
    for line in r: print("  report:", line)
    for line in [l for l in ng.read(uz_log).splitlines() if re.search(r"new game|difficulty|class", l)][-12:]: print("  uz:", line)
    return ok


def main():
    mode, stage = sys.argv[1], Path(sys.argv[2])
    run = stage / "test-noclass"
    run.mkdir(parents=True, exist_ok=True)
    ok = {"standalone": standalone, "e1m1": e1m1, "bridged": bridged}[mode](stage, run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
