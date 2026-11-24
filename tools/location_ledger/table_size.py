"""Prints the size and rows of the world table (ddoverworld), place list (ddspaces) and plans (ddplans) in .zds saves.

usage: table_size.py SAVE.zds [...]
"""
import json
import sys
import zipfile


def find(node, key):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                return v
            found = find(v, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = find(v, key)
            if found is not None:
                return found
    return None


for path in sys.argv[1:]:
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            data = json.loads(z.read(name))
            for key in ("ddoverworld", "ddspaces", "ddplans"):
                text = find(data, key)
                if isinstance(text, str):
                    rows = text.splitlines()
                    print(f"{path} [{name}] {key}: {len(text)} bytes, {len(rows)} lines")
                    for row in rows[:12]:
                        print("    ", row[:160])
