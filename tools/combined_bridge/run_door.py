"""Takes a real door trip with both games running through the real launcher, minimized, and prints the evidence.

Usage: run_door.py NAME [--baseline] [--group 9183] [--target ID|dungeon] [--menu] [--timeout 30]
The route waits for Daggerfall, takes 10 damage outside, goes in, takes 7 inside, holds, comes out, and holds.
--menu also opens Daggerfall's travel map indoors and closes it with Esc.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import re
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\combined-bridge")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
DAGGER = r"D:\dev\DoomDaggerfall\GameResources\DAGGER"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error", "Execution could not continue", "Unable to open map")

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--baseline", action="store_true")
ap.add_argument("--group", type=int, default=9183)
ap.add_argument("--target", default="")
ap.add_argument("--menu", action="store_true")
ap.add_argument("--seam", action="store_true", help="after the door trips, walk out of town and warp across the overworld")
ap.add_argument("--timeout", type=int, default=30)
args = ap.parse_args()

root = REVIEW / "baseline" if args.baseline else REVIEW
data, run = REVIEW / "data", root / "run"
run.mkdir(parents=True, exist_ok=True)
uz_log, df_log, console, launcher_log = run / f"{args.name}-uz.log", run / f"{args.name}-df.log", run / f"log-{args.name}.txt", run / f"{args.name}-launcher.log"
for path in (uz_log, df_log, console, launcher_log):
    path.unlink(missing_ok=True)


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


doors = [l.split() for l in lumps(data / "cache" / f"T{args.group:05d}.ddt")["DDDOORS"].decode().splitlines() if l.strip()]
if args.target == "dungeon":
    door = next(d for d in doors if d[0] == "1")
elif args.target:
    door = next(d for d in doors if d[0] == "0" and d[1] == args.target)
else:  # The first building whose interior is already converted, so the launch stays short.
    door = next(d for d in doors if d[0] == "0" and (data / "cache" / f"T{d[1]}.ddt").exists())
exits = []
if args.target == "dungeon":
    with zipfile.ZipFile(data / "privateershold_doors.pk3") as z:
        exits = [l.split()[1:] for l in z.read("DDDUNGN").decode().splitlines() if l.startswith("exit")][:1]

text = (HERE.parent / "overworld" / "door_harness.zs").read_text()
text = text.replace("@DOORS@", ", ".join(door[3:8])).replace("@EXITS@", ", ".join(v for e in exits for v in e) or "0, 0, 0, 0, 0")
text = text.replace("EXITS.Size() >= FIELDS", "HasExit()").replace("const FIELDS = 5;", "const FIELDS = 5;\n\tbool HasExit() { int i = level.maptime * 0 + 3; return EXITS[i] != 0 || EXITS[i + 1] != 0; }")
text = text.replace("@MODE@", "route")
# Real damage has to reach the bridge, and Daggerfall has to be in play before the first door.
text = text.replace("players[0].cheats |= CF_GODMODE;", "")
text = text.replace("if (inside || level.maptime < 4) break;", 'if (inside || level.maptime < 4 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;\n\t\t\tif (st.visits == 0 && !st.hitOut) { st.hitOut = true; p.DamageMobj(null, null, 10, \'None\'); Console.Printf("CBHP hit 10 outside"); }')
text = text.replace("int leg, phase, timer, visits, killed;", "int leg, phase, timer, visits, killed; bool hitOut, hitIn;")
text = text.replace("if (st.timer == 24)\n", 'if (st.timer == 12 && !st.hitIn) { st.hitIn = true; p.DamageMobj(null, null, 7, \'None\'); Console.Printf("CBHP hit 7 inside, hp=%d", p.player.health); }\n\t\t\t' + ('if (st.timer == 70) CVar.FindCVar("dd_ui_test_hold").SetInt(0);\n\t\t\t' if args.menu else '') + 'if (st.timer == 24)\n')
text = text.replace("st.timer == 28", "st.timer == 175").replace("st.timer > 40 && !inside", "st.timer > 180 && !inside")
text = text.replace('Console.Printf("DTRETURN leg', 'Console.Printf("CBHP back outside, hp=%d", p.player.health); Console.Printf("DTRETURN leg')
tail = "if (st.leg >= count && ++st.timer < 140) return;"
if args.seam:  # Walk out of the town through the real handoff, then make a long overworld warp.
    tail = ('if (st.leg >= count) { st.timer++;\n'
            '\t\t\tif (st.timer == 60) { Console.Printf("CBSEAM leaving town from %s", level.MapName); p.SetOrigin(p.pos + (30000, 0, 0), false); }\n'
            '\t\t\tif (st.timer == 200) { Console.Printf("CBSEAM on %s, warping", level.MapName); CVar.FindCVar("dd_tm_warp").SetString("14079 43710"); }\n'
            '\t\t\tif (st.timer == 330) Console.Printf("CBSEAM arrived on %s", level.MapName);\n'
            '\t\t\tif (st.timer < 420) return; }')
text = text.replace("if (st.leg >= count) { Finish(", tail + "\n\t\tif (st.leg >= count) { Finish(")
harness = run / f"{args.name}_harness.pk3"
with zipfile.ZipFile(harness, "w") as z:
    z.writestr("zscript.txt", text)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DTHarness" }\n')

uz_args = ["-noactivate", "-config", str(run / f"{args.name}.ini"), "-savedir", str(run / "saves"), "-dfbridgelog", str(uz_log), "-nosound", "-noautoload", "-skill", "3",
           "-ddtowncache", str(data / "cache"), "-ddconverter", str(data / "converter" / "DungeonConverter.exe"), "-ddarena2", DAGGER + r"\ARENA2",
           "+logfile", args.name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
if args.menu:
    uz_args += ["-dfuitest", "1", "+dd_ui_test_hold", "1"]
uz_args += ["+map", f"DDT{args.group:05d}"]
dfu_args = ["-dfbridgelog", str(df_log), "-dfsynctest", DAGGER, "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"]
command = [sys.executable, QUIET, "--timeout", str(args.timeout), "--", str(root / "doomerfall-launcher.exe"), "--minimized", "--nodraw",
           "--uzdoom", str(root / "uzdoom" / "uzdoom.exe"), "--dfu", str(root / "dfu" / "DaggerfallUnity.exe"), "--iwad", IWAD,
           "--uzdoom-cwd", str(run), "--log", str(launcher_log)]
for name in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"):
    command += ["--mod", str(data / name)]
command += ["--mod", str(harness)]
for arg in uz_args:
    command += ["--uzdoom-arg", arg]
for arg in dfu_args:
    command += ["--dfu-arg", arg]


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def press_escape():
    user32 = ctypes.WinDLL("user32")
    user32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
    pids = {int(m) for m in re.findall(r"started UZDoom pid (\d+)", read(launcher_log))}
    found = []
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def visit(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(visit), 0)
    for hwnd in found[:1]:
        user32.PostMessageW(hwnd, 0x0100, 0x1B, 1 | (1 << 16))
        time.sleep(0.08)
        user32.PostMessageW(hwnd, 0x0101, 0x1B, 1 | (1 << 16) | (3 << 30))
    return bool(found)


proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
reason, end, escape_at = "timeout", time.time() + args.timeout + 3, 0
while time.time() < end and proc.poll() is None:
    time.sleep(0.2)
    body = read(console)
    bridge = read(uz_log)
    if args.menu and not escape_at and "ui: Daggerfall opened menu" in bridge:
        escape_at = time.time() + 2
    if escape_at > 0 and time.time() >= escape_at:
        print("escape sent:", press_escape())
        escape_at = -1
    if "DTDONE" in body:
        reason = "route finished"
        time.sleep(2.2)  # One more Daggerfall status line.
        break
    if any(k in body for k in FATAL) or "error:" in read(df_log):
        reason = "fatal"
        break
if proc.poll() is None:
    subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait()

print("stopped:", reason)
for line in read(console).splitlines():
    if re.match(r"(CBHP|CBSEAM|DDSTITCH arrive|DTFAIL|DTARRIVE|DTRETURN|DTDONE|DDTRANSITION)", line) or any(k in line for k in FATAL):
        print(line[:170])
for line in read(uz_log).splitlines():
    if " ui:" in line or "direct assignment" in line:
        print("uz", line[:150])
status = []
for line in read(df_log).splitlines():
    if "error" in line or " sync: " in line or " ui: " in line or "hp: applied" in line:
        print("df", line[:150])
    m = re.search(r"sync engaged=(\w+).*?gps=(-?\d+),(-?\d+) pixel=(-?\d+),(-?\d+) applies=(\d+) teleports=(\d+).*?health=(-?\d+)", line)
    if m:
        status.append(m.groups())
print("distinct Daggerfall states (engaged, pixel, teleports, health):")
seen = []
for s in status:
    key = (s[0], s[3], s[4], s[6], s[7])
    if not seen or seen[-1] != key:
        seen.append(key)
for key in seen:
    print(" ", key)
