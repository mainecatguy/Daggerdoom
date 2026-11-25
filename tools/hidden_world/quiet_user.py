"""quiet_run.py with --user-desktop, for harnesses that drive Doom's window with window messages.

Those drivers find Doom's window with EnumWindows, which sees only the caller's desktop, so they cannot work when
quiet_run puts UZDoom on a private desktop. UZDoom still starts minimized with -noactivate, and the launcher's
--minimized still runs Daggerfall Unity on its own private desktop.
"""
import subprocess
import sys

QUIET = r"D:\dev\DoomDaggerfall\scripts\overnight\quiet_run.py"
sys.exit(subprocess.call([sys.executable, QUIET, "--user-desktop"] + sys.argv[1:]))
