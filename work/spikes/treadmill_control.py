"""Controls for the treadmill test, all with the patch inactive (no -ddtreadmill).

1. Physics: load one treadmill window as an ordinary static sloped UDMF map and report top speed.
2. Compatibility: stock IWAD startup check (exit 1337) and a live MAP01 run.
"""
import io, os, re, struct, subprocess, time, zipfile

REVIEW = r"D:\dev\DoomDaggerfall-loop\review\terrain-treadmill"
EXE = r"D:\dev\DoomDaggerfall-build\uzdoom-treadmill\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
WINDOW_TILE = 32  # the window the treadmill shows after its first shift
COMMON = ["-iwad", IWAD, "-config", os.path.join(REVIEW, "control.ini"), "-nosound", "-noautoload", "-stdout", "-noactivate",
          "-width", "1280", "-height", "720", "+vid_fullscreen", "0", "+wipetype", "0", "+gl_cachenodes", "0", "+disableautosave", "1",
          "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0"]

ZS = '''version "4.14"
class TMPlayer : DoomPlayer { override void PlayerThink() { player.cmd.forwardmove = 12800; player.cheats |= CF_GODMODE; Super.PlayerThink(); } }
class CtlHandler : EventHandler {
  Vector2 last; bool has; double top; bool done;
  override void WorldTick() {
    let p = players[0].mo; if (!p || done) return;
    if (has) top = max(top, (p.pos.xy - last).Length());
    last = p.pos.xy; has = true;
    if (p.pos.x > 4096 || level.maptime > 900) { done = true; Console.Printf("CTRL static map topStep=%.2f endX=%.1f tic=%d", top, p.pos.x, level.maptime); }
  }
}
'''


def run(name, args, seconds):
    log = os.path.join(REVIEW, name + ".log")
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7
    with open(log, "wb") as out:
        p = subprocess.Popen([EXE] + COMMON + args, stdout=out, stderr=subprocess.STDOUT, cwd=REVIEW, startupinfo=si)
        t = time.time()
        while time.time() - t < seconds and p.poll() is None:
            time.sleep(0.25)
        code = p.poll()
        if code is None:
            p.kill()
            p.wait()
    return code, open(log, "rb").read().decode("utf8", "replace")


with open(os.path.join(REVIEW, "heights.bin"), "rb") as f:
    _, _, cells, spacing, width, height, _, _ = struct.unpack("<4s7i", f.read(32))
    heights = struct.unpack(f"<{width * height}f", f.read())

wad = zipfile.ZipFile(os.path.join(REVIEW, "treadmill.pk3")).read("maps/TREADM01.wad")
offset, size = struct.unpack_from("<ii", wad, struct.unpack_from("<i", wad, 8)[0] + 16)
text = wad[offset:offset + size].decode()
index = [0]


def add_height(match):
    n = index[0]
    index[0] += 1
    i, j = n % (cells + 1), n // (cells + 1)
    return f"{match.group(1)}zfloor={heights[j * width + WINDOW_TILE + i]:.3f};}}"


text = re.sub(r"(vertex\{x=-?\d+;y=-?\d+;)\}", add_height, text).replace("thing{x=-3968;", "thing{x=-4094;")
body = text.encode()
lumps = [("TREADM01", b""), ("TEXTMAP", body), ("ENDMAP", b"")]
out, dirs, pos = io.BytesIO(), [], 12
for n, d in lumps:
    out.write(d)
    dirs.append((pos, len(d), n))
    pos += len(d)
new_wad = b"PWAD" + struct.pack("<ii", 3, pos) + out.getvalue() + b"".join(struct.pack("<ii", p, s) + n.encode().ljust(8, b"\0") for p, s, n in dirs)
pk3 = os.path.join(REVIEW, "control.pk3")
with zipfile.ZipFile(pk3, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("maps/TREADM01.wad", new_wad)
    z.writestr("zscript.txt", ZS)
    z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "CtlHandler" playerclasses = "TMPlayer" }\nmap TREADM01 "Control" { sky1 = "SKY1" }\n')

_, log = run("control_static", ["-file", pk3, "+map", "TREADM01"], 45)
print("static:", re.findall(r"CTRL .*", log) or "no result", "| treadmill active:", "DDTM active" in log)
code, _ = run("control_norun", ["-norun"], 60)
print("stock -norun exit code:", code)
code, log = run("control_map01", ["+map", "MAP01"], 20)
print("stock MAP01 still running after 20 s:", code is None, "| entered map:", "MAP01" in log, "| treadmill active:", "DDTM" in log)
