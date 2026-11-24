version "4.14"

// Gun pictures in Daggerfall's inventory. The take run picks up DRLA guns with Use (Doom sees each one on the floor)
// and autosaves. The load run loads that save in fresh copies of both games, so Doom has seen none of the guns and
// must find each picture from the class alone. Daggerfall's -dfdoomitemstest writes every picture it gets.
class GIHarness : EventHandler
{
	static const double DOORDATA[] = { @DOOR@ };
	static const String GUNS[] = { "RLChaingunPickup", "RLCombatShotgunPickup", "RLShotgunPickup", "RLPlasmaRiflePickup", "RLRocketLauncherPickup", "RLPistolPickupModded" };
	const LIMIT = 35 * 20;
	const LOADRUN = @LOADRUN@;
	const SAVED = 10; // The phase the autosave is made in. A load run that reaches it has loaded.

	int phase, timer, step, gun;
	bool done;
	Actor item;
	vector3 home;
	vector2 ahead;

	void Finish(String why)
	{
		Console.Printf("GIDONE %s", why);
		done = true;
	}

	void Next() { phase++; timer = 0; step = 0; }

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
		if (LOADRUN && phase == SAVED) { phase = 20; timer = 0; }
		if (LOADRUN && phase < SAVED) return;

		switch (phase)
		{
		case 0: // Enter the dungeon by the test door hook.
			if (inside) { Next(); break; }
			if (level.maptime < 8 || CVar.FindCVar("dd_sync_df_phase").GetInt() != 3) break;
			p.SetOrigin((door.xy + normal * 48, door.z), false);
			p.vel = (0, 0, 0);
			p.angle = atan2(-normal.y, -normal.x);
			if (timer < 12) break;
			CVar.FindCVar("dd_tm_use").SetInt(1);
			Next();
			break;
		case 1: // Daggerfall's pile list shows it is ready in this space.
			if (timer > LIMIT) { Finish("Daggerfall never listed this space"); break; }
			if (!inside || !AnyPile() || timer < 35) break;
			RemoveMonsters();
			FindClearSpot(p);
			Next();
			break;
		case 2: // Take each gun with Use.
			if (gun >= GUNS.Size()) { Next(); break; }
			if (!Take(p, GUNS[gun])) break;
			gun++;
			step = 0;
			timer = 0;
			break;
		case 3:
			if (timer < 70) break;
			Console.Printf("GISAVE autosave");
			LevelLocals.MakeAutoSave();
			Next();
			phase = SAVED;
			break;
		case SAVED:
			if (timer > 35 * 8) Finish("saved");
			break;
		case 20: // Loaded: Daggerfall asks Doom for each picture after the load. Give it time.
			if (timer == 35 * 8) Finish("loaded");
			break;
		}
	}

	// Spawns a pickup ahead, waits for it to land, presses Use, and returns true 70 tics later.
	bool Take(PlayerPawn p, String cls)
	{
		switch (step)
		{
		case 0:
			GoHome(p);
			item = Actor.Spawn(cls, (home.xy + ahead * 48, home.z), NO_REPLACE);
			Console.Printf("GISPAWN %s", cls);
			timer = 0;
			step = 1;
			break;
		case 1: // DRLA items only become pickups after landing.
			if (!item) { Console.Printf("GIFAIL %s vanished at spawn", cls); return true; }
			if (item.bSPECIAL && timer > 8) { GoHome(p); timer = 0; step = 2; }
			else if (timer > 70) { Console.Printf("GIFAIL %s never became a pickup", cls); return true; }
			break;
		case 2:
			if (timer == 3) PressUse(p);
			if (timer >= 70) return true;
			break;
		}
		return false;
	}
}
