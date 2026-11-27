"""Scan the five supported weapon sets for every pickup-able weapon and its pickup sprite size.

Usage: python -I tools/weapon_values/scan_weapons.py [--json out.json]

Reads (never writes) GameMods/ExtractedData (DRLA, DRLAX, Schism + its patch) and the IWADs in GameResources/wads
(DOOM2.WAD, heretic.wad, hexen.wad). For each weapon it prints: set, class, DRLA tier folder (DRLA only), slot,
ammo, DRLA type tokens it gives, pickup sprite lump, sprite size, and the count of its non-black pixels times the
actor's Scale (the "visual area" used to scale weight within a kind).

Only numbers leave this script; no game data is copied. build_weapon_values.py turns the scan into
daggerfall-unity-master/Assets/Resources/Doomerfall/WeaponValues.txt.
"""
import io
import json
import os
import re
import struct
import sys
import zlib

ROOT = r"D:\dev\DoomDaggerfall"
EXTRACTED = os.path.join(ROOT, "GameMods", "ExtractedData")
WADS = os.path.join(ROOT, "GameResources", "wads")

# A pixel counts as "non-black" when it is opaque and its brightest channel exceeds this (0-255). Doom sprites draw
# shadows and outlines in near-black palette entries; the owner asked for the size of the non-black sprite.
BLACK_MAX = 24


# ---------------------------------------------------------------- lumps and pictures

def read_wad(path):
    with open(path, "rb") as f:
        data = f.read()
    _, count, offset = struct.unpack_from("<4sii", data, 0)
    lumps = []
    for i in range(count):
        pos, size, name = struct.unpack_from("<ii8s", data, offset + i * 16)
        lumps.append((name.rstrip(b"\0").decode("latin-1").upper(), data[pos:pos + size]))
    return lumps


def wad_sprites(lumps):
    out, inside = {}, False
    for name, data in lumps:
        if name in ("S_START", "SS_START"):
            inside = True
        elif name in ("S_END", "SS_END"):
            inside = False
        elif inside:
            out[name] = data
    return out


def palette_of(lumps):
    for name, data in lumps:
        if name == "PLAYPAL":
            return [tuple(data[i * 3:i * 3 + 3]) for i in range(256)]
    raise SystemExit("no PLAYPAL")


def png_pixels(data):
    """Minimal PNG decoder: returns (w, h, list of (r,g,b,a)). Supports 8-bit gray/RGB/RGBA/palette, no interlace."""
    pos, chunks = 8, []
    plte, trns, idat = None, None, b""
    while pos < len(data):
        length, kind = struct.unpack_from(">I4s", data, pos)
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            plte = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat += body
    if depth != 8 or interlace:
        return None
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * channels
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        ft = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ft == 1:
                line[x] = (line[x] + a) & 255
            elif ft == 2:
                line[x] = (line[x] + b) & 255
            elif ft == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    px = []
    for line in rows:
        for x in range(w):
            if ctype == 6:
                px.append(tuple(line[x * 4:x * 4 + 4]))
            elif ctype == 2:
                px.append(tuple(line[x * 3:x * 3 + 3]) + (255,))
            elif ctype == 0:
                v = line[x]; px.append((v, v, v, 255))
            elif ctype == 4:
                v = line[x * 2]; px.append((v, v, v, line[x * 2 + 1]))
            else:
                idx = line[x]
                r, g, b = plte[idx]
                alpha = trns[idx] if trns is not None and idx < len(trns) else 255
                px.append((r, g, b, alpha))
    return w, h, px


