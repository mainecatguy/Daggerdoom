"""Top-down picture of a converted map's collision lines, for judging jagged edges and stepped ramps.

Usage: python tools/dungeon_converter/sector_view.py <map.wad> <out.png> [--crop x0,y0,x1,y1] [--scale 0.5] [--z lo,hi]
Colours: grey = axis-aligned wall, cyan = angled wall, yellow = flat-to-flat floor step (a stair or jag),
green = edge of a sloped floor, dark = boundary with no floor difference. --z keeps lines whose sectors have a floor in range.
Also prints counts: angled vs axis lines, and "stair corners" (90-degree turns between two short axis-aligned wall
segments, the signature of a staircase edge on a diagonal).
"""
import argparse
import re
import struct
from collections import defaultdict

from PIL import Image, ImageDraw


def read_textmap(path):
    data = open(path, "rb").read()
    count, offset = struct.unpack_from("<4xii", data, 0)
    for n in range(count):
        pos, size, name = struct.unpack_from("<ii8s", data, offset + 16 * n)
        if name.rstrip(b"\0") == b"TEXTMAP":
            return data[pos:pos + size].decode("ascii", "replace")
    raise SystemExit("no TEXTMAP in " + path)


def parse(text):
    blocks = defaultdict(list)
    for kind, body in re.findall(r"(\w+)\s*\{([^}]*)\}", text):
        fields = {}
        for key, value in re.findall(r"(\w+)\s*=\s*([^;]+);", body):
            value = value.strip()
            fields[key] = value.strip('"') if value.startswith('"') else (float(value) if re.match(r"^-?[\d.eE+-]+$", value) else value)
        blocks[kind].append(fields)
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wad")
    ap.add_argument("out")
    ap.add_argument("--crop")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--z")
    a = ap.parse_args()
    m = parse(read_textmap(a.wad))
    verts = [(v["x"], v["y"]) for v in m["vertex"]]
    sides = [int(s["sector"]) for s in m["sidedef"]]
    sectors = m["sector"]
    sloped = ["floorplane_a" in s for s in sectors]
    zr = tuple(float(v) for v in a.z.split(",")) if a.z else None
    # 8x8 one-sided squares off the map are 3D-floor and door control sectors, not places.
    box = defaultdict(lambda: [1e9, 1e9, -1e9, -1e9])
    for l in m["linedef"]:
        for key in ("sidefront", "sideback"):
            if key in l:
                b = box[sides[int(l[key])]]
                for v in (verts[int(l["v1"])], verts[int(l["v2"])]):
                    b[0], b[1], b[2], b[3] = min(b[0], v[0]), min(b[1], v[1]), max(b[2], v[0]), max(b[3], v[1])
    control = {s for s, b in box.items() if b[2] - b[0] <= 8.5 and b[3] - b[1] <= 8.5}
    lines = []
    for l in m["linedef"]:
        front = sides[int(l["sidefront"])] if "sidefront" in l else -1
        back = sides[int(l["sideback"])] if "sideback" in l else -1
        if front in control or back in control:
            continue
        if zr and not any(s >= 0 and zr[0] <= sectors[s].get("heightfloor", 0) <= zr[1] for s in (front, back)):
            continue
        lines.append((verts[int(l["v1"])], verts[int(l["v2"])], front, back))
    if a.crop:
        x0, y0, x1, y1 = (float(v) for v in a.crop.split(","))
        lines = [l for l in lines if max(l[0][0], l[1][0]) >= x0 and min(l[0][0], l[1][0]) <= x1 and max(l[0][1], l[1][1]) >= y0 and min(l[0][1], l[1][1]) <= y1]
    else:
        xs = [p[0] for l in lines for p in l[:2]]
        ys = [p[1] for l in lines for p in l[:2]]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    s = a.scale
    img = Image.new("RGB", (int((x1 - x0) * s) + 20, int((y1 - y0) * s) + 20), (16, 16, 24))
    d = ImageDraw.Draw(img)

    def P(p):
        return (10 + (p[0] - x0) * s, 10 + (y1 - p[1]) * s)

    angled = axis = steps = ramps = 0
    wall_ends = defaultdict(list)
    for p, q, f, b in lines:
        is_angled = abs(p[0] - q[0]) > 0.01 and abs(p[1] - q[1]) > 0.01
        if f < 0 or b < 0:
            colour = (90, 220, 255) if is_angled else (170, 170, 170)
            angled += is_angled
            axis += not is_angled
            if not is_angled:
                wall_ends[p].append(q)
                wall_ends[q].append(p)
        elif sloped[f] or sloped[b]:
            colour = (60, 200, 80)
            ramps += 1
        else:
            df = abs(sectors[f].get("heightfloor", 0) - sectors[b].get("heightfloor", 0))
            if 0 < df <= 24:
                colour = (240, 210, 40)
                steps += 1
            elif df > 24:
                colour = (90, 220, 255) if is_angled else (170, 170, 170)
                angled += is_angled
                axis += not is_angled
                if not is_angled:
                    wall_ends[p].append(q)
                    wall_ends[q].append(p)
            else:
                colour = (55, 55, 75)
        d.line([P(p), P(q)], fill=colour, width=1 if s < 1 else 2)
    short = 24.0
    corners = 0
    for v, others in wall_ends.items():
        if len(others) != 2:
            continue
        (ax, ay), (bx, by) = others
        la, lb = abs(ax - v[0]) + abs(ay - v[1]), abs(bx - v[0]) + abs(by - v[1])
        turns = (abs(ax - v[0]) < 0.01) != (abs(bx - v[0]) < 0.01)
        if turns and la <= short and lb <= short:
            corners += 1
            d.ellipse([P(v)[0] - 2, P(v)[1] - 2, P(v)[0] + 2, P(v)[1] + 2], outline=(255, 60, 60))
    img.save(a.out)
    print(f"walls: axis {axis}, angled {angled}; stair corners {corners}; floor steps {steps}; sloped edges {ramps}")


if __name__ == "__main__":
    main()
