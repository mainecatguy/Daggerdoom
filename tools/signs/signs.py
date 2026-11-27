"""Readable signs (Daggerfall's bulletin boards): census, paired test and demo.

usage: signs.py census | convert GROUP | build-uz | assemble | run NAME [--board N] | check
census lists the location groups that hold a bulletin board (converter --list-boards).
convert converts one group with the converter built from this checkout, prints its boards' Doom positions and the
map lines around each (are they solid in Doom?).
build-uz builds this checkout's UZDoom (unchanged by this work) so the stage matches the branch.
assemble stages review\\readable-signs: launcher, bridge DLL, data and item package from SOURCE, this checkout's UZDoom
and Daggerfall Unity builds, fresh Doomerfall packages, the test town's cache file, and a demo play.bat.
run starts both games minimized with DRLA on quiet_run's private desktop and presses Doom's real Use button (QA channel)
at one of the town's bulletin boards, from too far and then close, and saves Doom's screen with Daggerfall's box.
check runs DOOM.WAD E1M1 with no bridge, stock and with DRLA.
"""
import argparse
import math
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUILD = Path(r"D:\dev\DoomDaggerfall-build\signs-converter")
CONVERTER = BUILD / "bin" / "Release" / "net9.0" / "DungeonConverter.exe"
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
ARENA2 = GAME / "DAGGER" / "ARENA2"


