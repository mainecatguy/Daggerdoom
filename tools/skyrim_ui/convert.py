"""Converts a Skyrim UI menu SWF into Doom resources: one PNG per vector shape and a text lump with the display lists.

Usage: convert.py <menu.swf> <ExportedRootSymbol> <name> <out_dir>
Writes <out_dir>/graphics/skyrimui/<name>/S<id>.png and <out_dir>/skyrimui/<name>.txt.

build_pk3.py runs this for every mods/doomerfall/skyrimui/*.swf listed in menus.txt, so the art in the pk3 is generated
from the committed SWF. The Doom side (zscript/DoomerfallSwfMenu.zs) reads the lump and draws the shapes with the
SWF's own transforms and frames. ActionScript is not converted: a menu's script behaviour is written in ZScript.

Lump format, one record per line, fields separated by single spaces (units are SWF pixels, 1/20 of a twip):
  swfui 1 <stage width> <stage height> <frame rate> <root sprite id>
  image <shape id> <lump path> <x> <y> <pixels per unit>       the PNG's top left corner in the shape's own space
  text <id> <x0> <y0> <x1> <y1> <font height> <align 0 left 1 right 2 center> <r> <g> <b> <a> <text...>
  sprite <id> <frame count>
  label <sprite id> <frame> <name>
  place <sprite id> <frame> <depth> <char id> <a> <b> <c> <d> <tx> <ty> <alpha> <r> <g> <b> <clip> <name or ->
    every frame's full display list, so the reader never replays changes; a b c d tx ty map local x,y to
    x*a + y*c + tx, x*b + y*d + ty; alpha r g b are the colour transform's multipliers; clip is 1 for a mask layer
"""
import io, math, os, re, sys
from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swf import Swf, Shape, Sprite, IDENTITY, mat_mul

SUPERSAMPLE = 4
STAGE_SCALE = 2.0   # PNG pixels per stage pixel at the largest scale a shape is shown: sharp up to 1440p screens
MAX_SIZE = 2048


def walk(swf, cid, matrix, scales, seen=()):
    """Records the largest scale each shape is drawn at, over every frame."""
    c = swf.chars.get(cid)
    if isinstance(c, Shape):
        s = max(math.hypot(matrix[0], matrix[1]), math.hypot(matrix[2], matrix[3]))
        scales[cid] = max(scales.get(cid, 0), s)
    elif isinstance(c, Sprite) and cid not in seen:
        for frame in c.frames:
            for p in frame.values():
                if p.char is not None:
                    walk(swf, p.char, mat_mul(matrix, p.matrix), scales, seen + (cid,))


def lut(stops):
    """256 RGBA colours along a SWF gradient."""
    out = []
    for i in range(256):
        if i <= stops[0][0]:
            out.append(stops[0][1])
            continue
        if i >= stops[-1][0]:
            out.append(stops[-1][1])
            continue
        for (r0, c0), (r1, c1) in zip(stops, stops[1:]):
            if r0 <= i <= r1:
                t = (i - r0) / max(1, r1 - r0)
                out.append(tuple(int(round(c0[k] + (c1[k] - c0[k]) * t)) for k in range(4)))
                break
    return out


def gradient_image(style):
    """The gradient's square (-16384..16384 twips) as a 768 px image, its middle 256 px, padded with the end colours."""
    if style['type'] == 'linear':
        row = Image.new('L', (768, 1), 0)
        row.paste(Image.frombytes('L', (256, 1), bytes(range(256))), (256, 0))
        row.paste(255, (512, 0, 768, 1))
        g = row.resize((768, 768), Image.NEAREST)
    else:
        g = Image.new('L', (768, 768), 255)
        g.paste(Image.radial_gradient('L'), (256, 256))
    colours = lut(style['stops'])
    bands = [g.point([c[k] for c in colours]) for k in range(4)]
    return Image.merge('RGBA', bands)


def render_shape(shape, ppu):
    """The shape at ppu PNG pixels per stage pixel, and its top left corner in stage pixels."""
    x0, x1, y0, y1 = [v / 20.0 for v in shape.bounds]
    ppu = min(ppu, MAX_SIZE / max(1.0, x1 - x0), MAX_SIZE / max(1.0, y1 - y0))
    w, h = max(1, int(math.ceil((x1 - x0) * ppu)) + 2), max(1, int(math.ceil((y1 - y0) * ppu)) + 2)
    ss = SUPERSAMPLE
    k = ppu * ss / 20.0  # canvas pixels per twip
    ox, oy = shape.bounds[0] - 20.0 / ppu, shape.bounds[2] - 20.0 / ppu  # one PNG pixel of margin

    def px(p):
        return ((p[0] - ox) * k, (p[1] - oy) * k)

    size = (w * ss, h * ss)
    canvas = Image.new('RGBA', size, (0, 0, 0, 0))
    for group, index, style, loops in shape.fills:
        mask = Image.new('1', size, 0)
        for loop in loops:
            if len(loop) < 3:
                continue
            one = Image.new('1', size, 0)
            ImageDraw.Draw(one).polygon([px(p) for p in loop], fill=1)
            mask = ImageChops.logical_xor(mask, one)
        if style['type'] == 'solid':
            layer = Image.new('RGBA', size, style['color'])
        elif style['type'] in ('linear', 'radial'):
            a, b, c, d, tx, ty = style['matrix']
            # Gradient image pixel (u, v) -> gradient twips g = (u - 384) * 32768 / 256 -> shape twips -> canvas.
            s = 128.0
            fa, fb, fc, fd = a * s * k, b * s * k, c * s * k, d * s * k
            fx = (tx - ox) * k - 384 * (fa + fc)
            fy = (ty - oy) * k - 384 * (fb + fd)
            det = fa * fd - fb * fc
            if abs(det) < 1e-9:
                continue
            ia, ib, ic, id_ = fd / det, -fc / det, -fb / det, fa / det
            layer = gradient_image(style).transform(size, Image.AFFINE, (ia, ib, -(ia * fx + ib * fy), ic, id_, -(ic * fx + id_ * fy)), Image.BILINEAR)
        else:
            continue  # No bitmap fills in these menus.
        alpha = ImageChops.multiply(layer.getchannel('A'), mask.convert('L'))
        layer.putalpha(alpha)
        canvas = Image.alpha_composite(canvas, layer)
    for style, pts in shape.lines:
        layer = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).line([px(p) for p in pts], fill=style['color'], width=max(1, int(round(style['width'] * k))))
        canvas = Image.alpha_composite(canvas, layer)
    img = canvas.convert('RGBa').resize((w, h), Image.BOX).convert('RGBA')
    return img, ox / 20.0, oy / 20.0, ppu


