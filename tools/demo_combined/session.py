"""Runs the merged features' own paired tests against one installed play folder (scripts/play/install.py).

usage: session.py <play folder> [step ...]     (no steps: all of them, in order)
Each step is one short paired launch, minimized, with private configs and saves in <play folder>/run-tests.
Output of each step goes to run-tests/session-<step>.txt and a one-line summary is printed.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
PY = sys.executable
RETARGET = [PY, str(HERE / "retarget.py")]


def steps(play):
    tests = play / "run-tests"
    containers = [PY, str(TOOLS / "containers" / "containers.py"), "--review", str(tests)]
    rt = RETARGET + [str(play)]
    return {
        # name: (command, regex that marks a pass in the output)
        "e1m1": (containers + ["check"], r"stock exit 0 .*\n.*drla exit 0"),
        "newgame": (rt + ["--play-mods", "--set", "TIMEOUT=180", str(TOOLS / "new_game" / "run_new_game.py"), "create", "save"], r"result: PASS"),
        "pickups": (rt + [str(TOOLS / "pickups" / "pickups.py"), "first"], r"PKTOOK"),
        "pickups-load": (rt + [str(TOOLS / "pickups" / "pickups.py"), "load"], r"PK[A-Z]* .*(PASS|still gone)"),
        "loot": (containers + ["run", "loot"], r"loottest:|items: opening"),
        "hotkeys": (rt + [str(TOOLS / "hotkeys" / "hotkeys.py"), "swap"], r"PASS"),
        "hotkeys-load": (rt + [str(TOOLS / "hotkeys" / "hotkeys.py"), "load"], r"PASS"),
        "dialogue": (rt + [str(TOOLS / "npc_dialogue" / "npc_dialogue.py"), "run", "talk"], r"top window|Talk"),
        "shop": (rt + [str(TOOLS / "shop_menu" / "shop_menu.py"), "run", "shop"], r"menu|Trade"),
        "theft": (containers + ["run", "theft", "--building", "GeneralStore", "--target", "box", "--crouch", "--stay", "--df-arg=-dfguardtest"], r"guard"),
        "census": (rt + [str(TOOLS / "townhomes" / "townhomes.py"), "run", "census"], r"townhome|census"),
        "homes": (rt + [str(TOOLS / "townhomes" / "townhomes.py"), "run", "homes"], r"at home|home"),
        "drops": (rt + [str(TOOLS / "real_drops" / "real_drops.py"), "run", "drops", "--drla"], r"MD[A-Z]+ .*(drop|PASS)"),
        "climb": ([PY, str(TOOLS / "climb" / "run_paired_probe.py"), str(TOOLS / "climb" / "paired_probe.zs"), str(tests / "climb"), "--demo", str(tests)], r"climb"),
    }


def town_bat(play):
    """The climb probe reads a play.bat that starts in town. Made from the installed one, for tests only."""
    bat = (play / "play.bat").read_text()
    bat = bat.replace("--uzdoom-arg -dfflow", "--uzdoom-arg -skill --uzdoom-arg 3 --uzdoom-arg +map --uzdoom-arg DDT07154")
    bat = bat.replace("--dfu-arg -dfflow", "--dfu-arg -dfsynctest").replace("%HERE%run\\", "%HERE%play\\").replace('"%HERE%run"', '"%HERE%play"')
    (play / "run-tests" / "play.bat").write_text(bat)


def main():
    play = Path(sys.argv[1]).resolve()
    (play / "run-tests").mkdir(exist_ok=True)
    for folder in ("uzdoom", "dfu", "data"):  # As retarget.py makes them, for the tools run without it.
        if not (play / "run-tests" / folder).exists():
            subprocess.check_call(["cmd", "/c", "mklink", "/J", str(play / "run-tests" / folder), str(play / folder)], stdout=subprocess.DEVNULL)
    for name in ("dfitems.pk3", "doomerfall.pk3", "doomerfall-launcher.exe"):
        shutil.copy2(play / name, play / "run-tests" / name)
    if not (play / "run-tests" / "doomerfall").exists():  # The drops test loads the mod as a folder: this checkout's source of doomerfall.pk3.
        subprocess.check_call(["cmd", "/c", "mklink", "/J", str(play / "run-tests" / "doomerfall"), str(TOOLS.parent / "mods" / "doomerfall" / "src")], stdout=subprocess.DEVNULL)
    table = steps(play)
    chosen = sys.argv[2:] or list(table)
    for name in chosen:
        command, mark = table[name]
        if name == "climb":
            town_bat(play)
        start = time.time()
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", timeout=900)
        out = result.stdout + result.stderr
        (play / "run-tests" / f"session-{name}.txt").write_text(out)
        fatal = re.search(r"stopped: fatal|result: fatal|Traceback|DIED WITH FATAL|VM execution aborted", out)
        verdict = "FATAL" if fatal else ("seen" if re.search(mark, out) else "CHECK")
        print(f"{name:13} {verdict:6} exit {result.returncode:3} {int(time.time() - start):4}s  session-{name}.txt", flush=True)


if __name__ == "__main__":
    main()
