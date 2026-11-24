"""Paired test for encounter card 4: area facts, encounter markers, and leaders.

usage: encounter_facts.py build | wad | assemble | run NAME [--load] [--drla] [--presave] | compare NAME

Reuses the monster death route (tools/monster_deaths/harness.zs): enter Privateer's Hold with a real kill quest, kill
the quest foe and placed monsters until one drops, take the drop, save, leave, and re-enter. A --load run repeats the
trip from that save. This wrapper swaps in a map whose monsters are replaced by the converter's encounter markers, and
compares the facts Daggerfall sent with the facts Doom received. Game data and generated maps stay outside the repo.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "monster_deaths"))
import monster_deaths as md  # noqa: E402

base, pickup = md.base, md.pickup
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\encounter-facts")
md.REVIEW = REVIEW
base.REVIEW, base.BUILD, base.RUN = REVIEW, REVIEW / "build", REVIEW / "run"
pickup.REVIEW = REVIEW
# The combined-bridge data's town cache and converter are older than this UZDoom reads; the doom-items data is current.
pickup.DATA = Path(r"D:\dev\DoomDaggerfall-loop\review\doom-items\data")
LANE_UZ = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-encounters\Release")  # Built from this worktree (see the task notes).
CONVERTER = Path(r"D:\dev\DoomDaggerfall-build\converter-encounters\bin\Release\net9.0\DungeonConverter.dll")
ROSTER = {3004, 9, 65, 3001, 3002, 58, 3006, 3005, 69, 3003, 66, 67, 68, 71, 64}  # the old converter's monster types
FACT_FIELDS = ("map", "dungeonIndex", "locationId", "name", "region", "regionName", "world", "type", "typeName", "areaLevel", "seedOffset")


MENU_CLOSER = """	bool presave;

	// Daggerfall's quest messages now open as a Doom menu and pause Doom (bridge kind 25). The old route predates
	// that, so it presses Back on any menu that stays open for a second, as a player would dismiss the message.
	ui int menuTics;
	override void UiTick()
	{
		let m = Menu.GetCurrentMenu();
		if (!m) { menuTics = 0; return; }
		if (++menuTics == 35) { Console.Printf("MDMENU back on %s", m.GetClassName()); m.MenuEvent(Menu.MKEY_Back, false); menuTics = 0; }
	}
"""


def patch_route():
    """A copy of the monster death route that answers Daggerfall's windows."""
    folder = REVIEW / "route"
    folder.mkdir(parents=True, exist_ok=True)
    text = (md.HERE / "harness.zs").read_text()
    # Interact on a pile now opens Daggerfall's loot window, which this route cannot drive, so it leaves the drop on the
    # ground and expects it to persist. It also kills at least two placed leaders besides the quest foe.
    edits = [("\tbool presave;\n", MENU_CLOSER),
             ("\t\t\t\tif (pile)\n", "\t\t\t\tif (pile && st.kills >= 3)\n"),
             ("\t\t\t\t\tst.phase = 3;\n", "\t\t\t\t\tst.phase = 4;\n"),
             ("Finish(now == st.alive && !present ?", "Finish(now == st.alive && present ?"),
             # Card 7: with Civil War and infighting a monster can die after the save (Daggerfall records it), so the
             # re-entry count is compared with the living count when the player leaves, not at the save.
             ("\t\t\tConsole.Printf(\"MDCHECK living %d, expected %d,",
              "\t\t\tif (Living() != st.alive) Console.Printf(\"MDLATE %d died after the save\", st.alive - Living());\n"
              "\t\t\tst.alive = Living();\n\t\t\tConsole.Printf(\"MDCHECK living %d, expected %d,")]
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    (folder / "harness.zs").write_text(text)
    md.HERE = folder


