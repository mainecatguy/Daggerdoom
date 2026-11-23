"""Screenshot a converted dungeon's deepest water from above and below.

Usage: python water_shot.py <dir with slug.wad, slug_mesh.pk3, slug_doors.pk3, slug_waterprobe> <slug> <output dir>
The window runs off-screen and never takes focus, because a minimized UZDoom renders only 320x200.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UZDOOM = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
WIDTH, HEIGHT, OFFSCREEN = 1280, 720, -32000
SW_SHOWNOACTIVATE = 4
VIEWS = ["above", "under", "under_up"]

folder, slug, out = os.path.abspath(sys.argv[1]), sys.argv[2], os.path.abspath(sys.argv[3])
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "shot.cfg"), "w", newline="\n") as f:
    for i, name in enumerate(VIEWS):
        shot = os.path.join(out, name + ".png").replace("\\", "/")
        f.write(f'alias dfstep{i} "netevent dfwatershot {i}; wait 12; screenshot \\"{shot}\\"; wait 6; dfstep{i + 1}"\n')
    f.write(f'alias dfstep{len(VIEWS)} "quit"\nalias dfgo "vid_setsize {WIDTH} {HEIGHT}; wait 35; dfstep0"\nwait 105; dfgo\n')
with open(os.path.join(out, "shot.ini"), "w", newline="\n") as f:
    f.write(f"[GlobalSettings]\nqueryiwad=false\nvid_fullscreen=false\nwin_maximized=false\nvid_defwidth={WIDTH}\n"
            f"vid_defheight={HEIGHT}\nwin_w={WIDTH}\nwin_h={HEIGHT}\nvid_scalefactor=1\nwin_x={OFFSCREEN}\nwin_y={OFFSCREEN}\n")
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = SW_SHOWNOACTIVATE
files = [os.path.join(folder, slug + suffix) for suffix in (".wad", "_mesh.pk3", "_doors.pk3", "_waterprobe")]
process = subprocess.Popen([UZDOOM, "-iwad", IWAD, "-file", *files, os.path.join(HERE, "water_view"), os.path.join(HERE, "water_shot"),
                            "-config", os.path.join(out, "shot.ini"), "-noactivate", "-nosound", "-nomonsters", "-skill", "3",
                            "-width", str(WIDTH), "-height", str(HEIGHT), "+vid_fullscreen", "0", "+vid_scalefactor", "1",
                            "+screenblocks", "12", "+crosshair", "0", "+screenshot_type", "png", "+show_messages", "0",
                            "+i_pauseinbackground", "0", "+vid_activeinbackground", "1", "+vid_lowerinbackground", "0",
                            "+logfile", "watershot", "+map", "MAP01", "+exec", "shot.cfg"], cwd=out, startupinfo=startup)
try:
    code = process.wait(30)
except subprocess.TimeoutExpired:
    process.kill()
    process.wait()
    code = "timed out"
print("UZDoom exit:", code, "| shots:", [n for n in VIEWS if os.path.exists(os.path.join(out, n + ".png"))])
