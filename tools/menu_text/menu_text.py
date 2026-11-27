"""Paired run that opens a Daggerfall menu in Doom, hovers an item, and screenshots it, to compare menu text sharpness.

usage: menu_text.py <demo folder> <out folder> [--menu 2] [--size 1280x800] [--dfsize WxH] [--hover x,y ...]
The demo folder is a review demo laid out like review/hud-messages (uzdoom, dfu, data, pk3s). The whole script reruns
itself under quiet_run.py, so the driver shares the games' private desktop and can post mouse messages to Doom.
Doom's -dfuitest opens the menu and screenshots it every second into <out>/shots.
The launcher gets --show-dfu: under quiet_run the launcher's own nested desktop gives Daggerfall black frames.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys
import time
from pathlib import Path

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
RES = r"D:\dev\DoomDaggerfall\GameResources"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
TEST_MARK = 0x8000  # Doom ignores unmarked mouse messages in test mode.


def args():
    p = argparse.ArgumentParser()
    p.add_argument("demo")
    p.add_argument("out")
    p.add_argument("--menu", default="2")
    p.add_argument("--size", default="1280x800")
    p.add_argument("--dfsize", default="")
    p.add_argument("--map", default="DDT07154")
    p.add_argument("--timeout", type=int, default=40)
    p.add_argument("--hover", nargs="*", default=["184,57", "208,55"], help="native 320x200 points to hover in turn")
    p.add_argument("--click", action="store_true", help="click each point instead of only moving to it")
    p.add_argument("--hold", type=float, default=4)
    p.add_argument("--extra-uz", nargs="*", default=[])
    p.add_argument("--extra-df", nargs="*", default=[])
    p.add_argument("--menutext", action="store_true", help="Daggerfall's -dfmenutexttest: Casual Pants in the info panel")
    p.add_argument("--drive", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


def launcher_command(a, here, out):
    w, h = a.size.split("x")
    dw, dh = (a.dfsize or a.size).split("x")
    mods = [MODS + "\\DoomRL_Arsenal_1.1.5.pk3", MODS + "\\DoomRL_Monsters_Beta_7.3.pk3", MODS + "\\drlax_1.2b.pk3",
            here / "data/ddruntime.pk3", here / "data/overworld.pk3", here / "data/privateershold.wad",
            here / "data/privateershold_mesh.pk3", here / "data/privateershold_doors.pk3", here / "dfitems.pk3",
            here / "doomerfall.pk3", here / "doomerfall-drla.pk3"]
    uz = ["-config", out / "uzdoom.ini", "-savedir", out / "saves", "-dfbridgelog", out / "uz.log", "-skill", "3",
          "-ddtowncache", here / "data/cache", "-ddconverter", here / "data/converter/DungeonConverter.exe",
          "-ddarena2", RES + "\\DAGGER\\ARENA2", "-dfuitest", "1", "+dd_ui_test_menu", a.menu,
          "+screenshot_dir", out / "shots", "+map", a.map, "-width", w, "-height", h, "+vid_fullscreen", "0",
          "+win_w", w, "+win_h", h, "+vid_scalemode", "0", "+vid_scalefactor", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"] + a.extra_uz
    df = ["-dfbridgelog", out / "df.log", "-dfsynctest", RES + "\\DAGGER", "-screen-fullscreen", "0",
          "-screen-width", dw, "-screen-height", dh] + a.extra_df + (["-dfmenutexttest"] if a.menutext else [])
    cmd = [str(here / "doomerfall-launcher.exe"), "--show-dfu", "--nodraw",  # Not --minimized: a minimized Doom renders at 320x200.
           "--uzdoom", str(here / "uzdoom/uzdoom.exe"), "--dfu", str(here / "dfu/DaggerfallUnity.exe"),
           "--iwad", RES + "\\wads\\DOOM2.WAD", "--uzdoom-cwd", str(out), "--log", str(out / "launcher.log")]
    for m in mods:
        cmd += ["--mod", str(m)]
    for x in uz:
        cmd += ["--uzdoom-arg", str(x)]
    for x in df:
        cmd += ["--dfu-arg", str(x)]
    return cmd


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def doom_window(out):
    user = ctypes.WinDLL("user32", use_last_error=True)
    pids = {int(m) for m in re.findall(r"started UZDoom pid (\d+)", read(out / "launcher.log"))}
    found = []
    proc_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def visit(hwnd, _):
        pid = wt.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd, 4):
            found.append(hwnd)
        return True

    user.EnumWindows(proc_type(visit), 0)
    return user, (found[0] if found else None)


def drive(a):
    here, out = Path(a.demo), Path(a.out)
    proc = subprocess.Popen(launcher_command(a, here, out), stdin=subprocess.DEVNULL)
    deadline = time.time() + a.timeout - 3
    opened = re.compile(r"Daggerfall opened menu \d+ at (\d+)x(\d+)")
    surface = None
    while time.time() < deadline and proc.poll() is None:
        m = opened.search(read(out / "uz.log"))
        if m:
            surface = int(m.group(1)), int(m.group(2))
            break
        time.sleep(0.5)
    if surface:
        user, hwnd = doom_window(out)
        user.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        print("menu open, surface", surface, "doom window", hwnd)
        w, h = surface
        scale = min(w / 320, h / 200)
        for point in a.hover:
            x, y = (float(v) for v in point.split(","))
            lp = int((h - 200 * scale) / 2 + y * scale) << 16 | int((w - 320 * scale) / 2 + x * scale)
            if hwnd:
                user.PostMessageW(hwnd, 0x200, TEST_MARK, lp)
                time.sleep(0.2)
                if a.click:
                    user.PostMessageW(hwnd, 0x201, 1 | TEST_MARK, lp)
                    time.sleep(0.1)
                    user.PostMessageW(hwnd, 0x202, TEST_MARK, lp)
            time.sleep(a.hold)  # Doom's screenshots come once a second; hold each point for several.
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.5)
    if proc.poll() is None:
        subprocess.call(["taskkill", "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    a = args()
    if a.drive:
        drive(a)
        return
    out = Path(a.out)
    (out / "shots").mkdir(parents=True, exist_ok=True)
    code = subprocess.call([sys.executable, QUIET, "--timeout", str(a.timeout + 10), "--", sys.executable] + sys.argv + ["--drive"],
                           stdin=subprocess.DEVNULL)
    shots = sorted((out / "shots").glob("*.png"))
    print(f"exit {code}, {len(shots)} screenshots in {out / 'shots'}")
    for log in ("uz.log", "df.log"):
        for line in read(out / log).splitlines():
            if any(k in line for k in FATAL):
                print("FATAL?", log, line)


if __name__ == "__main__":
    main()
