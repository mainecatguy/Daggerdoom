"""Builds the one-click Scourg Barrow action demo. The output is derived from game data, so keep it outside the repo.

Usage: python tools/dungeon_converter/make_action_demo.py [--out D:\\dev\\DoomDaggerfall-loop\\review\\action-system]
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EXE_DIR = r"D:\dev\DoomDaggerfall-build\uzdoom-mesh\Release"
DLL_SOURCE = r"D:\dev\DoomDaggerfall-build\uzdoom-launcher\Release"
IWAD = r"D:\dev\DoomDaggerfall\GameResources\wads\DOOM2.WAD"

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=r"D:\dev\DoomDaggerfall-loop\review\action-system")
out = os.path.abspath(parser.parse_args().out)
if (os.path.normcase(out) + os.sep).startswith(os.path.normcase(REPO) + os.sep) and "__pycache__" not in out:  # git ignores __pycache__
    sys.exit("--out must be outside the repository: the demo contains files derived from game data")
os.makedirs(out, exist_ok=True)
project = os.path.join(HERE, "DungeonConverter.csproj")
for extra in (["--daggerfall-player"], ["--export-mesh"]):
    subprocess.run(["dotnet", "run", "-c", "Release", "-v", "q", "--project", project, "--", "Scourg Barrow", "--out", out,
                    "--world-scale", "0.75", *extra], check=True, stdout=subprocess.DEVNULL)
for dll in ("sndfile.dll", "soft_oal.dll"):
    if not os.path.exists(os.path.join(EXE_DIR, dll)):
        shutil.copy2(os.path.join(DLL_SOURCE, dll), EXE_DIR)
files = " ".join(f'"%~dp0scourgbarrow{suffix}"' for suffix in (".wad", "_mesh.pk3", "_doors.pk3", "_player.pk3"))
with open(os.path.join(out, "play.bat"), "w", newline="\r\n") as f:
    f.write("@echo off\nrem Scourg Barrow with Daggerfall action objects. Use a coffin lid, then jump in.\n")
    f.write(f'start "" /D "%~dp0." "{os.path.join(EXE_DIR, "uzdoom.exe")}" -iwad "{IWAD}" -file {files} -config "%~dp0demo.ini" -skill 3 +vid_fullscreen 0 +gl_bloom 1 +gl_light_shadowmap 1 +gl_ssao 2 +gl_lens 1 +map MAP01\n')
print("demo written to", os.path.join(out, "play.bat"))
