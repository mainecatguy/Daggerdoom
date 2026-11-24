"""Converts a location, lists its doors, and converts a sample of its building interiors.

Usage: interior_batch.py GROUP CACHE_DIR CONVERTER [--sample N]
Generated files stay in CACHE_DIR, which must be outside the repository.
"""
import argparse, os, struct, subprocess, sys, time, zlib


def lumps(path):
    with open(path, "rb") as f:
        if f.read(4) != b"DDT3":
            sys.exit("not a cache file: " + path)
        count = struct.unpack("<i", f.read(4))[0]
        heads = [(f.read(8).rstrip(b"\0").decode(), *struct.unpack("<II", f.read(8))) for _ in range(count)]
        return {name: zlib.decompress(f.read(packed)) if raw else b"" for name, raw, packed in heads}


ap = argparse.ArgumentParser()
ap.add_argument("group", type=int)
ap.add_argument("cache")
ap.add_argument("converter")
ap.add_argument("--sample", type=int, default=12)
ap.add_argument("--arena2", default=r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2")
args = ap.parse_args()
os.makedirs(args.cache, exist_ok=True)


def convert(target):
    out = os.path.join(args.cache, f"T{target:05d}.ddt")
    if os.path.exists(out):
        return out, 0.0, 0, ""
    start = time.time()
    p = subprocess.run([args.converter, "--group", str(target), "--ddt", out, "--out", os.path.join(args.cache, "work", str(target)), "--arena2", args.arena2],
                       capture_output=True, text=True, timeout=120)
    lines = (p.stdout + p.stderr).strip().splitlines()
    return out, time.time() - start, p.returncode, lines[-1] if lines else ""


town, seconds, code, last = convert(args.group)
if code:
    sys.exit(f"town failed: {last}")
doors = [l.split() for l in lumps(town)["DDDOORS"].decode().splitlines() if l.strip()]
buildings = sorted({int(d[1]) for d in doors if d[0] == "0"})
print(f"group {args.group}: {len(doors)} doors, {len(buildings)} buildings, {sum(d[0] == '1' for d in doors)} dungeon doors, town convert {seconds:.1f}s")
step = max(1, len(buildings) // max(1, args.sample))
ok = failed = 0
times = []
for b in buildings[::step][:args.sample]:
    _, t, code, last = convert(b)
    ok += code == 0
    failed += code != 0
    times.append(t)
    print(f"{b} exit={code} {t:.2f}s {last[:150]}")
print(f"interiors ok={ok} failed={failed} slowest={max(times or [0]):.2f}s")
