"""Compares Doom's nature port with Daggerfall Unity's own output.

    python tools/nature/compare.py unity <dfu dump dir>            checks the Unity RNG and Perlin ports against unity.txt
    python tools/nature/compare.py layout <dfu pixel file> <doom dump file>

The ports here mirror UZDoom/src/playsim/dd_nature.cpp line for line, in 32-bit float where it matters.
"""
import struct
import sys

import math

PERM = [151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,
        247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,
        74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,
        65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,
        52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,
        119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,
        218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,
        184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180]
assert sorted(PERM) == list(range(256))
def F(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]
M32 = 0xFFFFFFFF


def grad(h, x, y):
    h &= 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h in (12, 14) else F(0))
    return F((-u if h & 1 else u) + (-v if h & 2 else v))


def perlin(x, y):
    x, y = F(x), F(y)
    p = lambda i: PERM[i & 255]
    fx, fy = float(math.floor(x)), float(math.floor(y))
    X, Y = int(fx) & 255, int(fy) & 255
    x, y = F(x - fx), F(y - fy)
    xm, ym = F(x - 1), F(y - 1)
    u = F(F(F(x * x) * x) * F(x * F(F(x * 6) - 15) + 10))
    v = F(F(F(y * y) * y) * F(y * F(F(y * 6) - 15) + 10))
    A, B = p(X) + Y, p(X + 1) + Y
    lerp = lambda t, a, b: F(a + F(t * F(b - a)))
    n = lerp(v, lerp(u, grad(p(A), x, y), grad(p(B), xm, y)), lerp(u, grad(p(A + 1), x, ym), grad(p(B + 1), xm, ym)))
    return F(F(n + F(0.69)) / F(1.483))


class UnityRandom:
    def __init__(self, seed):
        self.x = seed & M32
        self.y = (self.x * 1812433253 + 1) & M32
        self.z = (self.y * 1812433253 + 1) & M32
        self.w = (self.z * 1812433253 + 1) & M32

    def next(self):
        t = (self.x ^ (self.x << 11)) & M32
        self.x, self.y, self.z = self.y, self.z, self.w
        self.w = (self.w ^ (self.w >> 19) ^ t ^ (t >> 8)) & M32
        return self.w

    def value(self):
        return F(F(self.next() & 0x7FFFFF) * F(1.0 / 8388607.0))

    def range_int(self, lo, hi):
        return lo + self.next() % (hi - lo)


def indexed(index, lo, hi):
    n = (index + 62) & M32
    n = (n ^ 61) ^ (n >> 16)
    n = (n * 9) & M32
    n ^= n >> 4
    n = (n * 0x27d4eb2d) & M32
    n ^= n >> 15
    s = n
    def nxt():
        nonlocal s
        t = s
        s ^= (s << 13) & M32
        s ^= s >> 17
        s ^= (s << 5) & M32
        return t
    nxt()
    f = struct.unpack("<f", struct.pack("<I", 0x3f800000 | (nxt() >> 9)))[0]
    return F(F(f - 1) * F(hi - lo) + F(lo))


def check_unity(folder):
    lines = open(f"{folder}/unity.txt").read().split("\n")
    worst, bad = 0.0, 0
    for l in lines:
        p = l.split()
        if p and p[0] == "perlin":
            got, want = perlin(float(p[1]), float(p[2])), float(p[3])
            worst = max(worst, abs(got - want))
    print(f"perlin: worst difference {worst:.7f}")
    r = UnityRandom(12345)
    vals = [float(l.split()[1]) for l in lines if l.startswith("value ")]
    mine = [float(r.value()) for _ in vals]
    print("value:", "MATCH" if all(abs(a - b) < 1e-7 for a, b in zip(vals, mine)) else f"DIFFER {vals[:3]} vs {mine[:3]}")
    key = (213 << 16) + 207
    r = UnityRandom(key)
    vals = [float(l.split()[1]) for l in lines if l.startswith("range01 ")]
    mine = [float(r.value()) for _ in vals]
    print("range01:", "MATCH" if all(abs(a - b) < 1e-7 for a, b in zip(vals, mine)) else f"DIFFER {vals[:3]} vs {mine[:3]}")
    vals = [int(l.split()[1]) for l in lines if l.startswith("range132 ")]
    mine = [r.range_int(1, 32) for _ in vals]
    print("range132:", "MATCH" if vals == mine else f"DIFFER {vals} vs {mine}")
    pairs = [(int(l.split()[1]), float(l.split()[2])) for l in lines if l.startswith("indexed ")]
    print("indexed:", "MATCH" if all(abs(indexed(i, -1.5, 1.5) - v) < 1e-6 for i, v in pairs) else "DIFFER")


def read_flats(path, skip_header_lines):
    flats = []
    for l in open(path).read().split("\n"):
        p = l.split()
        if len(p) == 3 and all(s.lstrip("-").isdigit() for s in p):
            flats.append(tuple(int(s) for s in p))
    return flats


def check_layout(dfu_file, doom_file):
    dfu = read_flats(dfu_file, 0)
    doom = read_flats(doom_file, 0)
    head = open(dfu_file).readline().strip()
    print(head)
    print(open(doom_file).readline().strip())
    exact = len(set(dfu) & set(doom))
    spots = len({(x, y) for x, y, _ in dfu} & {(x, y) for x, y, _ in doom})
    print(f"flats: Daggerfall Unity {len(dfu)}, Doom {len(doom)}; same tile {spots}, same tile and record {exact}")
    # Density in 16x16-tile blocks, as a placement measure that does not need exact tiles.
    def grid(fl):
        g = [0] * 64
        for x, y, _ in fl:
            g[(y // 16) * 8 + x // 16] += 1
        return g
    a, b = grid(dfu), grid(doom)
    ma, mb = sum(a) / 64, sum(b) / 64
    cov = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    va, vb = sum((p - ma) ** 2 for p in a), sum((q - mb) ** 2 for q in b)
    if va > 0 and vb > 0:
        print(f"16-tile block density correlation {cov / math.sqrt(va * vb):.3f}")
    print("records used, Daggerfall Unity:", len({r for _, _, r in dfu}), " Doom:", len({r for _, _, r in doom}))

if __name__ == "__main__":
    if sys.argv[1] == "unity":
        check_unity(sys.argv[2])
    else:
        check_layout(sys.argv[2], sys.argv[3])
