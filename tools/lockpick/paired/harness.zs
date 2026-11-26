version "4.14"

// Test only: locked dungeon doors with both real games (tools/lockpick/paired/run_paired.py). Enters Privateer's Hold
// by the town door, walks to the locked door @LOADID@, and presses the real Use on it:
//   no picks (Daggerfall's -dflocktest held them back) -> refused; with picks: damage cancel, miss, hit -> opens;
//   action records 20 (relock), 17, 16, 18 (open and unlock) through DFAction.Perform; autosave.
// The New Game run (@NEWGAME@ = 1) starts inside from the real New Game flow and uses the starting picks (no refusal case).
// The load run (@LOADRUN@ = 1) closes the door again after the load and checks that Daggerfall's list keeps it unlocked.
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
	// Members, not consts: with these as constants, the constant-false "if (...) { ...; break; }" blocks inside
	// WorldTick's switch crashed UZDoom while loading scripts (C0000005, every time with the DRLA set).
	bool DEMO;    // the review demo: enter, stand at the door, then hand over to the player
	bool NEWGAME; // the real New Game flow: already inside, with the character's starting picks
	override void OnRegister() { DEMO = @DEMO@; NEWGAME = @NEWGAME@; }
	const LIMIT = 35 * 25;

	int phase, timer, passed, failed;
	bool done, started;
	DFDoor door;
	DLPresser presser;
	vector3 spot;
	double face;

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
		if (type == 18) ok = door.swung > 0 && door.lockState == 0;
		else if (type == 17) ok = Shut() && door.lockState == 0;
		else ok = Shut() && door.lockState == 1;
		Report(ok, what);
		phase = next;
		timer = 0;
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = !DEMO;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
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
		case 1: // Daggerfall's locked list marks the door.
			if (timer > LIMIT) { Report(false, "Daggerfall never listed the door as locked"); Finish(); break; }
			if (!inside) break;
			if (!door) door = FindDoor();
			if (!door || door.lockState != 1) break;
			Report(true, String.Format("door %d found, starting lock %d, Daggerfall lists it locked", LOADID, door.startingLock));
			if (!DEMO) RemoveMonsters();
			if (!PlaceAtDoor(p)) { Report(false, "no spot in front of the door"); Finish(); break; }
			if (DEMO) { done = true; break; }
			phase = NEWGAME ? 3 : 2; // a New Game character holds its starting picks, so the refusal case is the take run's
			timer = NEWGAME ? 35 * 22 - 70 : 0; // the New Game run skips the take run's 22 s wait for picks
			break;
		case 2: // Look at it (label checked from the log), then Use without picks.
			Back(p);
			if (timer == 35) PressUse(p);
			if (timer == 140)
			{
				Report(Shut() && !g, "no picks: the door stays shut and no minigame starts");
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
				phase = 5; timer = 0; started = false;
			}
			break;
		case 5: // A hit.
			Back(p);
			if (timer == 35) PressUse(p);
			if (g) { started = true; if (g.Off(g.pointer) <= g.arc / 2 - 0.01) presser.press = BT_ATTACK; }
			if (timer == 35 * 6)
			{
				Report(started && !g && door.swung > 0 && door.lockState == 0, "a hit unlocks and opens the door");
				phase = 6; timer = 0;
			}
			break;
		case 6: SwitchCase(20, 7, "action 20 closes the door and Daggerfall locks it again (its starting lock)"); break;
		case 7: SwitchCase(17, 8, "action 17 unlocks it in Daggerfall"); break;
		case 8: SwitchCase(16, 10, "action 16 locks it in Daggerfall"); break;
		case 10:
			SwitchCase(18, 10, "action 18 opens the door and Daggerfall clears the lock");
			if (timer != 0) break;
			if (NEWGAME) { Finish(); break; }
			Console.Printf("DLSAVE autosave");
			phase = 9;
			LevelLocals.MakeAutoSave();
			break;
		case 9:
			if (timer > 35 * 8) Finish();
			break;
		case 20: // After the load: close the door, wait for Daggerfall's list, and Use it.
			if (!door) door = FindDoor();
			if (!door) { Report(false, "door missing after the load"); Finish(); break; }
			if (timer == 70) door.ActionSet(false);
			if (timer == 35 * 6) PressUse(p);
			if (timer == 35 * 9)
			{
				Report(door.lockState == 0 && door.swung > 0 && !g, "after the load the door is still unlocked and opens on Use");
				Finish();
			}
			break;
		}
	}
}
