"""Standalone (no bridge) interior test for location state card 1.

usage: interior.py prepare | run NAME first|load [--base] | remap | unmap | sig NAME

prepare: picks a building of town group 7154 whose converted interior has at least two map pickups, converts it with
         this lane's converter into a private cache (review\\locledger\\icache), and notes its door and exit.
run:     starts UZDoom in the town through quiet_run with tools/location_ledger/interior.zs. "first" makes the changes,
         leaves, re-enters, and autosaves in the town; "load" loads that save and enters again. --base uses the
         baseline engine built before this card.
remap:   fakes a converter regrouping: the building's cache file moves to another space id (so another map name) and
         the town's door is pointed at it. unmap undoes it.
"""
import json
import re
import shutil
import struct
import subprocess
import sys
import time
import zlib
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import location_ledger as ll  # noqa: E402

base = ll.base
REVIEW = ll.REVIEW
CACHE = REVIEW / "icache"
RUN = REVIEW / "irun"
STATE = REVIEW / "interior.json"
GROUP = 7154
SHIFT = 600  # The fake regrouping moves the building this many space ids along.
NEW_UZ = ll.UZ_TREE / "uzdoom.exe"
BASE_UZ = REVIEW / "base" / "uzdoom.exe"
FATAL = ("DIED WITH FATAL", "VM execution aborted", "Script error", "Execution could not continue", "Unable to open map")


def read_ddt(path):
    with open(path, "rb") as f:
        assert f.read(4) == b"DDT3"
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return [(name, zlib.decompress(f.read(packed)) if raw else b"") for name, raw, packed in heads]


def write_ddt(path, lumps):
    packed = [zlib.compress(body) if body else b"" for _, body in lumps]
    with open(path, "wb") as f:
        f.write(b"DDT3" + struct.pack("<i", len(lumps)))
        for (name, body), p in zip(lumps, packed):
            f.write(name.encode().ljust(8, b"\0") + struct.pack("<II", len(body), len(p)))
        for p in packed:
            f.write(p)


def town_file():
    return CACHE / f"T{GROUP:05d}.ddt"


