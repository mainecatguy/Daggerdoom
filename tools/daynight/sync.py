"""Combined check of fog, foggy sky, lit windows and winter together (both day/night follow-up branches merged).

usage: sync.py UZDOOM CONVERTER OUT [assets] [shots] [cost] [stage] [town [lowres]] [interior]

assets    OUT/data/ddruntime.pk3 with the window masks (CONVERTER --runtime-assets).
shots     Doom only, Gothway Garden in winter (converter --winter through the town cache), hand-fed lines:
          winter-noon-clear, winter-night-clear, winter-night-heavyfog, each with Daggerfall's window colour.
cost      frame times: winter night with heavy fog and windows, against the same night without fog or windows, twice.
stage     this worktree's Daggerfall Unity build to OUT/dfu (paired.py stage).
town      paired, Daggerfall steps noon clear, noon heavy fog, 22:00 clear, 22:00 heavy fog, all in Morning Star
          (winter), with Daggerfall's camera saved each step; side-by-side sheet run/town-sheet.png.
interior  paired, Doom walks into the tavern (dd_tm_use hook), Daggerfall follows; noon then 22:00 inside;
          sheet run/interior-sheet.png.
Game-derived output stays in OUT.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import interior  # noqa: E402  (tavern door and its walk-in harness)
import windows  # noqa: E402  (views, light_shots wrapper, sheet)

GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
# Daggerfall's own values (notes 20261125-202716 and 20261126-114057), as the bridge sends them; 10th sky field 1 = winter.
NOON, NIGHT = "sky 19 32 0 0 91 0 0 62 90 1", "sky 19 0 1 1 20 0 0 0 -60 1"
FOG_CLEAR_NOON, FOG_CLEAR_NIGHT = "fog 1 2 0.0005 0 0 168 176 198 0", "fog 1 2 0.0005 0 0 20 20 20 0"
FOG_HEAVY = "fog 1 2 0.05 0 0 128 128 128 1"
WIN_NIGHT, WIN_DAY = windows.WIN_NIGHT, windows.WIN_DAY
# The minimized paired window renders at 320x200; a fixed scene size keeps windows and fog readable in the screenshots.
SCALE = ["+vid_scalemode", "5", "+vid_scale_customwidth", "960", "+vid_scale_customheight", "540"]


def doom_shots(exe, converter, out):
    for name, lines, win in (("winter-noon-clear", [NOON, FOG_CLEAR_NOON], WIN_DAY),
                             ("winter-night-clear", [NIGHT, FOG_CLEAR_NIGHT], WIN_NIGHT),
                             ("winter-night-heavyfog", [NIGHT, FOG_HEAVY], WIN_NIGHT),
                             ("winter-night-heavyfog-nowin", [NIGHT, FOG_HEAVY], None)):
        views = out / "views.txt"
        views.write_text(windows.VIEWS)
        args = [sys.executable, str(HERE.parent / "lights" / "light_shots.py"), "--exe", exe, "--out", str(out / name), "--map", "DDT07154",
                "--views", str(views), "--measure", "1", "--files", str(out / "data" / "ddruntime.pk3"), str(windows.OVERWORLD),
                "--cache", str(out / "cache"), "--converter", converter, "--timeout", "60", "--doom-args"]
        for line in lines:
            args += ["+dd_sky", line]
        if win:
            args += ["+dfmesh_windows", win]
        print("==", name, flush=True)
        subprocess.call(args, stdin=subprocess.DEVNULL)


def cost(exe, converter, out):
    """Frame times, two alternating passes: winter night with heavy fog, fogged sky and windows, against the same night
    with no fog line and no windows (winter is free per frame: it is baked into the place's package)."""
    views = out / "views.txt"
    views.write_text(windows.VIEWS)
    for p in "12":
        for name, extra in ((f"cost-all{p}", ["+dd_sky", FOG_HEAVY, "+dfmesh_windows", WIN_NIGHT]), (f"cost-none{p}", [])):
            print("==", name, flush=True)
            subprocess.call([sys.executable, str(HERE.parent / "lights" / "light_shots.py"), "--exe", exe, "--out", str(out / name), "--map", "DDT07154",
                             "--views", str(views), "--measure", "3", "--files", str(out / "data" / "ddruntime.pk3"), str(windows.OVERWORLD),
                             "--cache", str(out / "cache"), "--converter", converter, "--doom-args", "+dd_sky", NIGHT] + extra, stdin=subprocess.DEVNULL)


def setup_paired(exe, converter, out):
    import paired
    paired.REVIEW, paired.UZDOOM_BUILD = out, Path(exe).parents[1].name
    paired.RUNTIME, paired.CACHE, paired.CONVERTER = out / "data" / "ddruntime.pk3", out / "cache", Path(converter)
    (out / "run").mkdir(parents=True, exist_ok=True)
    if hasattr(paired.run, "done"):
        del paired.run.done  # paired.run marks itself finished; a second run in this process starts fresh
    return paired


def interior_harness(out):
    import zipfile
    x, y, z, nx, ny = interior.DOOR
    path = out / "run" / "dn_interior.pk3"
    code = interior.HARNESS.replace("@X@", str(x)).replace("@Y@", str(y)).replace("@Z@", str(z)).replace("@NX@", str(nx)).replace("@NY@", str(ny))
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("zscript.txt", code)
        zf.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "DNInterior" }\n')
    return path


def main():
    exe, converter, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    steps = sys.argv[4:] or ["assets", "shots"]
    (out / "data").mkdir(parents=True, exist_ok=True)
    if "assets" in steps:
        subprocess.check_call([converter, "--runtime-assets", "--out", str(out / "data" / "ddruntime.pk3"), "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                              stdin=subprocess.DEVNULL)
    if "shots" in steps:
        doom_shots(exe, converter, out)
    if "cost" in steps:
        cost(exe, converter, out)
    if "stage" in steps:
        setup_paired(exe, converter, out).stage()
    if "town" in steps:
        paired = setup_paired(exe, converter, out)
        # Doom stands at the "wide" view (two houses) with light_shots' harness; Daggerfall's camera follows Doom's player.
        # The winter hint makes the first place convert as winter (it loads before Daggerfall's first line; known gap).
        harness = out / "winter-night-clear" / "lt_harness.pk3"
        (out / "run" / "town-view.cfg").write_text("".join("wait 35; netevent lt_view 2; " for _ in range(60)) + "\n")
        name = "town-lowres" if "lowres" in steps else "town"
        paired.run(name, "12:0:0 12:3:0 22:0:0 22:3:0", 8, 1, True, ["-file", str(harness), "+exec", "town-view.cfg", "+dd_sky", NOON]
                   + ([] if "lowres" in steps else SCALE))
        windows.sheet(out / "run", name, 8)
    if "interior" in steps:
        paired = setup_paired(exe, converter, out)
        paired.run("interior", "12:0:0 12:0:0 22:0:0", 8, 1, True, ["-file", str(interior_harness(out)), "+dd_sky", NOON] + SCALE)
        windows.sheet(out / "run", "interior", 8)


if __name__ == "__main__":
    main()
