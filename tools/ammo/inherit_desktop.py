"""Stands in for quiet_run.py inside a harness that already runs under quiet_run.py (a private desktop).

usage: inherit_desktop.py [--timeout SECONDS] [--cwd DIR] [quiet_run flags...] -- PROGRAM [ARGS...]
Runs PROGRAM directly, so it shares the outer private desktop with the harness. Harnesses that find Doom's window with
EnumWindows and drive it with PostMessage (tools/new_game/run_new_game.py) cannot see a window on a nested private
desktop, so they wait until timeout. Use it through tools/demo_combined/retarget.py --set QUIET=r"<this file>", with
the whole command wrapped in quiet_run.py.

For the Doomerfall launcher it adds --dfu-arg -dfmute (quiet_run would add it to Daggerfall Unity itself), and each
--dfu-arg named in the INHERIT_DFU_ARGS environment variable or in a file next to this script named like it plus
".args" (space separated), for example -dfinvtabstest.
"""
import os
import subprocess
import sys

args = sys.argv[1:]
timeout, cwd = None, None
while args and args[0] != "--":
    flag = args.pop(0)
    if flag == "--timeout":
        timeout = float(args.pop(0))
    elif flag == "--cwd":
        cwd = args.pop(0)
if not args:
    sys.exit("usage: inherit_desktop.py [--timeout S] -- PROGRAM [ARGS...]")
command = args[1:]
if command and os.path.basename(command[0]).lower().startswith("doomerfall-launcher"):
    sidecar = os.path.abspath(__file__) + ".args"
    extras = os.environ.get("INHERIT_DFU_ARGS", "").split()
    if os.path.exists(sidecar):
        extras += open(sidecar).read().split()
    for extra in ["-dfmute"] + extras:
        command += ["--dfu-arg", extra]
try:
    sys.exit(subprocess.run(command, cwd=cwd, timeout=timeout).returncode)
except subprocess.TimeoutExpired:
    sys.exit(124)
