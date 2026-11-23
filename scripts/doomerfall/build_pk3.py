"""Build doomerfall.pk3 from mods/doomerfall/src. Usage: build_pk3.py [--smoke] [out.pk3]  (--smoke builds the test-only trigger pk3)"""
import sys, zipfile, pathlib
src = pathlib.Path(__file__).resolve().parents[2] / "mods" / "doomerfall" / ("smoke-src" if "--smoke" in sys.argv else "src")
sys.argv = [x for x in sys.argv if x != "--smoke"]
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "doomerfall.pk3")
out.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(src).as_posix())
print("wrote", out)
