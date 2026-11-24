"""Drives the real New Game flow through the launcher, minimized, with window messages to Doom.

  run_new_game.py back          Open character creation, press Esc until it closes, and stay at the title.
  run_new_game.py create [mode] Make a character by mouse and keyboard, skip the cinematics, and arrive.
                                mode: save, death, or menu runs Doom's load test on that character.

Uses a private config, private saves, and the portable Daggerfall build. Stops at once on a fatal error.
"""
import ctypes
import ctypes.wintypes as wt
import re
import subprocess
import sys
import time
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\new-game")
DATA = REVIEW.parent / "combined-bridge" / "data"
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
FATAL = ("Fatal", "FATAL", "VM execution aborted", "Script error")
TIMEOUT = 50  # Boot, about twenty wizard screens, and the trip into the dungeon.
TEST_MARK = 0x8000
SURFACE = [1280, 800]
OK = (282, 183)

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
WM_KEYDOWN, WM_KEYUP, WM_CHAR, WM_MOUSEMOVE, WM_LDOWN, WM_LUP = 0x100, 0x101, 0x102, 0x200, 0x201, 0x202
EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def doom_window(launcher_log):
    pids = {int(m) for m in re.findall(r"started UZDoom pid (\d+)", read(launcher_log))}
    found = []

    def visit(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(visit), 0)
    return found[0] if found else None


def key(hwnd, vk):
    scan = user32.MapVirtualKeyW(vk, 0)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 1 | (scan << 16))
    time.sleep(0.07)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 1 | (scan << 16) | (3 << 30))
    time.sleep(0.15)


def point(x, y):
    width, height = SURFACE
    scale = min(width / 320, height / 200)
    return int((width - 320 * scale) / 2 + x * scale), int((height - 200 * scale) / 2 + y * scale)


def click(hwnd, x, y, times=1):
    px, py = point(x, y)
    lp = py << 16 | px
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, TEST_MARK, lp)
    time.sleep(0.12)
    for _ in range(times):
        user32.PostMessageW(hwnd, WM_LDOWN, 1 | TEST_MARK, lp)
        time.sleep(0.05)
        user32.PostMessageW(hwnd, WM_LUP, TEST_MARK, lp)
        time.sleep(0.05)
    time.sleep(0.2)


def top_window(df_log):
    found = re.findall(r"ui: top window is (\w+)", read(df_log))
    return found[-1] if found else ""


def act(hwnd, top, tries):
    """One step on the current wizard screen. Real clicks and keys only."""
    if top == "CreateCharRaceSelect":
        click(hwnd, *[(90, 70), (120, 100), (200, 80), (60, 120)][tries % 4])
    elif top == "CreateCharGenderSelect":
        key(hwnd, 0x4D)  # M
    elif top == "CreateCharChooseClassGen":
        click(hwnd, 90, 60)  # Choose from a list
    elif top == "CreateCharClassSelect":
        click(hwnd, 100, 64, 2)
    elif top == "CreateCharChooseBio":
        click(hwnd, 90, 65)  # Generate
    elif top == "CreateCharNameSelect":
        click(hwnd, 297, 8)  # Random name
        click(hwnd, *OK)
    elif top in ("CreateCharFaceSelect", "CreateCharAddBonusStats", "CreateCharAddBonusSkills", "CreateCharReflexSelect", "CreateCharSummary"):
        click(hwnd, *OK)
    elif top == "DaggerfallVidPlayerWindow":
        time.sleep(0.8)  # Lets real frames of the cinematic reach Doom before skipping it.
        key(hwnd, 0x1B)
    elif "MessageBox" in top or top == "DaggerfallPopupWindow":
        key(hwnd, 0x59)  # Y
        key(hwnd, 0x0D)
    else:
        time.sleep(0.1)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "back"
    load = sys.argv[2] if len(sys.argv) > 2 else ""
    name = f"{mode}{'-' + load if load else ''}"
    run = REVIEW / "test-run"
    (run / "saves").mkdir(parents=True, exist_ok=True)
    uz_log, df_log, console, launcher = run / f"{name}-uz.log", run / f"{name}-df.log", run / f"log-{name}.txt", run / f"{name}-launcher.log"
    for path in (uz_log, df_log, console, launcher):
        path.unlink(missing_ok=True)

    uz_args = ["-noactivate", "-config", str(run / "test.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-dfflow",
               "-dfnewgametest", "once", "-dfuitest", "0", "-nosound", "-ddtowncache", str(DATA / "cache"),
               "-ddconverter", str(DATA / "converter" / "DungeonConverter.exe"), "-ddarena2", DAGGER + r"\ARENA2",
               "+logfile", f"log-{name}.txt", "+vid_fullscreen", "0", "+wipetype", "0", "+screenshot_dir", str(run / f"shots-{name}"),
               "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    if load:
        uz_args += ["-dfloadtest", f"{load}:{run / 'saves' / (name + '.zds')}"]
    dfu_args = ["-dfbridgelog", str(df_log), "-dfflow", DAGGER, "-screen-fullscreen", "0", "-screen-width", "1280", "-screen-height", "800"]
    command = [sys.executable, QUIET, "--timeout", str(TIMEOUT), "--", str(REVIEW / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
               "--uzdoom-cwd", str(run), "--log", str(launcher)]
    for mod in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
        command += ["--mod", str(DATA / mod)]
    for arg in uz_args:
        command += ["--uzdoom-arg", arg]
    for arg in dfu_args:
        command += ["--dfu-arg", arg]

    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + TIMEOUT
    result, hwnd, tries, last = "timeout", None, 0, ""
    goal = "backed out" if mode == "back" else "both games running"
    try:
        while time.time() < deadline and proc.poll() is None:
            uz = read(uz_log)
            if any(k in read(console) for k in FATAL):
                result = "fatal"
                break
            if goal in uz and not load:
                result = "reached"
                time.sleep(2.5)  # Both games run together briefly before the check.
                break
            if load and re.search(r"load test: (PASS|FAIL)", uz):
                result = re.search(r"load test: (PASS|FAIL)", uz).group(1)
                break
            size = re.search(r"opened menu 4 at (\d+)x(\d+)", uz)
            if not size or "ui: closed" in uz[uz.rfind("opened menu 4"):]:
                time.sleep(0.05)
                continue
            SURFACE[:] = [int(size.group(1)), int(size.group(2))]
            hwnd = hwnd or doom_window(launcher)
            if not hwnd:
                continue
            top = top_window(df_log)
            tries = tries + 1 if top == last else 0
            last = top
            if mode == "back":
                time.sleep(1.0)
                key(hwnd, 0x1B)
                time.sleep(0.4)
            else:
                act(hwnd, top, tries)
                time.sleep(0.15)
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    print("result:", result, "| last window:", last)
    pattern = r"new game|flow:|load test|campaign|top window is (DaggerfallVid|CreateCharSummary)|FAILED|error"
    for path in (uz_log, df_log):
        lines = [l for l in read(path).splitlines() if re.search(pattern, l)]
        print(f"--- {path.name}: {len(lines)} lines")
        print("\n".join(lines[-22:]))


if __name__ == "__main__":
    main()
