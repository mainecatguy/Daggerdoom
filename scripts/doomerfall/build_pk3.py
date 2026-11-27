"""Build doomerfall.pk3 from mods/doomerfall/src. Usage: build_pk3.py [--smoke | --drla] [out.pk3]
(--smoke builds the test-only trigger pk3; --drla builds doomerfall-drla.pk3, the part loaded only with DRLA)"""
import sys, zipfile, pathlib
folder = "smoke-src" if "--smoke" in sys.argv else "drla-src" if "--drla" in sys.argv else "src"
src = pathlib.Path(__file__).resolve().parents[2] / "mods" / "doomerfall" / folder
sys.argv = [x for x in sys.argv if x not in ("--smoke", "--drla")]
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "doomerfall.pk3")
out.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(src).as_posix())
print("wrote", out)
