"""Collision lines of a UDMF map inside a box, with the sectors on each side.

usage: wad_lines.py <map.wad> x0,x1,y0,y1
"""
import re
import struct
import sys


def load(wad):
    data = open(wad, "rb").read()
    n, off = struct.unpack("<ii", data[4:12])
    for i in range(n):
        o, s, name = struct.unpack("<ii8s", data[off + 16 * i: off + 16 * i + 16])
        if name.rstrip(b"\0") == b"TEXTMAP":
            text = data[o:o + s].decode(errors="replace")
    return re.findall(r"(\w+)\s*\{([^}]*)\}", text)


def get(block, key):
    m = re.search(r"\b" + key + r"\s*=\s*([-\d.]+)", block)
    return float(m.group(1)) if m else None


def main():
    blocks = load(sys.argv[1])
    x0, x1, y0, y1 = map(float, sys.argv[2].split(","))
    verts = [(get(b, "x"), get(b, "y")) for k, b in blocks if k == "vertex"]
    sides = [b for k, b in blocks if k == "sidedef"]
    sectors = [b for k, b in blocks if k == "sector"]
    for line in (b for k, b in blocks if k == "linedef"):
        a, c = verts[int(get(line, "v1"))], verts[int(get(line, "v2"))]
        if max(a[0], c[0]) < x0 or min(a[0], c[0]) > x1 or max(a[1], c[1]) < y0 or min(a[1], c[1]) > y1:
            continue
        info = []
        for key in ("sidefront", "sideback"):
            s = get(line, key)
            if s is not None and s >= 0:
                sec = int(get(sides[int(s)], "sector"))
                slope = " sloped" if get(sectors[sec], "floorplane_c") else ""
                info.append(f"{sec}: floor {get(sectors[sec], 'heightfloor')} ceil {get(sectors[sec], 'heightceiling')}{slope}")
        print(f"({a[0]:.1f},{a[1]:.1f})-({c[0]:.1f},{c[1]:.1f}) {'two-sided' if len(info) > 1 else 'wall'} | " + " | ".join(info))


if __name__ == "__main__":
    main()