def patch_pixels(data, pal):
    w, h = struct.unpack_from("<hh", data, 0)
    if w <= 0 or h <= 0 or w > 4096 or h > 4096 or len(data) < 8 + 4 * w:
        return None
    px = [(0, 0, 0, 0)] * (w * h)
    for x in range(w):
        (col,) = struct.unpack_from("<I", data, 8 + 4 * x)
        p, top = col, -1
        while p < len(data) and data[p] != 0xFF:
            delta, length = data[p], data[p + 1]
            top = delta if delta > top else top + delta  # tall patches
            for j in range(length):
                y = top + j
                if 0 <= y < h and p + 3 + j < len(data):
                    px[y * w + x] = pal[data[p + 3 + j]] + (255,)
            p += length + 4
    return w, h, px


def measure(data, pal):
    pic = png_pixels(data) if data[:8] == b"\x89PNG\r\n\x1a\n" else patch_pixels(data, pal)
    if pic is None:
        return None
    w, h, px = pic
    n = sum(1 for (r, g, b, a) in px if a >= 128 and max(r, g, b) > BLACK_MAX)
    return w, h, n


# ---------------------------------------------------------------- DECORATE

def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


class Tree:
    """An extracted PK3 folder, case-insensitive; later trees override earlier ones (a patch over its mod)."""

    def __init__(self, *roots):
        self.files, self.sprites = {}, {}
        for root in roots:
            for dirpath, _, names in os.walk(root):
                rel = os.path.relpath(dirpath, root).replace("\\", "/").lower()
                for n in names:
                    full = os.path.join(dirpath, n)
                    self.files[(rel + "/" + n.lower()).lstrip("./")] = full
                    if rel.split("/")[0] == "sprites":
                        self.sprites[os.path.splitext(n)[0].upper()] = full

    def read(self, rel):
        path = self.files.get(rel.replace("\\", "/").lower().lstrip("./"))
        if not path:
            return None
        with open(path, "rb") as f:
            return f.read().decode("latin-1")


def load_decorate(tree, root_name):
    """Every actor reachable from the root DECORATE by #include: name -> dict."""
    actors, seen = {}, set()

    def visit(rel):
        if rel.lower() in seen:
            return
        seen.add(rel.lower())
        text = tree.read(rel)
        if text is None:
            return
        text = strip_comments(text)
        for inc in re.findall(r'#include\s+"([^"]+)"', text, flags=re.I):
            visit(inc)
        parse_actors(text, rel, actors)

    visit(root_name)
    return actors


HEADER = re.compile(r"(?im)^\s*actor\s+([\w.]+)\s*(?::\s*([\w.]+))?\s*(?:replaces\s+([\w.]+))?\s*(\d+)?[^{\n]*\n?\s*\{")


