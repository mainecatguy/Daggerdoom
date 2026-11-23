"""Exports mesh/door/action packages for each dungeon id and smoke-loads it (see smoke_load.py).

Usage: python smoke_all.py <out dir> <seconds> "#id" ...
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
out, seconds = sys.argv[1], sys.argv[2]
for name in sys.argv[3:]:
    slug = "".join(c for c in name if c.isalnum()).lower()
    folder = os.path.join(out, slug)
    r = subprocess.run(["dotnet", "run", "-c", "Release", "-v", "q", "--no-build", "--project", os.path.join(HERE, "DungeonConverter.csproj"),
                        "--", name, "--out", folder, "--export-mesh"], capture_output=True, text=True, errors="replace")
    tail = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(("doors:", "actions:", "mesh:")) or "xception" in l]
    print(f"== {name}: export exit {r.returncode}; " + " | ".join(l[:110] for l in tail[:4]))
    if r.returncode:
        continue
    s = subprocess.run([sys.executable, os.path.join(HERE, "smoke_load.py"), folder, slug, "--seconds", seconds], capture_output=True, text=True, errors="replace")
    print(s.stdout.strip() or s.stderr.strip()[-300:])
    sys.stdout.flush()
