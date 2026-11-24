"""Runs an existing feature test against an installed play folder instead of its own review folder.

usage: retarget.py <play folder> [--play-mods] [--set NAME=VALUE ...] <tool script> [tool arguments...]
The play folder is what scripts/play/install.py writes: uzdoom, dfu, data, dfitems.pk3, doomerfall.pk3, and the launcher.
The tool's module-level REVIEW constant (and a DATA folder derived from another review folder) is pointed at it, and the
tool runs unchanged otherwise. Its logs and saves go to <play folder>/run-tests, never to the owner's run folder.
--play-mods: launcher commands that lack them also get play.bat's DRLA set, dfitems.pk3, and doomerfall.pk3.
--set: replaces a module-level constant, for example --set TIMEOUT=90.
--uz ARG: adds one UZDoom argument to launcher commands, for example --uz +vid_defwidth.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

DRLA = [Path(r"D:\dev\DoomDaggerfall\GameMods") / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")]

args = sys.argv[1:]
play = Path(args.pop(0)).resolve()
play_mods, sets, uz = False, [], []
while args and args[0].startswith("--"):
    flag = args.pop(0)
    if flag == "--play-mods":
        play_mods = True
    elif flag == "--uz":
        uz.append(args.pop(0))
    elif flag == "--set":
        sets.append(args.pop(0).split("=", 1))
    else:
        sys.exit("unknown option " + flag)
tool = Path(args.pop(0)).resolve()
if args[:1] == ["assemble"]:
    sys.exit("assemble would replace the play folder's builds through the junctions")

tests = play / "run-tests"  # The layout the tools expect: REVIEW/run, REVIEW/data, REVIEW/uzdoom...
tests.mkdir(exist_ok=True)
for name in ("uzdoom", "dfu", "data"):  # Junctions: no copy, no admin rights, and they follow a reinstall.
    if not (tests / name).exists():
        subprocess.check_call(["cmd", "/c", "mklink", "/J", str(tests / name), str(play / name)], stdout=subprocess.DEVNULL)
for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe"):
    shutil.copy2(play / name, tests / name)

source = tool.read_text()
source, count = re.subn(r"^REVIEW = .*$", lambda m: f"REVIEW = Path(r\"{tests}\")", source, count=1, flags=re.M)
if not count:
    sys.exit("no REVIEW constant in " + str(tool))
source = re.sub(r"^DATA = REVIEW\.parent / .*$", "DATA = REVIEW / \"data\"", source, flags=re.M)
source = re.sub(r"^DATA = Path\(r\"[^\"]*\\data\"\)$", "DATA = REVIEW / \"data\"", source, flags=re.M)
for name, value in sets:
    source, count = re.subn(rf"^{name} = .*$", lambda m: f"{name} = {value}", source, count=1, flags=re.M)
    if not count:
        sys.exit(f"no {name} constant in {tool}")

if play_mods or uz:
    popen = subprocess.Popen

    def with_play_mods(command, *a, **kw):
        if uz and isinstance(command, list) and "--uzdoom-arg" in command:
            command = [str(c) for c in command] + [x for u in uz for x in ("--uzdoom-arg", u)]
        if play_mods and isinstance(command, list) and "--mod" in command and not any("DoomRL_Arsenal" in str(c) for c in command):
            command = [str(c) for c in command]
            first, last = command.index("--mod"), len(command) - 1 - command[::-1].index("--mod")
            tail = [] if any(c.endswith("doomerfall.pk3") for c in command) else ["--mod", str(tests / "dfitems.pk3"), "--mod", str(tests / "doomerfall.pk3")]
            command = command[:first] + [x for m in DRLA for x in ("--mod", str(m))] + command[first:last + 2] + tail + command[last + 2:]
        return popen(command, *a, **kw)
    subprocess.Popen = with_play_mods

sys.argv = [str(tool), *args]
sys.path.insert(0, str(tool.parent))
exec(compile(source, str(tool), "exec"), {"__name__": "__main__", "__file__": str(tool)})
