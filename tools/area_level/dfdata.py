"""Minimal readers for Daggerfall's MAPS.BSA and POLITIC.PAK.

Ported from Daggerfall Unity's MapsFile.cs, BsaFile.cs, and PakFile.cs.
Reads only what the area level proposal needs: each location's name, region,
map pixel, location type, and dungeon type.
"""
import os
import struct

REGION_NAMES = [
    "Alik'r Desert", "Dragontail Mountains", "Glenpoint Foothills", "Daggerfall Bluffs",
    "Yeorth Burrowland", "Dwynnen", "Ravennian Forest", "Devilrock",
    "Malekna Forest", "Isle of Balfiera", "Bantha", "Dak'fron",
    "Islands in the Western Iliac Bay", "Tamarilyn Point", "Lainlyn Cliffs", "Bjoulsae River",
    "Wrothgarian Mountains", "Daggerfall", "Glenpoint", "Betony", "Sentinel", "Anticlere", "Lainlyn", "Wayrest",
    "Gen Tem High Rock village", "Gen Rai Hammerfell village", "Orsinium Area", "Skeffington Wood",
    "Hammerfell bay coast", "Hammerfell sea coast", "High Rock bay coast", "High Rock sea coast",
    "Northmoor", "Menevia", "Alcaire", "Koegria", "Bhoriane", "Kambria", "Phrygias", "Urvaius",
    "Ykalon", "Daenia", "Shalgora", "Abibon-Gora", "Kairou", "Pothago", "Myrkwasa", "Ayasofya",
    "Tigonus", "Kozanset", "Satakalaam", "Totambu", "Mournoth", "Ephesus", "Santaki", "Antiphyllos",
    "Bergama", "Gavaudon", "Tulune", "Glenumbra Moors", "Ilessan Hills", "Cybiades",
]

LOCATION_TYPES = [
    "TownCity", "TownHamlet", "TownVillage", "HomeFarms", "DungeonLabyrinth",
    "ReligionTemple", "Tavern", "DungeonKeep", "HomeWealthy", "ReligionCult",
    "DungeonRuin", "HomePoor", "Graveyard", "Coven", "HomeYourShips",
]

DUNGEON_TYPES = [
    "Crypt", "OrcStronghold", "HumanStronghold", "Prison", "DesecratedTemple",
    "Mine", "NaturalCave", "Coven", "VampireHaunt", "Laboratory", "HarpyNest",
    "RuinedCastle", "SpiderNest", "GiantStronghold", "DragonsDen",
    "BarbarianStronghold", "VolcanicCaves", "ScorpionNest", "Cemetery",
]
NO_DUNGEON = 255


def _bsa_records(path):
    with open(path, "rb") as f:
        data = f.read()
    count, dirtype = struct.unpack_from("<hH", data, 0)
    if dirtype != 0x0100:
        raise ValueError("MAPS.BSA should use a name-record directory")
    pos = 4
    dir_at = len(data) - 18 * count
    records = []
    for i in range(count):
        size = struct.unpack_from("<i", data, dir_at + i * 18 + 14)[0]
        records.append(data[pos:pos + size])
        pos += size
    return records


def read_locations(arena2):
    """Return a list of dicts, one per classic location."""
    records = _bsa_records(os.path.join(arena2, "MAPS.BSA"))
    out = []
    for region, rname in enumerate(REGION_NAMES):
        names = records[region * 4 + 3]
        table = records[region * 4 + 2]
        if not names or not table:
            continue
        n = struct.unpack_from("<I", names, 0)[0]
        for i in range(n):
            raw = names[4 + i * 32:4 + i * 32 + 32]
            name = raw.split(b"\0", 1)[0].decode("latin-1")
            o = i * 17
            map_id, bits, lat_raw, dtype, _key = struct.unpack_from("<iIiBI", table, o)
            lon = (bits & 0x1FFFFFF) >> 8
            ltype = ((4 * bits) & 0xFFFFFFFF) >> 27
            lat = (lat_raw & 0xFFFFFF) >> 8
            out.append({
                "region": region,
                "region_name": rname,
                "name": name,
                "map_id": map_id,
                "x": lon // 128,
                "y": 499 - lat // 128,
                "ltype": ltype,
                "ltype_name": LOCATION_TYPES[ltype] if ltype < len(LOCATION_TYPES) else str(ltype),
                "dtype": dtype,
                "dtype_name": DUNGEON_TYPES[dtype] if dtype < len(DUNGEON_TYPES) else None,
            })
    return out


def read_politic(arena2):
    """Return a function (x, y) -> region index, or -1 for water, per map pixel."""
    with open(os.path.join(arena2, "POLITIC.PAK"), "rb") as f:
        data = f.read()
    width, height = 1001, 500
    buf = bytearray(width * height)
    for row in range(height):
        off = struct.unpack_from("<I", data, row * 4)[0]
        p, col = off, 0
        while col < width:
            count, value = struct.unpack_from("<HB", data, p)
            p += 3
            buf[row * width + col:row * width + col + count] = bytes([value]) * count
            col += count

    def region_at(x, y):
        v = buf[y * width + x + 1]  # DFU adds 1 to x to line up with the height map
        if v == 64 or v < 128:
            return -1
        r = (v - 128) & 0x7F
        return r if r < len(REGION_NAMES) else -1

    return region_at