def build():
    """Bridge DLL and launcher from this worktree (the layout hash changed); UZDoom from the lane build tree."""
    base.BUILD.mkdir(parents=True, exist_ok=True)
    for name, source in (("bridge", "bridge"), ("launcher", "launcher")):
        target, log = base.BUILD / name, base.BUILD / f"{name}-build.log"
        log.unlink(missing_ok=True)
        if not (target / "CMakeCache.txt").exists():
            base.call(["cmake", "-S", str(base.WORKTREE / source), "-B", str(target), "-G", "Visual Studio 18 2026", "-A", "x64"], log)
        base.call(["cmake", "--build", str(target), "--config", "Release", "--parallel", "6"], log)
        print("built", name)
    base.copy_tree(LANE_UZ, base.BUILD / "uzdoom" / "Release")
    print("copied uzdoom from", LANE_UZ)


def make_wad():
    """The packaged map with its old monster things replaced by the fresh converter's encounter markers."""
    out = REVIEW / "wad"
    out.mkdir(parents=True, exist_ok=True)
    code = subprocess.call(["dotnet", str(CONVERTER), "Privateer's Hold", "--out", str(out)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if code:
        sys.exit(f"converter failed ({code})")
    fresh = dict(md.read_wad(out / md.WAD))
    markers = re.findall(rb"thing \{[^}]*type = 9001;[^}]*\}\n?", fresh["TEXTMAP"])
    packaged = md.read_wad(pickup.DATA / md.WAD)
    text = dict(packaged)["TEXTMAP"]
    old = [t for t in re.findall(rb"thing \{[^}]*\}\n?", text) if int(re.search(rb"type = (\d+);", t).group(1)) in ROSTER]
    for t in old:
        text = text.replace(t, b"", 1)
    text += b"".join(markers)
    hashes = {re.search(rb"comment = \"encounter ([0-9a-f]+)\"", m).group(1) for m in markers}
    print(f"removed {len(old)} monster things, added {len(markers)} encounter markers ({len(hashes)} unique hashes), fresh map still places monsters: "
          f"{any(int(t) in ROSTER for t in re.findall(rb'type = (\d+);', fresh['TEXTMAP']))}")
    lumps = [(n, text if n == "TEXTMAP" else d) for n, d in packaged if n != "DDMONST"]
    md.write_wad(out / ("ids_" + md.WAD), lumps)


def facts(line):
    m = re.search(r"facts map (-?\d+) dungeonIndex (-?\d+) locationId (-?\d+) name '(.*?)' region (-?\d+) '(.*?)' world ([\d.]+,[\d.]+) type (-?\d+) \((\w*)\) areaLevel (-?\d+) seedOffset (-?\d+)", line)
    return dict(zip(FACT_FIELDS, m.groups())) if m else None


def compare(name):
    runs = REVIEW / "run"
    uz = [l for l in base.read(runs / f"log-{name}.txt").splitlines() if l.startswith("DDENC") or l.startswith("DDMON dungeon")]
    df = [l for l in base.read(runs / f"{name}-df.log").splitlines() if "encounters:" in l]
    for line in uz[:12] + ([f"... {len(uz) - 12} more DDENC lines"] if len(uz) > 12 else []):
        print("uz", line[:200])
    for line in df[:6]:
        print("df", line[:220])
    sent = next((facts(l) for l in df if facts(l)), None)
    got = next((facts(l) for l in uz if facts(l)), None)
    if not sent or not got:
        print("facts compare: missing", "Daggerfall" if not sent else "", "Doom" if not got else "")
        return
    diff = [k for k in FACT_FIELDS if sent[k] != got[k]]
    print("facts compare:", "identical" if not diff else "differ in " + ", ".join(f"{k} ({sent[k]} vs {got[k]})" for k in diff))
    leaders = [l for l in uz if l.startswith("DDENC leader")]
    print(f"leaders spawned: {len(leaders)}, of them quest: {sum('(quest' in l for l in leaders)}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        build()
    elif command == "wad":
        make_wad()
    elif command == "assemble":
        md.assemble()
    elif command == "run":
        patch_route()
        md.run(sys.argv[2], "--load" in sys.argv, "--drla" in sys.argv, "--presave" in sys.argv)
        compare(sys.argv[2])
    elif command == "compare":
        compare(sys.argv[2])
    else:
        sys.exit(__doc__)
