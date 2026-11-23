"""Builds the overworld treadmill package from WOODS.WLD.

Output is derived from game data. Keep it out of the repository.
The engine samples terrain at runtime, using the same math as Daggerfall Unity's
DefaultTerrainSampler, from the compact DDWORLD lump written here.
"""
import argparse, io, os, struct, zipfile

W, H = 1000, 500
CELLS, SPACING = 128, 192  # 256 Daggerfall units per tile at 75% scale
CEILING = 32768  # UDMF's limit. The engine raises the sky above the highest terrain at startup.
# Town meshes are built from these smoothed, flattened heights, so the overworld's collision must use them too.
DEFAULT_WORLD_DIR = r"D:\dev\DoomDaggerfall-build\stitch-data"

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


def build_map(floor="RROCK19", scale=""):
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
    o += [f'sector{{heightfloor=0;heightceiling={CEILING};texturefloor="{floor}";textureceiling="F_SKY1";lightlevel=192;{scale}}}'] * tris
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
    ap.add_argument("--ground-from", help="town mesh package: its grass tile becomes the overworld floor")
    ap.add_argument("--world-dir", help="DDWORLD and DDLOCS from the converter's --world mode. Defaults to DEFAULT_WORLD_DIR.")
    ap.add_argument("--raw-world", action="store_true", help="use unsmoothed WOODS.WLD heights with no location flattening. Town meshes will not match.")
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
    mapinfo = f'gameinfo {{ addeventhandlers = {names} }}\nmap DDOVER01 "Daggerfall Overworld" {{ sky1 = "{sky}" keepfullinventory pixelratio = 1.0 }}\n'

    with open(args.woods, "rb") as f:
        woods = f.read()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        if args.ground_from:
            # One Daggerfall ground tile per terrain tile, so open ground matches the town mesh it meets.
            with zipfile.ZipFile(args.ground_from) as town:
                tile = next(n for n in town.namelist() if n.startswith("dfmesh/a") and n.endswith("r02.png") and 302 <= int(n[8:11]) <= 402)
                z.writestr("flats/DFGROUND.png", town.read(tile))
            z.writestr("maps/DDOVER01.wad", build_map("DFGROUND", "xscalefloor=0.3333333;yscalefloor=0.3333333;"))
        else:
            z.writestr("maps/DDOVER01.wad", build_map())
        world_dir = None if args.raw_world else args.world_dir or DEFAULT_WORLD_DIR
        if world_dir:
            if not all(os.path.isfile(os.path.join(world_dir, n)) for n in ("DDWORLD", "DDLOCS")):
                raise SystemExit(f"{world_dir} needs DDWORLD and DDLOCS. Run the converter with --world --out <dir>, or pass --raw-world.")
            z.write(os.path.join(world_dir, "DDWORLD"), "DDWORLD")
            z.write(os.path.join(world_dir, "DDLOCS"), "DDLOCS")
        else:
            z.writestr("DDWORLD", world_lump(woods))
        z.writestr("DDWLDCFG", config)
        z.writestr("zscript.txt", zscript)
        z.writestr("mapinfo.txt", mapinfo)
    print(f"wrote {args.out} start_tile={start_x},{start_y} size={os.path.getsize(args.out)}")


if __name__ == "__main__":
    main()
