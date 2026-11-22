"""Throwaway: synthetic triangular-sector terrain UDMF maps in a PK3 for load/runtime tests.
Contains no game data. Output path is argv[1]."""
import io, math, os, struct, sys, zipfile

CELL = int(sys.argv[4]) if len(sys.argv) > 4 else 256

def wad(name, textmap):
    lumps = [(name, b""), ("TEXTMAP", textmap), ("ENDMAP", b"")]
    body, dirs, pos = io.BytesIO(), [], 12
    for n, data in lumps:
        body.write(data); dirs.append((pos, len(data), n)); pos += len(data)
    out = io.BytesIO()
    out.write(b"PWAD" + struct.pack("<ii", len(lumps), pos)); out.write(body.getvalue())
    for p, s, n in dirs:
        out.write(struct.pack("<ii", p, s) + n.encode().ljust(8, b"\0"))
    return out.getvalue()

def grid(n, flat=False, offset=0):
    h = n * CELL // 2
    def z(i, j):
        if flat: return 0
        x, y = i * CELL, j * CELL
        return int(128 * math.sin(x / 1700) + 96 * math.cos(y / 1300) + 40 * math.sin((x + y) / 500))
    o = ['namespace="zdoom";']
    for j in range(n + 1):
        for i in range(n + 1):
            o.append(f"vertex{{x={-h + i*CELL + offset};y={-h + j*CELL};zfloor={z(i,j)};}}")
    vid = lambda i, j: j * (n + 1) + i
    edges, tris = {}, 0
    def tri(a, b, c):  # clockwise
        nonlocal tris
        for u, v in ((a, b), (b, c), (c, a)):
            if (v, u) in edges: edges[(v, u)][1] = tris
            else: edges[(u, v)] = [tris, -1]
        tris += 1
    for j in range(n):
        for i in range(n):
            a, b, c, d = vid(i, j), vid(i+1, j), vid(i+1, j+1), vid(i, j+1)
            tri(a, c, b); tri(a, d, c)
    for _ in range(tris):
        o.append('sector{heightfloor=0;heightceiling=2048;texturefloor="RROCK19";textureceiling="F_SKY1";lightlevel=192;}')
    sides, lines = [], []
    for (u, v), (f, b) in edges.items():
        sf = len(sides); sides.append(f)
        if b >= 0:
            sb = len(sides); sides.append(b)
            ui, uj, vi, vj = u % (n + 1), u // (n + 1), v % (n + 1), v // (n + 1)
            zb = (ui == vi and ui % 32 == 0) or (uj == vj and uj % 32 == 0)
            lines.append(f"linedef{{v1={u};v2={v};sidefront={sf};sideback={sb};twosided=true;{'zoneboundary=true;' if zb else ''}}}")
        else:
            lines.append(f"linedef{{v1={u};v2={v};sidefront={sf};blocking=true;}}")
    o += lines
    o += [f'sidedef{{sector={s};texturemiddle="-";}}' for s in sides]
    o[len(o):] = [f"thing{{x={offset + CELL//2 + 8};y={CELL//2 - 64};type=1;angle=0;coop=true;dm=true;single=true;skill1=true;skill2=true;skill3=true;skill4=true;skill5=true;}}"]
    return "\n".join(o).encode()

