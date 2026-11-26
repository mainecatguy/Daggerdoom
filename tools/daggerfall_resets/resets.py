"""Paired test for "Turn off Daggerfall's resets": a cleared dungeon stays cleared after leaving, passing days, and returning.

usage: resets.py build | assemble | run NAME [--days N] [--drla] | sig NAME

Reuses the location ledger route (tools/location_ledger, tools/monster_deaths/harness.zs) in Privateer's Hold with a real
kill quest. This wrapper changes the route to kill every monster in the dungeon, then leave. Daggerfall runs with
-dfresettest N (DoomerfallResetsTest.cs): when it follows the player out, it passes N days on its clock and forces a
map pixel change, the place where Daggerfall Unity forgets cached place state. Doom waits outside, re-enters, and
passes only if nothing is alive and every corpse is where it was. Game data and generated maps stay outside the repo.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "location_ledger"))
import location_ledger as ll  # noqa: E402

ef, md, base, pickup = ll.ef, ll.md, ll.base, ll.pickup
REVIEW = Path(r"D:\dev\DoomDaggerfall-loop\review\daggerfall-resets")
PREVIOUS = Path(r"D:\dev\DoomDaggerfall-loop\review\locledger")  # converter, town cache, map and sprites, unchanged
ll.REVIEW = ef.REVIEW = md.REVIEW = pickup.REVIEW = base.REVIEW = REVIEW
base.BUILD, base.RUN, base.PREVIOUS = REVIEW / "build", REVIEW / "run", PREVIOUS
TREES = {"uzdoom": r"D:\dev\DoomDaggerfall-build\uzdoom-npckill\Release",      # these three are configured from this worktree
         "bridge": r"D:\dev\DoomDaggerfall-build\bridge-npckill\Release",
         "launcher": r"D:\dev\DoomDaggerfall-build\launcher-npckill\Release"}

KILL_ALL = """		case 2: // Kill every monster in the dungeon, in waves, until none is left for two checks in a row.
			if (st.timer % 50 != 0) break;
			{
				Array<Actor> targets;
				let it = ThinkerIterator.Create("Actor");
				Actor mo;
				while (mo = Actor(it.Next()))
					if (mo.bISMONSTER && mo.health > 0 && !mo.player) targets.Push(mo);
				for (int i = 0; i < targets.Size(); i++)
					if (targets[i] && targets[i].health > 0) targets[i].DamageMobj(p, p, targets[i].health + 100000, 'None', DMG_FORCED | DMG_THRUSTLESS);
				Console.Printf("RTKILL wave %d killed %d, living %d", st.kills, targets.Size(), Living());
				if (targets.Size() == 0 && Living() == 0 && st.kills > 1) { Console.Printf("RTCLEARED"); st.phase = 4; st.timer = 0; }
				else if (++st.kills > 40) { Console.Printf("MDFAIL dungeon would not clear"); Finish("failed"); }
			}
			break;
"""


def patch_route():
    folder = REVIEW / "route"
    folder.mkdir(parents=True, exist_ok=True)
    text = (ll.md.HERE / "harness.zs").read_text()
    text = re.sub(r"\t\tcase 2:.*?(?=\t\tcase 3:)", lambda m: KILL_ALL, text, count=1, flags=re.S)
    edits = [("\tbool presave;\n", ef.MENU_CLOSER + ll.SIGNATURE),
             ("\t\t\tCVar.FindCVar(\"dd_mon_test_kill\").SetInt(2);\n", ""),
             # Outside after leaving: give Daggerfall time to pass its days before going back in.
             ("\t\t\tif (st.timer < 50) break;\n", "\t\t\tif (st.timer < (st.phase == 6 ? 35 * 4 : 50)) break;\n"),
             ("\t\t\tp.SetOrigin((EXITDATA[0]", "\t\t\tSignature(\"leave\");\n\t\t\tp.SetOrigin((EXITDATA[0]"),
             ("\t\t\tConsole.Printf(\"MDREENTRY", "\t\t\tSignature(\"reentry\");\n\t\t\tConsole.Printf(\"MDREENTRY"),
             ("Finish(now == st.alive && !present ?", "Finish(now == 0 && st.alive == 0 ?")]
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new, 1)
    (folder / "harness.zs").write_text(text)
    md.HERE = folder


def build():
    """Copies the three native builds made from this worktree; it does not compile anything."""
    for name, tree in TREES.items():
        base.copy_tree(Path(tree), base.BUILD / name / "Release")
        print("copied", name, "from", tree)


def assemble():
    base.assemble()
    for name in ("sndfile.dll", "soft_oal.dll"):
        shutil.copy2(base.SOUND / name, REVIEW / "uzdoom")
    base.copy_tree(PREVIOUS / "data", REVIEW / "data")
    for name in ("dfitems.pk3", "demo_start.pk3"):
        shutil.copy2(PREVIOUS / name, REVIEW / name)
    args = pickup.launch_args("%HERE%", [], ["-dfmonsterquest", md.QUEST])
    (REVIEW / "play.bat").write_text(
        "@echo off\r\n"
        "rem Starts at the Privateer's Hold door with a kill quest running. Press Use to enter, clear the dungeon, leave,\r\n"
        "rem rest or wait a few days outside, and go back in: it stays cleared, with its corpses and drops.\r\n"
        "set \"HERE=%~dp0\"\r\n"
        "if not exist \"%HERE%play\" mkdir \"%HERE%play\"\r\n"
        "set BINDS=\r\n"
        f"if not exist \"%HERE%play\\uzdoom.ini\" set BINDS={pickup.quoted(pickup.bind_args)}\r\n"
        f"start \"\" \"%HERE%doomerfall-launcher.exe\" {pickup.quoted(args)} %BINDS%\r\n", newline="")
    print("assembled", REVIEW)


def sig(name):
    """Corpses and items at leaving against re-entry, plus Daggerfall's test lines."""
    leave, back = ll.signature(name, "leave"), ll.signature(name, "reentry")
    dead_leave = sorted(r for r in leave if r.startswith("dead "))
    dead_back = sorted(r for r in back if r.startswith("dead "))
    alive_back = [r for r in back if r.startswith("alive ")]
    print(f"{name}: leave {len(leave)} rows ({len(dead_leave)} dead), reentry {len(back)} rows ({len(dead_back)} dead, {len(alive_back)} alive), "
          f"identical {leave == back}, corpses identical {dead_leave == dead_back}")
    for row in sorted(set(leave) ^ set(back))[:20]:
        print("  only at", "leave  " if row in leave else "reentry", row)
    for line in base.read(REVIEW / "run" / f"log-{name}.txt").splitlines():
        if line.startswith(("RT", "MDINSIDE", "MDSAVE", "MDCHECK", "MDREENTRY", "MDDONE", "MDFAIL")):
            print(" ", line[:200])
    for line in base.read(REVIEW / "run" / f"{name}-df.log").splitlines():
        if "resettest:" in line:
            print("  df", line[:240])


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        build()
    elif command == "assemble":
        assemble()
    elif command == "run":
        days = sys.argv[sys.argv.index("--days") + 1] if "--days" in sys.argv else "3"
        md.EXTRA_DF = ["-dfresettest", days]
        patch_route()
        md.run(sys.argv[2], False, "--drla" in sys.argv)
        sig(sys.argv[2])
    elif command == "sig":
        sig(sys.argv[2])
    else:
        sys.exit(__doc__)
