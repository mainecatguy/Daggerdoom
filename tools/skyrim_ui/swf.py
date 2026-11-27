"""Minimal SWF reader for the Skyrim UI menus (Scaleform GFx SWFs with vector art).

Reads what the converter needs: shapes (DefineShape 1-4), sprites with their display lists (PlaceObject2/3), edit text
fields and exported names. ActionScript is not run; animations made in script are rebuilt by the Doom menu itself.
"""
import struct, zlib


class Bits:
    def __init__(self, data, pos=0):
        self.d, self.p, self.bit = data, pos, 0

    def align(self):
        if self.bit:
            self.bit = 0
            self.p += 1

    def ub(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.p] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit = 0
                self.p += 1
        return v

    def sb(self, n):
        if n == 0:
            return 0
        v = self.ub(n)
        return v - (1 << n) if v & (1 << (n - 1)) else v

    def fb(self, n):
        return self.sb(n) / 65536.0

    def u8(self):
        self.align()
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        self.align()
        v = struct.unpack_from('<H', self.d, self.p)[0]
        self.p += 2
        return v

    def s16(self):
        self.align()
        v = struct.unpack_from('<h', self.d, self.p)[0]
        self.p += 2
        return v

    def u32(self):
        self.align()
        v = struct.unpack_from('<I', self.d, self.p)[0]
        self.p += 4
        return v

    def string(self):
        self.align()
        e = self.d.index(0, self.p)
        s = self.d[self.p:e].decode('utf-8', 'replace')
        self.p = e + 1
        return s

    def rect(self):
        self.align()
        n = self.ub(5)
        r = [self.sb(n) for _ in range(4)]  # xmin xmax ymin ymax, twips
        self.align()
        return r

    def matrix(self):
        self.align()
        a = d = 1.0
        b = c = 0.0
        if self.ub(1):
            n = self.ub(5)
            a, d = self.fb(n), self.fb(n)
        if self.ub(1):
            n = self.ub(5)
            b, c = self.fb(n), self.fb(n)
        n = self.ub(5)
        tx, ty = self.sb(n), self.sb(n)
        self.align()
        return (a, b, c, d, tx, ty)  # x' = a*x + c*y + tx ; y' = b*x + d*y + ty

    def cxform(self, alpha=True):
        self.align()
        has_add, has_mult = self.ub(1), self.ub(1)
        n = self.ub(4)
        k = 4 if alpha else 3
        mult = [self.sb(n) / 256.0 for _ in range(k)] if has_mult else [1.0] * k
        add = [self.sb(n) for _ in range(k)] if has_add else [0] * k
        self.align()
        if not alpha:
            mult.append(1.0)
            add.append(0)
        return (tuple(mult), tuple(add))

    def rgb(self, alpha):
        self.align()
        c = tuple(self.d[self.p:self.p + (4 if alpha else 3)])
        self.p += 4 if alpha else 3
        return c if alpha else c + (255,)


def mat_mul(m, n):
    """m applied after n."""
    a, b, c, d, tx, ty = m
    e, f, g, h, ux, uy = n
    return (a * e + c * f, b * e + d * f, a * g + c * h, b * g + d * h, a * ux + c * uy + tx, b * ux + d * uy + ty)


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0, 0)


class Shape:
    def __init__(self, cid, bounds):
        self.id, self.bounds = cid, bounds
        self.fills = []   # (group, index, style, edges) edges: list of polylines [(x,y),...] in twips
        self.lines = []   # (style, polyline)


def read_fill_style(r, shape_ver):
    t = r.u8()
    alpha = shape_ver >= 3
    if t == 0x00:
        return {'type': 'solid', 'color': r.rgb(alpha)}
    if t in (0x10, 0x12, 0x13):
        m = r.matrix()
        r.align()
        spread, interp, num = r.ub(2), r.ub(2), r.ub(4)
        stops = [(r.u8(), r.rgb(alpha)) for _ in range(num)]
        focal = r.s16() / 256.0 if t == 0x13 else 0.0
        return {'type': 'linear' if t == 0x10 else 'radial', 'matrix': m, 'stops': stops, 'spread': spread, 'focal': focal}
    if 0x40 <= t <= 0x43:
        bid = r.u16()
        m = r.matrix()
        return {'type': 'bitmap', 'id': bid, 'matrix': m}
    raise ValueError('fill style type %#x' % t)


