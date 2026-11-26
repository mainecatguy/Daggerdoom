"""Fixed drops: the owner's rules for monsters Daggerfall did not place, with Daggerfall and Doom together (test only).

usage: rules.py <play folder> revisit|adaptive<N>|armageddon<N> [--out <results folder name>]
  revisit     DRLA at skill 3, a real New Game: a placed monster raised by a stock Arch-vile drops nothing on its second
              death; a raised monster and a summoned Lost Soul left alive drop nothing after the player leaves the
              dungeon and comes back; an id-less DRLA Adaptive spawner present at the exit is not stored or brought back.
  adaptive1   DRLA's Adaptive skill (menu index 7), Armageddon (6) for armageddon1, with the encounter planner removed
              (a copy of doomerfall.pk3 with its planner class renamed), so placements use the stock roster through the
              skill's replacements, which are DRLA's Monster-flagged spawners. Every monster on the level is killed and
              every death and drop is listed with its seed.
Runs through tools/fixed_drops/paired.py's launcher driver. Wrap the whole script in quiet_run.py.
"""
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402

MODES = {"revisit": 0, "adaptive": 1, "armageddon": 1}
SKILL = {"adaptive": "7", "armageddon": "6"}  # Skill menu indexes (DRLA mapinfo order)


def make_harness(out, name, play=None):
    harness = out / f"rules-{name}.pk3"
    with zipfile.ZipFile(harness, "w") as z:
        text = (HERE / "rules.zs").read_text().replace("@MODE@", str(MODES[name.rstrip("0123456789")]))
        z.writestr("zscript.txt", text.replace("@DOOR@", paired.door_spot(PLAY)))
        z.writestr("mapinfo.txt", 'gameinfo { addeventhandlers = "PDRules" }\n')
    return harness


def roster_play(play):
    """A sibling play folder whose doomerfall.pk3 has no encounter planner. The big folders are junctions."""
    import shutil
    import subprocess
    other = play.parent / (play.name + "-roster")
    other.mkdir(exist_ok=True)
    for name in ("uzdoom", "dfu", "data"):
        if not (other / name).exists():
            subprocess.check_call(["cmd", "/c", "mklink", "/J", str(other / name), str(play / name)], stdout=subprocess.DEVNULL)
    for name in ("doomerfall-launcher.exe", "dfitems.pk3"):
        shutil.copy2(play / name, other / name)
    with zipfile.ZipFile(play / "doomerfall.pk3") as src, zipfile.ZipFile(other / "doomerfall.pk3", "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.lower().endswith("encounterleaders.zs"):
                data = data.replace(b"class DoomerfallEncounterLeaders play", b"class DoomerfallEncounterLeadersOff play")
            dst.writestr(item, data)
    return other


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    PLAY = Path(sys.argv[1]).resolve()
    out = PLAY.parent / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "fixed-drops-rules")
    out.mkdir(exist_ok=True)
    name = sys.argv[2]
    kind = name.rstrip("0123456789")
    play = PLAY
    if kind in SKILL:
        play = roster_play(PLAY)
        paired.EXTRA_UZ[:] = ["-dfnewgameskill", SKILL[kind]]
    paired.make_harness = make_harness
    paired.TIMEOUT = 420
    paired.run(play, out, name, 10)
    text = (out / f"result-{name}.txt").read_text()
    print("\n".join(l for l in text.splitlines() if not l.startswith(("PDRDROP", "PDRLIVE", "PDRDIED")))[:4000])