ZS = r'''version "4.14"
class DDPlayer : DoomPlayer { override void PlayerThink() { player.cmd.forwardmove = 12800; Super.PlayerThink(); } }
class DDProbe : StaticEventHandler {
  double t0; int idx; double sx; bool loggedSpeed; ui int frames; ui double f0; ui string fmap; ui bool fdone;
  static const string seq[] = {@SEQ@};
  override void WorldLoaded(WorldEvent e) {
    if (t0 > 0) Console.Printf("DDLOAD %s changeMs=%.1f saved=%d", level.MapName, MSTimeF()-t0, e.IsSaveGame);
    Console.Printf("DDMAP %s sectors=%d lines=%d sides=%d verts=%d", level.MapName, level.sectors.Size(), level.lines.Size(), level.sides.Size(), level.vertexes.Size());
    loggedSpeed = false;
  }
  override void WorldTick() {
    let p = players[0].mo; if (!p) return;
    int t = level.maptime;
    if (t == 35) sx = p.pos.x;
    if (t == 105 && !loggedSpeed) { loggedSpeed = true; Console.Printf("DDSPEED %s unitsPerSec=%.2f velx=%.3f", level.MapName, (p.pos.x-sx)/2.0, p.vel.x); }
    if (t == 110) {
      double a = MSTimeF(); int n = level.sectors.Size();
      for (int i = 0; i < n; i++) { let s = level.sectors[i]; s.SetPlaneTexZ(Sector.floor, s.GetPlaneTexZ(Sector.floor) + 0.0, true); }
      Console.Printf("DDPLANES %s zscriptTouch=%d ms=%.2f", level.MapName, n, MSTimeF()-a);
      a = MSTimeF(); let v = p.pos; p.SetOrigin(v + (64,0,0), false); p.SetOrigin(v, false);
      Console.Printf("DDORIGIN ms=%.3f", MSTimeF()-a);
      Console.Printf("DDMAP alert-start %s", level.MapName); a = MSTimeF(); p.A_AlertMonsters();
      Console.Printf("DDPLANES alert ms=%.2f", MSTimeF()-a);
    }
    if (t == 140) {
      idx++;
      if (idx >= @LEN@) { Console.Printf("DDDONE"); return; }
      t0 = MSTimeF();
      level.ChangeLevel(seq[idx], 0, CHANGELEVEL_NOINTERMISSION);
    }
  }
  override void RenderOverlay(RenderEvent e) {
    if (fmap != level.MapName) { fmap = level.MapName; frames = 0; f0 = 0; fdone = false; }
    int t = level.maptime;
    if (t >= 35 && f0 == 0) { f0 = MSTimeF(); frames = 0; }
    if (f0 > 0) frames++;
    if (t >= 105 && f0 > 0 && !fdone) { fdone = true; double d = MSTimeF()-f0; Console.Printf("DDFPS %s fps=%.1f msPerFrame=%.2f", level.MapName, frames*1000.0/d, d/frames); }
  }
}
'''
HOP = r'''version "4.14"
class DDPlayer : DoomPlayer { override void PlayerThink() { player.cmd.forwardmove = 12800; Super.PlayerThink(); } }
class DDProbe : StaticEventHandler {
  Array<double> gx, gy; double ox, px, py, pz, vx, vy, vz, pang, t0; int hop; bool pending, seeded;
  const SHIFT = 32640.0; const N = 2000;
  override void WorldTick() {
    let p = players[0].mo; if (!p) return;
    if (!seeded) {
      seeded = true; ox = 10000000.0; p.player.cheats |= CF_GODMODE;
      for (int i = 0; i < N; i++) { double a = i * 2.399963, r = 1500 + 14000 * sqrt((i + 0.5) / N); gx.Push(ox + r * cos(a)); gy.Push(r * sin(a)); }
      Respawn(); return;
    }
    if (pending) {
      pending = false; double a = MSTimeF();
      p.SetOrigin((px - ox, py, pz), false); p.vel = (vx, vy, vz); p.angle = pang; p.player.cheats |= CF_GODMODE;
      int got = Respawn();
      double e = abs((p.pos.x + ox) - px) + abs(p.pos.y - py);
      Console.Printf("DDHOP %d swapMs=%.1f restoreMs=%.2f actors=%d reg=%d x0=%.1f ox=%.1f playerErr=%.9f vel=%.3f localX=%.1f", hop, a - t0, MSTimeF() - a, got, gx.Size(), gx.Size() ? gx[0] - ox : 0, ox, e, p.vel.length(), p.pos.x);
    }
    if (level.maptime == 70) {
      hop++;
      if (hop > 8) { Console.Printf("DDDONE"); return; }
      px = p.pos.x + ox; py = p.pos.y; pz = p.pos.z; vx = p.vel.x; vy = p.vel.y; vz = p.vel.z; pang = p.angle;
      ox += (hop % 2) ? SHIFT : -SHIFT; pending = true; t0 = MSTimeF();
      level.ChangeLevel((hop % 2) ? "file:@A@" : "file:@B@", 0, CHANGELEVEL_NOINTERMISSION);
    }
  }
  int Respawn() {
    int spawned = 0;
    for (int i = 0; i < N; i++) {
      double x = gx[i] - ox, y = gy[i];
      if (abs(x) > 16000 || abs(y) > 16000) continue;
      let m = Actor.Spawn("ZombieMan", (x, y, 0)); if (m) { m.SetZ(m.floorz); spawned++; }
    }
    return spawned;
  }
}
'''
if len(sys.argv) > 6 and sys.argv[6] == "hop":
    b = sys.argv[1].replace("\\", "/")
    ZS = HOP.replace("@A@", b + ".a.wad").replace("@B@", b + ".b.wad")
    for s in ".a.wad", ".b.wad":
        open(sys.argv[1] + s, "wb").write(wad("EXTMAP", grid(128)))
SIZES = [int(x) for x in sys.argv[2].split(",")]
SEQ = sys.argv[3].split(",")
ZS = ZS.replace("@SEQ@", ",".join(f'"{m}"' for m in SEQ)).replace("@LEN@", str(len(SEQ)))
MAPINFO = 'gameinfo { addeventhandlers = "DDProbe" playerclasses = "DDPlayer" }\ncluster 1 { hub }\n' + "".join(
    f'map {m} "{m}" {{ sky1="SKY1" cluster=1 next="{m}" }}\n' for m in ["DDFLAT", "DDBAD"] + [f"DD{n:03d}" for n in SIZES])

out = sys.argv[1]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    z.writestr("zscript.txt", ZS); z.writestr("mapinfo.txt", MAPINFO)
    z.writestr("maps/DDFLAT.wad", wad("DDFLAT", grid(64, True)))
    for n in SIZES:
        t = grid(n, len(sys.argv) > 5 and sys.argv[5] == "flat"); print("cells", n, "textmap bytes", len(t))
        z.writestr(f"maps/DD{n:03d}.wad", wad(f"DD{n:03d}", t))
    z.writestr("maps/DDBAD.wad", wad("DDBAD", grid(8, True, 40000)))
open(out + ".src.wad", "wb").write(wad("EXTMAP", grid(64)))
print("wrote", out)
