"""Paired test for location state card 1: stable place keys, and a world table that stores only changes.

usage: location_ledger.py build | unity | wad | assemble | run NAME [--load] | sig NAME
       location_ledger.py remap   (fakes a converter regrouping: the building gets a new space id and map name)

Reuses the encounter-facts route (tools/encounter_facts, tools/monster_deaths/harness.zs): enter Privateer's Hold with a
real kill quest, kill the quest foe and placed monsters, save, leave and re-enter; a --load run repeats the trip from the
save. This wrapper adds to the route: before the save it takes one map pickup, moves another, and drops a clip; at the
save, on leaving and on re-entry it prints a signature of every monster, corpse and loose item (class, rounded spot,
health, id) so the runs can be compared line by line. Game data and generated maps stay outside the repo.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "encounter_facts"))
import encounter_facts as ef  # noqa: E402

md, base, pickup = ef.md, ef.base, ef.pickup
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger")
ef.REVIEW = md.REVIEW = pickup.REVIEW = base.REVIEW = REVIEW
base.BUILD, base.RUN = REVIEW / "build", REVIEW / "run"
UZ_TREE = Path(r"D:\dev\DoomDaggerfall-build\uzdoom-locledger\Release")
ef.LANE_UZ = UZ_TREE
CONVERTER_DIR = Path(r"D:\dev\DoomDaggerfall-build\converter-locledger\bin\Release\net9.0")
ef.CONVERTER = CONVERTER_DIR / "DungeonConverter.dll"

SIGNATURE = r"""
	// Location ledger test: every monster, corpse and loose item, one line each, sorted, so runs compare line by line.
	static void Signature(String when)
	{
		Array<String> rows;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (mo.player) continue;
			bool item = mo is "Inventory" && Inventory(mo).Owner == null;
			if (!mo.bISMONSTER && !item) continue;
			rows.Push(String.Format("%s %s %d,%d,%d hp %d%s", item ? "item" : mo.health > 0 ? "alive" : "dead", mo.GetClassName(),
				int(mo.pos.x / 8), int(mo.pos.y / 8), int(mo.pos.z / 8), mo.health, mo.bDROPPED ? " dropped" : ""));
		}
		// Insertion sort keeps this independent of thinker order.
		for (int i = 1; i < rows.Size(); i++)
			for (int j = i; j > 0 && rows[j] < rows[j - 1]; j--) { String t = rows[j]; rows[j] = rows[j - 1]; rows[j - 1] = t; }
		Console.Printf("LLSIG %s begin %d", when, rows.Size());
		for (int i = 0; i < rows.Size(); i++) Console.Printf("LLSIG %s %s", when, rows[i]);
		Console.Printf("LLSIG %s end", when);
	}

	// Takes the nearest map pickup, moves the next one, and drops a clip, so the table has a take, a move and a drop.
	static void ChangeItems(PlayerPawn p)
	{
		Array<Inventory> loose;
		let it = ThinkerIterator.Create("Inventory");
		Inventory inv;
		while (inv = Inventory(it.Next())) if (inv.Owner == null && !(inv is "DoomerfallWorldItem")) loose.Push(inv);
		Console.Printf("LLITEMS %d map items", loose.Size());
		if (loose.Size() > 0) { Console.Printf("LLTAKE %s", loose[0].GetClassName()); loose[0].CallTryPickup(p); }
		if (loose.Size() > 1)
		{
			loose[1].SetOrigin(loose[1].pos + (24, 0, 0), false);
			Console.Printf("LLMOVE %s", loose[1].GetClassName());
		}
		let clip = p.Spawn("Clip", p.pos + (32, 32, 0));
		if (clip) { clip.bDROPPED = true; Console.Printf("LLDROP Clip"); }
	}
"""


def patch_route():
    ef.patch_route()
    path = md.HERE / "harness.zs"
    text = path.read_text()
    edits = [("\tbool presave;\n", "\tbool presave;\n" + SIGNATURE),
             # Before the save: the item changes, then the signature the re-entry must match.
             ("\t\t\tif (st.timer == 20) st.alive = Living();\n",
              "\t\t\tif (st.timer == 10 && !st.saved) ChangeItems(p);\n\t\t\tif (st.timer == 20) st.alive = Living();\n"),
             ("\t\t\t\tConsole.Printf(\"MDSAVE living %d\", st.alive);\n",
              "\t\t\t\tConsole.Printf(\"MDSAVE living %d\", st.alive);\n\t\t\t\tSignature(\"save\");\n"),
             ("\t\t\tp.SetOrigin((EXITDATA[0]", "\t\t\tSignature(\"leave\");\n\t\t\tp.SetOrigin((EXITDATA[0]"),
             ("\t\t\tConsole.Printf(\"MDREENTRY", "\t\t\tSignature(\"reentry\");\n\t\t\tConsole.Printf(\"MDREENTRY")]
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    path.write_text(text)


def signature(name, when):
    rows = [l.split(" ", 2)[2] for l in base.read(REVIEW / "run" / f"log-{name}.txt").splitlines()
            if l.startswith(f"LLSIG {when} ") and not re.match(rf"LLSIG {when} (begin|end)", l)]
    return rows


def sig(name):
    """Compares the signature at leaving with the one on re-entry (and, for a load run, with the first run's save)."""
    leave, back = signature(name, "leave"), signature(name, "reentry")
    print(f"{name}: leave {len(leave)} rows, reentry {len(back)} rows, identical {leave == back}")
    for row in sorted(set(leave) ^ set(back))[:20]:
        print("  only at", "leave  " if row in leave else "reentry", row)
    for line in base.read(REVIEW / "run" / f"log-{name}.txt").splitlines():
        if line.startswith(("DDTM saved", "DDTM left", "DDTM place", "DDTM row", "DDTM corpse", "LL", "MDSAVE", "MDCHECK", "MDREENTRY", "MDDONE")) and not line.startswith("LLSIG"):
            print(" ", line[:200])
    for save in sorted((REVIEW / "run" / "saves").glob("*.zds")):
        print(f"  save {save.name} {save.stat().st_size} bytes")


def assemble():
    md.assemble()
    shutil.copytree(CONVERTER_DIR, REVIEW / "data" / "converter", dirs_exist_ok=True)
    print("converter from", CONVERTER_DIR)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        ef.build()
    elif command == "unity":
        base.unity()
    elif command == "wad":
        ef.make_wad()
    elif command == "assemble":
        assemble()
    elif command == "run":
        patch_route()
        md.run(sys.argv[2], "--load" in sys.argv, "--drla" in sys.argv)
        sig(sys.argv[2])
    elif command == "sig":
        sig(sys.argv[2])
    else:
        sys.exit(__doc__)
