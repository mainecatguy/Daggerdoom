"""Stages review/newgame-restart: New Game from inside a running game.

Daggerfall Unity, the launcher, the bridge DLL, the converted data and the mod packages come from the latest merged
demo (review/expandedinv, built from integration); this branch changes only UZDoom, whose build is copied in.
"""
import shutil
from pathlib import Path

BUILD = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-encounters\Release")
SOURCE = Path(r"D:\dev\DoomDaggerfall-loop\review\expandedinv")
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\newgame-restart")

PLAY = r'''@echo off
rem New Game from inside a running game. Choose New Game at Doom's title and make a character. Play a little,
rem save if you like (Doom's Save Game), then press Escape and choose New Game again: Doom asks to confirm, and
rem Yes drops the running game and opens Daggerfall's character creation. The new character starts fresh in
rem Privateer's Hold in both games. Load Game still loads the save you made with the first character.
set "HERE=%~dp0"
set "DATA=%HERE%data"
set "MODS=D:\dev\DoomDaggerfall\GameMods"
set "DF=D:\dev\DoomDaggerfall\GameResources\DAGGER"
if not exist "%HERE%play\saves" mkdir "%HERE%play\saves"
start "" "%HERE%doomerfall-launcher.exe" --nodraw --uzdoom "%HERE%uzdoom\uzdoom.exe" --dfu "%HERE%dfu\DaggerfallUnity.exe" --iwad "D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD" --mod "%MODS%\DoomRL_Arsenal_1.1.5.pk3" --mod "%MODS%\DoomRL_Monsters_Beta_7.3.pk3" --mod "%MODS%\drlax_1.2b.pk3" --mod "%DATA%\ddruntime.pk3" --mod "%DATA%\overworld.pk3" --mod "%DATA%\privateershold.wad" --mod "%DATA%\privateershold_mesh.pk3" --mod "%DATA%\privateershold_doors.pk3" --mod "%HERE%dfitems.pk3" --mod "%HERE%doomerfall.pk3" --uzdoom-cwd "%HERE%play" --log "%HERE%play\launcher.log" --uzdoom-arg -dfflow --uzdoom-arg -config --uzdoom-arg "%HERE%play\uzdoom.ini" --uzdoom-arg -savedir --uzdoom-arg "%HERE%play\saves" --uzdoom-arg -dfbridgelog --uzdoom-arg "%HERE%play\uz.log" --uzdoom-arg -ddtowncache --uzdoom-arg "%DATA%\cache" --uzdoom-arg -ddconverter --uzdoom-arg "%DATA%\converter\DungeonConverter.exe" --uzdoom-arg -ddarena2 --uzdoom-arg "%DF%\ARENA2" --uzdoom-arg +vid_fullscreen --uzdoom-arg 0 --uzdoom-arg +i_pauseinbackground --uzdoom-arg 0 --dfu-arg -dfflow --dfu-arg "%DF%" --dfu-arg -dfbridgelog --dfu-arg "%HERE%play\df.log" --dfu-arg -screen-fullscreen --dfu-arg 0 --dfu-arg -screen-width --dfu-arg 1280 --dfu-arg -screen-height --dfu-arg 800
'''


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    for name in ("dfu", "data"):
        if not (REVIEW / name).exists():
            shutil.copytree(SOURCE / name, REVIEW / name)
    for name in ("doomerfall-launcher.exe", "doomerfall.pk3", "dfitems.pk3"):
        shutil.copy2(SOURCE / name, REVIEW / name)
    shutil.copytree(SOURCE / "uzdoom", REVIEW / "uzdoom", dirs_exist_ok=True)  # Runtime DLLs the build tree lacks.
    for name in ("uzdoom.exe", "uzdoom.pk3", "game_support.pk3", "game_widescreen_gfx.pk3", "lights.pk3", "brightmaps.pk3"):
        if (BUILD / name).exists():
            shutil.copy2(BUILD / name, REVIEW / "uzdoom" / name)
    (REVIEW / "play.bat").write_text(PLAY, newline="\r\n")
    print("staged", REVIEW)


if __name__ == "__main__":
    main()