def read_styles(r, ver):
    n = r.u8()
    if n == 0xFF and ver >= 2:
        n = r.u16()
    fills = [read_fill_style(r, ver) for _ in range(n)]
    n = r.u8()
    if n == 0xFF:
        n = r.u16()
    lines = []
    for _ in range(n):
        w = r.u16()
        if ver == 4:
            r.ub(2)
            join = r.ub(2)
            has_fill = r.ub(1)
            r.ub(3)
            r.ub(5)
            r.ub(1)
            r.ub(2)
            if join == 2:
                r.u16()
            if has_fill:
                f = read_fill_style(r, ver)
                color = f.get('color', f['stops'][-1][1] if 'stops' in f else (255, 255, 255, 255))
            else:
                color = r.rgb(True)
        else:
            color = r.rgb(ver >= 3)
        lines.append({'width': w, 'color': color})
    r.align()
    nf, nl = r.ub(4), r.ub(4)
    return fills, lines, nf, nl


def flatten_quad(p0, p1, p2, steps=8):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / steps for i in range(1, steps + 1))]


def read_shape(body, tag):
    ver = {2: 1, 22: 2, 32: 3, 83: 4}[tag]
    r = Bits(body)
    cid = r.u16()
    bounds = r.rect()
    if ver == 4:
        r.rect()
        r.u8()
    shape = Shape(cid, bounds)
    fills, lines, nf, nl = read_styles(r, ver)
    group = 0
    x = y = 0
    fs0 = fs1 = ls = 0
    # Edges per (group, fill index): list of (start, end, points) oriented so the fill lies on the right.
    fill_edges = {}
    line_edges = []
    styles = {0: (fills, lines)}
    while True:
        if r.ub(1) == 0:
            flags = r.ub(5)
            if flags == 0:
                break
            if flags & 1:
                n = r.ub(5)
                x, y = r.sb(n), r.sb(n)
            if flags & 2:
                fs0 = r.ub(nf)
            if flags & 4:
                fs1 = r.ub(nf)
            if flags & 8:
                ls = r.ub(nl)
            if flags & 16:
                fills, lines, nf, nl = read_styles(r, ver)
                group += 1
                styles[group] = (fills, lines)
            continue
        if r.ub(1):  # straight
            n = r.ub(4) + 2
            if r.ub(1):
                dx, dy = r.sb(n), r.sb(n)
            elif r.ub(1):
                dx, dy = 0, r.sb(n)
            else:
                dx, dy = r.sb(n), 0
            pts = [(x + dx, y + dy)]
        else:
            n = r.ub(4) + 2
            cx, cy = x + r.sb(n), y + r.sb(n)
            ax, ay = cx + r.sb(n), cy + r.sb(n)
            pts = flatten_quad((x, y), (cx, cy), (ax, ay))
        start = (x, y)
        x, y = int(round(pts[-1][0])), int(round(pts[-1][1]))
        pts[-1] = (x, y)
        if fs1:
            fill_edges.setdefault((group, fs1), []).append([start] + pts)
        if fs0:
            fill_edges.setdefault((group, fs0), []).append(([start] + pts)[::-1])
        if ls:
            line_edges.append((group, ls, [start] + pts))
    for (g, i), edges in sorted(fill_edges.items()):
        shape.fills.append((g, i, styles[g][0][i - 1], chain(edges)))
    for g, i, pts in line_edges:
        shape.lines.append((styles[g][1][i - 1], pts))
    return shape


def chain(edges):
    """Joins oriented edges into closed loops where their ends meet."""
    by_start = {}
    for e in edges:
        by_start.setdefault(e[0], []).append(e)
    used = set()
    loops = []
    for e in edges:
        if id(e) in used:
            continue
        used.add(id(e))
        loop = list(e)
        while loop[-1] != loop[0]:
            nxt = next((c for c in by_start.get(loop[-1], []) if id(c) not in used), None)
            if nxt is None:
                break
            used.add(id(nxt))
            loop.extend(nxt[1:])
        loops.append(loop)
    return loops


