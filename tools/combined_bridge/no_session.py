"""Checks that launches without a bridge session are unaffected.

Usage: no_session.py regkey   prints a hash of the owner's Daggerfall Unity registry key (read only, values are not shown)
       no_session.py dfu      normal launch of the private Daggerfall copy with the bridge DLL hidden
       no_session.py doom     compares UZDoom logs between the before and after builds, stock and with the DRLA set
"""
import hashlib
import re
import subprocess
import sys
import time
import winreg
from pathlib import Path

REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\combined-bridge")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
WADS = r"D:\dev\DoomDaggerfall\GameResources\wads"
MODS = r"D:\dev\DoomDaggerfall\GameMods"
REG_KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"


def regkey():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
    except FileNotFoundError:
        print("registry key absent")
        return
    digest, count, i = hashlib.sha256(), 0, 0
    values = []
    while True:
        try:
            values.append(winreg.EnumValue(key, i))
        except OSError:
            break
        i += 1
    for name, value, kind in sorted(values, key=lambda v: v[0]):
        digest.update(repr((name, value, kind)).encode("utf-8", "replace"))
        count += 1
    print(f"registry values {count}, sha256 {digest.hexdigest()[:16]}")


def dfu():
    root = REVIEW / "dfu"
    log = REVIEW / "run" / "nosession-dfu.log"
    log.unlink(missing_ok=True)
    dll = root / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
    hidden = dll.with_suffix(".hidden")
    dll.rename(hidden)
    try:
        code = subprocess.run([sys.executable, QUIET, "--timeout", "20", "--", str(root / "DaggerfallUnity.exe"), "-logFile", str(log),
                               "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"], capture_output=True, text=True).returncode
    finally:
        hidden.rename(dll)
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    print(f"exit {code}; log {len(text)} bytes; bridge mentions {len(re.findall(r'doomerfall_bridge|[[]bridge[]]|DllNotFound|DoomerfallBridge|hp:', text))}; exceptions {text.count('Exception')}")


VOLATILE = re.compile(r"\d+\.\d+ ?(ms|s)\b|^(Log started|Log stopped|Script warning)|\b0x[0-9a-fA-F]+\b|[A-Za-z]:[\\/][^ ]*|commit|Git|built|\d\d:\d\d:\d\d", re.I)


def launch(exe, work, name, game, seconds):
    log = work / f"log-{name}.txt"
    log.unlink(missing_ok=True)
    args = [sys.executable, QUIET, "--timeout", str(seconds), "--", str(exe), "-config", str(work / f"{name}.ini"), "-savedir", str(work), "-nosound", "-noautoload", "-noactivate",
            "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
            "+logfile", name] + game
    proc = subprocess.Popen(args, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + seconds
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        if log.exists() and "FATAL" in log.read_text(errors="replace"):
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    return log.read_text(errors="replace").splitlines() if log.exists() else []


def doom():
    work = REVIEW / "run" / "nosession"
    work.mkdir(parents=True, exist_ok=True)
    before, after = REVIEW / "baseline" / "uzdoom" / "uzdoom.exe", REVIEW / "uzdoom" / "uzdoom.exe"
    base = ["-iwad", WADS + r"\DOOM.WAD", "-skill", "3"]
    drla = ["-file", MODS + r"\DoomRL_Arsenal_1.1.5.pk3", MODS + r"\DoomRL_Monsters_Beta_7.3.pk3", MODS + r"\drlax_1.2b.pk3"]
    code = subprocess.run([sys.executable, QUIET, "--timeout", "20", "--", str(after), *base, "-norun", "-nosound", "-stdout", "-config", str(work / "norun.ini")], capture_output=True).returncode
    print("norun exit", code)
    for name, game, seconds in (("stock", base + ["+map", "E1M1"], 12), ("drla", base + drla + ["+map", "E1M1"], 30)):
        a = [l for l in launch(before, work, name + "-before", game, seconds) if not VOLATILE.search(l)]
        b = [l for l in launch(after, work, name + "-after", game, seconds) if not VOLATILE.search(l)]
        only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
        fatal = sum("FATAL" in l or "Execution could not continue" in l for l in b)
        door = sum("DDDOORS" in l or "DDTRANSITION" in l or "[bridge]" in l for l in b)
        print(f"{name}: lines before {len(a)}, after {len(b)}, only before {len(only_a)}, only after {len(only_b)}, fatal {fatal}, door or bridge lines {door}, entered {any('E1M1' in l for l in b)}")
        for line in (only_a[:4] + only_b[:4]):
            print("   diff:", line[:130])


{"regkey": regkey, "dfu": dfu, "doom": doom}[sys.argv[1]]()
