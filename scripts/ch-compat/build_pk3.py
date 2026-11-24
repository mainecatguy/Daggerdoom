"""Build ch-compat.pk3, the Colourful Hell 1.04 + DRLA compatibility patch.

Usage: build_pk3.py [--ch PATH_TO_ColourfulHell_1_04.pk3] [out.pk3]
Default output: D:\\dev\\DoomDaggerfall-build\\ch-compat.pk3 (outside the repo).

The repo holds only our own text (mods/ch-compat/src). Fixing Colourful Hell's sprite
name clashes needs renamed copies of its sprites and of the DECORATE files that use
them. Those are generated here from the local Colourful Hell PK3 and written only into
the output PK3, never into the repo. See mods/ch-compat/src/README.md.
"""
import pathlib, re, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "mods" / "ch-compat" / "src"

# Colourful Hell sprite prefix -> new prefix. Each old prefix is also used by DRLA for
# different art, and DRLA (loaded after Colourful Hell) wins every shared frame.
RENAMES = {
    "AMIN": "XCAM",  # Abyss Mastermind vs DRLA Arsenal assault minigun pickup
    "TSHO": "XCTS",  # Cyberdemon projectile vs DRLA Arsenal tactical shotgun HUD frames
    "SMK2": "XCSK",  # small smoke vs DRLA's large smoke
    "CIMP": "XCCI",  # Cyan Imp vs DRLA Monsters cybernetic imp
    "CACO": "XCCA",  # cacodemon gib frames vs DRLA Monsters / DRLAX cacodemon walk frames
    "HMZP": "XCHZ",  # zombie vs DRLAX Sweeper player class
    "GIB1": "XCG1",  # Nash gore gibs vs DRLA Monsters' smaller gibs
    "GIB2": "XCG2",
    "GIB4": "XCG4",
    "GIB5": "XCG5",
}
# A state line: optional indent, sprite, frame letters, then a duration.
STATE = re.compile(r"(?im)^([ \t]*)(%s)(?=[ \t]+[A-Z\[\]\\^#]+[ \t]+(?:-?\d|random))" % "|".join(RENAMES))

args = sys.argv[1:]
ch = ROOT / "GameMods" / "ColourfulHell_1_04.pk3"
if "--ch" in args:
    i = args.index("--ch"); ch = pathlib.Path(args[i + 1]); del args[i:i + 2]
out = pathlib.Path(args[0]) if args else ROOT.parent / "DoomDaggerfall-build" / "ch-compat.pk3"

def short(name):
    return name.rsplit("/", 1)[-1].split(".")[0][:8].upper()

src_zip = zipfile.ZipFile(ch)
names = [n for n in src_zip.namelist() if not n.endswith("/")]
if "DECORATE" not in names or "decorate/Imps" not in names:
    sys.exit(f"{ch} does not look like Colourful Hell 1.04")

# New prefixes must be unused by every mod next to Colourful Hell.
for pk3 in ch.parent.glob("*.pk3"):
    used = {short(n)[:4] for n in zipfile.ZipFile(pk3).namelist() if n.lower().startswith("sprites/")}
    taken = used & set(RENAMES.values())
    if taken:
        sys.exit(f"new sprite prefixes {sorted(taken)} already used in {pk3.name}")

out.parent.mkdir(parents=True, exist_ok=True)
counts = dict.fromkeys(RENAMES, 0)
sprites = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and p.suffix.lower() != ".md":
            z.write(p, p.relative_to(SRC).as_posix())
    for n in names:
        base = n.rsplit("/", 1)[-1]
        if n.lower().startswith("sprites/") and base[:4].upper() in RENAMES:
            z.writestr("sprites/chcompat/" + RENAMES[base[:4].upper()] + base[4:], src_zip.read(n))
            sprites += 1
        elif "/" not in n or n.lower().startswith("decorate/"):
            if n.upper() in ("CREDITS", "SNDINFO", "CVARINFO", "MENUDEF", "TRNSLATE", "LOADACS"):
                continue
            text = src_zip.read(n).decode("latin-1")
            def swap(m):
                counts[m.group(2).upper()] += 1
                return m.group(1) + RENAMES[m.group(2).upper()]
            new = STATE.sub(swap, text)
            if new != text:
                if n == "DECORATE":
                    sys.exit("root DECORATE would need rewriting; overriding it would define every actor twice")
                # Same full path as Colourful Hell's file, so its #include picks this copy.
                z.writestr(n, new.encode("latin-1"))
                print("  rewrote", n)
missing = [k for k, v in counts.items() if not v]
if missing:
    sys.exit(f"no state lines found for {missing}; Colourful Hell version changed?")
print("  sprite lumps copied:", sprites, "| state lines renamed:", counts)
print("wrote", out)