def prepare():
    CACHE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ll.pickup.DATA / "cache" / f"T{GROUP:05d}.ddt", town_file())
    doors = [l.split() for l in dict(read_ddt(town_file()))["DDDOORS"].decode().splitlines() if l.startswith("0 ")]
    work = REVIEW / "iconvert"
    seen = set()
    for row in doors:
        space = int(row[1])
        if space in seen or len(seen) >= 25:
            continue
        seen.add(space)
        out = CACHE / f"T{space:05d}.ddt"
        code = subprocess.call(["dotnet", str(ll.CONVERTER_DIR / "DungeonConverter.dll"), "--group", str(space), "--ddt", str(out), "--out", str(work),
                                "--arena2", base.DAGGER + r"\ARENA2"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if code or not out.exists():
            continue
        lumps = dict(read_ddt(out))
        wad = lumps.get("MAPWAD", b"")
        count, table = struct.unpack("<ii", wad[4:12]) if len(wad) >= 12 else (0, 0)
        text = b""
        for k in range(count):
            off, size = struct.unpack("<ii", wad[table + 16 * k:table + 16 * k + 8])
            if wad[table + 16 * k + 8:table + 16 * k + 16].rstrip(b"\0") == b"TEXTMAP":
                text = wad[off:off + size]
        pickups = len(re.findall(rb"type = 3164[012];", text))
        town = lumps["DDTOWN"].decode()
        place = re.search(r"place (-?\d+) (\d+)", town)
        print(f"space {space}: {pickups} pickups, place {place.group(0) if place else None}")
        if pickups >= 2 and place:
            exit_row = next(l.split()[1:] for l in town.splitlines() if l.startswith("exit "))
            STATE.write_text(json.dumps({"space": space, "door": row[3:8], "exit": exit_row, "place": place.group(0)}))
            print("chosen", space)
            return
        out.unlink()
    sys.exit("no building with two pickups among the first doors")


def remap(undo=False):
    s = json.loads(STATE.read_text())
    old, new = (s["space"] + SHIFT, s["space"]) if undo else (s["space"], s["space"] + SHIFT)
    shutil.move(CACHE / f"T{old:05d}.ddt", CACHE / f"T{new:05d}.ddt")
    lumps = read_ddt(town_file())
    fixed = []
    for name, body in lumps:
        if name == "DDDOORS":
            body = "\n".join(re.sub(rf"^0 {old} ", f"0 {new} ", l) for l in body.decode().split("\n")).encode()
        fixed.append((name, body))
    write_ddt(town_file(), fixed)
    print(f"building moved from space {old} to {new}; town door rewritten")


def run(name, mode, use_base):
    s = json.loads(STATE.read_text())
    RUN.mkdir(parents=True, exist_ok=True)
    saves = RUN / ("saves-base" if use_base else "saves")
    saves.mkdir(exist_ok=True)
    console = RUN / f"log-{name}.txt"
    console.unlink(missing_ok=True)
    text = (HERE / "interior.zs").read_text().replace("@DOOR@", ", ".join(s["door"])).replace("@EXIT@", ", ".join(s["exit"][:5])).replace("@MODE@", mode)
    harness = RUN / f"{name}_harness.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        z.writestr("zscript.txt", text)
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "LLHarness" }\n')
    data = ll.pickup.DATA
    files = [data / "ddruntime.pk3", data / "overworld.pk3", ll.md.SOURCE_SPRITES, base.WORKTREE / "mods" / "doomerfall" / "src", harness]
    uz = [str(BASE_UZ if use_base else NEW_UZ), "-iwad", base.IWAD2, "-noautoload", "-skill", "3", "-config", str(RUN / f"{name}.ini"), "-savedir", str(saves),
          "-ddtowncache", str(CACHE), "-ddconverter", str(ll.CONVERTER_DIR / "DungeonConverter.exe"), "-ddarena2", base.DAGGER + r"\ARENA2",
          "+logfile", name, "+vid_fullscreen", "0", "+wipetype", "0", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]
    uz += ["-file"] + [str(f) for f in files]
    if mode == "load":
        save = max(saves.glob("*.zds"), key=lambda p: p.stat().st_mtime)
        uz += ["-loadgame", save.name]  # Relative to -savedir.
    else:
        for old in saves.glob("*.zds"):
            old.unlink()
        uz += ["+map", f"DDT{GROUP:05d}"]
    timeout = 60
    proc = subprocess.Popen([sys.executable, base.QUIET, "--timeout", str(timeout), "--cwd", str(RUN), "--"] + uz,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason, end = "timeout", time.time() + timeout + 3
    while time.time() < end and proc.poll() is None:
        time.sleep(0.25)
        body = base.read(console)
        if "LLDONE" in body:
            reason = "route finished"
            time.sleep(1)
            break
        if any(k in body for k in FATAL):
            reason = "fatal"
            break
    if proc.poll() is None:
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    print("stopped:", reason)
    sig(name)


def rows(name, when):
    return [l.split(" ", 2)[2] for l in base.read(RUN / f"log-{name}.txt").splitlines()
            if l.startswith(f"LLSIG {when} ") and not re.match(rf"LLSIG {when} (begin|end)", l)]


def sig(name):
    body = base.read(RUN / f"log-{name}.txt")
    for line in body.splitlines():
        if line.startswith(("DDTM ", "LL", "DDTRANSITION", "DDTCACHE", "DDTCONV")) and not line.startswith("LLSIG") or any(k in line for k in FATAL):
            print(" ", line[:200])
    for when in ("leave", "reentry", "loaded"):
        r = rows(name, when)
        if r:
            print(f"  signature {when}: {len(r)} rows")


def compare(a, wa, b, wb):
    ra, rb = rows(a, wa), rows(b, wb)
    print(f"{a}:{wa} ({len(ra)} rows) vs {b}:{wb} ({len(rb)} rows): identical {ra == rb}")
    for row in sorted(set(ra) ^ set(rb))[:20]:
        print("  only in", f"{a}:{wa}" if row in ra else f"{b}:{wb}", row)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "prepare":
        prepare()
    elif command == "run":
        run(sys.argv[2], sys.argv[3], "--base" in sys.argv)
    elif command == "remap":
        remap()
    elif command == "unmap":
        remap(True)
    elif command == "sig":
        sig(sys.argv[2])
    elif command == "compare":
        compare(*sys.argv[2:6])
    else:
        sys.exit(__doc__)
