"""Extract a Daggerfall Unity .dfmod (or the Nexus zip holding one) and decompile its assemblies.

Usage (keep the output folder outside the repo; the extracted bundle is reference material, not committed):
    python tools/expanded_inventory/extract.py <zip-or-dfmod> <out-dir> [--ilspy <ilspycmd.cmd>]

Writes every TextAsset (mod json, .cs sources, .dll.bytes assemblies) and every other asset name to
<out-dir>/assets, and decompiles each assembly into a C# project at <out-dir>/src/<name>.
Needs UnityPy (pip) and ilspycmd (dotnet tool), both outside the repo.
"""
import argparse
import os
import subprocess
import sys
import zipfile

import UnityPy


def find_dfmods(path, out):
    if path.lower().endswith(".zip"):
        found = []
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith(".dfmod"):
                    target = os.path.join(out, "bundle", os.path.basename(name))
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(name) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    found.append(target)
        return found
    return [path]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--ilspy", default=r"D:\dev\DoomDaggerfall-build\tools\ilspy\ilspycmd.cmd")
    a = ap.parse_args()

    assets_dir = os.path.join(a.out, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    dlls = []
    listing = []
    for dfmod in find_dfmods(a.source, a.out):
        env = UnityPy.load(dfmod)
        for obj in env.objects:
            kind = obj.type.name
            try:
                data = obj.read()
            except Exception as e:  # keep going; list what failed
                listing.append(f"{kind}\t<unreadable: {e}>")
                continue
            name = getattr(data, "m_Name", "") or getattr(data, "name", "") or f"path{obj.path_id}"
            listing.append(f"{kind}\t{name}")
            if kind != "TextAsset":
                continue
            raw = data.m_Script
            if isinstance(raw, str):
                raw = raw.encode("utf-8", "surrogateescape")
            target = os.path.join(assets_dir, os.path.basename(name))
            if raw[:2] == b"MZ":
                base = os.path.basename(name)
                if base.endswith(".bytes"):
                    base = base[: -len(".bytes")]
                target = os.path.join(assets_dir, base)
                if not target.lower().endswith(".dll"):
                    target += ".dll"
                dlls.append(target)
            with open(target, "wb") as f:
                f.write(raw)
    with open(os.path.join(a.out, "listing.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(listing)) + "\n")
    print(f"{len(listing)} objects, {len(dlls)} assemblies -> {a.out}")

    for dll in dlls:
        dest = os.path.join(a.out, "src", os.path.splitext(os.path.basename(dll))[0])
        os.makedirs(dest, exist_ok=True)
        r = subprocess.run([a.ilspy, "-p", "-o", dest, dll])
        print(f"decompile {os.path.basename(dll)}: exit {r.returncode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
