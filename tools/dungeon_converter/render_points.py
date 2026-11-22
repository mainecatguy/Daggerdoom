"""Render a converter points file as a top-down PNG for debugging.

Usage: python render_points.py <points.txt> <out.png> [zmin zmax]
Gray: walkable node. Green: reachable from the entrance. Blue: door node. Red: entrance.
"""
import collections
import struct
import sys
import zlib

path, out = sys.argv[1:3]
zmin = int(sys.argv[3]) if len(sys.argv) > 3 else -10**9
zmax = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
nodes, adjacency, start = {}, collections.defaultdict(list), 0
for line in open(path):
    p = line.split()
    if p[0] == "S":
        start = int(p[1])
    elif p[0] == "N":
        nodes[int(p[1])] = (int(p[2]), int(p[3]), int(p[4]), int(p[7]))
    elif p[0] == "E":
        adjacency[int(p[1])].append(int(p[2]))
seen, queue = {start}, collections.deque([start])
while queue:
    for n in adjacency[queue.popleft()]:
        if n not in seen:
            seen.add(n)
            queue.append(n)
x0 = min(n[0] for n in nodes.values())
y0 = min(n[1] for n in nodes.values())
w = (max(n[0] for n in nodes.values()) - x0) // 32 + 1
h = (max(n[1] for n in nodes.values()) - y0) // 32 + 1
SCALE = 2
pixels = bytearray(b"\x10\x10\x10" * (w * h * SCALE * SCALE))
order = sorted(nodes.items(), key=lambda kv: (kv[0] in seen, kv[1][3], kv[0] == start))
for node_id, (x, y, z, door) in order:
    if not zmin <= z <= zmax:
        continue
    color = (120, 120, 120)
    if node_id in seen:
        color = (40, 200, 70)
    if door:
        color = (60, 120, 255)
    if node_id == start:
        color = (255, 40, 40)
    px, py = (x - x0) // 32, h - 1 - (y - y0) // 32
    for sy in range(SCALE):
        for sx in range(SCALE):
            at = ((py * SCALE + sy) * w * SCALE + px * SCALE + sx) * 3
            pixels[at:at + 3] = bytes(color)
stride = w * SCALE * 3
raw = b"".join(b"\0" + bytes(pixels[r * stride:(r + 1) * stride]) for r in range(h * SCALE))


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


with open(out, "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * SCALE, h * SCALE, 8, 2, 0, 0, 0)))
    f.write(chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
print(f"nodes={len(nodes)} reachable={len(seen)} start={nodes[start]}")