class Place:
    def __init__(self):
        self.depth = 0
        self.char = None
        self.matrix = IDENTITY
        self.cx = None
        self.name = None
        self.clip = None
        self.visible = True
        self.blend = 0


class Sprite:
    def __init__(self, cid, frames):
        self.id = cid
        self.frame_count = frames
        self.frames = []  # list of {depth: Place} after each ShowFrame
        self.labels = {}


class Swf:
    def __init__(self, path):
        data = open(path, 'rb').read()
        sig = data[:3]
        body = zlib.decompress(data[8:]) if sig in (b'CWS', b'CFX') else data[8:]
        r = Bits(body)
        self.rect = r.rect()
        self.rate = r.u16() / 256.0
        r.u16()
        self.chars = {}
        self.exports = {}
        self.root = Sprite(0, 1)
        self.read_tags(body, r.p, self.root)

    def read_tags(self, d, p, sprite):
        display = {}
        while p < len(d):
            h = struct.unpack_from('<H', d, p)[0]
            p += 2
            tag, ln = h >> 6, h & 63
            if ln == 63:
                ln = struct.unpack_from('<I', d, p)[0]
                p += 4
            body = d[p:p + ln]
            p += ln
            if tag == 0:
                break
            if tag in (2, 22, 32, 83):
                s = read_shape(body, tag)
                self.chars[s.id] = s
            elif tag == 39:
                r = Bits(body)
                cid, frames = r.u16(), r.u16()
                sp = Sprite(cid, frames)
                self.chars[cid] = sp
                self.read_tags(body, 4, sp)
            elif tag == 37:
                self.read_edit_text(body)
            elif tag == 56:
                r = Bits(body)
                for _ in range(r.u16()):
                    cid = r.u16()
                    self.exports[r.string()] = cid
            elif tag == 43:
                sprite.labels[Bits(body).string()] = len(sprite.frames)
            elif tag in (26, 70):
                self.place(body, tag, display)
            elif tag in (5, 28):
                r = Bits(body)
                if tag == 5:
                    r.u16()
                display.pop(r.u16(), None)
            elif tag == 1:
                sprite.frames.append({k: v for k, v in display.items()})
        return p

    def place(self, body, tag, display):
        r = Bits(body)
        f = r.u8()
        f2 = r.u8() if tag == 70 else 0
        depth = r.u16()
        old = display.get(depth)
        pl = Place()
        if old and (f & 1):
            pl.__dict__.update(old.__dict__)
        pl.depth = depth
        if tag == 70 and (f2 & 8 or (f2 & 16 and f & 2)):
            r.string()
        if f & 2:
            pl.char = r.u16()
        if f & 4:
            pl.matrix = r.matrix()
        if f & 8:
            pl.cx = r.cxform(True)
        if f & 16:
            r.u16()
        if f & 32:
            pl.name = r.string()
        if f & 64:
            pl.clip = r.u16()
        if tag == 70 and f2 & 1:
            pass  # filters: not needed, stop reading here
        elif tag == 70 and f2 & 2:
            pl.blend = r.u8()
        display[depth] = pl

    def read_edit_text(self, body):
        r = Bits(body)
        cid = r.u16()
        bounds = r.rect()
        f1, f2 = r.u8(), r.u8()
        t = {'type': 'text', 'id': cid, 'bounds': bounds, 'html': bool(f2 & 2)}
        if f1 & 1:  # HasFont
            t['font'] = r.u16()
        if f2 & 128:  # HasFontClass
            t['font_class'] = r.string()
        if f1 & 1 or f2 & 128:
            t['height'] = r.u16()
        if f1 & 4:
            t['color'] = r.rgb(True)
        if f1 & 2:
            r.u16()
        if f2 & 32:
            t['align'] = r.u8()
            r.u16(); r.u16(); r.u16(); r.s16()
        t['var'] = r.string()
        if f1 & 128:
            t['initial'] = r.string()
        self.chars[cid] = t
