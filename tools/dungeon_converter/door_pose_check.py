"""Checks every exported door against Daggerfall Unity's transform, closed and fully open.

Usage: python tools/dungeon_converter/door_pose_check.py <slug>_doors.pk3 <door dump log>
The dump comes from running the converter with --door-dump. Reads generated files and writes nothing.

Truth is RDBLayout.AddActionDoor (world Y, then X, then Z) with DaggerfallActionDoor's -90 degree swing about the door's
own Y axis, applied to the raw model bounds. It is compared with what door_objects.zs places. Also checks that
MODELDEF names a model that exists and that the model's vertices match the bounds in DFDOORS.
"""
import math
import re
import sys
import zipfile

TOLERANCE = 0.02  # DFDOORS stores three decimals and the dump prints two


def rotate_y(p, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


def unity_rotate(p, rx, ry, rz):
    p = rotate_y(p, ry)
    c, s = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    p = (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)
    c, s = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2])


def bounds(points):
    return [f(p[i] for p in points) for i in range(3) for f in (min, max)]


def corners(b):
    return [(x, y, z) for x in b[:2] for y in b[2:4] for z in b[4:]]


package, dump_path = sys.argv[1:3]
number = r"(-?[\d.]+)"
dump_re = re.compile(rf"DOORDUMP \d+ m(\d+) b\d+ pivot {number},{number},{number} rot {number},{number},{number} "
                     rf"local x {number}\.\.{number} y {number}\.\.{number} z {number}\.\.{number}")
truth = {}
for line in open(dump_path, encoding="utf8", errors="replace"):
    m = dump_re.search(line)
    if m:
        v = [float(g) for g in m.groups()[1:]]
        truth[(int(m.group(1)), round(v[0]), round(v[1]), round(v[2]))] = v

with zipfile.ZipFile(package) as z:
    names = set(z.namelist())
    modeldef = z.read("MODELDEF").decode()
    slots = {int(a): b for a, b in re.findall(r'Model DFDoorVisual(\d+)\s*\{.*?Model 0 "([^"]+)"', modeldef, re.S)}
    objs = {}
    for name in set(slots.values()):
        path = "models/dfdoors/" + name
        if path in names:
            objs[name] = [tuple(float(x) for x in l.split()[1:4]) for l in z.read(path).decode().splitlines() if l.startswith("v ")]
    lines = [l.split() for l in z.read("DFDOORS").decode().splitlines() if l.strip()]

failures, flipped, worst = 0, 0, 0.0
for index, f in enumerate(lines):
    slot = int(f[0])
    px, py, pz, closed = (float(x) for x in f[1:5])
    box = [float(x) for x in f[5:11]]
    swing = float(f[11]) if len(f) > 11 else 1.0
    name = slots.get(slot)
    problems = []
    if name not in objs:
        problems.append(f"model {name} is missing")
    expected_name = re.compile(r"m\d+f\.obj" if swing < 0 else r"m\d+\.obj")
    if name and not expected_name.fullmatch(name):
        problems.append(f"swing {swing:g} uses model {name}")
    model_id = int(re.match(r"m(\d+)", name).group(1)) if name else -1
    t = truth.get((model_id, round(px), round(py), round(pz)))
    if t is None:
        problems.append("no matching door in the dump")
    else:
        rx, ry, rz = t[3:6]
        raw = (t[6], t[7], t[8], t[9], t[10], t[11])
        for label, swung in (("closed", 0.0), ("open", 90.0)):
            angle = math.radians(closed + swung * swing)
            c, s = math.cos(angle), math.sin(angle)
            placed = bounds([(px + x * c - y * s, py + x * s + y * c, pz + h) for x, y, h in corners(box)])
            real = []
            for x, y, h in corners(raw):
                u = rotate_y((x, h, y), -swung)  # Doom local (x, y, height) is Unity (x, height, y)
                w = unity_rotate(u, rx, ry, rz)
                real.append((px + w[0], py + w[2], pz + w[1]))
            error = max(abs(a - b) for a, b in zip(placed, bounds(real)))
            worst = max(worst, error)
            if error > TOLERANCE:
                problems.append(f"{label} is off by {error:.2f}")
        if name in objs:
            cx, cy = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
            drawn = bounds([(vx + cx, -vz + cy, vy) for vx, vy, vz in objs[name]])
            error = max(abs(a - b) for a, b in zip(drawn, box))
            if error > TOLERANCE:
                problems.append(f"model differs from its bounds by {error:.2f}")
    if swing < 0:
        flipped += 1
        print(f"flipped door {index}: {name} pivot {px:.1f},{py:.1f},{pz:.1f} floor {pz + box[4]:.1f} {'ok' if not problems else '; '.join(problems)}")
    elif problems:
        print(f"door {index}: {name} {'; '.join(problems)}")
    failures += bool(problems)
print(f"POSE doors={len(lines)} flipped={flipped} failed={failures} worst_error={worst:.3f}")
sys.exit(1 if failures else 0)
