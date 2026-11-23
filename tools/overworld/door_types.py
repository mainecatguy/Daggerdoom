"""Prints each interior's real Daggerfall building type, and a warp line beside a converted location.

Usage: door_types.py BUILD_DIR id,id,... [--warp GROUP]
"""
import os, re, struct, subprocess, sys, tempfile, zlib

build, ids = sys.argv[1], sys.argv[2].split(",")
exe = os.path.join(build, "converter", "DungeonConverter.exe")
arena2 = r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2"
if ids[0].startswith("pick"):  # pick:GROUP lists one enterable building of each real type.
    group = int(ids[0].split(":")[1])
    with open(os.path.join(build, "testcache", f"T{group:05d}.ddt"), "rb") as f:
        f.read(4)
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(struct.unpack("<i", f.read(4))[0])]
        data = {n: zlib.decompress(f.read(k)) if r else b"" for n, r, k in heads}
    doors = {l.split()[1] for l in data["DDDOORS"].decode().splitlines() if l.startswith("0 ")}
    out = subprocess.run([exe, "--group", str(group), "--list-buildings", "--out", build, "--arena2", arena2], capture_output=True, text=True, timeout=60).stdout
    types = {}
    for _, i, t in (l.split() for l in out.splitlines() if l.startswith("BUILDING")):
        if i in doors:
            types.setdefault(t, []).append(i)
    print({t: len(v) for t, v in types.items()})
    print(",".join(v[len(v) // 2] for t, v in types.items() if not t.startswith("House")) + "," + types["House2"][0])
    print(" ".join(f"{v[len(v) // 2]}={t}" for t, v in types.items()))
    sys.exit(0)
with tempfile.TemporaryDirectory(dir=build) as temp:
    for i in ids:
        p = subprocess.run([exe, "--group", i, "--ddt", os.path.join(temp, i + ".ddt"), "--out", temp, "--arena2", arena2], capture_output=True, text=True, timeout=60)
        m = re.search(r"interior (\S+) .*? (\S+:\d+) type (\S+)", p.stdout)
        print(i, *(m.groups() if m else ("failed", p.returncode)))
if "--warp" in sys.argv:
    group = int(sys.argv[sys.argv.index("--warp") + 1])
    with open(os.path.join(build, "testcache", f"T{group:05d}.ddt"), "rb") as f:
        f.read(4)
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(struct.unpack("<i", f.read(4))[0])]
        data = {n: zlib.decompress(f.read(k)) if r else b"" for n, r, k in heads}
    rects = [list(map(int, l.split()[1:])) for l in data["DDTOWN"].decode().splitlines() if l.startswith("rect")]
    print(f'dd_tm_warp "{max(r[1] for r in rects) + 30} {(rects[0][2] + rects[0][3]) // 2}"')
