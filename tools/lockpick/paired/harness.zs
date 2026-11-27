version "4.14"

// Test only: locked dungeon doors with both real games (tools/lockpick/paired/run_paired.py). Enters Privateer's Hold
// by the town door, waits for Daggerfall's door facts to arm the locks, walks to the locked door @LOADID@, and presses
// the real Use on it:
//   no picks (Daggerfall's -dflocktest held them back) -> refused; with picks: damage cancel, miss; action records
//   17, 16, 18, 20 through DFAction.Perform (Doom's own lock); then a hit opens it; autosave.
// The New Game run (@NEWGAME@ = 1) starts inside from the real New Game flow and uses the starting picks (no refusal case).
// The load run (@LOADRUN@ = 1) closes the door again after the load and checks it is still unlocked, then makes it
// magically held (Doom owns the lock) and checks Use starts nothing. DLTrip then leaves the dungeon, comes back, and
// checks that Daggerfall's location record keeps the picked door unlocked in the freshly built map.
// @ENDCASE@ picks how the take run leaves the door before the autosave (Privateer's Hold has one locked door, so the
// cases are separate runs): 0 picked open (the hit), 1 unlocked by action 17 instead of the hit, 2 picked and then
// relocked by action 20. Each run also locks a door that starts unlocked with action 16 (phase 11). The load run checks
// both after the load (Doom's snapshot) and after the trip (the rebuilt map, from Daggerfall's location record).
// Prints DLCASE lines and "DLDONE". Daggerfall's side (picks, messages) is checked from its log by the runner.

class DLPresser : Thinker
{
	int press;
	override void Tick() { if (press) { players[0].cmd.buttons |= press; press = 0; } }
}

class DLHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	const LOADID = @LOADID@;
	const LOADRUN = @LOADRUN@;
	const ENTRYRUN = @ENTRYRUN@; // loads the take run's dungeon-entry autosave and checks every lock came back at its starting lock
	int entryTimer;
	// Members, not consts: with these as constants, the constant-false "if (...) { ...; break; }" blocks inside
	// WorldTick's switch crashed UZDoom while loading scripts (C0000005, every time with the DRLA set).
	bool DEMO;    // the review demo: enter, stand at the door, then hand over to the player
	bool NEWGAME; // the real New Game flow: already inside, with the character's starting picks
	override void OnRegister() { DEMO = @DEMO@; NEWGAME = @NEWGAME@; ENDCASE = @ENDCASE@; }

	// The test door's lock as the take run left it.
	int EndLock() { return ENDCASE == 2 ? door.startingLock : 0; }
	const LIMIT = 35 * 25;

	int phase, timer, passed, failed;
	bool done, started;
	DFDoor door;
	DLPresser presser;
	DFDoorListener savedListener;
	DFAction doorRecord;
	int lockedId;	// the door that starts unlocked and is locked by action 16 (phase 11)
	int ENDCASE;
	vector3 spot, arrival;
	double face, arrivalAngle;

	void Finish()
	{
		Console.Printf("DLRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("DLDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		if (DEMO) return; // the demo shows the player nothing of the test
		Console.Printf("DLCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	DoomerfallPickGame Game()
	{
		let h = DoomerfallLockpick(EventHandler.Find("DoomerfallLockpick"));
		return h ? h.game : null;
	}

	DFDoor FindDoor()
	{
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while (d = DFDoor(it.Next())) if (d.loadId == LOADID) return d;
		return null;
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	// A free spot 40 units in front of the door's middle link, facing it, from which the view ray hits the door.
	bool PlaceAtDoor(PlayerPawn p)
	{
		int n = door.links.Size();
		if (n == 0) return false;
		vector2 mid = door.links[n / 2].pos.xy;
		vector2 dir = n > 1 ? (door.links[n - 1].pos.xy - door.links[0].pos.xy).Unit() : (cos(door.closedAngle), sin(door.closedAngle));
		vector2 perp = (-dir.y, dir.x);
		for (int s = 1; s >= -1; s -= 2)
		{
			vector2 at = mid + perp * s * 40;
			p.SetOrigin((at, door.bottom), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(mid.y - at.y, mid.x - at.x);
			p.pitch = 0;
			if (!p.TestMobjLocation()) continue;
			FLineTraceData t;
			p.LineTrace(p.angle, 64, 0, 0, p.player.viewheight, 0, 0, t);
			if (t.HitType == TRACE_HitActor && t.HitActor is "DFDoorBlocker")
			{
				spot = p.pos;
				face = p.angle;
				return true;
			}
		}
		return false;
	}

	void Back(PlayerPawn p)
	{
		p.SetOrigin(spot, false);
		p.vel = (0, 0, 0);
		p.angle = face;
		p.pitch = 0;
	}

	void PressUse(PlayerPawn p)
	{
		Back(p);
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	bool Shut() { return door.swung <= 0 && door.moving == 0; }

	// The entry run: the save was taken on arrival, before any pick, so every lockable door must be at its starting
	// lock. A load restores Doom's snapshot, so this is what the save holds.
	void EntryCheck()
	{
		if (++entryTimer != 70) return;
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		int lockable, kept;
		while (d = DFDoor(it.Next()))
		{
			if (d.startingLock <= 0) continue;
			lockable++;
			if (d.lockValue == d.startingLock) kept++;
			if (d.loadId == LOADID) Report(d.lockValue == d.startingLock, String.Format("door %d is locked after the load (lock %d of %d)", LOADID, d.lockValue, d.startingLock));
		}
		Report(lockable > 0 && kept == lockable, String.Format("%d of %d lockable doors are at their starting lock", kept, lockable));
		Finish();
	}

	static DFDoor FindId(int id)
	{
		let it = ThinkerIterator.Create("DFDoor");
		DFDoor d;
		while (d = DFDoor(it.Next())) if (d.loadId == id && id != 0) return d;
		return null;
	}

	static void RunActionOn(DFDoor d, int type)
	{
		let a = DFAction(Actor.Spawn("DFAction", d.pos, NO_REPLACE));
		a.flag = type;
		a.door = d;
		a.Perform(players[0].mo);
		a.Destroy();
	}

	// The door locked by action 16 keeps lock 16.
	static bool LockedHolds(int lockedId, out String got)
	{
		DFDoor c = FindId(lockedId);
		got = String.Format("door %d lock %d", lockedId, c ? c.lockValue : -1);
		return c && c.startingLock == 0 && c.lockValue == 16;
	}

	// Runs a Daggerfall action record of this type on the door, through the converter's real DFAction.Perform.
	void RunAction(int type)
	{
		let a = DFAction(Actor.Spawn("DFAction", door.pos, NO_REPLACE));
		a.flag = type;
		a.door = door;
		a.Perform(players[0].mo);
		a.Destroy();
	}

	// One switch case: run the action at 1 s, check at 4 s, then go on to the next phase.
	void SwitchCase(int type, int next, String what)
	{
		Back(players[0].mo);
		if (timer == 35) RunAction(type);
		if (timer != 35 * 4) return;
		bool ok;
		if (type == 18) ok = door.swung > 0 && door.lockValue == 0;
		else if (type == 17) ok = Shut() && door.lockValue == 0;
		else if (type == 16) ok = Shut() && door.lockValue == 16;
		else ok = Shut() && door.lockValue == door.startingLock;
		Report(ok, what);
		phase = next;
		timer = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = !DEMO;
		if (!DEMO) p.bSOLID = false;	// the test player stands in the swing; a door waits for a body in its way (solid again in DLTrip)
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		if (ENTRYRUN) { if (inside) EntryCheck(); return; } // the run starts outside; the load test then loads the save
		if (!DEMO && inside && phase >= 2 && phase < 9) RemoveMonsters(); // the encounters can spawn after the door cases start (New Game)
		timer++;
		if (LOADRUN && phase == 9) { phase = 20; timer = 0; } // the load restored this handler from the take run's save
		if (LOADRUN && phase < 9) return;
		if (!presser) { presser = new("DLPresser"); presser.ChangeStatNum(Thinker.STAT_USER); }
		let g = Game();

		switch (phase)
		{
		case 0: // Enter the dungeon by the test door hook.
		{
			vector3 tdoor = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
			vector2 normal = (DOORDATA[3], DOORDATA[4]);
			if (inside) { phase = 1; timer = 0; break; }
			if (NEWGAME) break; // the New Game flow takes the player inside by itself
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((tdoor.xy + normal * 48, tdoor.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			phase = 1;
			timer = 0;
			break;
		}
		case 1: // Inside: the door is at its starting lock from the map itself.
			if (timer > LIMIT) { Report(false, "never got inside to the door"); Finish(); break; }
			if (!inside) break;
			if (arrival == (0, 0, 0)) { arrival = p.pos; arrivalAngle = p.angle; } // DLTrip leaves from here
			if (!door) door = FindDoor();
			if (!door) break;
			Report(door.lockValue == door.startingLock && door.startingLock > 0, String.Format("door %d found, locked at its starting lock %d", LOADID, door.lockValue));
			if (!DEMO) RemoveMonsters();
			if (!PlaceAtDoor(p)) { Report(false, "no spot in front of the door"); Finish(); break; }
			if (DEMO) { done = true; break; }
			phase = NEWGAME ? 3 : 2; // a New Game character holds its starting picks, so the refusal case is the take run's
			timer = NEWGAME ? 35 * 22 - 70 : 0; // the New Game run skips the take run's 22 s wait for picks
			break;
		case 2: // Look at it (label checked from the log), then Use without picks. The door carries a Door-triggered
		        // type 17 (unlock) record for this case, which a refused Use must not run (as DaggerfallActionDoor.Open).
			Back(p);
			if (timer == 30)
			{
				savedListener = door.listener;
				doorRecord = DFAction(Actor.Spawn("DFAction", door.pos, NO_REPLACE));
				doorRecord.flag = 30; // does nothing when run; only its activation count is checked
				doorRecord.trigger = 10; // TR_DOOR
				doorRecord.door = door;
				door.listener = doorRecord;
			}
			if (timer == 35) PressUse(p);
			if (timer == 140)
			{
				Report(Shut() && !g, "no picks: the door stays shut and no minigame starts");
				Report(door.lockValue > 0 && doorRecord.activationCount == 0, "a Door-triggered record does not run on the refused Use");
				phase = 3;
				timer = 0;
			}
			break;
		case 3: // Daggerfall's test gives 3 picks 20 s after entry. Then: damage cancel.
			Back(p);
			if (timer == 35 * 22) PressUse(p);
			if (timer > 35 * 22 && g && g.age == 8) p.DamageMobj(null, null, 1, 'None', DMG_NO_ARMOR);
			if (timer > 35 * 22 && g) started = true;
			if (timer == 35 * 22 + 105)
			{
				Report(started && !g && Shut(), "damage cancels the attempt and the door stays shut");
				phase = 4; timer = 0; started = false;
			}
			break;
		case 4: // A miss.
			Back(p);
			if (timer == 35) PressUse(p);
			if (g) { started = true; if (g.Off(g.pointer) >= 120) presser.press = BT_ATTACK; }
			if (timer == 35 * 5)
			{
				Report(started && !g && Shut(), "a miss leaves the door shut");
				phase = 6; timer = 0; started = false;
			}
			break;
		// The action records, then the hit last, so the autosave follows the hit directly.
		case 6: SwitchCase(17, 7, "action 17 unlocks it"); break;
		case 7: SwitchCase(16, 8, "action 16 locks it at 16"); break;
		case 8: SwitchCase(18, 10, "action 18 opens the door and clears the lock"); break;
		case 10: SwitchCase(20, NEWGAME ? 5 : 11, "action 20 closes the door and locks it again at its starting lock"); break;
		case 11: // A door that starts unlocked, locked by action 16 (see the top).
		{
			Back(p);
			if (timer < 35) break;
			let it = ThinkerIterator.Create("DFDoor");
			DFDoor d, locked;
			while (d = DFDoor(it.Next())) if (d.loadId != 0 && d.loadId != LOADID && d.startingLock == 0) { locked = d; break; }
			if (!locked) { Report(false, "a door that starts unlocked"); phase = 5; timer = 0; break; }
			lockedId = locked.loadId;
			RunActionOn(locked, 16);
			String got;
			Report(LockedHolds(lockedId, got), "action 16 locks a door that starts unlocked (" .. got .. ")");
			phase = 5; timer = 0;
			break;
		}
		case 5: // A hit (or, case lever, action 17), then the autosave.
			Back(p);
			if (timer == 35 && ENDCASE == 1) RunAction(17);
			if (timer == 35 * 2 && ENDCASE == 1)
			{
				Report(Shut() && door.lockValue == 0, "case lever: action 17 unlocks the shut door");
				if (doorRecord) { door.listener = savedListener; doorRecord.Destroy(); }
				Console.Printf("DLSAVE autosave");
				phase = 9; timer = 0;
				LevelLocals.MakeAutoSave();
				break;
			}
			if (ENDCASE == 1) break;
			if (timer == 35) PressUse(p);
			if (g) { started = true; if (g.Off(g.pointer) <= g.arc / 2 - 0.01) presser.press = BT_ATTACK; }
			if (timer == 35 * 6)
			{
				Report(started && !g && door.swung > 0 && door.lockValue == 0, "a hit unlocks and opens the door");
				if (doorRecord)
				{
					Report(doorRecord.activationCount == 1, String.Format("the Door-triggered record ran once, on the hit's open (count %d)", doorRecord.activationCount));
					door.listener = savedListener;
					doorRecord.Destroy();
				}
				timer = 0;
				if (NEWGAME) { Finish(); break; }
				if (ENDCASE == 2) { phase = 12; break; }
				Console.Printf("DLSAVE autosave");
				phase = 9;
				LevelLocals.MakeAutoSave();
			}
			break;
		case 12: // case relock: the picked door, once fully open, is closed and relocked by action 20.
			Back(p);
			if (timer == 35 * 2) RunAction(20);
			if (timer == 35 * 4)
			{
				Report(Shut() && door.lockValue == door.startingLock, "case relock: action 20 closes the picked door and relocks it at its starting lock");
				Console.Printf("DLSAVE autosave");
				phase = 9; timer = 0;
				LevelLocals.MakeAutoSave();
			}
			break;
		case 9:
			if (timer > 35 * 8) Finish();
			break;
		case 20: // After the load: close the door and Use it.
			if (!door) door = FindDoor();
			if (!door) { Report(false, "door missing after the load"); Finish(); break; }
			if (timer == 70) door.ActionSet(false);
			if (timer == 35 * 6 && EndLock() == 0) PressUse(p);
			if (timer == 35 * 9)
			{
				if (EndLock() == 0) Report(door.lockValue == 0 && door.swung > 0 && !g, "after the load the door is still unlocked and opens on Use");
				else Report(door.lockValue == door.startingLock && Shut(), String.Format("after the load the relocked door is still locked at %d", door.lockValue));
				String got;
				Report(LockedHolds(lockedId, got), "after the load the door locked by action 16 is still locked (" .. got .. ")");
				phase = 21; timer = 0;
			}
			break;
		case 21: // Doom owns the lock: make it magically held (as a Lock spell would, later). Use must start nothing.
			Back(p);
			if (timer == 35) door.ActionSet(false);
			if (timer < 35 * 3) break;
			door.lockValue = 25;
			phase = 22; timer = 0; started = false;
			break;
		case 22:
			Back(p);
			if (timer == 35) PressUse(p);
			if (g) started = true;
			if (timer == 35 * 4)
			{
				Report(!started && Shut() && door.lockValue == 25, "a magically held door stays shut and Use starts no minigame");
				door.lockValue = EndLock(); // the door as the save holds it, for the trip
				let trip = DLTrip(StaticEventHandler.Find("DLTrip"));
				if (trip) trip.Begin(arrival, arrivalAngle, passed, failed, lockedId, EndLock());
				done = true;
			}
			break;
		}
	}
}

// The load run's trip: out of the dungeon by the way the player came in, back in by the town door, and a check that the
// freshly built map got the location record's locks (the picked door unlocked, other doors at their starting lock).
// Static, so it lives across maps.
class DLTrip : StaticEventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	int phase, timer, passed, failed, lockedId, endLock, insideFor;
	vector3 arrival;
	double arrivalAngle;

	void Begin(vector3 at, double angle, int p, int f, int locked, int end)
	{
		arrival = at; arrivalAngle = angle; passed = p; failed = f; phase = 1; timer = 0;
		if (players[0].mo) players[0].mo.bSOLID = true;
		lockedId = locked; endLock = end;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("DLCASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void Finish()
	{
		Console.Printf("DLRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("DLDONE %s", failed == 0 ? "passed" : "failed");
		phase = 9;
	}

	override void WorldTick()
	{
		if (phase == 0 || phase == 9 || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		timer++;
		if (timer > 35 * 40) { Report(false, String.Format("the trip got stuck in step %d", phase)); Finish(); return; }
		switch (phase)
		{
		case 1: // Inside: back to where the player came in, facing out, and use the way out.
			if (!inside) { phase = 2; timer = 0; break; }
			if (timer == 10) { p.SetOrigin(arrival, false); p.vel = (0, 0, 0); p.angle = arrivalAngle + 180; }
			if (timer == 14) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		case 2: // Outside: the town door again.
		{
			if (inside) { phase = 3; timer = 0; break; }
			vector3 tdoor = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
			vector2 normal = (DOORDATA[3], DOORDATA[4]);
			if (timer < 70) break;
			p.SetOrigin((tdoor.xy + normal * 48, tdoor.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer == 82) CVar.FindCVar("dd_tm_use").SetInt(1);
			break;
		}
		case 3: // Inside again: the record applies during the arrival wait, before any tic of play.
		{
			DFDoor door, locked;
			let it = ThinkerIterator.Create("DFDoor");
			DFDoor d;
			while (d = DFDoor(it.Next())) { if (d.loadId == @LOADID@) door = d; else if (d.startingLock > 0 && !locked) locked = d; }
			if (!door || ++insideFor < 35) break;
			Report(true, "back inside the rebuilt map");
			Report(door.lockValue == endLock, String.Format("the test door keeps its lock after leaving and coming back (lock %d, want %d)", door.lockValue, endLock));
			Report(!locked || locked.lockValue == locked.startingLock, "another door keeps its starting lock");
			String got;
			Report(DLHarness.LockedHolds(lockedId, got), "after leaving and coming back the door locked by action 16 is still locked (" .. got .. ")");
			Finish();
			break;
		}
		}
	}
}
