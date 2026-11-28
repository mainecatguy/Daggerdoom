"""Adds the outdoor swimming demo to a play folder made by scripts/play/install.py: play.bat starts a paired
overworld session (Daggerfall's sync test character, DDOVER01, DRLA) and puts the player in the sea about 14,000 units
west of the start, using swim_probe.zs in demo mode (it only moves the player there, then lets go).
The real game (play-full.bat, New Game; the install's play.bat, renamed) has the same swimming; Privateer's Hold is on an island, so the sea is near its door.
usage: make_demo.py <play folder>"""
import os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r"D:\dev\DoomDaggerfall\GameResources"
MODS = r"D:\dev\DoomDaggerfall\GameMods"

NOTES = """rem Doomerfall outdoor swimming demo. You start in the overworld and are moved into the sea after a few seconds.
rem Try: walk towards the shore and back. In the water the view drops to the water line, you move at 25%% + Swimming/2 %%
rem of your speed, and Jump does nothing. On land the view comes back. You never run out of breath outdoors (as in Daggerfall).
rem The full game is play-full.bat (New Game): Privateer's Hold is on an island, so the sea is a short walk from its door.
rem This demo uses Daggerfall's test character without a running Daggerfall game, so its per-minute rules (Swimming
rem practice, swimming fatigue) only run in play-full.bat.
"""


def main():
    play = os.path.abspath(sys.argv[1])
    text = open(os.path.join(HERE, "swim_probe.zs")).read().replace("@WATER_DX@", "-13749.0").replace("@WATER_DY@", "4537.0") \
        .replace("@STAY_TICS@", "0").replace("@DEMO@", "1")
    with zipfile.ZipFile(os.path.join(play, "swimdemo.pk3"), "w") as z:
        z.writestr("zscript/probe.zs", text)
        z.writestr("ZSCRIPT.txt", 'version "4.14"\n#include "zscript/probe.zs"\n')
        z.writestr("MAPINFO.txt", 'gameinfo { AddEventHandlers = "DoomerfallSwimTest" }\n')
    mods = [os.path.join(MODS, m) for m in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]
    mods += ["%DATA%\\" + m for m in ("ddruntime.pk3", "overworld.pk3", "privateershold.wad", "privateershold_mesh.pk3", "privateershold_doors.pk3")]
    mods += ["%HERE%dfitems.pk3", "%HERE%doomerfall.pk3", "%HERE%doomerfall-drla.pk3", "%HERE%swimdemo.pk3"]
    uz = ["-config", "%HERE%water\\uzdoom.ini", "-savedir", "%HERE%water\\saves", "-dfbridgelog", "%HERE%water\\uz.log",
          "-ddtowncache", "%DATA%\\cache", "-ddconverter", "%DATA%\\converter\\DungeonConverter.exe", "-ddarena2", GAME + "\\DAGGER\\ARENA2",
          "-skill", "3", "+map", "DDOVER01", "+vid_fullscreen", "0", "+i_pauseinbackground", "0"]
    df = ["-dfbridgelog", "%HERE%water\\df.log", "-dfsynctest", GAME + "\\DAGGER", "-dfswimtest", "-screen-fullscreen", "0", "-screen-width", "1280",
          "-screen-height", "800"]
    args = ["--nodraw", "--uzdoom", "%HERE%uzdoom\\uzdoom.exe", "--dfu", "%HERE%dfu\\DaggerfallUnity.exe", "--iwad", GAME + "\\wads\\DOOM2.WAD"]
    for m in mods:
        args += ["--mod", m]
    args += ["--uzdoom-cwd", "%HERE%water", "--log", "%HERE%water\\launcher.log"]
    for x in uz:
        args += ["--uzdoom-arg", x]
    for x in df:
        args += ["--dfu-arg", x]
    q = " ".join(f'"{a}"' if (" " in a or "%" in a or "\\" in a) else a for a in args)
    bat = "@echo off\n" + NOTES + 'set "HERE=%~dp0"\nset "DATA=%HERE%data"\nif not exist "%HERE%water\\saves" mkdir "%HERE%water\\saves"\n' \
        + f'start "" "%HERE%doomerfall-launcher.exe" {q}\n'
    full = os.path.join(play, "play-full.bat")
    current = os.path.join(play, "play.bat")
    if os.path.exists(current) and "swimdemo" not in open(current).read():
        os.replace(current, full)  # the install's full game (fresh after each install) stays one click away
    with open(os.path.join(play, "play.bat"), "w", newline="\r\n") as f:
        f.write(bat)
    print("wrote", os.path.join(play, "play.bat"), "(the full game is play-full.bat)")


if __name__ == "__main__":
    main()