def parse_actors(text, rel, actors):
    for m in HEADER.finditer(text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[m.end():i - 1]
        actors[m.group(1).lower()] = {"name": m.group(1), "parent": (m.group(2) or "").lower(), "file": rel,
                                      "body": body, "replaces": (m.group(3) or "").lower()}


FRAME = re.compile(r'^\s*("?[A-Z0-9_#\-]{4}"?)\s+("?[A-Z\[\]\\#^]+"?)\s+(-?\d+|random\s*\()', re.I)


def states_of(body):
    m = re.search(r"(?i)\bstates\s*\{", body)
    if not m:
        return {}
    labels, current = {}, []
    for line in body[m.end():].splitlines():
        for lab in re.findall(r"^\s*([\w.]+)\s*:", line):
            current = labels.setdefault(lab.lower(), [])
            line = line.split(":", 1)[1]
        current_list = current
        line = line.strip()
        if not line:
            continue
        g = re.match(r"(?i)(goto|loop|stop|wait|fail)\b\s*([\w.:]*)", line)
        if g:
            current_list.append(("goto", g.group(2).lower()) if g.group(1).lower() == "goto" else ("end", ""))
            continue
        f = FRAME.match(line)
        if f:
            current_list.append(("frame", f.group(1).strip('"').upper(), f.group(2).strip('"').upper()))
    return labels


def find_state(actors, cls, label):
    while cls in actors:
        st = states_of(actors[cls]["body"])
        if label in st:
            return st[label]
        cls = actors[cls]["parent"]
    return None


def spawn_sprite(actors, cls):
    """The first visible frame of the actor's Spawn state (DRLA pickups: SpawnFrame), as (sprite, frame letter)."""
    for start in ("spawnframe", "spawn"):
        label = start
        for _ in range(6):
            frames = find_state(actors, cls, label)
            if not frames:
                break
            nxt = None
            for item in frames:
                if item[0] == "frame" and item[1] not in ("TNT1", "####", "----") and item[2] not in ("#",):
                    return item[1], item[2][0]
                if item[0] == "goto":
                    nxt = item[1].split("::")[-1]
                    break
                if item[0] == "end":
                    break
            if not nxt:
                break
            label = nxt
    m = re.search(r"\$Sprite\s+(\w{5,})", actors[cls]["body"]) if cls in actors else None
    return (m.group(1)[:4].upper(), m.group(1)[4].upper()) if m else None


def prop(actors, cls, key):
    rx = re.compile(r"(?im)^\s*" + re.escape(key) + r"\s+(.+?)\s*$")
    while cls in actors:
        m = rx.search(actors[cls]["body"].split("States")[0] if "States" in actors[cls]["body"] else actors[cls]["body"])
        if m:
            return m.group(1).strip().strip('"')
        cls = actors[cls]["parent"]
    return None


def ancestors(actors, cls):
    out = []
    while cls:
        out.append(cls)
        cls = actors[cls]["parent"] if cls in actors else ""
    return out


def scale_of(actors, cls):
    s = prop(actors, cls, "Scale")
    sx = prop(actors, cls, "XScale") or s or "1"
    sy = prop(actors, cls, "YScale") or s or "1"
    try:
        return float(sx.split()[0].rstrip(";")), float(sy.split()[0].rstrip(";"))
    except ValueError:
        return 1.0, 1.0


def sprite_lump(sprites, spr, frame):
    for name in (spr + frame + "0", spr + frame + "1"):
        if name in sprites:
            return name
    for name in sorted(sprites):
        if name.startswith(spr + frame) and len(name) >= 6:
            return name
    return None


def read_lump(sprites, name):
    v = sprites[name]
    if isinstance(v, bytes):
        return v
    with open(v, "rb") as f:
        return f.read()


WEAPON_BASES = {"weapon", "doomweapon", "hereticweapon", "fighterweapon", "clericweapon", "mageweapon", "weaponpiece",
                "fist", "chainsaw", "pistol", "shotgun", "supershotgun", "chaingun", "rocketlauncher", "plasmarifle",
                "bfg9000", "staff", "gauntlets", "goldwand", "crossbow", "blaster", "skullrod", "phoenixrod", "mace"}

TOKENS = ["RLPistolTypeWeapon", "RLShotgunTypeWeapon", "RLRapidfireTypeWeapon", "RLSingleShotRifleTypeWeapon",
          "RLMeleeTypeWeapon"]


def entry(set_name, cls, pickup, actors, sprites, pal, tier=""):
    spr = spawn_sprite(actors, pickup)
    lump = sprite_lump(sprites, *spr) if spr else None
    size = measure(read_lump(sprites, lump), pal) if lump else None
    sx, sy = scale_of(actors, pickup)
    body = "".join(actors[a]["body"] for a in ancestors(actors, cls) if a in actors)
    return {
        "set": set_name, "class": actors[cls]["name"], "pickup": actors[pickup]["name"], "tier": tier,
        "file": actors[cls]["file"], "slot": prop(actors, cls, "Weapon.SlotNumber") or "",
        "ammo": (prop(actors, cls, "Weapon.AmmoType2") or prop(actors, cls, "Weapon.AmmoType") or prop(actors, cls, "Weapon.AmmoType1") or ""),
        "ammo1": prop(actors, cls, "Weapon.AmmoType1") or prop(actors, cls, "Weapon.AmmoType") or "",
        "tokens": [t for t in TOKENS if t.lower() in body.lower()],
        "tag": prop(actors, cls, "Tag") or "",
        "sprite": lump or "", "w": size[0] if size else 0, "h": size[1] if size else 0,
        "pixels": size[2] if size else 0, "scale": [sx, sy],
        "area": round(size[2] * sx * sy, 1) if size else 0,
    }


def with_iwad(tree, doom2):
    """The mod's sprites over DOOM2.WAD's: a mod pickup may reuse a stock sprite (Schism's BFG giver shows BFUGA0)."""
    merged = dict(wad_sprites(doom2))
    merged.update(tree.sprites)
    return merged


def scan_drla(doom2):
    out = []
    pal = palette_of(doom2)
    for set_name, folder in (("DRLA", "DoomRL_Arsenal_1.1.5"), ("DRLAX", "DRLAX_1.2b")):
        root = os.path.join(EXTRACTED, folder)
        tree = Tree(os.path.join(EXTRACTED, "DoomRL_Arsenal_1.1.5"), root) if set_name == "DRLAX" else Tree(root)
        actors = load_decorate(tree, "decorate.txt")
        if set_name == "DRLAX":
            drla_names = set(load_decorate(Tree(os.path.join(EXTRACTED, "DoomRL_Arsenal_1.1.5")), "decorate.txt"))
        for key, a in sorted(actors.items()):
            f = a["file"].replace("\\", "/").lower()
            if not f.startswith("actors/weapons/") or (key + "pickup") not in actors:
                continue
            if set_name == "DRLAX" and key in drla_names:
                continue
            parts = f.split("/")
            tier = parts[2] if len(parts) > 3 else os.path.splitext(parts[2])[0].replace("assemblies", "")
            out.append(entry(set_name, key, key + "pickup", actors, with_iwad(tree, doom2), pal, tier))
    return out


def scan_schism(doom2):
    pal = palette_of(doom2)
    tree = Tree(os.path.join(EXTRACTED, "Schism_097D"), os.path.join(EXTRACTED, "Schism_097D_Patch_0.1"))
    actors = load_decorate(tree, "decorate")
    weapons = set()
    for key, a in actors.items():
        anc = ancestors(actors, key)
        if set(anc[1:]) & WEAPON_BASES and "weaponpiece" not in anc[1:]:
            weapons.add(key)
    # Schism's floor pickups are CustomInventory "givers" (Schism_ShotgunGiver) that give the weapon. A giver that
    # gives several weapons (dual wield) counts for the first one it names.
    givers = {}
    for key, a in actors.items():
        if key in weapons or "custominventory" not in ancestors(actors, key):
            continue
        names = [n.lower() for n in re.findall(r'A_GiveInventory\s*\(\s*"(\w+)"', a["body"], flags=re.I)]
        given = [n for n in names if n in weapons]
        if given and spawn_sprite(actors, key):
            givers.setdefault(given[0], []).append(key)
    out = []
    for key in sorted(weapons):
        a = actors[key]
        if key.endswith("powered") or "/weapons/" not in a["file"].replace("\\", "/").lower():
            continue
        if key in givers:
            pick = sorted(givers[key], key=lambda g: ("giver" not in g, "empty" in g, len(g)))
            e = entry("Schism", key, pick[0], actors, with_iwad(tree, doom2), pal)
            e["pickups"] = [actors[g]["name"] for g in pick]
        else:
            e = entry("Schism", key, key, actors, with_iwad(tree, doom2), pal)
            e["pickups"] = [a["name"]]
            e["nogiver"] = True
        out.append(e)
    return out


STOCK = [
    # set, class, spawn sprite (None = never a pickup; it is a starting weapon), slot
    ("Doom", "Fist", None, 1), ("Doom", "Chainsaw", "CSAWA0", 1), ("Doom", "Pistol", "PISTA0", 2),
    ("Doom", "Shotgun", "SHOTA0", 3), ("Doom", "SuperShotgun", "SGN2A0", 3), ("Doom", "Chaingun", "MGUNA0", 4),
    ("Doom", "RocketLauncher", "LAUNA0", 5), ("Doom", "PlasmaRifle", "PLASA0", 6), ("Doom", "BFG9000", "BFUGA0", 7),
    ("Heretic", "Staff", None, 1), ("Heretic", "Gauntlets", "WGNTA0", 1), ("Heretic", "GoldWand", None, 2),
    ("Heretic", "Crossbow", "WBOWA0", 3), ("Heretic", "Blaster", "WBLSA0", 4), ("Heretic", "SkullRod", "WSKLA0", 5),
    ("Heretic", "PhoenixRod", "WPHXA0", 6), ("Heretic", "Mace", "WMCEA0", 7),
    ("Hexen", "FWeapFist", None, 1), ("Hexen", "FWeapAxe", "WFAXA0", 2), ("Hexen", "FWeapHammer", "WFHMA0", 3),
    ("Hexen", "FWeapQuietus", None, 4), ("Hexen", "FWeaponPiece1", "WFR1A0", 4), ("Hexen", "FWeaponPiece2", "WFR2A0", 4),
    ("Hexen", "FWeaponPiece3", "WFR3A0", 4),
    ("Hexen", "CWeapMace", None, 1), ("Hexen", "CWeapStaff", "WCSSA0", 2), ("Hexen", "CWeapFlame", "WCFMA0", 3),
    ("Hexen", "CWeapWraithverge", None, 4), ("Hexen", "CWeaponPiece1", "WCH1A0", 4), ("Hexen", "CWeaponPiece2", "WCH2A0", 4),
    ("Hexen", "CWeaponPiece3", "WCH3A0", 4),
    ("Hexen", "MWeapWand", None, 1), ("Hexen", "MWeapFrost", "WMCSA0", 2), ("Hexen", "MWeapLightning", "WMLGA0", 3),
    ("Hexen", "MWeapBloodscourge", None, 4), ("Hexen", "MWeaponPiece1", "WMS1A0", 4), ("Hexen", "MWeaponPiece2", "WMS2A0", 4),
    ("Hexen", "MWeaponPiece3", "WMS3A0", 4),
]


def scan_stock(wads):
    out = []
    for set_name, cls, lump, slot in STOCK:
        lumps = wads[set_name]
        sprites, pal = wad_sprites(lumps), palette_of(lumps)
        size = measure(sprites[lump], pal) if lump and lump in sprites else None
        out.append({"set": set_name, "class": cls, "pickup": cls, "tier": "", "file": "", "slot": str(slot), "ammo": "",
                    "ammo1": "", "tokens": [], "tag": "", "sprite": lump or "", "w": size[0] if size else 0,
                    "h": size[1] if size else 0, "pixels": size[2] if size else 0, "scale": [1, 1],
                    "area": size[2] if size else 0})
    return out


def main():
    wads = {"Doom": read_wad(os.path.join(WADS, "DOOM2.WAD")), "Heretic": read_wad(os.path.join(WADS, "heretic.wad")),
            "Hexen": read_wad(os.path.join(WADS, "hexen.wad"))}
    rows = scan_stock(wads) + scan_drla(wads["Doom"]) + scan_schism(wads["Doom"])
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            json.dump(rows, f, indent=1)
    for r in rows:
        print("{set:7} {class:28} {tier:9} slot={slot:2} ammo={ammo:18} {tok:30} {sprite:9} {w:3}x{h:<3} px={pixels:5} area={area}".format(
            tok=",".join(t.replace("TypeWeapon", "").replace("RL", "") for t in r["tokens"]), **r))
    print(len(rows), "weapons")


if __name__ == "__main__":
    main()
