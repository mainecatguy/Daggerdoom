@echo off
rem Launches the 75% Privateer's Hold demo.
set "EXE=D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release\uzdoom.exe"
set "IWAD=D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"
set "DEMO=D:\dev\DoomDaggerfall-loop\review\stock-demo-75"

start "" /D "%DEMO%" "%EXE%" -iwad "%IWAD%" -config "%DEMO%\demo.ini" -file "%DEMO%\privateershold.wad" "%DEMO%\privateershold_mesh.pk3" "%DEMO%\privateershold_width.pk3" "%DEMO%\privateershold_monsters.pk3" +gl_bloom 1 +gl_light_shadowmap 1 +gl_ssao 2 +gl_lens 1 +map MAP01
