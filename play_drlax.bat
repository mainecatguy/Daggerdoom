@echo off
rem Runs stock DOOM.WAD E1M1 with DRLA, DRLA Monsters, and DRLAX. No Daggerfall content.
set "EXE=D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
set "IWAD=D:\dev\DoomDaggerfall\GameResources\wads\DOOM.WAD"
set "MODS=D:\dev\DoomDaggerfall\GameMods"
set "RUN=D:\dev\DoomDaggerfall-loop\review\drlax-e1m1"

start "" /D "%RUN%" "%EXE%" -iwad "%IWAD%" -file "%MODS%\DoomRL_Arsenal_1.1.5.pk3" "%MODS%\DoomRL_Monsters_Beta_7.3.pk3" "%MODS%\drlax_1.2b.pk3" -config "%RUN%\drlax.ini" -skill 3 +map E1M1
