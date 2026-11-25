"""Builds a play folder copy for the ammo inventory fix: the installed play folder's UZDoom, launcher, bridge DLL, data,
pk3s and play.bat, with this checkout's Daggerfall Unity build in place of its dfu folder.

usage: assemble_inv.py [target]   (default D:\\dev\\DoomDaggerfall-loop\\review\\ammoinv)
Valid only while the native code (bridge, launcher, UZDoom) and mods/doomerfall match the play folder's build.
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAY = Path(r"D:\dev\DoomDaggerfall-loop\play")
target = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\dev\DoomDaggerfall-loop\review\ammoinv")
target.mkdir(parents=True, exist_ok=True)

for name in ("uzdoom", "data"):
    shutil.rmtree(target / name, ignore_errors=True)
    shutil.copytree(PLAY / name, target / name)
for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe", "play.bat"):
    shutil.copy2(PLAY / name, target / name)

dfu = target / "dfu"
shutil.rmtree(dfu, ignore_errors=True)
shutil.copytree(REPO / "daggerfall-unity-master" / "Builds" / "Windows64", dfu)
plugins = dfu / "DaggerfallUnity_Data" / "Plugins" / "x86_64"
plugins.mkdir(parents=True, exist_ok=True)
shutil.copy2(PLAY / "dfu" / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll", plugins / "doomerfall_bridge.dll")
(dfu / "Portable.txt").write_text("")
# As scripts/play/install.py isolate_registry: this copy must not share the owner's Daggerfall settings.
managers = dfu / "DaggerfallUnity_Data" / "globalgamemanagers"
data = managers.read_bytes()
stock, private = b"\x10\0\0\0Daggerfall Unity", b"\x10\0\0\0Doomerfall Local"
if stock in data:
    managers.write_bytes(data.replace(stock, private))
elif private not in data:
    sys.exit("could not isolate the Daggerfall registry key")
print("assembled", target)
