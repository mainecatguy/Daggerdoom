"""Paired test for location state card 2: Daggerfall's location ledger, dungeons first.

usage: ledger2.py build | assemble | run NAME [--load] [--notable] | report NAME [FIRST]

Route (ledger2.zs) in Privateer's Hold at area level 30 (-dfarealevel 30), stock monsters: kill most of the pack, wound
one monster and let it chase the player, take, move and drop items, leave, return, leave again and save outside.
A --load run loads that save, enters, and prints the place. --notable adds UZDoom's -ddlocnotable test hook, which
loads the save as if it had no world table, so the dungeon can only come back from Daggerfall's ledger.
`report NAME FIRST` compares a load run's place with the first run's place at leaving. Game data stays outside the repo.
"""
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import location_ledger as ll  # noqa: E402

ef, md, base, pickup = ll.ef, ll.md, ll.base, ll.pickup
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger2")
ef.REVIEW = md.REVIEW = pickup.REVIEW = base.REVIEW = REVIEW
base.BUILD, base.RUN = REVIEW / "build", REVIEW / "run"
OLD_WAD = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger\wad\ids_privateershold.wad")
md.EXTRA_DF = ["-dfarealevel", "30"]
EXTRA_UZ = []

_popen = subprocess.Popen


def _popen_with_args(command, *args, **kwargs):
    """md.run builds the launcher command itself; this adds UZDoom arguments to it."""
    if isinstance(command, list) and "--uzdoom" in command:
        for arg in EXTRA_UZ:
            command += ["--uzdoom-arg", arg]
    return _popen(command, *args, **kwargs)


subprocess.Popen = _popen_with_args


def route(mode):
    folder = REVIEW / "route"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "harness.zs").write_text((HERE / "ledger2.zs").read_text().replace("@ROUTE@", mode))
    md.HERE = folder


def log(name):
    return base.read(REVIEW / "run" / f"log-{name}.txt")


def signature(name, when):
    rows = [l.split(" ", 2)[2] for l in log(name).splitlines() if l.startswith(f"LLSIG {when} ")]
    head = next((r for r in rows if r.startswith("begin")), "missing")
    return head, [r for r in rows if not r.startswith(("begin", "end"))]


def parse(row):
    state, cls, spot, _, hp, *rest = row.split(" ")
    return (state, cls, hp, bool(rest)), tuple(int(v) for v in spot.split(","))


def compare(a, b, label):
    """Row by row as multisets. A row that differs must match one on the other side with the same kind, class, health
    and drop flag, within one 8-unit cell across, and at the same or a lower height: Doom's physics may settle it by a
    unit or let it fall (a corpse that rested on a living monster comes back before the pack is rebuilt under it)."""
    (ha, ra), (hb, rb) = a, b
    print(f"{label}: {ha} | {hb} | identical {ra == rb}")
    ca, cb = Counter(ra), Counter(rb)
    only_a = [parse(r) for r in (ca - cb).elements()]
    only_b = [parse(r) for r in (cb - ca).elements()]
    unmatched, fell = [], 0
    for key, (x, y, z) in only_a:
        hit = next((i for i, (k2, (x2, y2, z2)) in enumerate(only_b) if k2 == key and abs(x - x2) <= 1 and abs(y - y2) <= 1 and z2 <= z + 1), None)
        if hit is None:
            unmatched.append(("first ", key, (x, y, z)))
        else:
            fell += only_b[hit][1][2] < z - 4
            only_b.pop(hit)
    unmatched += [("second", key, spot) for key, spot in only_b]
    print(f"   rows that differ: {len(only_a)}; matched by settling or falling: {len(only_a) - len(unmatched)} ({fell} fell more than 32 units); unmatched: {len(unmatched)}")
    for side, key, spot in unmatched[:15]:
        print("   unmatched in", side, key, spot)


def report(name, first=None):
    if first:
        compare(signature(first, "leave"), signature(name, "loaded"), f"{first} leave vs {name} loaded")
    else:
        compare(signature(name, "leave"), signature(name, "reentry"), f"{name} leave vs reentry")
    for line in log(name).splitlines():
        if line.startswith(("DDLOC", "DDTM saved", "DDTM left", "DDTM place", "DDENC spawned", "LL", "MD")) and not line.startswith("LLSIG"):
            print(" ", line[:220])
    for line in base.read(REVIEW / "run" / f"{name}-df.log").splitlines():
        if "locations:" in line or ("save" in line and "ms" in line):
            print("  df", line[:220])
    for save in sorted((REVIEW / "run" / "saves").glob("*.zds")):
        print(f"  save {save.name} {save.stat().st_size} bytes")
        try:
            with zipfile.ZipFile(save) as z:
                for info in z.infolist():
                    if "Doomerfall" in info.filename or info.filename.endswith((".json", ".txt")):
                        print(f"    {info.filename} {info.file_size} bytes ({info.compress_size} packed)")
        except zipfile.BadZipFile:
            print("    (not a zip)")


def assemble():
    (REVIEW / "wad").mkdir(parents=True, exist_ok=True)
    shutil.copy2(OLD_WAD, REVIEW / "wad" / ("ids_" + md.WAD))  # md.assemble copies it into the data folder
    print("wad from", OLD_WAD)
    ll.assemble()


def keep_first_save():
    """The first run's last save, kept under its own name, so every load run starts from it."""
    saves = REVIEW / "run" / "saves"
    newest = max(saves.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
    if newest:
        shutil.copy2(newest, REVIEW / "run" / "first.zds")
        print("kept", newest.name, "as first.zds")


def stage_first_save():
    saves = REVIEW / "run" / "saves"
    resume = saves / "resume.zds"
    shutil.copyfile(REVIEW / "run" / "first.zds", resume)  # copyfile: a fresh mtime, so md.run picks it


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        ef.build()
    elif command == "assemble":
        assemble()
    elif command == "run":
        if "--notable" in sys.argv:
            EXTRA_UZ.append("-ddlocnotable")
        load = "--load" in sys.argv
        route("load" if load else "first")
        if load:
            stage_first_save()
        md.run(sys.argv[2], load)
        if not load:
            keep_first_save()
        report(sys.argv[2])
    elif command == "report":
        report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        sys.exit(__doc__)
