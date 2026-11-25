"""Builds a test and demo folder for Expanded Inventory: another review folder's UZDoom, launcher, bridge DLL, data and
pk3s, with this checkout's Daggerfall Unity build and the mod's pictures.

usage: assemble.py <source review folder> <target> <pictures folder, or the mod's .zip>
The source folder's native builds (bridge, launcher, UZDoom) and mods/doomerfall must match this checkout's; Daggerfall
logs 'bridge DLL does not match this build' otherwise. The pictures are game data and never go in the repository.
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
source, target, art = (Path(a) for a in sys.argv[1:4])
target.mkdir(parents=True, exist_ok=True)

for name in ("uzdoom", "data"):
    shutil.rmtree(target / name, ignore_errors=True)
    shutil.copytree(source / name, target / name)
for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe", "play.bat"):
    shutil.copy2(source / name, target / name)

dfu = target / "dfu"
shutil.rmtree(dfu, ignore_errors=True)
shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
plugins.mkdir(parents=True, exist_ok=True)
shutil.copy2(source / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
(dfu / "Portable.txt").write_text("")
# As scripts/play/install.py isolate_registry: this copy must not share the owner's Daggerfall settings.
managers = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
data = managers.read_bytes()
stock, private = b"\x10\0\0\0Daggerfall Unity", b"\x10\0\0\0Doomerfall Local"
if stock in data:
    managers.write_bytes(data.replace(stock, private))
elif private not in data:
    sys.exit("could not isolate the Daggerfall registry key")

if art.is_file():
    out = target / "expanded-inventory-extract"
    subprocess.check_call([sys.executable, str(REPO / "tools" / "expanded_inventory" / "extract.py"), str(art), str(out), "--no-decompile"])
    art = out / "textures"
pictures = dfu / "DaggerfallUnity_Data" / "StreamingAssets" / "ExpandedInventory"
pictures.mkdir(parents=True, exist_ok=True)
for png in art.glob("*.png"):
    shutil.copy2(png, pictures / png.name)
print("assembled", target)
