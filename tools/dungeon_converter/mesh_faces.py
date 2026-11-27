"""Every visible mesh triangle above each point, at any slope (floor_check.py skips faces steeper than about 72 degrees),
as (height, slope in degrees, facing). Only heights 900-1500 are printed. The facing label is not reliable (axis order).
usage: mesh_faces.py <privateershold_mesh.pk3> "x,y;x,y"
"""
import math, struct, sys, zipfile
data = zipfile.ZipFile(sys.argv[1]).read("DFMESH")
textures, batches, vertices = struct.unpack("<iii", data[12:24])
start = 24 + textures * 32 + batches * 12
v = struct.unpack(f"<{vertices * 8}f", data[start:start + vertices * 32])
pts = [tuple(map(float, p.split(","))) for p in sys.argv[2].split(";")]
res = {p: [] for p in pts}
for t in range(vertices // 3):
    a, b, c = [(v[(t * 3 + k) * 8], v[(t * 3 + k) * 8 + 2], v[(t * 3 + k) * 8 + 1]) for k in range(3)]
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    wx, wy, wz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-6:
        continue
    for (x, y) in pts:
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-6:
            res[(x, y)].append((round(l1 * a[2] + l2 * b[2] + l3 * c[2], 1), round(math.degrees(math.acos(abs(nz) / L)), 1), "up?" if nz > 0 else "down?"))
for p in pts:
    print(p, sorted(h for h in res[p] if 900 < h[0] < 1500))
