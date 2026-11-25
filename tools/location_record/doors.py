"""Door route (doors.zs) in paired.py's folder: hinged doors keep their position (location record card 5).

usage: doors.py first NAME | load NAME | stamp NAME | report NAME

first: DRLA set, Privateer's Hold at area level 1: open doors, a lever-driven door, one door caught moving, leave, come
       back, pull the lever again, leave and save outside. The save is kept as doors_first.zds.
load:  loads that save in a new launch, enters, prints the doors.
stamp: the same with the door record's stamp changed by hand in the save's DoomerfallLocations.json: the doors reset.
The route needs about 1.5 minutes, so its limit is 120 s rather than the usual 30 s; it ends at once when it finishes or
a fatal error is logged.
"""
import inspect
import re
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402

l2 = paired.ledger2
md, base, REVIEW = l2.md, l2.base, paired.REVIEW
SAVES, KEPT = REVIEW / "run" / "saves", REVIEW / "run" / "doors_first.zds"

_source = inspect.getsource(md.run).replace("timeout = 75", "timeout = 120")
assert "timeout = 120" in _source
exec(compile(_source, md.__file__, "exec"), md.__dict__)
md.EXTRA_DF = ["-dfarealevel", "1"]


def route(mode):
    folder = REVIEW / "route_doors"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "harness.zs").write_text((HERE / "doors.zs").read_text().replace("@ROUTE@", mode))
    md.HERE = folder


def stage(change_stamp):
    """The kept save as the newest one, so md.run loads it; for the stamp route its door record's stamp is changed."""
    resume = SAVES / "resume.zds"
    if not change_stamp:
        shutil.copyfile(KEPT, resume)
        return
    with zipfile.ZipFile(KEPT) as src, zipfile.ZipFile(resume, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename.endswith("DoomerfallLocations.json"):
                text, count = re.subn(r'"([0-9a-f]{8}) ([0-9a-f]+)"', lambda m: f'"{int(m.group(1), 16) ^ 0x10:08x} {m.group(2)}"', data.decode())
                print("stamp changed in", count, "door record(s)")
                data = text.encode()
            dst.writestr(info, data)


def report(name):
    for line in l2.log(name).splitlines():
        if line.startswith(("DRSIG", "DRLEVER", "MDDONE", "MDFAIL", "DFDOORS", "DFACTIONS")) or "DDLOC" in line and "door" in line:
            print(" ", line[:300])
    print("  script errors", l2.log(name).count("Script error"))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in ("first", "load", "stamp"):
        route(command)
        if command != "first":
            stage(command == "stamp")
        md.run(sys.argv[2], command != "first", drla=True)
        if command == "first":
            newest = max(SAVES.glob("auto*.zds"), key=lambda p: p.stat().st_mtime, default=None)
            if newest:
                shutil.copy2(newest, KEPT)
                print("kept", newest.name, "as", KEPT.name)
        report(sys.argv[2])
    elif command == "report":
        report(sys.argv[2])
    else:
        sys.exit(__doc__)
