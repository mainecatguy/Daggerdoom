"""Builds the climbing test map (climbtest.wad) and harness (climbharness.pk3) into an output folder.

usage: python tools/climb/build_test.py <outdir>

The map is hand made (no game data): a 192-unit wall, a 75-degree slope, and a 60-degree slope in one room.
"""
import math
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

verts, lines, sides, sectors = [], [], [], []


def vertex(x, y):
    verts.append((x, y))
    return len(verts) - 1


def sector(floor, ceil=512, plane=None):
    sectors.append((floor, ceil, plane))
    return len(sectors) - 1


def centroid(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def line(a, b, front, front_center, back=None):
    (x1, y1), (x2, y2) = verts[a], verts[b]
    dx, dy = x2 - x1, y2 - y1
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if (front_center[0] - mx) * dy + (front_center[1] - my) * -dx < 0:
        a, b = b, a
    sides.append(front)
    f = len(sides) - 1
    k = -1
    if back is not None:
        sides.append(back)
        k = len(sides) - 1
    lines.append((a, b, f, k))


def slope_plane(x0, degrees):
    """Floor plane rising toward +x from x0 at this angle."""
    r = math.radians(degrees)
    return (-math.sin(r), 0.0, math.cos(r), x0 * math.sin(r))


def build_map():
    outer = sector(0)
    o = [vertex(0, 0), vertex(0, 1024), vertex(1024, 1024), vertex(1024, 0)]
    for i in range(4):
        line(o[i], o[(i + 1) % 4], outer, (512, 512))

    def box(x1, y1, x2, y2, sec):
        v = [vertex(x1, y1), vertex(x1, y2), vertex(x2, y2), vertex(x2, y1)]
        return v

    tower = sector(192)
    v = box(512, 448, 640, 576, tower)
    for i in range(4):
        line(v[i], v[(i + 1) % 4], tower, (576, 512), outer)

    for y1, y2, deg in ((150, 250, 75), (750, 850, 60)):
        rise = 88 * math.tan(math.radians(deg))
        slope = sector(0, plane=slope_plane(512, deg))
        top = sector(round(rise))
        a, b, c = vertex(512, y1), vertex(600, y1), vertex(700, y1)
        d, e, f = vertex(700, y2), vertex(600, y2), vertex(512, y2)
        sc, tc = (556, (y1 + y2) / 2), (650, (y1 + y2) / 2)
        line(a, b, slope, sc, outer)
        line(b, e, slope, sc, top)
        line(e, f, slope, sc, outer)
        line(f, a, slope, sc, outer)
        line(b, c, top, tc, outer)
        line(c, d, top, tc, outer)
        line(d, e, top, tc, outer)

    # Rows of floors rising toward +x: a staircase far too steep to walk (32-unit risers, 12-unit treads, like
    # Privateer's Hold's cliff) and a wall with a 64-unit ledge before a taller wall.
    def row(y1, y2, cols):
        xs = [c[0] for c in cols]
        vs = [(vertex(x, y1), vertex(x, y2)) for x in xs]
        secs = [sector(f) for _, f in cols[:-1]]
        for i, s in enumerate(secs):
            c = ((xs[i] + xs[i + 1]) / 2, (y1 + y2) / 2)
            line(vs[i][0], vs[i][1], s, c, secs[i - 1] if i else outer)
            line(vs[i][0], vs[i + 1][0], s, c, outer)
            line(vs[i][1], vs[i + 1][1], s, c, outer)
        last = len(secs) - 1
        line(vs[-1][0], vs[-1][1], secs[last], ((xs[-2] + xs[-1]) / 2, (y1 + y2) / 2), outer)

    row(350, 430, [(800 + 12 * i, 32 * (i + 1)) for i in range(10)] + [(920, 320), (1000, 0)])
    row(620, 700, [(800, 96), (864, 192), (1000, 0)])

    out = ['namespace = "zdoom";',
           'thing { x = 400.0; y = 512.0; angle = 0; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }']
    for x, y in verts:
        out.append(f'vertex {{ x = {x:.1f}; y = {y:.1f}; }}')
    for a, b, f, k in lines:
        extra = 'twosided = true;' if k >= 0 else 'blocking = true;'
        back = f' sideback = {k};' if k >= 0 else ''
        out.append(f'linedef {{ v1 = {a}; v2 = {b}; sidefront = {f};{back} {extra} }}')
    for s in sides:
        out.append(f'sidedef {{ sector = {s}; texturemiddle = "STARTAN3"; texturetop = "STARTAN3"; texturebottom = "STARTAN3"; }}')
    for floor, ceil, plane in sectors:
        p = ''
        if plane:
            p = ' floorplane_a = {:.6f}; floorplane_b = {:.6f}; floorplane_c = {:.6f}; floorplane_d = {:.6f};'.format(*plane)
        out.append(f'sector {{ heightfloor = {floor}; heightceiling = {ceil}; texturefloor = "FLOOR4_8"; textureceiling = "CEIL3_5"; lightlevel = 192;{p} }}')
    return '\n'.join(out).encode()


def write_wad(path, lumps):
    data = b''
    directory = []
    offset = 12
    for name, body in lumps:
        directory.append((offset, len(body), name))
        data += body
        offset += len(body)
    with open(path, 'wb') as f:
        f.write(b'PWAD' + struct.pack('<ii', len(lumps), offset))
        f.write(data)
        for off, size, name in directory:
            f.write(struct.pack('<ii8s', off, size, name.encode().ljust(8, b'\0')))


def main():
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    write_wad(os.path.join(outdir, 'climbtest.wad'), [('CLIMB01', b''), ('TEXTMAP', build_map()), ('ENDMAP', b'')])
    with zipfile.ZipFile(os.path.join(outdir, 'climbharness.pk3'), 'w') as z:
        z.write(os.path.join(HERE, 'harness.zs'), 'zscript/harness.zs')
        z.writestr('ZSCRIPT.txt', 'version "4.14"\n#include "zscript/harness.zs"\n')
        z.writestr('MAPINFO.txt', 'gameinfo { PlayerClasses = "ClimbTestPlayer" AddEventHandlers = "ClimbHarness" }\n')
        z.writestr('CVARINFO.txt', 'server int climbtest_part = 1;\n')
    print('wrote', outdir)


if __name__ == '__main__':
    main()
