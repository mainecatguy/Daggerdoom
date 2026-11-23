"""A normal Daggerfall launch (no -dfbridge) with the bridge DLL hidden must start and log no bridge activity."""
import re
import subprocess
import sys
import time
from pathlib import Path

DFU = Path(r"D:\dev\DoomDaggerfall-loop\review\hp-sync\dfu")
QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
LOG = Path(r"D:\dev\DoomDaggerfall-loop\review\hp-sync\run\nosession-dfu-player.log")

dll = DFU / "DaggerfallUnity_Data" / "Plugins" / "x86_64" / "doomerfall_bridge.dll"
hidden = dll.with_suffix(".hidden")
LOG.unlink(missing_ok=True)
dll.rename(hidden)
try:
    code = subprocess.run([sys.executable, QUIET, "--timeout", "20", "--", str(DFU / "DaggerfallUnity.exe"), "-logFile", str(LOG),
                           "-screen-fullscreen", "0", "-screen-width", "640", "-screen-height", "360"], capture_output=True, text=True).returncode
finally:
    hidden.rename(dll)
text = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
print(f"exit {code}; log {len(text)} bytes; bridge mentions {len(re.findall(r'doomerfall_bridge|[[]bridge[]]|DllNotFound|DoomerfallBridge|hp:', text))};"
      f" exceptions {text.count('Exception')}")
