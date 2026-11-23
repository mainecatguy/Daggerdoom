"""Builds the overworld treadmill package from WOODS.WLD.

Output is derived from game data. Keep it out of the repository.
The engine samples terrain at runtime, using the same math as Daggerfall Unity's
DefaultTerrainSampler, from the compact DDWORLD lump written here.
"""
import argparse, io, os, struct, zipfile

W, H = 1000, 500
CELLS, SPACING = 128, 192  # 256 Daggerfall units per tile at 75% scale
CEILING = 32768  # UDMF's limit. The engine raises the sky above the highest terrain at startup.

PLAYER_ZS = '''version "4.14"
// Overworld player width: 75% of Daggerfall's character. Height and eye stay stock Doom.
class DDOverworldSize : EventHandler
{
	override void WorldTick()
	{
		for (int i = 0; i < MAXPLAYERS; i++)
			if (playeringame[i] && players[i].mo && players[i].mo.radius != 10.5)
				players[i].mo.A_SetSize(10.5, players[i].mo.height);
	}
}
'''


def world_lump(woods):
    hm_off = struct.unpack_from("<I", woods, 28)[0]
    small = woods[hm_off:hm_off + W * H]
    offsets = struct.unpack_from(f"<{W * H}I", woods, 144)
    large = bytearray(W * H * 9)
    for i, off in enumerate(offsets):
        o = off + 22
        for b in range(3):  # Inner 3x3 with Y inverted, as GetLargeHeightMapValuesRange reads it.
            row = o + (3 - b) * 5 + 1
            large[i * 9 + b * 3:i * 9 + b * 3 + 3] = woods[row:row + 3]
    return b"DDW1" + struct.pack("<HH", W, H) + small + bytes(large)


def build_map():
    half = CELLS * SPACING // 2
    o = ['namespace="zdoom";']
    for j in range(CELLS + 1):
        for i in range(CELLS + 1):
            o.append(f"vertex{{x={-half + i * SPACING};y={-half + j * SPACING};}}")
    vid = lambda i, j: j * (CELLS + 1) + i
    edges, tris = {}, 0

    def tri(a, b, c):
        nonlocal tris
        for u, v in ((a, b), (b, c), (c, a)):
            if (v, u) in edges:
                edges[(v, u)][1] = tris
            else:
                edges[(u, v)] = [tris, -1]
        tris += 1

    for j in range(CELLS):
        for i in range(CELLS):
            a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
            tri(a, c, b)
            tri(a, d, c)
    o += [f'sector{{heightfloor=0;heightceiling={CEILING};texturefloor="RROCK19";textureceiling="F_SKY1";lightlevel=192;}}'] * tris
    sides, lines = [], []
    for (u, v), (f, b) in edges.items():
        sf = len(sides)
        sides.append(f)
        if b >= 0:
            sb = len(sides)
            sides.append(b)
            ui, uj, vi, vj = u % (CELLS + 1), u // (CELLS + 1), v % (CELLS + 1), v // (CELLS + 1)
            zone = (ui == vi and ui % 32 == 0) or (uj == vj and uj % 32 == 0)
            lines.append(f"linedef{{v1={u};v2={v};sidefront={sf};sideback={sb};twosided=true;{'zoneboundary=true;' if zone else ''}}}")
        else:
            lines.append(f"linedef{{v1={u};v2={v};sidefront={sf};blocking=true;}}")
    o += lines
    o += [f'sidedef{{sector={s};texturemiddle="-";}}' for s in sides]
    o.append("thing{x=8;y=8;type=1;angle=0;coop=true;dm=true;single=true;skill1=true;skill2=true;skill3=true;skill4=true;skill5=true;}")
    textmap = "\n".join(o).encode()
    lumps = [("DDOVER01", b""), ("TEXTMAP", textmap), ("ENDMAP", b"")]
    body, dirs, pos = io.BytesIO(), [], 12
    for n, d in lumps:
        body.write(d)
        dirs.append((pos, len(d), n))
        pos += len(d)
    out = io.BytesIO()
    out.write(b"PWAD" + struct.pack("<ii", len(lumps), pos) + body.getvalue())
    for p, s, n in dirs:
        out.write(struct.pack("<ii", p, s) + n.encode().ljust(8, b"\0"))
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--woods", default=r"D:\dev\DoomDaggerfall\GameResources\DAGGER\ARENA2\WOODS.WLD")
    ap.add_argument("--out", required=True, help="output .pk3")
    ap.add_argument("--start", default="862,442", help="starting map pixel mx,my")
    ap.add_argument("--start-tile", help="window origin in global tiles, overrides --start")
    ap.add_argument("--start-angle", type=int, default=0)
    ap.add_argument("--world-dir", help="DDWORLD and DDLOCS from the converter's --world mode. Required for towns to match.")
    ap.add_argument("--packchance", type=float, default=0.2)
    ap.add_argument("--packsize", type=int, default=12)
    ap.add_argument("--classes", default="ZombieMan,ShotgunGuy,DoomImp,Demon")
    ap.add_argument("--harness", help="test ZScript file to include")
    ap.add_argument("--mode", default="compass", help="harness mode")
    args = ap.parse_args()

    mx, my = map(int, args.start.split(","))
    start_x = mx * 128 - CELLS // 2 + 64
    start_y = (H - 1 - my) * 128 - CELLS // 2 + 64
    if args.start_tile:
        start_x, start_y = map(int, args.start_tile.split(","))
    config = (f"starttilex {start_x}\nstarttiley {start_y}\nstartangle {args.start_angle}\npackchance {args.packchance}\n"
              f"packsize {args.packsize}\nclasses {args.classes}\n")

    handlers = ["DDOverworldSize"]
    zscript = PLAYER_ZS
    if args.harness:
        text = open(args.harness).read().replace("@MODE@", args.mode)
        zscript += text.split("\n", 1)[1]  # Drop the harness file's version line.
        handlers.append("OWHarness")
    names = ", ".join(f'"{h}"' for h in handlers)
    sky = "DFSKY" if args.world_dir else "SKY1"  # DFSKY comes from the town package
    mapinfo = f'gameinfo {{ addeventhandlers = {names} }}\nmap DDOVER01 "Daggerfall Overworld" {{ sky1 = "{sky}" keepfullinventory }}\n'

    with open(args.woods, "rb") as f:
        woods = f.read()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("maps/DDOVER01.wad", build_map())
        if args.world_dir:
            z.write(os.path.join(args.world_dir, "DDWORLD"), "DDWORLD")
            z.write(os.path.join(args.world_dir, "DDLOCS"), "DDLOCS")
        else:
            z.writestr("DDWORLD", world_lump(woods))
        z.writestr("DDWLDCFG", config)
        z.writestr("zscript.txt", zscript)
        z.writestr("mapinfo.txt", mapinfo)
    print(f"wrote {args.out} start_tile={start_x},{start_y} size={os.path.getsize(args.out)}")


if __name__ == "__main__":
    main()