def strip_html(s):
    s = re.sub(r'<[^>]*>', '', s or '')
    return s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&apos;', "'").strip()


def text_align(t):
    m = re.search(r'align="(\w+)"', t.get('initial', ''))
    a = m.group(1) if m else ('left', 'right', 'center', 'center')[t.get('align', 0)]
    return {'left': 0, 'right': 1, 'center': 2}.get(a, 0)


def text_height(t):
    m = re.search(r'size="(\d+)"', t.get('initial', ''))
    return int(m.group(1)) if m else t.get('height', 240) / 20.0


def convert(swf_path, root_name, name):
    """{path in pk3: bytes} for one menu."""
    swf = Swf(swf_path)
    root = swf.exports[root_name]
    scales = {}
    walk(swf, root, IDENTITY, scales)
    files = {}
    lines = ['swfui 1 %g %g %g %d' % ((swf.rect[1] - swf.rect[0]) / 20.0, (swf.rect[3] - swf.rect[2]) / 20.0, swf.rate, root)]
    for cid in sorted(scales):
        img, x, y, ppu = render_shape(swf.chars[cid], max(0.05, scales[cid]) * STAGE_SCALE)
        path = 'graphics/skyrimui/%s/S%d.png' % (name, cid)
        buf = io.BytesIO()
        img.save(buf, 'PNG', optimize=True)
        files[path] = buf.getvalue()
        lines.append('image %d %s %.3f %.3f %.5f' % (cid, path, x, y, ppu))
    sprites, texts = [], []

    def collect(cid):
        c = swf.chars.get(cid)
        if isinstance(c, Sprite) and cid not in sprites:
            sprites.append(cid)
            for f in c.frames:
                for p in f.values():
                    collect(p.char)
        elif isinstance(c, dict) and cid not in texts:
            texts.append(cid)

    collect(root)
    for cid in texts:
        t = swf.chars[cid]
        b = [v / 20.0 for v in t['bounds']]
        col = t.get('color', (255, 255, 255, 255))
        lines.append('text %d %.2f %.2f %.2f %.2f %g %d %d %d %d %d %s' % (cid, b[0], b[2], b[1], b[3], text_height(t), text_align(t), col[0], col[1], col[2], col[3], strip_html(t.get('initial', ''))))
    for cid in sprites:
        sp = swf.chars[cid]
        lines.append('sprite %d %d' % (cid, len(sp.frames)))
        for label, frame in sorted(sp.labels.items(), key=lambda kv: kv[1]):
            lines.append('label %d %d %s' % (cid, frame, label))
        for i, frame in enumerate(sp.frames):
            for depth in sorted(frame):
                p = frame[depth]
                if p.char is None or p.char not in swf.chars:
                    continue
                a, b, c, d, tx, ty = p.matrix
                mult = p.cx[0] if p.cx else (1.0, 1.0, 1.0, 1.0)
                lines.append('place %d %d %d %d %.4f %.4f %.4f %.4f %.2f %.2f %.3f %.3f %.3f %.3f %d %s' % (
                    cid, i, depth, p.char, a, b, c, d, tx / 20.0, ty / 20.0, mult[3], mult[0], mult[1], mult[2], 1 if p.clip else 0, p.name or '-'))
    files['skyrimui/%s.txt' % name] = ('\n'.join(lines) + '\n').encode('utf-8')
    return files


def convert_all(folder):
    """Every menu listed in <folder>/menus.txt ("<swf file> <root export> <name>" per line, # comments)."""
    files = {}
    listing = os.path.join(folder, 'menus.txt')
    if not os.path.exists(listing):
        return files
    for line in open(listing, encoding='utf-8'):
        line = line.split('#', 1)[0].split()
        if len(line) == 3:
            files.update(convert(os.path.join(folder, line[0]), line[1], line[2]))
    return files


if __name__ == '__main__':
    out = sys.argv[4]
    for path, data in convert(sys.argv[1], sys.argv[2], sys.argv[3]).items():
        full = os.path.join(out, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, 'wb').write(data)
        print('wrote', full)
