version "4.10"

// Test only: the Doom-side lock gate on converted dungeon doors (door_objects.zs DFDoor.lockState). Load after a
// converted dungeon's _doors.pk3 and run with +dd_lockdoor <LoadID of a door>. Prints DGTEST lines and "DGTEST done p/t".
class DGTest : EventHandler
{
	int step, passed, total, uses;
	DFDoor door, other;

	void Check(bool ok, String what) { total++; if (ok) passed++; Console.Printf("DGTEST %s %s", what, ok ? "PASS" : "FAIL"); }

	override void NetworkProcess(ConsoleEvent e) { if (e.Name.Left(11) == "dfdoor_use:") { uses++; Console.Printf("DGTEST event %s", e.Name); } }

	override void WorldTick()
	{
		let pmo = players[0].mo;
		int t = level.maptime;
		if (t == 10)
		{
			int want = CVar.FindCVar("dd_lockdoor").GetInt();
			let it = ThinkerIterator.Create("DFDoor");
			DFDoor d;
			while (d = DFDoor(it.Next())) { if (d.loadId == want) door = d; else if (!other && d.loadId != 0) other = d; }
			Check(door != null && other != null, String.Format("found doors (lock %d)", door ? door.startingLock : -1));
			if (!door || !other) { step = 99; return; }
			EventHandler.SendNetworkEvent(String.Format("dfdoor_lock:%d:1", want));
		}
		else if (t == 14 && step == 0)
		{
			pmo.SetOrigin((door.pivotX, door.pivotY, door.pivotZ + 1), false);
			Check(door.TryUse(pmo), "Use reaches the locked door");
		}
		else if (t == 20 && step == 0)
		{
			Check(door.moving == 0 && door.swung <= 0, "locked door stays shut");
			Check(uses == 1, "locked door reported its use");
			EventHandler.SendNetworkEvent(String.Format("dfdoor_lock:%d:0:open", door.loadId));
		}
		else if (t == 40 && step == 0)
		{
			Check(door.swung > 0, "unlocked door opens on Daggerfall's word");
			Console.Printf("DGTEST done %d/%d", passed, total);
			step = 1;
		}
	}
}
