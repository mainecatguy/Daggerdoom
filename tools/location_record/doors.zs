version "4.14"

// Location record card 5 route (tools/location_record/doors.py): hinged doors keep their position. Route "first": enter
// Privateer's Hold, open every third door, open a lever-driven door through its action (flag 18), start one more door
// opening just before leaving (caught moving), leave, come back, pull the lever again, leave and save outside. Routes
// "load" and "stamp": load that save in a new launch, enter, and print the doors. Every check prints DRSIG: the doors'
// bits (a moving door counted at the end it is heading to) and any door whose sight blocker or collision disagrees.
class MDState : Inventory
{
	Default { Inventory.MaxAmount 1; +INVENTORY.UNDROPPABLE +INVENTORY.UNTOSSABLE }
	int phase, timer;
}

class MDHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITDATA[] = { @EXIT@ };
	const LIMIT = 35 * 20;
	const CAUGHT = 1;	// the door started just before leaving
	bool done, loadRoute;
	int kPhase, kTimer, leverDoor;

	override void OnRegister() { loadRoute = !("@ROUTE@" ~== "first"); leverDoor = -1; }

	void Finish(String why) { Console.Printf("MDDONE %s", why); done = true; }

	static int DoorCount()
	{
		int n = 0;
		let it = ThinkerIterator.Create("DFDoor");
		while (it.Next()) n++;
		return n;
	}

	static DFDoor DoorAt(int index)
	{
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		for (int n = 0; (d = DFDoor(it.Next())); n++) if (n == index) return d;
		return null;
	}

	// The lever-driven door: an action that opens a door (flag 18), as the end of a lever's chain does.
	static DFAction LeverAction()
	{
		let it = ThinkerIterator.Create("DFAction");
		DFAction a;
		while (a = DFAction(it.Next())) if (a.flag == 18 && a.door) return a;
		return null;
	}

	static int IndexOf(DFDoor door)
	{
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		for (int n = 0; (d = DFDoor(it.Next())); n++) if (d == door) return n;
		return -1;
	}

	static void Signature(String when)
	{
		String bits = "", bad = "";
		int n = 0, open = 0, moving = 0;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while (d = DFDoor(it.Next()))
		{
			bool heading = d.moving != 0 ? d.moving > 0 : d.swung > 0;
			bits = bits .. (heading ? "1" : "0");
			if (heading) open++;
			if (d.moving != 0) moving++;
			else
			{
				// At rest: sight open exactly when swung, the sight blockers at their end, the links solid when closed.
				bool sightOk = d.sightOpen == (d.swung > 0);
				for (int i = 0; i < d.sightSectors.Size(); i++)
				{
					Sector s = level.Sectors[d.sightSectors[i]];
					double want = d.swung > 0 ? s.CenterFloor() : d.sightTops[i];
					if (abs(s.CenterCeiling() - want) > 0.5) sightOk = false;
				}
				bool solid = d.links.Size() > 0 && d.links[0].bSOLID;
				bool solidOk = d.solidWhenOpen || solid == (d.swung <= 0) || (d.swung <= 0 && !d.Clear(0, true));
				if (!sightOk || !solidOk) bad.AppendFormat(" %d(swung %d sight %d solid %d)", n, int(d.swung), d.sightOpen, solid);
			}
			n++;
		}
		Console.Printf("DRSIG %s doors %d open %d moving %d bits %s bad%s", when, n, open, moving, bits, bad == "" ? " none" : bad);
	}

	void GoToExit(PlayerPawn p)
	{
		p.SetOrigin((EXITDATA[0] + EXITDATA[3] * 40, EXITDATA[1] + EXITDATA[4] * 40, EXITDATA[2]), false);
		p.angle = atan2(-EXITDATA[4], -EXITDATA[3]);
		p.pitch = 0;
		p.vel = (0, 0, 0);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		let st = MDState(p.FindInventory("MDState"));
		if (!st) st = MDState(p.GiveInventoryType("MDState"));
		if (!st) return;
		if (kPhase > 0 && st.phase == 0 && kPhase != 9) { st.phase = kPhase; st.timer = kTimer; }	// DRLA may swap the player class
		if (loadRoute && st.phase == 9) { st.phase = 0; st.timer = 0; }	// the save carries the first route's state
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName ~== "MAP01";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		st.timer++;
		if (level.maptime % 350 == 1) Console.Printf("MDSTATUS step %d, timer %d, map %s, doors %d", st.phase, st.timer, level.MapName, DoorCount());
		switch (st.phase)
		{
		case 0: // Outside: use the dungeon's door once Daggerfall is in play.
		case 5:
			if (inside || level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			if (CVar.FindCVar("dd_ui_test_hold").GetInt() != 0) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (st.timer < 50) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			st.phase = st.phase == 0 && !loadRoute ? 1 : 6;
			st.timer = 0;
			break;
		case 1: // Inside: set the doors.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("MDFAIL no entry"); Finish("failed"); } break; }
			if (st.timer < 35 * 6 || DoorCount() == 0) break;
			Signature("entry");
			{
				let lever = LeverAction();
				leverDoor = lever ? IndexOf(lever.door) : -1;
				for (int i = 0; i < DoorCount(); i++)
					if (i % 3 == 0 && i != leverDoor) DoorAt(i).ActionSet(true);
				if (lever) { lever.Perform(p); Console.Printf("DRLEVER pulled: action %d opens door %d (moving %d)", lever.id, leverDoor, lever.door.moving); }
				else Console.Printf("DRLEVER no lever-driven door (action flag 18 with a door) in this dungeon");
			}
			st.phase = 2;
			st.timer = 0;
			break;
		case 2: // Let them finish swinging, then catch one door moving and leave.
			if (st.timer < 35 * 3) break;
			{
				let d = DoorAt(CAUGHT);
				if (d && CAUGHT != leverDoor) d.ActionSet(true);
			}
			if (st.timer < 35 * 3 + 5) break;
			Signature("leave");
			GoToExit(p);
			st.phase = 4;
			st.timer = 0;
			break;
		case 4: // Leave.
		case 8:
			p.vel = (0, 0, 0);
			if (st.timer == 5) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) { st.phase = st.phase == 4 ? 5 : 9; st.timer = 0; }
			else if (st.timer > LIMIT) { Console.Printf("MDFAIL exit did not work"); Finish("failed"); }
			break;
		case 6: // Back inside (or loaded and entered): print the doors.
			if (!inside) { if (st.timer > LIMIT) { Console.Printf("MDFAIL no re-entry"); Finish("failed"); } break; }
			if (st.timer < 35 * 6 || DoorCount() == 0) break;
			Signature(loadRoute ? "@ROUTE@" : "reentry");
			if (loadRoute) { Finish("passed"); break; }
			{
				// Pull the reset lever again on its door, already open: nothing may change.
				let lever = LeverAction();
				if (lever)
				{
					int before = lever.door.moving;
					lever.Perform(p);
					Console.Printf("DRLEVER pulled again: door %d swung %d, moving %d before and %d after", IndexOf(lever.door), int(lever.door.swung), before, lever.door.moving);
				}
			}
			st.phase = 7;
			st.timer = 0;
			break;
		case 7:
			if (st.timer < 35 * 2) break;
			Signature("again");
			GoToExit(p);
			st.phase = 8;
			st.timer = 0;
			break;
		case 9: // Outside: save, so the doors live only in Daggerfall's record.
			if (st.timer == 35) { Console.Printf("MDSAVE outside"); level.MakeAutoSave(); }
			if (st.timer > 35 * 2) Finish("passed");
			break;
		}
		kPhase = st.phase; kTimer = st.timer;
	}
}