def census():
    out = subprocess.run([str(CONVERTER), "--list-boards", "--arena2", str(ARENA2)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    (BUILD / "boards.txt").write_text(out.stdout + out.stderr)
    print(out.stdout[-6000:], out.stderr[-2000:])


def convert(group, cache):
    """Converts one location group into the cache, as the engine does, and returns the boards' Doom positions."""
    cache.mkdir(parents=True, exist_ok=True)
    work = BUILD / "work"
    out = subprocess.run([str(CONVERTER), "--group", str(group), "--ddt", str(cache / f"T{group:05d}.ddt"), "--out", str(work),
                          "--arena2", str(ARENA2), "--list-board-positions"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    boards = [tuple(float(v) for v in l.split()[1:]) for l in out.stdout.splitlines() if l.startswith("BOARDPOS ")]
    if out.returncode:
        sys.exit(f"converter failed {out.returncode}: {out.stderr[-2000:]}")
    return boards


UZ_BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-signs")


def build_uzdoom():
    """This worktree's UZDoom (unchanged by this work), so the stage matches the branch's bridge kinds."""
    with open(UZ_BUILD.parent / "uzdoom-signs-build.log", "w") as log:
        code = subprocess.call(["cmake", "-S", str(REPO / "UZDoom"), "-B", str(UZ_BUILD), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=log, stderr=log)
        if not code:
            code = subprocess.call(["cmake", "--build", str(UZ_BUILD), "--config", "Release", "--parallel", "6"], stdout=log, stderr=log)
        # The bridge DLL and launcher share the session layout with UZDoom, so they come from this checkout too.
        for name in ("bridge", "launcher"):
            out = UZ_BUILD.parent / f"{name}-signs"
            if not code:
                code = subprocess.call(["cmake", "-S", str(REPO / name), "-B", str(out), "-G", "Visual Studio 18 2026", "-A", "x64"], stdout=log, stderr=log)
            if not code:
                code = subprocess.call(["cmake", "--build", str(out), "--config", "Release", "--parallel", "6"], stdout=log, stderr=log)
    print("uzdoom, bridge and launcher build exit", code)


def lumps(path):
    with open(path, "rb") as f:
        f.read(4)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


def collision_near(ddt, boards, reach=48):
    """The map's lines within reach of each board's centre: is the board solid in Doom?"""
    found = lumps(ddt)
    print("lumps:", ", ".join(f"{k} {len(v)}" for k, v in found.items()))
    text = found["MAPWAD"].decode(errors="replace")
    blocks = re.findall(r"(vertex|linedef)\s*\{([^}]*)\}", text)
    verts, lines = [], []
    for kind, body in blocks:
        fields = dict((k.strip(), v.strip().strip('"')) for k, v in re.findall(r"(\w+)\s*=\s*([^;]+);", body))
        if kind == "vertex":
            verts.append((float(fields["x"]), float(fields["y"])))
        else:
            lines.append((int(fields["v1"]), int(fields["v2"]), "blocking" in fields or "sideback" not in fields))
    print("map:", len(verts), "vertices,", len(lines), "lines")
    for b in boards:
        near = []
        for v1, v2, solid in lines:
            (x1, y1), (x2, y2) = verts[v1], verts[v2]
            dx, dy = x2 - x1, y2 - y1
            t = max(0, min(1, ((b[0] - x1) * dx + (b[1] - y1) * dy) / (dx * dx + dy * dy or 1)))
            d = math.hypot(x1 + t * dx - b[0], y1 + t * dy - b[1])
            if d < reach:
                near.append((round(d, 1), (x1, y1, x2, y2), solid))
        near.sort()
        print("board", b[:2], "lines within", reach, ":", len(near), near[:6])


REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\readable-signs")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\transport")  # launcher, bridge DLL, data, converter, item package
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
MODS = GAME.parent / "GameMods"
DRLA = ["DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3"]
DATA = ["ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3"]
GROUP = 1426  # Cromwark Hamlet (Wrothgarian Mountains), a small walled town: 8 boards at its 4 gates
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Execution could not continue", "Unable to open map")


def read(path):
    return path.read_text(errors="replace") if path.exists() else ""


def assemble():
    sys.path.insert(0, str(REPO / "scripts" / "play"))
    argv, sys.argv[:] = sys.argv[:], sys.argv[:1]
    import install  # noqa: E402  (only for its registry isolation)
    sys.argv[:] = argv
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("uzdoom", "dfu", "data"):
        shutil.rmtree(REVIEW / name, ignore_errors=True)
    shutil.copytree(SOURCE / "uzdoom", REVIEW / "uzdoom")
    for f in (UZ_BUILD / "Release").glob("*"):
        if f.is_file() and f.suffix.lower() in (".exe", ".pk3"):
            shutil.copy2(f, REVIEW / "uzdoom" / f.name)
    shutil.copytree(SOURCE / "data", REVIEW / "data", ignore=shutil.ignore_patterns("work"))
    shutil.copy2(BUILD / "cache" / f"T{GROUP:05d}.ddt", REVIEW / "data" / "cache" / f"T{GROUP:05d}.ddt")
    shutil.copy2(BUILD / "boards.txt", REVIEW / "data" / "boards.txt")
    shutil.copy2(SOURCE / "dfitems.pk3", REVIEW / "dfitems.pk3")
    shutil.copy2(UZ_BUILD.parent / "launcher-signs" / "Release" / "doomerfall-launcher.exe", REVIEW / "doomerfall-launcher.exe")
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), str(REVIEW / "doomerfall.pk3")])
    subprocess.check_call([sys.executable, str(REPO / "scripts" / "doomerfall" / "build_pk3.py"), "--drla", str(REVIEW / "doomerfall-drla.pk3")])
    shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", REVIEW / "dfu", ignore=shutil.ignore_patterns("*.pdb"))
    plugins = REVIEW / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
    plugins.mkdir(parents=True, exist_ok=True)
    shutil.copy2(UZ_BUILD.parent / "bridge-signs" / "Release" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
    (REVIEW / "dfu" / "Portable.txt").write_text("")
    install.isolate_registry(REVIEW / "dfu")
    write_demo()
    print("assembled", REVIEW)


def boards():
    """The test town's boards in Doom map units, from the converter (x, y, bottom z, facing x, facing y)."""
    saved = BUILD / f"boardpos-{GROUP}.txt"
    if not saved.exists():
        saved.write_text("\n".join(" ".join(str(v) for v in b) for b in convert(GROUP, BUILD / "cache")))
    return [tuple(float(v) for v in l.split()) for l in saved.read_text().splitlines() if l.strip()]


def launch(runs, extra_mods, uz_extra, df_extra, minimized):
    command = [str(REVIEW / "doomerfall-launcher.exe")] + (["--minimized"] if minimized else []) + ["--nodraw",
               "--uzdoom", str(REVIEW / "uzdoom" / "uzdoom.exe"), "--dfu", str(REVIEW / "dfu" / "DaggerfallUnity.exe"),
               "--iwad", str(GAME / "wads" / "DOOM2.WAD"), "--uzdoom-cwd", str(runs), "--log", str(runs / "launcher.log")]
    for mod in [MODS / n for n in DRLA] + [REVIEW / "data" / n for n in DATA] + [REVIEW / "dfitems.pk3", REVIEW / "doomerfall.pk3", REVIEW / "doomerfall-drla.pk3"] + extra_mods:
        command += ["--mod", str(mod)]
    uz = ["-config", str(runs / "uzdoom.ini"), "-savedir", str(runs / "saves"), "-dfbridgelog", str(runs / "uz.log"), "-skill", "3",
          "-ddtowncache", str(REVIEW / "data" / "cache"), "-ddconverter", str(REVIEW / "data" / "converter" / "DungeonConverter.exe"),
          "-ddarena2", str(ARENA2), "+vid_fullscreen", "0", "+map", f"DDT{GROUP:05d}"] + uz_extra
    df = ["-dfbridgelog", str(runs / "df.log"), "-dfsynctest", str(GAME / "DAGGER"), "-screen-fullscreen", "0",
          "-screen-width", "1280", "-screen-height", "800"] + df_extra
    for arg in uz:
        command += ["--uzdoom-arg", arg]
    for arg in df:
        command += ["--dfu-arg", arg]
    return command


def write_demo():
    b = boards()[0]
    x, y = b[0] + b[3] * 56, b[1] + b[4] * 56
    start = f"""version "4.14"
// Demo only: starts the player in front of one of the town's bulletin boards, beside a gate.
class SGDemoStart : StaticEventHandler
{{
	bool done;
	override void WorldLoaded(WorldEvent e) {{ if (e.IsSaveGame) done = true; }}
	override void WorldTick()
	{{
		if (done || level.maptime < 5 || !players[0].mo) return;
		done = true;
		let p = players[0].mo;
		p.SetOrigin(({x:.1f}, {y:.1f}, {b[2]:.1f}), false);
		p.SetZ(p.floorz);
		p.angle = atan2({-b[4]:.6f}, {-b[3]:.6f});
	}}
}}
"""
    with zipfile.ZipFile(REVIEW / "demo_start.pk3", "w") as z:
        z.writestr("zscript.txt", start)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SGDemoStart" }\n')
    command = launch(REVIEW / "play", [REVIEW / "demo_start.pk3"], ["+i_pauseinbackground", "0"], ["-dfmute"], False)
    line = " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in command).replace(str(REVIEW) + "\\", "%HERE%")
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Readable signs. Starts with DRLA in Cromwark Hamlet, a small walled town, facing one of the bulletin boards that\r\n"
        "rem Daggerfall places beside each town gate. Press Use (E) on the board: Daggerfall's notice box opens with the town's\r\n"
        "rem name and its news or rumors, as in Daggerfall Unity. A click or a key closes it. From too far away Daggerfall says\r\n"
        "rem \"You are too far away.\" Every walled town has these boards at its gates (two per gate).\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        f"start \"\" {line}\r\n", newline="")


def run(name, side):
    runs = REVIEW / "run" / name
    shutil.rmtree(runs, ignore_errors=True)
    (runs / "saves").mkdir(parents=True)
    (runs / "qa").mkdir()
    inbox = runs / "qa" / "inbox.txt"
    inbox.write_text("")
    board = boards()[side]
    print("board", board)
    harness = runs / "harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", (HERE / "harness.zs").read_text().replace("@BOARD@", ", ".join(f"{v:.4f}" for v in board)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "SGHarness" }\n')
    console, views = runs / "log-console.txt", runs / "views.log"
    uz = ["-ddqa", str(inbox.parent), "-noactivate", "-nosound", "-noautoload", "+logfile", "console", "+wipetype", "0",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    timeout = 150
    command = [sys.executable, QUIET, "--timeout", str(timeout), "--"] + launch(runs, [harness], uz, ["-dfmute", "-dfstatustest", str(views)], True)
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end, sent, shots = "timeout", time.time() + timeout + 3, 0, 0
    opened_at = None
    while time.time() < end and proc.poll() is None:
        time.sleep(0.2)
        body = read(console)
        wanted = len(re.findall(r"(?m)^SGUSE\s*$", body))
        while sent < wanted:
            sent += 1
            with open(inbox, "a") as f:
                f.write(f"u{sent} use\n")
        if opened_at is None and "Daggerfall opened menu" in read(runs / "uz.log"):
            opened_at = time.time()
        if opened_at and shots < 2 and time.time() - opened_at > 1.5 * (shots + 1):
            shots += 1
            with open(inbox, "a") as f:
                f.write(f"s{shots} con screenshot \"{runs / f'board-{shots}.png'}\"\n")
        if shots >= 2 and time.time() - opened_at > 4.5:
            reason = "box shown and captured"
            break
        if "SGDONE" in body:
            reason = "route finished"
            time.sleep(2)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    body, dflog, uzlog = read(console), read(runs / "df.log"), read(runs / "uz.log")
    for line in body.splitlines():
        if line.startswith(("SGPRESS", "SGDONE")) or any(k in line for k in FATAL) or "too far" in line.lower():
            print("doom:", line[:200])
    infos = [l for l in dflog.splitlines() if "info: request" in l or "opened" in l.lower() and "ui" in l.lower()]
    for line in infos:
        print("df:", line[:300])
    boxes = re.findall(r"top DaggerfallMessageBox \| area (\S+) \| here '(.*?)' \| hour (\d+) \| text '(.*)'", read(views))
    for box in boxes:
        print("box:", box[0], box[1], "|", box[3][:400])
    far = [l for l in infos if "bulletin board" in l and "too far away" in l.lower()]
    near = [l for l in infos if "bulletin board" in l and re.search(r", [0-5]\.\d m away: 0 messages", l)]
    shown = "Daggerfall opened menu" in uzlog
    town = boxes[-1][1] if boxes else ""
    checks = [("a press from 260 units reached a board and Daggerfall said it is too far away", bool(far)),
              ("a press from 40 units read the board in Daggerfall, with no HUD message", bool(near)),
              ("Daggerfall opened its message box and Doom showed it", shown),
              ("the box starts with the town's name, as Daggerfall Unity's board does", bool(boxes) and bool(town) and boxes[-1][3].startswith(town))]
    for what, ok in checks:
        print("SGCHECK", "pass" if ok else "FAIL", what)
    print("RESULT", "PASS" if all(ok for _, ok in checks) else "FAIL")


def check():
    runs = REVIEW / "run"
    runs.mkdir(parents=True, exist_ok=True)
    for label, mods in (("stock", []), ("drla", [str(MODS / n) for n in DRLA])):
        log = runs / f"log-check-{label}.txt"
        log.unlink(missing_ok=True)
        command = [sys.executable, QUIET, "--timeout", "30", "--cwd", str(runs), "--", str(REVIEW / "uzdoom" / "uzdoom.exe"), "-noactivate", "-iwad", str(GAME / "wads" / "DOOM.WAD"),
                   "-config", str(runs / f"check-{label}.ini"), "-nosound", "-noautoload", "-skill", "3", "-file", *mods, "+logfile", f"check-{label}",
                   "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "+map", "E1M1", "+wait 140;quit"]
        code = subprocess.call(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        body = read(log)
        print(label, "exit", code, "| E1M1 entered", "E1M1" in body, "| script errors", sum("Script error" in l for l in body.splitlines()),
              "| fatal", any(k in body for k in FATAL))


ap = argparse.ArgumentParser()
ap.add_argument("command", choices=("census", "convert", "build-uz", "assemble", "run", "check"))
ap.add_argument("arg", nargs="?", default="")
ap.add_argument("--board", type=int, default=0, help="run: which of the town's boards")
args = ap.parse_args()
if args.command == "census":
    census()
elif args.command == "assemble":
    assemble()
elif args.command == "run":
    run(args.arg or "t", args.board)
elif args.command == "check":
    check()
elif args.command == "build-uz":
    build_uzdoom()
elif args.command == "convert":
    boards = convert(int(args.arg), BUILD / "cache")
    for b in boards:
        print("board", b)
    collision_near(BUILD / "cache" / f"T{int(args.arg):05d}.ddt", boards)
