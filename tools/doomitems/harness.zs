version "4.14"

// Doom items held by Daggerfall, on the real dungeon. Takes real DRLA items with the real Use check, lets
// Daggerfall's test mode use the blur sphere from its inventory, then makes a synchronized autosave. After the
// save is loaded, it checks that Doom still holds the gun.
class DIHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const String USE[] = { @USE@ };
	const LIMIT = 35 * 20;

	int phase, timer, index, step, passed, failed;
	bool done;
	Actor item;
	vector3 home;
	vector2 ahead;

	override void WorldLoaded(WorldEvent e)
	{
		if (!e.IsSaveGame) return;
		phase = 10;
		timer = 0;
		done = false;
		passed = failed = 0;
	}

	void Finish()
	{
		Console.Printf("DIRESULT passed=%d failed=%d", passed, failed);
		Console.Printf("DIDONE %s", failed == 0 ? "passed" : "failed");
		done = true;
	}

	void Report(bool ok, String what)
	{
		if (ok) passed++; else failed++;
		Console.Printf("DICASE %s %s", ok ? "pass" : "FAIL", what);
	}

	void PressUse(PlayerPawn p)
	{
		uint saved = players[0].cmd.buttons;
		players[0].cmd.buttons |= BT_USE;
		players[0].usedown = false;
		p.CheckUse();
		players[0].cmd.buttons = saved;
	}

	void FindClearSpot(PlayerPawn p)
	{
		home = p.pos;
		for (int a = 0; a < 360; a += 45)
		{
			FLineTraceData t;
			if (!p.LineTrace(a, 96, 0, TRF_THRUACTORS, 16, 0, 0, t) || t.HitType == TRACE_HitNone)
			{
				p.angle = a;
				break;
			}
		}
		ahead = (cos(p.angle), sin(p.angle));
		p.pitch = 0;
	}

	void GoHome(PlayerPawn p)
	{
		p.SetOrigin(home, false);
		p.vel = (0, 0, 0);
		p.angle = atan2(ahead.y, ahead.x);
		p.pitch = 0;
	}

	bool AnyPile()
	{
		let it = ThinkerIterator.Create("DoomerfallWorldItem");
		return it.Next() != null;
	}

	void RemoveMonsters()
	{
		Actor mo;
		let it = ThinkerIterator.Create("Actor");
		while (mo = Actor(it.Next()))
			if (mo.bISMONSTER && !mo.player) mo.Destroy();
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		bool inside = level.MapName.Left(3) ~== "DDS" || level.MapName ~== "MAP01";
		vector3 door = (DOORDATA[0], DOORDATA[1], DOORDATA[2]);
		vector2 normal = (DOORDATA[3], DOORDATA[4]);
		timer++;

		switch (phase)
		{
		case 0: // Enter the dungeon by the test door hook.
			if (inside) { phase = 1; timer = 0; break; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			phase = 1;
			timer = 0;
			break;
		case 1: // Daggerfall's pile list shows it is ready in this space.
			if (timer > LIMIT) { Report(false, "Daggerfall never listed this space"); Finish(); break; }
			if (!inside || !AnyPile() || timer < 35) break;
			RemoveMonsters();
			FindClearSpot(p);
			phase = 2;
			timer = 0;
			break;
		case 2: TakeCase(p); break;
		case 3: // Daggerfall's test mode uses the blur sphere from its inventory. Then save.
			if (timer == 105)
			{
				Report(p.FindInventory("RLPistol") != null, "Doom holds the RLPistol it took");
				Console.Printf("DISAVE autosave");
				LevelLocals.MakeAutoSave();
			}
			if (timer > 105 + 35 * 8) Finish();
			break;
		case 10: // After the load.
			if (timer < 70) break;
			Report(p.FindInventory("RLPistol") != null, "Doom holds the RLPistol after the load");
			Finish();
			break;
		}
	}

	void TakeCase(PlayerPawn p)
	{
		if (index >= USE.Size()) { phase = 3; timer = 0; return; }
		switch (step)
		{
		case 0:
		{
			class<Actor> cls = USE[index];
			if (!cls) { Report(false, "missing class " .. USE[index]); index++; return; }
			GoHome(p);
			item = Actor.Spawn(cls, (home.xy + ahead * 48, home.z), NO_REPLACE);
			timer = 0;
			step = 1;
			break;
		}
		case 1: // DRLA weapons only become pickups after landing.
			if (!item) { Report(false, USE[index] .. " vanished at spawn"); index++; step = 0; break; }
			if (item.bSPECIAL && timer > 8) { GoHome(p); timer = 0; step = 2; break; }
			if (timer > 70) { Report(false, USE[index] .. " never became a pickup"); item.Destroy(); index++; step = 0; }
			break;
		case 2: // One real Use press. Daggerfall answers, and only then does the item leave the floor.
			if (timer == 3) PressUse(p);
			if (timer < 4) break;
			if (!item || !item.bSPECIAL)
			{
				Report(true, String.Format("%s left the floor after Daggerfall answered (%d tics)", USE[index], timer - 3));
				index++;
				step = 0;
			}
			else if (timer > 105)
			{
				Report(false, USE[index] .. " still on the floor");
				item.Destroy();
				index++;
				step = 0;
			}
			break;
		}
	}
}
