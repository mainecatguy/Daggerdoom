"""Test helper: refresh the door classes inside an installed ddruntime.pk3 from tools/dungeon_converter/door_objects.zs.

The converter copies door_objects.zs verbatim into the runtime package's zscript.zs, so a door script change otherwise
needs a full data rebuild. Replaces each class of door_objects.zs found in the package by its current text.

    python tools/lockpick/patch_runtime_doors.py <install folder>
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "dungeon_converter" / "door_objects.zs"


def classes(text):
    """name -> (start, end) of each top-level class, by brace matching."""
    out = {}
    for m in re.finditer(r"^class (\w+)[^\n]*\n\{", text, re.M):
        depth, i = 0, m.end() - 1
        while True:
            c = text[i]
            depth += c == "{"
            depth -= c == "}"
            i += 1
            if depth == 0:
                break
        out[m.group(1)] = (m.start(), i)
    return out


def main():
    pk3 = Path(sys.argv[1]) / "data" / "ddruntime.pk3"
    new = SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    with zipfile.ZipFile(pk3) as z:
        items = [(info, z.read(info.filename)) for info in z.infolist()]
    done = 0
    for n, (info, data) in enumerate(items):
        if info.filename.lower() != "zscript.zs":
            continue
        text = data.decode("utf-8").replace("\r\n", "\n")
        want = classes(new)
        for name, (s, e) in sorted(classes(text).items(), key=lambda kv: -kv[1][0]):
            if name in want:
                a, b = want[name]
                text = text[:s] + new[a:b] + text[e:]
                done += 1
        items[n] = (info, text.encode("utf-8"))
    tmp = pk3.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in items:
            z.writestr(info, data)
    shutil.move(tmp, pk3)
    print(f"replaced {done} door classes in {pk3}")


if __name__ == "__main__":
    main()
