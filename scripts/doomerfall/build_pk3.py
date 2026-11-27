"""Build doomerfall.pk3 from mods/doomerfall/src. Usage: build_pk3.py [--smoke | --drla] [out.pk3]
(--smoke builds the test-only trigger pk3; --drla builds doomerfall-drla.pk3, the part loaded only with DRLA)
The main pk3 also gets the Skyrim UI menus generated from mods/doomerfall/skyrimui (see its README.md)."""
import sys, zipfile, pathlib
folder = "smoke-src" if "--smoke" in sys.argv else "drla-src" if "--drla" in sys.argv else "src"
repo = pathlib.Path(__file__).resolve().parents[2]
src = repo / "mods" / "doomerfall" / folder
sys.argv = [x for x in sys.argv if x not in ("--smoke", "--drla")]
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "doomerfall.pk3")
out.parent.mkdir(parents=True, exist_ok=True)
generated = {}
if folder == "src":
    sys.path.insert(0, str(repo / "tools" / "skyrim_ui"))
    import convert
    generated = convert.convert_all(str(repo / "mods" / "doomerfall" / "skyrimui"))
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(src).as_posix())
    for name, data in sorted(generated.items()):
        z.writestr(name, data)
print("wrote", out)
