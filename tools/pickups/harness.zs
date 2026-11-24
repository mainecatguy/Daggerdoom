version "4.14"

// Pickups in Privateer's Hold with DRLA and both real games. Enters by the test door hook, counts the converter's
// pickups, takes the nearest by touch, leaves, comes back, checks it stayed taken, and autosaves. A load run loads
// that autosave and checks again. The handler is saved with the game, so the load run still knows the taken spot.
class PKHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const double EXITSPOT[] = { @EXIT@ };
	const LIMIT = 35 * 25;
	const LOADRUN = @LOADRUN@;
	const SAVED = 7;

	int phase, timer, passed, failed, firstCount, afterTake, healthBefore, ammoBefore;
	bool done;
	vector3 takenSpot, start;
	String takenClass;
	Actor target;

	static bool IsPickup(Actor mo)
	{
		let inv = Inventory(mo);
		if (!inv || inv.Owner) return false;
		Name n = mo.GetClassName();
		return n == 'RLStimpack' || n == 'RLClip' || n == 'RLShell' || n == 'Stimpack' || n == 'Clip' || n == 'Shell';
	}

	int Count(bool print)
	{
		int n = 0, stim = 0, clip = 0, shell = 0, other = 0;
		Actor mo;
		let it = ThinkerIterator.Create("Inventory");
		while (mo = Actor(it.Next()))
		{
			if (Inventory(mo).Owner) continue;
			if (!IsPickup(mo)) { if (mo is "RLPistolPickup" || mo.GetClassName() == 'RLClipSpawner') other++; continue; }
			n++;
			String c = mo.GetClassName();
			if (c.IndexOf("Stimpack") >= 0) stim++; else if (c.IndexOf("Clip") >= 0) clip++; else shell++;
		}
		if (print) Console.Printf("PKCOUNT map=%s pickups=%d stimpacks=%d clips=%d shells=%d markers=%d pistols-or-spawners=%d", level.MapName, n, stim, clip, shell, Markers(), other);
		return n;
	}

	int Markers()
	{
		int n = 0;
		let it = ThinkerIterator.Create("DoomerfallPickupMarker");
		while (it.Next()) n++;
		return n;
	}

	bool AtTakenSpot()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Inventory");
		while (mo = Actor(it.Next()))
			if (IsPickup(mo) && (mo.pos.xy - takenSpot.xy).Length() < 16 && abs(mo.pos.z - takenSpot.z) < 32) return true;
		return false;
	}

	void Finish()
	{
		Console.Printf("PKRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("PKDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("PKCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void Next() { phase++; timer = 0; }

	bool AnyPile() { let it = ThinkerIterator.Create("DoomerfallWorldItem"); return it.Next() != null; }

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	int Ammo(PlayerPawn p) { return p.CountInv("Clip") + p.CountInv("Shell"); }

	bool EnterByDoor(PlayerPawn p, bool inside)
	{
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		if (inside) return true;
		if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) return false;
		p.SetOrigin((door.xy + normal * 48, door.z), false);
		p.vel = (0, 0, 0);
		p.angle = atan2(-normal.y, -normal.x);
		if (timer == 12 || timer % 140 == 139) CVar.FindCVar("dd_tm_use").SetInt(1);
		return false;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName ~== "MAP01" || level.MapName.Left(3) ~== "DDS";
		timer++;
		if (LOADRUN && phase == SAVED) { phase = 10; timer = 0; passed = failed = 0; }
		if (LOADRUN && phase < SAVED) return;
		if (timer > LIMIT && phase != SAVED) { Report(false, String.Format("phase %d timed out", phase)); Finish(); return; }

		switch (phase)
		{
		case 0: if (EnterByDoor(p, inside)) Next(); break;
		case 1: // Inside, once Daggerfall's piles show the space is ready.
			if (!inside || !AnyPile() || timer < 35) break;
			RemoveMonsters();
			start = p.pos;
			firstCount = Count(true);
			Report(firstCount > 0, "the dungeon has pickups");
			Report(Markers() == 0, "every marker removed itself");
			{
				double best = 1e9;
				Actor mo;
				let it = ThinkerIterator.Create("Inventory");
				while (mo = Actor(it.Next()))
					if (IsPickup(mo) && p.Distance3D(mo) < best) { best = p.Distance3D(mo); target = mo; }
			}
			if (!target) { Finish(); break; }
			takenSpot = target.pos;
			takenClass = target.GetClassName();
			p.A_SetHealth(50);
			healthBefore = p.health;
			ammoBefore = Ammo(p);
			Console.Printf("PKTARGET %s at %.1f,%.1f,%.1f, %.0f units from the entrance", takenClass, takenSpot.x, takenSpot.y, takenSpot.z, p.Distance3D(target));
			Next();
			break;
		case 2: // Touch it.
			if (timer == 1) { p.SetOrigin(takenSpot + (2, 0, 0), false); p.vel = (0, 0, 0); p.TryMove(takenSpot.xy, 0); }
			if (timer < 10) break;
			Console.Printf("PKTOOK %s: item %s, health %d -> %d, Clip+Shell %d -> %d", takenClass, target ? "still there" : "gone", healthBefore, p.health, ammoBefore, Ammo(p));
			Report(!target || Inventory(target).Owner, "touch took the pickup");
			Report(p.health > healthBefore || Ammo(p) > ammoBefore, "the player got its health or ammo");
			afterTake = Count(true);
			Next();
			break;
		case 3: // Leave by the exit.
			if (timer == 2)
			{
				p.vel = (0, 0, 0);
				if (EXITSPOT[3] != 0 || EXITSPOT[4] != 0)
				{
					p.SetOrigin((EXITSPOT[0] + EXITSPOT[3] * 40, EXITSPOT[1] + EXITSPOT[4] * 40, EXITSPOT[2]), false);
					p.angle = atan2(-EXITSPOT[4], -EXITSPOT[3]);
				}
				else { p.SetOrigin(start, false); p.angle += 180; }
			}
			if (timer == 6 || timer % 140 == 139) CVar.FindCVar("dd_tm_use").SetInt(1);
			if (!inside) Next();
			break;
		case 4: // Outside: go back in.
			if (timer < 35) break;
			if (EnterByDoor(p, inside)) Next();
			break;
		case 5: // Back inside: the taken pickup stays taken, the rest are back.
			if (!inside || timer < 70) break;
			RemoveMonsters();
			{
				int again = Count(true);
				Report(again == afterTake, String.Format("after re-entry %d pickups, as after the take (%d)", again, afterTake));
				Report(!AtTakenSpot(), "nothing is at the taken spot after re-entry");
				Report(Markers() == 0, "no marker came back on re-entry");
			}
			Console.Printf("PKSAVE autosave");
			LevelLocals.MakeAutoSave();
			Next();
			Next(); // SAVED
			break;
		case SAVED:
			if (timer > 35 * 8) Finish();
			break;
		case 10: // After the load.
			if (timer < 105) break;
			{
				int loaded = Count(true);
				Report(inside, "the load put the player in the dungeon");
				Report(loaded == afterTake, String.Format("after the load %d pickups, as saved (%d)", loaded, afterTake));
				Report(!AtTakenSpot(), "nothing is at the taken spot after the load");
			}
			Finish();
			break;
		}
	}
}
