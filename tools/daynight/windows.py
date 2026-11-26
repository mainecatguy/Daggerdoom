"""Doom-only check of Daggerfall's window glow on a converted town (hw_dfmesh.cpp, CityExport.cs window masks).

usage: windows.py UZDOOM CONVERTER OUT [assets] [shots] [cost]

assets  writes OUT/data/ddruntime.pk3 with the window masks (dfwin/...), using CONVERTER (--runtime-assets).
shots   Gothway Garden at night and by day, each with and without Daggerfall's window line, through light_shots.py
        (quiet_run, private config). Window colours are MaterialReader's: night 255,182,56 x 0.8, day 89,154,178 x 0.5.
stage   copies this worktree's Daggerfall Unity build to OUT/dfu (paired.py stage).
paired  both games through the launcher, Daggerfall at noon then 22:00 (paired.py run, with --draw), Gothway Garden.
cost    the night views twice with and twice without windows, for frame times.
Game-derived output stays in OUT.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = Path(r"D:\dev\DoomDaggerfall\GameResources")
OVERWORLD = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items\data\overworld.pk3")
VIEWS = "street -4622 -13250 10006 90 -3\nsky -4622 -13250 10006 90 -30\nwide -3412 -13900 10006 0 -8\n"
NIGHT, DAY = "sky 19 0 1 1 20 0 0 0 -60", "sky 19 32 0 0 91 0 0 62 90"
WIN_NIGHT, WIN_DAY = "windows 204 146 45", "windows 45 77 89"


def shots(exe, converter, out, name, sky, windows, measure="1"):
    views = out / "views.txt"
    views.write_text(VIEWS)
    args = [sys.executable, str(HERE.parent / "lights" / "light_shots.py"), "--exe", exe, "--out", str(out / name), "--map", "DDT07154",
            "--views", str(views), "--measure", measure, "--files", str(out / "data" / "ddruntime.pk3"), str(OVERWORLD),
            "--cache", str(out / "cache"), "--converter", converter, "--doom-args", "+dd_sky", sky]
    if windows:
        args += ["+dfmesh_windows", windows]
    print("==", name, flush=True)
    subprocess.call(args, stdin=subprocess.DEVNULL)


def sheet(runs, name, hold):
    """<name>-sheet.png: one row per Daggerfall step, Daggerfall's camera on the left, Doom's screenshot on the right."""
    # Doom's shot for a step is its last one at least a second before Daggerfall's: Daggerfall saves its camera in
    # the same frame it starts the next step, and a Doom shot in that second can already show the next step.
    from PIL import Image
    doom = sorted((runs / f"{name}-shots").glob("*.png"), key=lambda p: p.stat().st_mtime)
    pairs = []
    for shot in sorted((runs / f"{name}-dfshots").glob("step*.png"), key=lambda p: int(p.stem[4:])):
        near = [p for p in doom if shot.stat().st_mtime - hold < p.stat().st_mtime <= shot.stat().st_mtime - 1]
        if near:
            pairs.append((shot, near[-1]))
            print(shot.name, "<->", near[-1].name)
    w, h = 640, 360
    out = Image.new("RGB", (w * 2, h * max(len(pairs), 1)))
    for i, (df, dm) in enumerate(pairs):
        out.paste(Image.open(df).convert("RGB").resize((w, h)), (0, i * h))
        out.paste(Image.open(dm).convert("RGB").resize((w, h)), (w, i * h))
    out.save(runs / f"{name}-sheet.png")
    print("sheet:", runs / f"{name}-sheet.png")


def main():
    exe, converter, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    steps = sys.argv[4:] or ["assets", "shots"]
    (out / "data").mkdir(parents=True, exist_ok=True)
    if "assets" in steps:
        subprocess.check_call([converter, "--runtime-assets", "--out", str(out / "data" / "ddruntime.pk3"), "--arena2", str(GAME / "DAGGER" / "ARENA2")],
                              stdin=subprocess.DEVNULL)
    if "shots" in steps:
        shots(exe, converter, out, "night-windows", NIGHT, WIN_NIGHT)
        shots(exe, converter, out, "night-plain", NIGHT, None)
        shots(exe, converter, out, "day-windows", DAY, WIN_DAY)
        shots(exe, converter, out, "day-plain", DAY, None)
    if "stage" in steps or "paired" in steps:
        import paired
        paired.REVIEW, paired.UZDOOM_BUILD = out, Path(exe).parents[1].name
        paired.RUNTIME, paired.CACHE, paired.CONVERTER = out / "data" / "ddruntime.pk3", out / "cache", Path(converter)
        if "stage" in steps:
            paired.stage()
        if "paired" in steps:
            # Noon then 22:00, clear: Daggerfall's camera is saved at the end of each step next to Doom's screenshots.
            # Doom stands at the "wide" view (two houses) with light_shots' harness from the shots step; Daggerfall's camera
            # follows Doom's player, so both look at the same windows.
            harness = out / "night-windows" / "lt_harness.pk3"
            (out / "run").mkdir(parents=True, exist_ok=True)
            (out / "run" / "windows-view.cfg").write_text("".join("wait 35; netevent lt_view 2; " for _ in range(40)) + "\n")
            paired.run("windows", "12:0 22:0", 8, 1, True, ["-file", str(harness), "+exec", "windows-view.cfg"])
            sheet(out / "run", "windows", 8)
    if "cost" in steps:
        for p in "12":
            shots(exe, converter, out, f"cost-win{p}", NIGHT, WIN_NIGHT, "3")
            shots(exe, converter, out, f"cost-plain{p}", NIGHT, None, "3")


if __name__ == "__main__":
    main()
