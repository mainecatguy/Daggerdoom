"""Proves in the running engine that a billboard's displayed size follows its actor scale, beside real map geometry.

Usage: python sprite_scale_probe.py <uzdoom.exe> <iwad> <work dir>
A 64x64 image at scale 0.75 must draw exactly as large as a 48-unit pillar at the same depth. One sprite stands on
the floor (town and item anchor) and one is centered on its position (dungeon anchor). Exits 1 on a mismatch.
"""
import os
import struct
import subprocess
import sys
import zipfile
import zlib

W, H, OFFSCREEN = 960, 600, -32000
RED, GREEN, BLUE = (255, 0, 0), (0, 255, 0), (0, 0, 255)


def read_png(path):
    """Decodes UZDoom's 8-bit RGB or RGBA screenshot into a {(x, y): (r, g, b)}-style accessor."""
    data, at, idat = open(path, "rb").read(), 8, b""
    while at < len(data):
        size, kind = struct.unpack_from(">I4s", data, at)
        body = data[at + 8:at + 8 + size]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack_from(">IIBB", body)
        elif kind == b"IDAT":
            idat += body
        at += 12 + size
    if depth != 8 or color not in (2, 6):
        raise ValueError(f"unsupported screenshot format: depth {depth}, color {color}")
    step = 3 if color == 2 else 4
    raw, stride = zlib.decompress(idat), width * step
    previous, rows = bytearray(stride), []
    for y in range(height):
        kind, row = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = row[i - step] if i >= step else 0
            b = previous[i]
            c = previous[i - step] if i >= step else 0
            if kind == 1: row[i] = (row[i] + a) & 255
            elif kind == 2: row[i] = (row[i] + b) & 255
            elif kind == 3: row[i] = (row[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(row)
        previous = row
    class Pixels:
        size = (width, height)
        def __getitem__(self, at):
            x, y = at
            return tuple(rows[y][x * step:x * step + 3])
    return Pixels()


def png(color, grab):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = (b"\0" + bytes(color + (255,)) * 64) * 64
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0))
            + chunk(b"grAb", struct.pack(">II", *grab)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def textmap():
    verts = [(-512, -128), (-512, 512), (512, 512), (512, -128), (-120, 256), (-72, 256), (-72, 304), (-120, 304)]
    m = 'namespace = "zdoom";\n' + "".join(f"vertex {{ x = {x}; y = {y}; }}\n" for x, y in verts)
    for i in range(4):
        m += f"linedef {{ v1 = {i}; v2 = {(i + 1) % 4}; sidefront = {i}; blocking = true; }}\n"
        m += 'sidedef { sector = 0; texturemiddle = "PROBEBK"; }\n'
    for i in range(4):
        # The front side faces the outer room. Only the face toward the camera is the red 48-unit reference.
        m += f"linedef {{ v1 = {4 + i}; v2 = {4 + (i + 1) % 4}; sidefront = {4 + i}; sideback = {8 + i}; twosided = true; }}\n"
        m += f'sidedef {{ sector = 0; texturebottom = "{"PROBERED" if i == 0 else "PROBEBK"}"; }}\n'
    m += 'sidedef { sector = 1; }\n' * 4
    for floor in (0, 48):
        m += f'sector {{ heightfloor = {floor}; heightceiling = 256; texturefloor = "PROBEBK"; textureceiling = "PROBEBK"; lightlevel = 255; }}\n'
    m += "thing { x = 0.0; y = 0.0; angle = 90; type = 1; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; }\n"
    return m.encode()


def wad(text):
    head = struct.pack("<4sii", b"PWAD", 3, 12 + len(text))
    entries = [(12, 0, b"PROBEMAP"), (12, len(text), b"TEXTMAP"), (12 + len(text), 0, b"ENDMAP")]
    return head + text + b"".join(struct.pack("<ii8s", o, s, n.ljust(8, b"\0")) for o, s, n in entries)


ZS = '''version "4.10"
class ProbeFlat : Actor
{
	Default { +NOINTERACTION +NOBLOCKMAP +NOGRAVITY Radius 1; Height 1; }
	States { Spawn: PLAY A -1 Bright; Stop; }
}
class ProbeHandler : EventHandler
{
	override void WorldLoaded(WorldEvent e)
	{
		Put("PROBEGRN", (-24, 256, 0));
		Put("PROBEBLU", (72, 256, 24));
	}
	static void Put(String tex, Vector3 at)
	{
		let a = Actor.Spawn("ProbeFlat", at);
		a.picnum = TexMan.CheckForTexture(tex, TexMan.Type_Any);
		a.scale = (0.75, 0.75);
	}
}
'''


def extent(pixels, color):
    width, height = pixels.size
    points = [(x, y) for y in range(height) for x in range(width) if all(abs(pixels[x, y][c] - color[c]) < 40 for c in range(3))]
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(ys)


def main():
    exe, iwad, work = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
    os.makedirs(work, exist_ok=True)
    package, shot = os.path.join(work, "probe.pk3"), os.path.join(work, "probe.png")
    if os.path.exists(shot):
        os.remove(shot)
    with zipfile.ZipFile(package, "w") as z:
        z.writestr("textures/PROBERED.png", png(RED, (0, 0)))
        z.writestr("textures/PROBEBK.png", png((20, 20, 20), (0, 0)))
        z.writestr("textures/PROBEGRN.png", png(GREEN, (32, 64)))
        z.writestr("textures/PROBEBLU.png", png(BLUE, (32, 32)))
        z.writestr("maps/PROBEMAP.wad", wad(textmap()))
        z.writestr("zscript.zs", ZS)
        z.writestr("MAPINFO", 'GameInfo { AddEventHandlers = "ProbeHandler" }\nmap PROBEMAP "Probe" { pixelratio = 1.0 }\n')
    with open(os.path.join(work, "probe.ini"), "w", newline="\n") as f:
        f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth={W}\nvid_defheight={H}\n"
                f"win_w={W}\nwin_h={H}\nvid_scalefactor=1\nwin_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
    with open(os.path.join(work, "probe.cfg"), "w", newline="\n") as f:
        f.write(f'alias go "vid_setsize {W} {H}; wait 35; screenshot \\"{shot.replace(chr(92), "/")}\\"; wait 10; quit"\nwait 70; go\n')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 4
    process = subprocess.Popen([exe, "-iwad", iwad, "-file", package, "-config", os.path.join(work, "probe.ini"), "-noactivate", "-nosound",
                                "-nomonsters", "-noautoload", "-skill", "3", "-width", str(W), "-height", str(H), "+vid_fullscreen", "0",
                                "+vid_scalefactor", "1", "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png", "+show_messages", "0",
                                "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0", "+movebob", "0",
                                "+map", "PROBEMAP", "+exec", "probe.cfg"], cwd=work, startupinfo=startup,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        code = process.wait(30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        code = "timed out"
    if not os.path.exists(shot):
        print("no screenshot, UZDoom exit:", code)
        return 1
    pixels = read_png(shot)
    red, green, blue = extent(pixels, RED), extent(pixels, GREEN), extent(pixels, BLUE)
    print(f"UZDoom exit {code}. Pixels (width, height, bottom row): 48-unit pillar {red}, floor-anchored sprite {green}, centered sprite {blue}")
    if not (red and green and blue):
        return 1
    ok = all(abs(s[i] - red[i]) <= 2 for s in (green, blue) for i in range(3))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
